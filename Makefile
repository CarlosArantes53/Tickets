# =============================================================================
# TechSupport Manager - Makefile
# =============================================================================

.PHONY: help install install-dev test test-cov lint format clean

# Variáveis
PYTHON = python3
PIP = pip3
PYTEST = pytest
SRC_DIR = src
TEST_DIR = tests

# Cores para output
GREEN = \033[0;32m
NC = \033[0m # No Color

help: ## Mostra esta mensagem de ajuda
	@echo "Comandos disponíveis:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'

# =============================================================================
# Instalação
# =============================================================================

install: ## Instala dependências de produção
	$(PIP) install -r requirements.txt

install-dev: ## Instala dependências de desenvolvimento
	$(PIP) install -r requirements.txt
	$(PIP) install mypy black isort flake8

venv: ## Cria ambiente virtual
	$(PYTHON) -m venv venv
	@echo "Ative com: source venv/bin/activate"

# =============================================================================
# Testes
# =============================================================================

test: ## Executa testes
	$(PYTEST) $(TEST_DIR) -v

test-cov: ## Executa testes com cobertura
	$(PYTEST) $(TEST_DIR) -v --cov=$(SRC_DIR)/core --cov-report=term-missing --cov-report=html

test-fast: ## Executa testes rápidos (sem markers slow)
	$(PYTEST) $(TEST_DIR) -v -m "not slow"

# =============================================================================
# Qualidade de Código
# =============================================================================

lint: ## Verifica código com flake8
	flake8 $(SRC_DIR) $(TEST_DIR)

format: ## Formata código com black e isort
	isort $(SRC_DIR) $(TEST_DIR)
	black $(SRC_DIR) $(TEST_DIR)

format-check: ## Verifica formatação sem alterar
	isort --check-only $(SRC_DIR) $(TEST_DIR)
	black --check $(SRC_DIR) $(TEST_DIR)

typecheck: ## Verifica tipos com mypy
	mypy $(SRC_DIR)

# =============================================================================
# Limpeza
# =============================================================================

clean: ## Remove arquivos de cache e build
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf htmlcov/ 2>/dev/null || true
	rm -rf build/ dist/ 2>/dev/null || true
	@echo "Limpeza concluída!"

# =============================================================================
# Projeto
# =============================================================================

init: install ## Inicializa projeto (instala dependências)
	cp -n .env.example .env 2>/dev/null || true
	@echo "Projeto inicializado! Edite .env com suas configurações."

check: lint format-check typecheck test ## Executa todas as verificações

all: clean install-dev check ## Rebuild completo

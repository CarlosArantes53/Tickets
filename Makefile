# =============================================================================
# TechSupport Manager - Makefile
# =============================================================================

.PHONY: help install install-dev test test-cov lint format clean db-up db-down migrate shell

# Variáveis
PYTHON = python3
PIP = pip3
PYTEST = pytest
MANAGE = python manage.py
DOCKER_COMPOSE = docker-compose
SRC_DIR = src
TEST_DIR = tests

# Cores para output
GREEN = \033[0;32m
YELLOW = \033[1;33m
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
# Docker / Infraestrutura
# =============================================================================

db-up: ## Inicia PostgreSQL via Docker
	$(DOCKER_COMPOSE) up -d postgres
	@echo "$(GREEN)PostgreSQL iniciado em localhost:5432$(NC)"
	@echo "Aguardando banco estar pronto..."
	@sleep 3

db-down: ## Para PostgreSQL
	$(DOCKER_COMPOSE) down

db-logs: ## Exibe logs do PostgreSQL
	$(DOCKER_COMPOSE) logs -f postgres

infra-up: ## Inicia toda infraestrutura (postgres, redis, rabbitmq)
	$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)Infraestrutura iniciada!$(NC)"
	@echo "  PostgreSQL: localhost:5432"
	@echo "  Redis: localhost:6379"
	@echo "  RabbitMQ: localhost:5672 (UI: localhost:15672)"
	@echo "  Adminer: localhost:8080"

infra-down: ## Para toda infraestrutura
	$(DOCKER_COMPOSE) down

infra-clean: ## Para e remove volumes (CUIDADO: apaga dados!)
	$(DOCKER_COMPOSE) down -v
	@echo "$(YELLOW)Volumes removidos!$(NC)"

# =============================================================================
# Django
# =============================================================================

migrate: ## Executa migrations
	$(MANAGE) migrate

migrations: ## Cria novas migrations
	$(MANAGE) makemigrations

shell: ## Abre shell Django
	$(MANAGE) shell

createsuperuser: ## Cria superusuário
	$(MANAGE) createsuperuser

runserver: ## Inicia servidor de desenvolvimento
	$(MANAGE) runserver

collectstatic: ## Coleta arquivos estáticos
	$(MANAGE) collectstatic --noinput

# =============================================================================
# Testes
# =============================================================================

test: ## Executa testes
	$(PYTEST) $(TEST_DIR) -v

test-cov: ## Executa testes com cobertura
	$(PYTEST) $(TEST_DIR) -v --cov=$(SRC_DIR)/core --cov=$(SRC_DIR)/adapters --cov-report=term-missing --cov-report=html

test-fast: ## Executa testes rápidos (sem markers slow)
	$(PYTEST) $(TEST_DIR) -v -m "not slow"

test-integration: ## Executa testes de integração
	$(PYTEST) $(TEST_DIR)/adapters -v

test-core: ## Executa apenas testes do Core
	$(PYTEST) $(TEST_DIR)/core -v

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
# Setup Completo
# =============================================================================

init: install db-up migrate ## Setup completo: instala deps, inicia DB, roda migrations
	cp -n .env.example .env 2>/dev/null || true
	@echo "$(GREEN)=== Projeto inicializado! ===$(NC)"
	@echo ""
	@echo "Próximos passos:"
	@echo "  1. Edite .env com suas configurações"
	@echo "  2. make createsuperuser"
	@echo "  3. make runserver"
	@echo ""

check: lint format-check test ## Executa todas as verificações

all: clean install-dev db-up migrate check ## Rebuild completo

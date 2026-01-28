# =============================================================================
# TechSupport Manager - Makefile
# =============================================================================

.PHONY: help install test lint format migrate runserver \
        db-up db-down db-logs infra-up infra-down infra-logs \
        celery-worker celery-beat celery-flower full-up full-down

# -----------------------------------------------------------------------------
# Help
# -----------------------------------------------------------------------------
help:
	@echo "TechSupport Manager - Comandos Disponíveis"
	@echo ""
	@echo "Setup:"
	@echo "  make install       - Instala dependências"
	@echo "  make migrate       - Executa migrações"
	@echo "  make init          - Setup completo inicial"
	@echo ""
	@echo "Desenvolvimento:"
	@echo "  make runserver     - Inicia servidor Django"
	@echo "  make shell         - Django shell"
	@echo "  make createsuperuser - Cria superusuário"
	@echo ""
	@echo "Infraestrutura:"
	@echo "  make db-up         - Inicia PostgreSQL"
	@echo "  make db-down       - Para PostgreSQL"
	@echo "  make infra-up      - Inicia toda infraestrutura (postgres, redis, rabbitmq)"
	@echo "  make infra-down    - Para toda infraestrutura"
	@echo ""
	@echo "Celery:"
	@echo "  make celery-worker - Inicia Celery worker"
	@echo "  make celery-beat   - Inicia Celery beat (tarefas agendadas)"
	@echo "  make celery-flower - Inicia Flower (monitoramento)"
	@echo ""
	@echo "Docker Full Stack:"
	@echo "  make full-up       - Inicia aplicação completa via Docker"
	@echo "  make full-down     - Para aplicação completa"
	@echo ""
	@echo "Testes:"
	@echo "  make test          - Roda todos os testes"
	@echo "  make test-cov      - Testes com cobertura"
	@echo "  make test-core     - Apenas testes do core"
	@echo "  make test-integration - Testes de integração"
	@echo ""
	@echo "Qualidade:"
	@echo "  make lint          - Verifica código"
	@echo "  make format        - Formata código"

# -----------------------------------------------------------------------------
# Setup
# -----------------------------------------------------------------------------
install:
	pip install --break-system-packages -r requirements.txt

migrate:
	python manage.py migrate

migrations:
	python manage.py makemigrations

init: install db-up migrate
	@echo "Setup completo! Execute: make runserver"

# -----------------------------------------------------------------------------
# Desenvolvimento
# -----------------------------------------------------------------------------
runserver:
	python manage.py runserver

shell:
	python manage.py shell

createsuperuser:
	python manage.py createsuperuser

# -----------------------------------------------------------------------------
# Infraestrutura - Banco de Dados
# -----------------------------------------------------------------------------
db-up:
	docker-compose up -d postgres
	@echo "PostgreSQL iniciado. Aguarde healthcheck..."
	@sleep 5

db-down:
	docker-compose stop postgres

db-logs:
	docker-compose logs -f postgres

# -----------------------------------------------------------------------------
# Infraestrutura - Completa
# -----------------------------------------------------------------------------
infra-up:
	docker-compose up -d postgres redis rabbitmq adminer
	@echo "Infraestrutura iniciada:"
	@echo "  - PostgreSQL: localhost:5432"
	@echo "  - Redis: localhost:6379"
	@echo "  - RabbitMQ: localhost:5672 (UI: localhost:15672)"
	@echo "  - Adminer: localhost:8080"

infra-down:
	docker-compose down

infra-logs:
	docker-compose logs -f

infra-clean:
	docker-compose down -v

# -----------------------------------------------------------------------------
# Celery
# -----------------------------------------------------------------------------
celery-worker:
	celery -A src.config.celery worker -l INFO -Q default,events,notifications

celery-beat:
	celery -A src.config.celery beat -l INFO

celery-flower:
	celery -A src.config.celery flower --port=5555

# -----------------------------------------------------------------------------
# Docker Full Stack
# -----------------------------------------------------------------------------
full-up:
	docker-compose --profile full up -d
	@echo "Aplicação completa iniciada:"
	@echo "  - Web: localhost:8000"
	@echo "  - Flower: localhost:5555"
	@echo "  - Adminer: localhost:8080"
	@echo "  - RabbitMQ: localhost:15672"

full-down:
	docker-compose --profile full down

full-logs:
	docker-compose --profile full logs -f

full-build:
	docker-compose --profile full build

# -----------------------------------------------------------------------------
# Testes
# -----------------------------------------------------------------------------
test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

test-core:
	pytest tests/core/ -v

test-adapters:
	pytest tests/adapters/ -v

test-integration:
	pytest tests/integration/ -v

test-fast:
	pytest tests/ -v -x --tb=short

# -----------------------------------------------------------------------------
# Qualidade de Código
# -----------------------------------------------------------------------------
lint:
	flake8 src/ tests/
	mypy src/

format:
	black src/ tests/
	isort src/ tests/

check: lint test
	@echo "Verificações completas!"

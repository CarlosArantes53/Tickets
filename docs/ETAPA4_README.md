# Etapa 4: Event Handlers + Testes de Integração

## 📋 Resumo

Esta etapa implementa processamento assíncrono de Domain Events usando Celery + RabbitMQ, além de testes de integração end-to-end.

## 🏗️ Componentes Implementados

### 1. Configuração Celery (`src/config/celery.py`)

```python
# Iniciar worker
celery -A src.config.celery worker -l INFO

# Iniciar beat (tarefas agendadas)
celery -A src.config.celery beat -l INFO

# Monitoramento (Flower)
celery -A src.config.celery flower --port=5555
```

**Características:**
- Broker: RabbitMQ (AMQP)
- Backend: Redis (resultados)
- Filas separadas: `default`, `events`, `notifications`, `reports`
- Retry automático em falhas
- ACK após execução (at-least-once)

### 2. Event Handlers (`src/adapters/django_app/events/handlers.py`)

| Handler | Evento | Ações |
|---------|--------|-------|
| `handle_ticket_criado` | TicketCriadoEvent | Notifica equipe, registra métrica |
| `handle_ticket_atribuido` | TicketAtribuidoEvent | Notifica técnico, atualiza workload |
| `handle_ticket_fechado` | TicketFechadoEvent | Calcula tempo resolução, métricas |
| `handle_ticket_reaberto` | TicketReabertoEvent | Registra reabertura |
| `handle_prioridade_alterada` | PrioridadeAlteradaEvent | Notifica se escalou |

**Dispatcher Central:**
```python
@shared_task
def dispatch_domain_event(event_type: str, event_data: dict):
    handlers = {
        'TicketCriadoEvent': handle_ticket_criado,
        'TicketAtribuidoEvent': handle_ticket_atribuido,
        ...
    }
    handler = handlers.get(event_type)
    if handler:
        handler.delay(event_data)
```

### 3. Tarefas Agendadas (Beat)

| Tarefa | Schedule | Descrição |
|--------|----------|-----------|
| `check_overdue_tickets` | A cada hora | Verifica tickets atrasados |
| `generate_daily_report` | 8h diário | Gera relatório |
| `cleanup_old_events` | Semanal | Limpa eventos > 90 dias |

### 4. Event Publishers Atualizados

```python
# Desenvolvimento (síncrono)
publisher = LoggingEventPublisher()

# Produção (assíncrono via Celery)
publisher = CeleryEventPublisher()

# Ambos
publisher = CompositeEventPublisher([
    LoggingEventPublisher(),
    CeleryEventPublisher()
])
```

### 5. Testes de Integração

**Localização:** `tests/integration/test_full_integration.py`

```python
# Fluxos testados:
- Ciclo completo: criar → atribuir → fechar
- Validações de negócio
- SLA por prioridade
- Publicação de eventos
- Unit of Work (commit/rollback)
- Handlers de eventos
```

## 📁 Estrutura de Arquivos

```
src/
├── config/
│   ├── __init__.py          # Export celery_app
│   ├── celery.py             # Configuração Celery (NOVO)
│   └── settings.py           # Atualizado com CELERY_*
└── adapters/
    └── django_app/
        └── events/
            ├── __init__.py
            ├── publishers.py  # Atualizado com CeleryEventPublisher
            └── handlers.py    # Event handlers (NOVO)

tests/
└── integration/
    ├── __init__.py
    └── test_full_integration.py  # Testes E2E (NOVO)

docker-compose.yml              # Atualizado com Celery services
Dockerfile                      # NOVO
Makefile                        # Atualizado com comandos Celery
requirements.txt                # Atualizado com celery, flower, etc
```

## 🐳 Docker Services

```yaml
services:
  postgres:     # Banco de dados
  redis:        # Cache + Result backend
  rabbitmq:     # Message broker
  adminer:      # UI banco
  web:          # Django app (profile: full)
  celery_worker: # Workers (profile: full)
  celery_beat:  # Scheduler (profile: full)
  flower:       # Monitoramento (profile: full)
```

## ▶️ Como Executar

### Desenvolvimento Local

```bash
# 1. Iniciar infraestrutura
make infra-up

# 2. Em terminais separados:

# Terminal 1: Django
make runserver

# Terminal 2: Celery Worker
make celery-worker

# Terminal 3: Celery Beat (opcional)
make celery-beat

# Terminal 4: Flower (opcional)
make celery-flower
```

### Docker Compose (Full Stack)

```bash
# Iniciar tudo
make full-up

# Ver logs
make full-logs

# Parar
make full-down
```

### URLs

| Serviço | URL |
|---------|-----|
| Django App | http://localhost:8000 |
| Django Admin | http://localhost:8000/admin/ |
| Flower (Celery) | http://localhost:5555 |
| RabbitMQ Management | http://localhost:15672 |
| Adminer (DB) | http://localhost:8080 |

## 🔄 Fluxo de Eventos

```
1. Usuário cria ticket via View
          ↓
2. Use Case executa lógica de negócio
          ↓
3. Repository persiste no banco
          ↓
4. UoW publica evento via EventPublisher
          ↓
5. CeleryEventPublisher envia para RabbitMQ
          ↓
6. Celery Worker recebe tarefa
          ↓
7. dispatch_domain_event roteia para handler
          ↓
8. Handler executa (notificação, métricas, etc)
```

## 🧪 Testes

```bash
# Todos os testes
make test

# Apenas integração
make test-integration

# Com cobertura
make test-cov

# Testes rápidos (para em erro)
make test-fast
```

### Exemplo de Teste de Integração

```python
def test_ciclo_completo_criar_atribuir_fechar(
    criar_ticket_service,
    atribuir_ticket_service,
    fechar_ticket_service,
    event_publisher,
):
    # 1. Criar
    ticket = criar_ticket_service.execute(input_criar)
    assert ticket.status == 'Aberto'
    
    # 2. Atribuir
    ticket = atribuir_ticket_service.execute(input_atribuir)
    assert ticket.status == 'Em Progresso'
    
    # 3. Fechar
    ticket = fechar_ticket_service.execute(input_fechar)
    assert ticket.status == 'Fechado'
    
    # Verificar eventos publicados
    assert len(event_publisher.get_events_by_type('TicketCriadoEvent')) == 1
    assert len(event_publisher.get_events_by_type('TicketAtribuidoEvent')) == 1
    assert len(event_publisher.get_events_by_type('TicketFechadoEvent')) == 1
```

## ⚙️ Configuração

### Variáveis de Ambiente

```bash
# .env
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//
CELERY_RESULT_BACKEND=redis://localhost:6379/1
EVENT_PUBLISHER_MODE=celery  # ou 'sync' para desenvolvimento
```

### Settings Django

```python
# src/config/settings.py

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'amqp://...')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://...')
CELERY_TASK_ACKS_LATE = True  # At-least-once delivery
CELERY_TASK_MAX_RETRIES = 3

EVENT_PUBLISHER_MODE = os.getenv('EVENT_PUBLISHER_MODE', 'sync')
```

## ✅ Critérios de Aceite

- [x] Celery configurado com RabbitMQ
- [x] Event Handlers para todos os eventos de ticket
- [x] Dispatcher central de eventos
- [x] Tarefas agendadas (Beat)
- [x] CeleryEventPublisher integrado
- [x] Testes de integração E2E
- [x] Docker Compose atualizado
- [x] Dockerfile criado
- [x] Makefile com comandos Celery

## 📊 Monitoramento

### Flower Dashboard
- Tasks ativas/pendentes/completadas
- Workers online
- Tempo de execução
- Taxa de sucesso/erro

### Logs
```bash
# Worker logs
make celery-worker  # -l INFO mostra logs

# Aplicação
docker-compose logs -f celery_worker
```

## 🔄 Próximas Etapas (Sugeridas)

**Etapa 5: API REST Completa**
- Django REST Framework
- Serializers
- ViewSets
- Autenticação JWT

**Etapa 6: Autenticação e Autorização**
- User model
- Permissões por papel (admin, técnico, usuário)
- OAuth2/OIDC

**Etapa 7: Frontend**
- React/Vue SPA
- Integração com API
- Real-time updates (WebSockets)

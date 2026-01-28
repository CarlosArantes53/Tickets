# Etapa 3: Views + Dependency Injection Container

## 📋 Resumo

Esta etapa implementa a camada de apresentação (Views) com integração completa de Dependency Injection, seguindo os princípios da Arquitetura Hexagonal.

## 🏗️ Componentes Implementados

### 1. Container de DI Aprimorado (`src/config/container.py`)

```
Container (Principal)
├── CoreContainer       → Configurações de domínio
├── InfrastructureContainer → Repositories, Event Store, UoW
└── ServiceContainer    → Use Cases (CriarTicket, AtribuirTicket, etc)
```

**Características:**
- Lazy loading com `dependency-injector`
- Thread-safe por padrão
- Padrões Singleton (repositories) e Factory (services)
- `TestingContainer` para testes com mocks

**Uso:**
```python
from src.config.container import get_container

container = get_container()
service = container.services.criar_ticket_service()
result = service.execute(input_dto)
```

### 2. Views HTML (`src/adapters/django_app/tickets/views.py`)

| View | URL | Método | Descrição |
|------|-----|--------|-----------|
| `DashboardView` | `/tickets/dashboard/` | GET | Visão geral com estatísticas |
| `TicketListView` | `/tickets/` | GET | Lista com filtros e paginação |
| `TicketDetailView` | `/tickets/<id>/` | GET | Detalhes do ticket |
| `TicketCreateView` | `/tickets/criar/` | GET/POST | Formulário de criação |
| `TicketAtribuirView` | `/tickets/<id>/atribuir/` | POST | Atribui a técnico |
| `TicketFecharView` | `/tickets/<id>/fechar/` | POST | Fecha ticket |
| `TicketReabrirView` | `/tickets/<id>/reabrir/` | POST | Reabre ticket |
| `TicketAlterarPrioridadeView` | `/tickets/<id>/prioridade/` | POST | Altera prioridade |

**Mixins:**
- `ContainerMixin` → Acesso ao DI Container
- `FlashMessageMixin` → Mensagens de feedback
- `UserContextMixin` → Informações do usuário

### 3. API JSON (`src/adapters/django_app/tickets/api_views.py`)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/tickets/api/` | GET | Lista tickets (paginado) |
| `/tickets/api/` | POST | Cria ticket |
| `/tickets/api/estatisticas/` | GET | Estatísticas |
| `/tickets/api/<id>/` | GET | Detalhes |
| `/tickets/api/<id>/` | PATCH | Atualização parcial |
| `/tickets/api/<id>/atribuir/` | POST | Atribui ticket |
| `/tickets/api/<id>/fechar/` | POST | Fecha ticket |
| `/tickets/api/<id>/reabrir/` | POST | Reabre ticket |

**Formato de Resposta:**
```json
{
  "success": true|false,
  "data": {...},
  "error": "mensagem de erro",
  "meta": {
    "total": 100,
    "page": 1,
    "per_page": 20
  }
}
```

### 4. Event Publishers (`src/adapters/django_app/events/publishers.py`)

- `EventPublisher` (ABC) → Interface
- `LoggingEventPublisher` → Loga eventos (dev)
- `InMemoryEventPublisher` → Para testes
- `CompositeEventPublisher` → Múltiplos destinos

### 5. Templates HTML (`templates/`)

```
templates/
├── base.html                    → Layout base com Bootstrap 5
├── includes/
│   ├── status_badge.html       → Badge de status
│   └── prioridade_badge.html   → Badge de prioridade
└── tickets/
    ├── list.html               → Listagem com filtros
    ├── detail.html             → Detalhes e ações
    ├── create.html             → Formulário de criação
    ├── dashboard.html          → Dashboard
    └── not_found.html          → 404
```

## 🎨 Interface Visual

A interface usa Bootstrap 5 com:
- Cards para estatísticas
- Badges coloridos para status/prioridade
- Paginação
- Flash messages
- Formulários modais
- Ícones Bootstrap Icons

## 📁 Estrutura de Arquivos Criados

```
src/
├── config/
│   └── container.py              # Container DI (atualizado)
└── adapters/
    └── django_app/
        ├── events/
        │   └── publishers.py     # Event Publishers
        └── tickets/
            ├── views.py          # Views HTML (atualizado)
            ├── api_views.py      # API JSON (novo)
            ├── urls.py           # URLs (atualizado)
            └── forms.py          # Forms (atualizado)

templates/
├── base.html
├── includes/
│   ├── status_badge.html
│   └── prioridade_badge.html
└── tickets/
    ├── list.html
    ├── detail.html
    ├── create.html
    ├── dashboard.html
    └── not_found.html

tests/
└── adapters/
    └── django_app/
        └── test_views.py         # Testes de views/API
```

## 🔧 Configuração

### URLs (`src/config/urls.py`)
```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('tickets/', include('src.adapters.django_app.tickets.urls')),
    path('health/', lambda r: JsonResponse({'status': 'ok'})),
]
```

### Settings (`src/config/settings.py`)
```python
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        ...
    },
]
```

## 🧪 Testes

```bash
# Rodar testes de views
pytest tests/adapters/django_app/test_views.py -v

# Todos os testes
pytest tests/ -v
```

## ▶️ Como Usar

```bash
# 1. Iniciar infraestrutura
make db-up

# 2. Aplicar migrations
make migrate

# 3. Iniciar servidor
make runserver

# 4. Acessar
# Dashboard: http://localhost:8000/tickets/dashboard/
# Lista: http://localhost:8000/tickets/
# API: http://localhost:8000/tickets/api/
```

## 🔄 Fluxo de Requisição

```
HTTP Request
    ↓
URL Router (urls.py)
    ↓
View (views.py / api_views.py)
    ↓
Container.get_service()
    ↓
Use Case (service)
    ↓
Repository / UoW
    ↓
Database
    ↓
Response (HTML/JSON)
```

## ✅ Critérios de Aceite da Etapa 3

- [x] Container DI com dependency-injector
- [x] Views HTML completas com templates
- [x] API JSON RESTful
- [x] Event Publishers abstraídos
- [x] Flash messages para feedback
- [x] Paginação na listagem
- [x] Filtros funcionais
- [x] Tratamento de erros padronizado
- [x] Testes para views e API

## 🔄 Próxima Etapa

**Etapa 4: Event Handlers + Testes de Integração**
- Celery para processamento assíncrono
- RabbitMQ como message broker
- Event Handlers para notificações
- Testes de integração end-to-end

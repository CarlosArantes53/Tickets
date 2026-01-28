# Etapa 2: Django Adapters + PostgreSQL

## 📋 Visão Geral

Esta etapa implementa os **DRIVEN ADAPTERS** da Arquitetura Hexagonal, conectando o Core Domain ao Django ORM e PostgreSQL.

### Arquivos Criados/Atualizados

```
src/
├── adapters/
│   └── django_app/
│       ├── shared/
│       │   ├── __init__.py
│       │   ├── database.py       # Abstração de banco de dados
│       │   ├── repository.py     # Base Repository com funcionalidades comuns
│       │   └── unit_of_work.py   # DjangoUnitOfWork + InMemoryUnitOfWork
│       │
│       └── tickets/
│           ├── __init__.py
│           ├── admin.py          # Django Admin
│           ├── apps.py           # Configuração do app
│           ├── forms.py          # Forms de validação
│           ├── mappers.py        # Entity ↔ Model
│           ├── models.py         # Django Models
│           ├── repositories.py   # DjangoTicketRepository
│           ├── urls.py           # Rotas
│           ├── views.py          # Views com DI
│           └── migrations/
│               └── 0001_initial.py
│
├── config/
│   ├── __init__.py
│   ├── container.py              # Dependency Injection Container
│   ├── settings.py               # Django settings
│   ├── urls.py                   # URLs principais
│   └── wsgi.py                   # WSGI config
│
├── manage.py                     # Django CLI
├── docker-compose.yml            # PostgreSQL + Redis + RabbitMQ
├── .env.example                  # Variáveis de ambiente
└── scripts/
    ├── setup_database.sh         # Setup PostgreSQL
    └── quick_setup.py            # Setup rápido (SQLite)
```

## 🏗️ Arquitetura Implementada

### Camadas de Abstração

```
┌─────────────────────────────────────────────────────────┐
│                    CORE DOMAIN                          │
│  (src/core/)                                            │
│                                                         │
│  ┌─────────────────┐  ┌─────────────────┐              │
│  │  TicketEntity   │  │  Use Cases      │              │
│  │  (Regras)       │  │  (Services)     │              │
│  └────────┬────────┘  └────────┬────────┘              │
│           │                    │                        │
│           │    Interfaces (Ports)                      │
│           │    ┌──────────────────────┐                │
│           └────│  TicketRepository    │────────────────│
│                │  UnitOfWork          │                │
│                └──────────┬───────────┘                │
└───────────────────────────┼─────────────────────────────┘
                            │
                            │ Implementa
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    ADAPTERS                             │
│  (src/adapters/django_app/)                             │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  DjangoTicketRepository                          │   │
│  │  - Implementa TicketRepository (Port)            │   │
│  │  - Usa Django ORM                                │   │
│  │  - Converte Entity ↔ Model via Mapper            │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  DjangoUnitOfWork                                │   │
│  │  - Implementa UnitOfWork (Port)                  │   │
│  │  - Gerencia transações PostgreSQL                │   │
│  │  - Publica eventos após commit                   │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  DatabaseAdapter (Abstração)                     │   │
│  │  - Interface para múltiplos bancos               │   │
│  │  - Facilita troca: PostgreSQL → MongoDB          │   │
│  │  - Database Router para sharding                 │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │  PostgreSQL  │
                     │  (ou SQLite) │
                     └──────────────┘
```

### Abstração de Banco de Dados

A camada `DatabaseAdapter` permite trocar implementações facilmente:

```python
# src/adapters/django_app/shared/database.py

# Configuração via variáveis de ambiente
config = DatabaseConfig.from_env()

# Ou via URL
config = DatabaseConfig.from_url(
    "postgresql://user:pass@host:5432/dbname"
)

# Criar adapter
adapter = DatabaseAdapterFactory.create(config, adapter_type="django")

# Verificar saúde
adapter.health_check()  # True se conectado

# Converter para Django settings
settings.DATABASES['default'] = config.to_django_config()
```

### Database Router para Escalabilidade

Preparado para sharding por domínio:

```python
# settings.py
DATABASE_ROUTERS = ['src.adapters.django_app.shared.database.DomainDatabaseRouter']

DATABASES = {
    'default': {...},        # Tickets
    'scheduling': {...},     # Agendamentos (futuro)
    'inventory': {...},      # Inventário (futuro)
}
```

## 🚀 Como Usar

### 1. Desenvolvimento Rápido (SQLite)

```bash
# Copiar variáveis de ambiente
cp .env.example .env

# Editar para usar SQLite
echo "DATABASE_URL=sqlite:///db.sqlite3" >> .env

# Setup rápido
python scripts/quick_setup.py --with-sample-data

# Iniciar servidor
python manage.py runserver
```

### 2. Com PostgreSQL (Docker)

```bash
# Iniciar PostgreSQL
docker-compose up -d postgres

# Aguardar inicialização
sleep 5

# Executar migrations
python manage.py migrate

# Criar superusuário
python manage.py createsuperuser

# Iniciar servidor
python manage.py runserver
```

### 3. Acessar Aplicação

- **Admin**: http://localhost:8000/admin/
- **Tickets**: http://localhost:8000/tickets/
- **API**: http://localhost:8000/tickets/api/

## 📦 Dependency Injection

O Container gerencia todas as dependências:

```python
from src.config.container import get_container

# Obter container
container = get_container()

# Usar service (já com repo e UoW injetados)
service = container.criar_ticket_service()
output = service.execute(input_dto)
```

### Nas Views

```python
from src.config.container import get_container

class TicketCreateView(View):
    def post(self, request):
        container = get_container()
        service = container.criar_ticket_service()
        
        output = service.execute(input_dto)
        return redirect('tickets:detail', pk=output.id)
```

## 🗄️ Models Django

### TicketModel

```python
class TicketModel(models.Model):
    id = models.CharField(max_length=36, primary_key=True)
    titulo = models.CharField(max_length=200, db_index=True)
    descricao = models.TextField()
    status = models.CharField(choices=TicketStatusChoices.choices)
    prioridade = models.CharField(choices=TicketPriorityChoices.choices)
    criador_id = models.CharField(max_length=100, db_index=True)
    atribuido_a_id = models.CharField(max_length=100, null=True)
    sla_prazo = models.DateTimeField(null=True, db_index=True)
    tags = models.JSONField(default=list)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tickets'
        indexes = [
            models.Index(fields=['status', 'criado_em']),
            models.Index(fields=['atribuido_a_id', 'status']),
            models.Index(fields=['prioridade', 'sla_prazo']),
        ]
```

### DomainEventModel (Event Store)

```python
class DomainEventModel(models.Model):
    event_id = models.CharField(max_length=36, primary_key=True)
    event_type = models.CharField(max_length=100, db_index=True)
    aggregate_type = models.CharField(max_length=100)
    aggregate_id = models.CharField(max_length=36, db_index=True)
    event_data = models.JSONField()
    sequence = models.BigIntegerField()
    occurred_at = models.DateTimeField()
    recorded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'domain_events'
```

## 🧪 Testes

### Executar Testes

```bash
# Todos os testes
make test

# Com cobertura
make test-cov

# Apenas adapters
make test-integration

# Apenas Core
make test-core
```

### Fixtures Disponíveis

```python
# tests/adapters/django_app/conftest.py

@pytest.fixture
def sample_ticket_entity():
    """Entidade de ticket para testes."""
    
@pytest.fixture
def inmemory_ticket_repo():
    """Repositório em memória."""
    
@pytest.fixture
def inmemory_uow():
    """Unit of Work em memória."""
```

## 🔧 Comandos Make

```bash
make init          # Setup completo
make db-up         # Iniciar PostgreSQL
make db-down       # Parar PostgreSQL
make migrate       # Executar migrations
make runserver     # Iniciar servidor
make test          # Rodar testes
make test-cov      # Testes com cobertura
make clean         # Limpar cache
```

## 📊 Próximas Etapas

### Etapa 3: Views + Templates
- Implementar templates HTML
- Adicionar autenticação
- API REST com Django REST Framework

### Etapa 4: Event Handlers
- Celery workers
- RabbitMQ integration
- Email notifications

## 🏗️ Escalabilidade Futura

### Trocar PostgreSQL por MongoDB

1. Criar `MongoDBAdapter`:
```python
class MongoDBAdapter(DatabaseAdapter):
    def connect(self):
        self.client = pymongo.MongoClient(self.config.to_mongo_url())
```

2. Criar `MongoTicketRepository`:
```python
class MongoTicketRepository(TicketRepositoryPort):
    def save(self, entity):
        self.collection.update_one(
            {'_id': entity.id},
            {'$set': self._to_document(entity)},
            upsert=True
        )
```

3. Registrar no Container:
```python
Container.ticket_repository.override(
    providers.Singleton(MongoTicketRepository)
)
```

### Adicionar Read Replicas

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'techsupport',
        'HOST': 'primary.db.local',
    },
    'replica': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'techsupport',
        'HOST': 'replica.db.local',
    },
}

# Router direciona leituras para replica
class ReadReplicaRouter:
    def db_for_read(self, model, **hints):
        return 'replica'
    
    def db_for_write(self, model, **hints):
        return 'default'
```

---

**Status**: ✅ Completo
**Próxima Etapa**: Views + Templates + API

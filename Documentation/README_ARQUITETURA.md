# TechSupport Manager - Arquitetura Hexagonal

## 1. Visão Geral da Arquitetura

Este documento especifica a **Arquitetura Hexagonal (Ports & Adapters)** do TechSupport Manager, um sistema de gerenciamento de suporte técnico desenvolvido em **Python/Django**.

O objetivo arquitetural é garantir que as regras de negócio permaneçam **isoladas, testáveis e independentes** de infraestrutura ou frameworks. Isto permite que a base de código evolua sem acoplamento a decisões técnicas específicas como banco de dados, frameworks web ou bibliotecas de terceiros.

---

## 2. Princípios Arquiteturais

### 2.1 Hexágono (Core Domain)

O **hexágono** é o coração puro da aplicação, localizado em `src/core/`. Representa a lógica de negócio sem qualquer contaminação externa.

**Características**:
- Sem dependências de Django, requests, SQLAlchemy ou qualquer framework
- Completamente agnóstico a detalhes de infraestrutura
- Utilizável em qualquer contexto (CLI, API REST, gRPC, mobile backend)
- 100% testável sem fixtures de banco de dados

**Componentes**:
- **Entidades**: Objetos de domínio que encapsulam regras de negócio e identidades
- **Use Cases (Services)**: Orquestram o fluxo de dados, coordenando múltiplas entidades e repositórios
- **Ports (Protocolos)**: Interfaces que definem contratos que o mundo externo deve implementar
- **DTOs (Data Transfer Objects)**: Estruturas simples para tráfego entre camadas, prevenindo vazamento de modelos internos

### 2.2 Adaptadores (Boundary Layer)

Localizados em `src/adapters/`, os adaptadores são implementações concretas das interfaces (Ports) definidas pelo Core.

**Categorias**:

1. **Driving Adapters (Lado Esquerdo)**: Direcionam requisições para o Core
   - Django Views (HTTP)
   - Forms HTML (validação)
   - Comandos CLI
   - Webhooks

2. **Driven Adapters (Lado Direito)**: São acionados pelo Core em resposta a operações
   - Repositórios (PostgreSQL via ORM)
   - Cache (Redis)
   - Event Publishers (Event Bus, Celery)
   - Serviços de Email

### 2.3 Padrão de Organização: Vertical Slicing

Em vez de organizar por camada técnica (`models/`, `views/`, `services/`), a arquitetura utiliza **vertical slicing** por contexto de negócio:

```
src/adapters/django_app/
├── tickets/           # Slice 1: Gerenciamento de Tickets
│   ├── models.py
│   ├── repositories.py
│   ├── views.py
│   └── mappers.py
├── agendamento/       # Slice 2: Agendamentos
│   ├── models.py
│   ├── repositories.py
│   ├── views.py
│   └── mappers.py
└── inventario/        # Slice 3: Inventário
    ├── models.py
    ├── repositories.py
    ├── views.py
    └── mappers.py
```

**Benefícios**:
- Developers trabalham em features end-to-end sem navegar múltiplas pastas
- Mudanças em um domínio ficam localizadas (blast radius reduzido)
- Cada slice pode evoluir padrões independentemente (tickets: rich domain model; inventário: transactional)
- Facilita delegação de features a diferentes squads

---

## 3. Fluxo de Dados: Exemplo Prático

Para entender como as camadas interagem, considere a operação **"Criar um Ticket"**:

### 3.1 Entrada (Driving Adapter)

```python
# src/adapters/django_app/tickets/views.py
from dependency_injector.wiring import Provide, inject
from src.core.tickets.use_cases import CriarTicketService

class TicketCreateView(View):
    @inject
    def post(self, request, service: CriarTicketService = Provide[Container.criar_ticket_service]):
        form = TicketForm(request.POST)
        if form.is_valid():
            # 1. View valida entrada via Django Form
            # 2. View invoca Service do Core (injeção no construtor)
            output = service.execute(form.cleaned_data)
            return redirect('ticket_detail', pk=output.ticket_id)
```

**Nota Arquitetural**: A injeção ocorre no **construtor do método** via decorador `@inject`, não via Service Locator. Isto mantém dependências **explícitas** e **testáveis**.

### 3.2 Processamento (Core Domain)

```python
# src/core/tickets/use_cases.py
from src.core.tickets.entities import TicketEntity
from src.core.interfaces import UnitOfWork

class CriarTicketService:
    def __init__(self, ticket_repo: TicketRepository, uow: UnitOfWork):
        self.ticket_repo = ticket_repo
        self.uow = uow

    def execute(self, data: dict) -> TicketOutputDTO:
        # Transação atômica: tudo ou nada
        with self.uow:
            # Criar entidade com regras de negócio
            ticket = TicketEntity.criar(
                titulo=data['title'],
                descricao=data['description'],
                usuario_criador_id=data['user_id']
            )
            
            # Persistir via interface (não conhece implementação)
            self.ticket_repo.save(ticket)
            
            # Disparar evento de domínio (side-effects assíncrono)
            self.uow.publish_event(TicketCriadoEvent(ticket.id))

        return TicketOutputDTO.from_entity(ticket)
```

**Características**:
- Service **não importa Django, ORM ou qualquer framework**
- Utiliza `UnitOfWork` para garantir transação atômica
- Dispara `DomainEvent` para notificações assíncronas desacopladas
- Retorna `OutputDTO` (não entidade)

### 3.3 Persistência (Driven Adapter)

```python
# src/adapters/django_app/tickets/repositories.py
from src.core.tickets.ports import TicketRepository as TicketRepositoryPort
from .models import TicketModel

class TicketRepository(TicketRepositoryPort):
    def save(self, ticket: TicketEntity) -> None:
        # Mapear entidade → modelo Django
        model = TicketModel(
            id=ticket.id,
            title=ticket.title,
            description=ticket.description,
            status=ticket.status.value
        )
        model.save()  # Postgres
```

**Nota de Desacoplamento**: Repository implementa interface do Core. Core não conhece ORM.

### 3.4 Finalização

```python
# src/adapters/django_app/tickets/views.py (continuação)
output = service.execute(form.cleaned_data)
# Service já retornou → UoW.commit() foi chamado
# Evento já foi publicado → consumidores assíncronos reagem
return JsonResponse(output.to_dict())  # Renderiza resposta
```

---

## 4. Padrões Arquiteturais Implementados

### 4.1 Unit of Work (Padrão de Transação)

**Objetivo**: Coordenar múltiplos repositórios em uma transação atômica sem que o Core importe `django.db.transaction`.

**No Core** (`src/core/ports.py`):
```python
from abc import ABC, abstractmethod

class UnitOfWork(ABC):
    """Interface de contrato para transações."""
    
    @abstractmethod
    def __enter__(self):
        return self
    
    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
    
    @abstractmethod
    def commit(self) -> None:
        raise NotImplementedError
    
    @abstractmethod
    def rollback(self) -> None:
        raise NotImplementedError
    
    @abstractmethod
    def publish_event(self, event: DomainEvent) -> None:
        raise NotImplementedError
```

**No Adapter** (`src/adapters/django_app/unit_of_work.py`):
```python
from django.db import transaction

class DjangoUnitOfWork(UnitOfWork):
    """Implementação concreta usando Django ORM."""
    
    def __enter__(self):
        transaction.set_autocommit(False)
        return self
    
    def commit(self) -> None:
        transaction.commit()
        transaction.set_autocommit(True)
    
    def rollback(self) -> None:
        transaction.rollback()
        transaction.set_autocommit(True)
    
    def publish_event(self, event: DomainEvent) -> None:
        # Delegado a event bus ou fila assíncrona
        event_bus.publish(event)
```

**Uso no Service**:
```python
def execute(self, data):
    with self.uow:  # Inicia transação
        ticket = TicketEntity.criar(data)
        self.repo.save(ticket)
        self.uow.publish_event(TicketCriadoEvent(ticket.id))
    # Ao sair do bloco, commit() ou rollback() é chamado automaticamente
```

**Benefício**: Se qualquer operação falhar, **tudo é desfeito**. Nenhuma persistência parcial.

### 4.2 Dependency Injection (Desacoplamento de Instâncias)

**Problema**: Views precisam instanciar Services, que precisam de Repositories, que precisam de Mappers...

**Solução**: Container declarativo gerencia dependências.

**Implementação Melhorada** (`src/config/container.py`):
```python
from dependency_injector import containers, providers
from src.core.tickets.use_cases import CriarTicketService
from src.adapters.django_app.tickets.repositories import TicketRepository
from src.adapters.django_app.unit_of_work import DjangoUnitOfWork

class Container(containers.DeclarativeContainer):
    # Lazy: criado sob demanda (não ao startup)
    ticket_repo = providers.Singleton(TicketRepository)
    uow = providers.Singleton(DjangoUnitOfWork)
    
    # Factory: nova instância a cada chamada (para thread-safety)
    criar_ticket_service = providers.Factory(
        CriarTicketService,
        ticket_repo=ticket_repo,
        uow=uow
    )
```

**Nota Crítica sobre Service Locator**:
❌ **Anti-pattern**: `service = container.get(CriarTicketService)` na View (dependência implícita)
✅ **Padrão Correto**: `@inject` no construtor (dependência explícita)

```python
# ✅ CORRETO: Constructor Injection
class TicketView(View):
    @inject
    def post(self, request, service: CriarTicketService = Provide[Container.criar_ticket_service]):
        service.execute(...)

# ❌ EVITAR: Service Locator
class TicketView(View):
    def post(self, request):
        service = container.get_criar_ticket_service()  # Acoplamento!
```

**Benefício**: Dependências são explícitas; mockar em testes é trivial.

### 4.3 Repository Pattern com Cautela

**Objetivo**: Abstrair persistência para permitir troca de banco sem afetar Core.

**Implementação em Domínios Críticos**:
```python
# src/core/tickets/ports.py
class TicketRepository(Protocol):
    def save(self, ticket: TicketEntity) -> None: ...
    def get_by_id(self, ticket_id: str) -> TicketEntity: ...
    def list_by_status(self, status: TicketStatus) -> list[TicketEntity]: ...

# src/adapters/django_app/tickets/repositories.py
class TicketRepository:
    def save(self, ticket: TicketEntity) -> None:
        model = self._mapper.to_model(ticket)
        model.save()
    
    def get_by_id(self, ticket_id: str) -> TicketEntity:
        model = TicketModel.objects.select_related('assigned_user').get(id=ticket_id)
        return self._mapper.to_entity(model)
```

**⚠️ Overhead de Mapper**: Cada repositório requer `to_entity()` e `from_entity()`. Para domínios simples (inventário), considere usar ORM direto:

```python
# ✅ PRAGMÁTICO para Inventário (CRUD simples)
class Inventario(models.Model):
    sku = models.CharField(max_length=50)
    quantidade = models.IntegerField()
    
    def validar_saida(self, qtd):
        if qtd > self.quantidade:
            raise InsufficientStock()
        self.quantidade -= qtd
        self.save()

# Service delega direto:
def usar_equipamento(self, inventario_id, qtd):
    inventario = Inventario.objects.get(id=inventario_id)
    inventario.validar_saida(qtd)  # Lógica de negócio no modelo
```

**Filosofia**: Repository Pattern é poderoso para domínios ricos (Tickets com SLA, validações complexas). Para domínios transacionais, ORM direto é mais pragmático.

### 4.4 DTOs como Contrato de Entrada/Saída

**Objetivo**: Desacoplar representação interna (Entity) de tráfego entre camadas.

```python
# src/core/tickets/use_cases.py
class CriarTicketInputDTO:
    title: str
    description: str
    assigned_to_id: str

class CriarTicketOutputDTO:
    ticket_id: str
    status: str
    created_at: datetime
    
    @classmethod
    def from_entity(cls, entity: TicketEntity) -> 'CriarTicketOutputDTO':
        return cls(
            ticket_id=entity.id,
            status=entity.status.value,
            created_at=entity.created_at
        )
```

**Benefício**: 
- View não expõe Entity em JSON (evita vazamento de estrutura interna)
- Service pode retornar dados diferentes da Entity (e.g., SLA calculado em tempo de execução)
- Contrato claro entre Core e Adapters

---

## 5. Módulos de Negócio

### 5.1 Tickets (Gerenciamento de Incidentes)

**Características Arquiteturais**:
- Entidade rica com regras complexas (SLA, status válidos, transições)
- Repository Pattern completo (múltiplas queries com filtros)
- Domain Events: `TicketCriado`, `TicketAtribuido`, `TicketFechado`
- Integração com notificações assíncronas

**Fluxo**:
1. User cria ticket via View
2. Service valida regras (descrição não-vazia, categoria válida)
3. Entity encapsula SLA inicial e status
4. Repository persiste no Postgres
5. Event disparado → consumidor envia email assíncrono

### 5.2 Agendamento (Scheduling)

**Características Arquiteturais**:
- Domínio transacional (CRUD simples)
- Regra crítica: impedir colisão de horários (validação no Core)
- Pode usar ORM direto com menos overhead

**Validação de Negócio** (no Core):
```python
# src/core/agendamento/entities.py
class Agendamento:
    def __init__(self, tecnico_id, data_hora_inicio, duracao):
        self.tecnico_id = tecnico_id
        self.data_hora_inicio = data_hora_inicio
        self.duracao = duracao
    
    def valida_colisao(self, repo: AgendamentoRepository) -> bool:
        agendamentos_existentes = repo.list_by_tecnico(self.tecnico_id)
        for agend in agendamentos_existentes:
            if self._sobrepoe(agend):
                raise ColisaoHorarioError()
```

### 5.3 Inventário (Gestão de Ativos)

**Características Arquiteturais**:
- CRUD direto sobre ORM (sem mapper)
- Histórico imutável de movimentações (Domain Events + Event Store)
- Auditoria nativa via event sourcing leve

**Simplificação Arquitetural**:
```python
# src/adapters/django_app/inventario/models.py
class Inventario(models.Model):
    sku = models.CharField()
    usuario_custodio = models.ForeignKey(User)
    data_movimentacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        # Apenas leitura na tabela; histórico em InventarioHistorico
        pass

class InventarioHistorico(models.Model):
    inventario = models.ForeignKey(Inventario)
    usuario_anterior = models.ForeignKey(User, null=True)
    usuario_novo = models.ForeignKey(User)
    data = models.DateTimeField(auto_now_add=True)
```

### 5.4 Notificações e Eventos (Side-Effects)

**Padrão**: Event-Driven Async

```python
# src/core/events.py
class DomainEvent(ABC):
    aggregate_id: str
    occurred_at: datetime

class TicketCriadoEvent(DomainEvent):
    ticket_id: str
    usuario_criador_id: str

# src/adapters/django_app/events/handlers.py
class TicketCriadoHandler:
    def handle(self, event: TicketCriadoEvent):
        # Executado assincronamente via Celery/Redis
        usuario = User.objects.get(id=event.usuario_criador_id)
        enviar_email(usuario, f"Ticket {event.ticket_id} criado")
```

**Desacoplamento**:
- Service dispara evento → Unit of Work publica
- Consumer assíncrono reage
- Core jamais aguarda resposta (side-effect)

---

## 6. Estrutura Completa de Diretórios

```
techsupport/
├── src/
│   ├── core/                           # HEXÁGONO (Pure Domain Logic)
│   │   ├── shared/
│   │   │   ├── exceptions.py          # Exceções de domínio
│   │   │   ├── interfaces.py          # UnitOfWork, Repository protocols
│   │   │   └── events.py              # DomainEvent base class
│   │   │
│   │   ├── tickets/
│   │   │   ├── entities.py            # TicketEntity, TicketStatus, SLA
│   │   │   ├── use_cases.py           # CriarTicketService, ListarTicketsService
│   │   │   ├── ports.py               # TicketRepository protocol
│   │   │   └── events.py              # TicketCriadoEvent, TicketAtribuidoEvent
│   │   │
│   │   ├── agendamento/
│   │   │   ├── entities.py
│   │   │   ├── use_cases.py
│   │   │   ├── ports.py
│   │   │   └── events.py
│   │   │
│   │   └── inventario/
│   │       ├── entities.py
│   │       ├── use_cases.py
│   │       ├── ports.py
│   │       └── events.py
│   │
│   ├── adapters/                       # ADAPTADORES (Concrete Implementations)
│   │   └── django_app/
│   │       ├── shared/
│   │       │   ├── middleware.py
│   │       │   ├── decorators.py
│   │       │   └── auth.py
│   │       │
│   │       ├── tickets/               # SLICE 1: Tickets
│   │       │   ├── models.py          # Django ORM Models
│   │       │   ├── repositories.py    # Implementação de TicketRepository
│   │       │   ├── mappers.py         # Conversão Model ↔ Entity
│   │       │   ├── views.py           # Django Views (Driving Adapters)
│   │       │   ├── forms.py           # Validação HTML
│   │       │   ├── serializers.py     # JSON/API (opcionalmente)
│   │       │   └── urls.py            # Rotas
│   │       │
│   │       ├── agendamento/           # SLICE 2: Agendamento
│   │       │   ├── models.py
│   │       │   ├── repositories.py
│   │       │   ├── views.py
│   │       │   ├── forms.py
│   │       │   └── urls.py
│   │       │
│   │       ├── inventario/            # SLICE 3: Inventário
│   │       │   ├── models.py
│   │       │   ├── repositories.py
│   │       │   ├── views.py
│   │       │   ├── forms.py
│   │       │   └── urls.py
│   │       │
│   │       ├── events/                # Handlers de Domain Events
│   │       │   ├── ticket_handlers.py
│   │       │   ├── agendamento_handlers.py
│   │       │   └── event_publisher.py
│   │       │
│   │       ├── unit_of_work.py        # Implementação DjangoUnitOfWork
│   │       │
│   │       └── apps.py
│   │
│   ├── config/                         # Configuração Global
│   │   ├── container.py               # DI Container
│   │   ├── settings.py                # Django settings
│   │   └── urls.py                    # URL master
│   │
│   └── manage.py
│
├── static/                             # FRONTEND (Desacoplado)
│   ├── css/
│   │   ├── base/
│   │   ├── components/
│   │   └── pages/
│   ├── js/
│   │   ├── core/
│   │   └── modules/
│   └── img/
│
├── templates/                          # Django Templates
│   ├── base.html
│   ├── components/
│   ├── tickets/
│   ├── agendamento/
│   └── inventario/
│
├── tests/                              # Testes (unitários, integração)
│   ├── core/
│   │   ├── tickets/
│   │   ├── agendamento/
│   │   └── inventario/
│   ├── adapters/
│   │   ├── test_repositories.py
│   │   ├── test_views.py
│   │   └── test_unit_of_work.py
│   └── integration/
│
└── requirements.txt
```

---

## 7. Padrões de Comunicação Entre Camadas

### 7.1 View → Service

**Fluxo de Entrada**:
```
HTTP Request
    ↓
Django Form (validação estrutural)
    ↓
InputDTO (dados validados)
    ↓
Service.execute(InputDTO)
```

### 7.2 Service → Repository

**Abstração de Persistência**:
```
Service (Core)
    ↓
Port: TicketRepository (interface)
    ↓
Adapter: TicketRepository (Django ORM)
    ↓
PostgreSQL
```

### 7.3 Service → Event Bus

**Desacoplamento de Side-Effects**:
```
Service (Core)
    ↓
UnitOfWork.publish_event(DomainEvent)
    ↓
EventBus (Redis/RabbitMQ/Celery)
    ↓
Handlers assíncronos (Email, Webhooks)
```

---

## 8. Princípios de Design

### 8.1 Separation of Concerns
- **Core**: Apenas regras de negócio
- **Adapters**: Apenas detalhes técnicos
- **No mixing**: Django não entra no Core; Core não entra em Adapters

### 8.2 Dependency Inversion
- Core define interfaces (Ports)
- Adapters implementam interfaces
- Fluxo de dependência aponta para Core

### 8.3 Open/Closed Principle
- Sistema aberto para extensão (novos adapters, novos domínios)
- Fechado para modificação (Core estável)

### 8.4 Single Responsibility
- Cada classe tem uma responsabilidade clara
- Services orquestram; Entities encapsulam; Repositories persistem

---

## 9. Trade-offs e Considerações

### Complexidade vs. Flexibilidade

**Hexagonal + DDD + DI introduz overhead**:
- Mais classes (Entity, DTO, Repository, Service, Adapter)
- Mais abstrações (Ports, Interfaces)
- Mais mapeamentos (Model → Entity → DTO)

**Justificado quando**:
- Equipe > 3 pessoas
- Projeto > 6 meses
- Mudanças frequentes em requisitos
- Testabilidade crítica

**Não justificado quando**:
- MVP para validar ideia
- CRUD simples sem lógica
- Projeto com prazo apertado

### N+1 Queries

**Risco**: Lazy evaluation do Django + abstração de Repository pode ocultar problemas.

**Mitigação**:
- Use `select_related()` explicitamente em queries críticas
- Implemente Query DTOs que carregam dados necessários
- Monitore com Django Debug Toolbar

### Performance de Mappers

**Risco**: Construir N entidades para 10k registros é custoso.

**Mitigação**:
- Use ORM direto para listas simples
- Implemente queries especializadas (TicketListDTO com `select_related`)
- Cache em memória para dados imutáveis

---

## 10. Conclusão Arquitetural

A arquitetura hexagonal do TechSupport Manager oferece:

✅ **Testabilidade Superior**: Core testável sem banco, Adapters com mocks  
✅ **Manutenibilidade**: Domínios organizados por slice, mudanças localizadas  
✅ **Escalabilidade**: Desacoplamento permite crescer sem refatoração massiva  
✅ **Agnósticismo Técnico**: Trocar Django por FastAPI, Postgres por MongoDB é viável  

A implementação é **pragmática**, não dogmática: simplificar onde apropriado (inventário direto em ORM), investir em abstração onde necessário (tickets com SLA complexo).

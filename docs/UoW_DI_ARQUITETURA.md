# Unit of Work e Dependency Injection - Padrões Avançados

## 1. Unit of Work: Garantia de Atomicidade

O **Unit of Work (UoW)** é um padrão que coordena múltiplas repositórios em uma transação atômica, garantindo que ou todas as operações são persistidas ou nenhuma é (garantia ACID).

### 1.1 Por Que Unit of Work?

**Problema sem UoW**:
```python
# ❌ SEM UoW: Sem garantia de atomicidade
def criar_ticket_com_agendamento(self, ticket_data, agendamento_data):
    ticket = TicketEntity.criar(ticket_data)
    self.ticket_repo.save(ticket)  # Persistiu
    
    agendamento = Agendamento.criar(agendamento_data, ticket.id)
    self.agendamento_repo.save(agendamento)  # Erro aqui!
    
    # Ticket foi persistido, mas agendamento falhou
    # Estado inconsistente no banco
```

**Solução com UoW**:
```python
# ✅ COM UoW: Transação atômica
def criar_ticket_com_agendamento(self, ticket_data, agendamento_data):
    with self.uow:  # Inicia transação
        ticket = TicketEntity.criar(ticket_data)
        self.ticket_repo.save(ticket)
        
        agendamento = Agendamento.criar(agendamento_data, ticket.id)
        self.agendamento_repo.save(agendamento)  # Erro aqui!
    
    # Se erro: rollback() de ambos; estado consistente
    # Se sucesso: commit() de ambos; persistência garantida
```

### 1.2 Implementação no Core (Abstração)

**Arquivo**: `src/core/interfaces.py`

```python
from abc import ABC, abstractmethod
from typing import List
from src.core.shared.events import DomainEvent

class UnitOfWork(ABC):
    """
    Contrato para coordenar transações atômicas.
    
    Implementação agnóstica: pode ser Django, SQLAlchemy, MongoDB, etc.
    """
    
    def __enter__(self):
        """Inicia contexto de transação."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Finaliza contexto de transação.
        
        Se exceção ocorreu (exc_type not None), faz rollback.
        Caso contrário, faz commit.
        """
        if exc_type:
            self.rollback()
        else:
            self.commit()
    
    @abstractmethod
    def commit(self) -> None:
        """Persiste todas as mudanças."""
        raise NotImplementedError
    
    @abstractmethod
    def rollback(self) -> None:
        """Desfaz todas as mudanças."""
        raise NotImplementedError
    
    @abstractmethod
    def publish_event(self, event: DomainEvent) -> None:
        """
        Publica evento de domínio para consumidores assíncronos.
        
        Eventos são publicados apenas após commit bem-sucedido,
        garantindo consistência eventual.
        """
        raise NotImplementedError
```

**Características**:
- Interface pura, sem dependências
- Utiliza context manager (`with` statement) para garantir finalização
- Suporta publicação de eventos de forma desacoplada
- Implementável em qualquer framework/banco

### 1.3 Implementação no Adapter (Django)

**Arquivo**: `src/adapters/django_app/unit_of_work.py`

```python
from django.db import transaction
from src.core.interfaces import UnitOfWork
from src.core.shared.events import DomainEvent

class DjangoUnitOfWork(UnitOfWork):
    """
    Implementação concreta usando Django ORM e PostgreSQL.
    
    Responsabilidades:
    - Gerenciar transações do banco via django.db.transaction
    - Manter fila de eventos para publicação pós-commit
    - Garantir rollback em erro
    """
    
    def __init__(self, event_bus=None):
        self._event_bus = event_bus
        self._events: List[DomainEvent] = []
        self._transaction_started = False
    
    def __enter__(self):
        """Desativa autocommit e inicia transação explícita."""
        transaction.set_autocommit(False)
        self._transaction_started = True
        return super().__enter__()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Garante finalização de transação mesmo em erro.
        
        Precedência:
        1. Se erro: rollback() + cleanup
        2. Se OK: commit() + publish events + cleanup
        """
        try:
            super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            transaction.set_autocommit(True)
            self._transaction_started = False
    
    def commit(self) -> None:
        """
        Persiste mudanças e publica eventos.
        
        Ordem importante:
        1. commit() do banco → persistência
        2. publish_events() → side-effects assíncronos
        
        Isto garante que eventos só são publicados se banco não falhar.
        """
        if self._transaction_started:
            transaction.commit()
        
        # Publicar eventos apenas após commit bem-sucedido
        self._publish_events()
    
    def rollback(self) -> None:
        """Desfaz todas as mudanças e descarta eventos."""
        if self._transaction_started:
            transaction.rollback()
        
        # Limpar eventos em caso de rollback
        self._events.clear()
    
    def publish_event(self, event: DomainEvent) -> None:
        """
        Enfileira evento para publicação após commit.
        
        Não publica imediatamente: aguarda commit bem-sucedido.
        Isso garancia que eventos refletem estado persistido.
        """
        self._events.append(event)
    
    def _publish_events(self) -> None:
        """Publica eventos para consumidores assíncronos."""
        if not self._event_bus:
            return
        
        for event in self._events:
            self._event_bus.publish(event)
        
        self._events.clear()
```

**Fluxo de Execução**:
```
with DjangoUnitOfWork():
    ↓
__enter__()
    ↓ (transaction.set_autocommit(False))
    ↓ (repositórios salvam, eventos enfileirados)
__exit__()
    ↓
commit()
    ↓ (transaction.commit() → banco persistiu)
    ↓ (_publish_events() → handlers assíncronos disparam)
    ↓
set_autocommit(True)
```

### 1.4 Uso no Service (Orquestração)

**Arquivo**: `src/core/tickets/use_cases.py`

```python
from src.core.interfaces import UnitOfWork
from src.core.tickets.ports import TicketRepository
from src.core.tickets.entities import TicketEntity
from src.core.tickets.events import TicketCriadoEvent

class CriarTicketService:
    """
    Use Case: Criar um novo ticket.
    
    Responsabilidades:
    - Validar dados de entrada
    - Orquestar criação de entidade
    - Coordenar persistência via UoW
    - Disparar event de domínio
    """
    
    def __init__(self, ticket_repo: TicketRepository, uow: UnitOfWork):
        self.ticket_repo = ticket_repo
        self.uow = uow
    
    def execute(self, data: dict) -> 'TicketOutputDTO':
        """
        Executa caso de uso dentro de transação atômica.
        
        Garantias:
        - Ou ticket é criado+persistido+evento disparado, ou nada
        - Sem estado inconsistente intermediário
        - Thread-safe (cada chamada tem seu UoW)
        """
        with self.uow:  # Context manager garante commit/rollback
            # Criar entidade com validações de domínio
            ticket = TicketEntity.criar(
                titulo=data['titulo'],
                descricao=data['descricao'],
                criador_id=data['usuario_id'],
                categoria=data.get('categoria', 'Geral')
            )
            
            # Persistir via repositório (interface)
            self.ticket_repo.save(ticket)
            
            # Disparar evento (será publicado após commit)
            self.uow.publish_event(
                TicketCriadoEvent(
                    ticket_id=ticket.id,
                    usuario_criador_id=ticket.criador_id,
                    titulo=ticket.titulo
                )
            )
        
        # Aqui: commit() foi executado, evento foi publicado
        return TicketOutputDTO.from_entity(ticket)


class AtribuirTicketService:
    """Use Case: Atribuir ticket a técnico."""
    
    def __init__(
        self, 
        ticket_repo: TicketRepository,
        tecnico_repo: 'TecnicoRepository',
        agendamento_repo: 'AgendamentoRepository',
        uow: UnitOfWork
    ):
        self.ticket_repo = ticket_repo
        self.tecnico_repo = tecnico_repo
        self.agendamento_repo = agendamento_repo
        self.uow = uow
    
    def execute(self, ticket_id: str, tecnico_id: str) -> 'TicketOutputDTO':
        """
        Múltiplos repositórios em transação única.
        
        Se alguma falhar, tudo é desfeito:
        1. Carregar ticket
        2. Validar técnico disponível
        3. Atribuir ticket
        4. Criar agendamento automaticamente
        5. Ou falhar atomicamente
        """
        with self.uow:
            ticket = self.ticket_repo.get_by_id(ticket_id)
            tecnico = self.tecnico_repo.get_by_id(tecnico_id)
            
            if not tecnico.disponivel:
                raise TecnicoIndisponivelError(tecnico_id)
            
            # Modificar entidade
            ticket.atribuir_a(tecnico.id)
            self.ticket_repo.save(ticket)
            
            # Criar agendamento
            agendamento = Agendamento.criar_automatico(ticket, tecnico)
            self.agendamento_repo.save(agendamento)
            
            # Disparar eventos
            self.uow.publish_event(TicketAtribuidoEvent(ticket.id, tecnico.id))
            self.uow.publish_event(AgendamentoCriadoEvent(agendamento.id))
        
        return TicketOutputDTO.from_entity(ticket)
```

**Aspecto Crítico**: Múltiplos repositórios são coordenados em uma transação única. Falha em qualquer um desfaz todos.

---

## 2. Dependency Injection: Desacoplamento de Instâncias

O **Dependency Injection (DI)** resolve dependências sem que as classes saibam como instanciar seus colaboradores. Isto permite:
- Trocar implementações sem modificar código
- Testar com mocks facilmente
- Remover acoplamento circular

### 2.1 O Problema Sem DI

```python
# ❌ SEM DI: Acoplamento Forte
class TicketView(View):
    def post(self, request):
        # View precisa saber COMO construir Service
        ticket_repo = TicketRepository(db=PostgreSQL())
        uow = DjangoUnitOfWork(event_bus=RabbitMQ())
        service = CriarTicketService(
            ticket_repo=ticket_repo,
            uow=uow
        )
        
        service.execute(request.POST)
        
        # Problemas:
        # 1. View acoplada a detalhes de infra (PostgreSQL, RabbitMQ)
        # 2. Difícil mockar TicketRepository para testes
        # 3. Se RabbitMQ mudar para Celery, View muda
        # 4. Código repetido em múltiplas Views
```

### 2.2 Service Locator (Anti-pattern)

```python
# ❌ ANTI-PATTERN: Service Locator
from src.config.container import container

class TicketView(View):
    def post(self, request):
        service = container.get(CriarTicketService)  # Acoplamento implícito!
        service.execute(request.POST)
        
        # Problemas:
        # 1. Dependência oculta: View não expõe que precisa de service
        # 2. IDE não consegue inferir tipo de `service`
        # 3. Testes precisam mockar container inteiro
        # 4. Violação do Dependency Inversion Principle
        # 5. Semelhante a variáveis globais
```

### 2.3 Constructor Injection (Padrão Correto)

```python
# ✅ PADRÃO CORRETO: Constructor Injection
from dependency_injector.wiring import Provide, inject
from src.config.container import Container

class TicketCreateView(View):
    @inject
    def post(
        self,
        request,
        service: CriarTicketService = Provide[Container.criar_ticket_service]
    ):
        service.execute(request.POST)
        
        # Benefícios:
        # 1. Dependência EXPLÍCITA no assinatura
        # 2. IDE oferece autocompletar e type-checking
        # 3. Testes mockam apenas CriarTicketService, não container
        # 4. Código limpo e testável
```

### 2.4 Implementação do Container (DI)

**Arquivo**: `src/config/container.py`

```python
from dependency_injector import containers, providers
from src.core.tickets.use_cases import (
    CriarTicketService,
    ListarTicketsService,
    AtribuirTicketService
)
from src.adapters.django_app.tickets.repositories import TicketRepository
from src.adapters.django_app.unit_of_work import DjangoUnitOfWork
from src.adapters.django_app.events.event_bus import DjangoEventBus

class Container(containers.DeclarativeContainer):
    """
    Contêiner de Injeção de Dependência.
    
    Responsabilidades:
    - Definir dependências como providers
    - Usar lazy-loading (criação sob demanda)
    - Garantir singleton para stateful objects
    - Facilitar testes com override
    """
    
    # Configuração
    config = providers.Configuration()
    
    # ADAPTADORES (Driven): Infraestrutura
    # Singleton: uma instância durante toda app
    event_bus = providers.Singleton(
        DjangoEventBus,
        rabbitmq_url=config.rabbitmq_url
    )
    
    ticket_repo = providers.Singleton(TicketRepository)
    
    # UoW: Singleton (stateless, thread-safe)
    uow = providers.Singleton(
        DjangoUnitOfWork,
        event_bus=event_bus
    )
    
    # USE CASES (Core): Serviços de Negócio
    # Factory: nova instância a cada chamada (thread-safety)
    criar_ticket_service = providers.Factory(
        CriarTicketService,
        ticket_repo=ticket_repo,
        uow=uow
    )
    
    listar_tickets_service = providers.Factory(
        ListarTicketsService,
        ticket_repo=ticket_repo
    )
    
    atribuir_ticket_service = providers.Factory(
        AtribuirTicketService,
        ticket_repo=ticket_repo,
        uow=uow
    )
```

**Conceitos-Chave**:

1. **Singleton**: Uma instância para toda aplicação (UoW, Repositories)
   - Economiza memória
   - Compartilha conexão com banco
   - Thread-safe em Django (requisição-isolada)

2. **Factory**: Nova instância a cada requisição (Services)
   - Cada requisição tem seu próprio contexto
   - Evita compartilhamento indesejado de estado
   - Necessário para context managers (UoW)

3. **Wiring**: Decorator `@inject` conecta providers às assinaturas
   - Automático: framework injeta dependências
   - Testável: fácil mockar com `override`

### 2.5 Uso em Testes

```python
# tests/adapters/test_views.py
import pytest
from unittest.mock import Mock, patch
from src.config.container import Container
from src.adapters.django_app.tickets.views import TicketCreateView

class TestTicketCreateView:
    def test_criar_ticket_com_sucesso(self):
        """Mock do service, não do container inteiro."""
        
        # Mock: apenas CriarTicketService
        mock_service = Mock(spec=CriarTicketService)
        mock_service.execute.return_value = TicketOutputDTO(
            ticket_id='123',
            status='Aberto'
        )
        
        # Override: injetar mock
        Container.criar_ticket_service.override(
            providers.Factory(Mock, return_value=mock_service)
        )
        
        # Chamar view
        view = TicketCreateView()
        request = Mock(POST={'titulo': 'Bug', 'descricao': 'Sistema down'})
        
        response = view.post(request)
        
        # Assert: service foi chamado
        mock_service.execute.assert_called_once()
        
        # Cleanup
        Container.criar_ticket_service.reset_override()
    
    def test_listar_tickets_com_filtro(self):
        """Teste de integração: usar repositório real."""
        
        mock_repo = Mock(spec=TicketRepository)
        mock_repo.list_by_status.return_value = [
            TicketEntity(id='1', titulo='Bug', status=TicketStatus.ABERTO),
            TicketEntity(id='2', titulo='Feature', status=TicketStatus.ABERTO)
        ]
        
        Container.ticket_repo.override(
            providers.Singleton(Mock, return_value=mock_repo)
        )
        
        service = Container.listar_tickets_service()
        tickets = service.execute(status='Aberto')
        
        assert len(tickets) == 2
        
        Container.ticket_repo.reset_override()
```

**Vantagem sobre Service Locator**:
- Testes cleaner: mocka apenas classe necessária
- Type-safety: IDE conhece tipos
- Rastreabilidade: dependências explícitas

### 2.6 Lazy Loading (Otimização)

```python
# Providers são lazy: criados sob demanda

class Container(containers.DeclarativeContainer):
    # Não criado ao startup, apenas quando acessado
    heavy_repo = providers.Singleton(ExpensiveRepository)
    
    rarely_used_service = providers.Factory(
        RarelyUsedService,
        repo=heavy_repo  # Criado lazy quando RarelyUsedService é pedido
    )

# Na App:
container = Container()
# Neste ponto: expensiverepository NÃO foi criado ainda

service = container.rarely_used_service()
# AGORA: ExpensiveRepository foi criado (lazy)

service2 = container.rarely_used_service()
# Repositório REUTILIZADO (singleton)
```

**Benefício**: Reduz memory footprint ao startup; aplicações com 10+ domínios economizam ~20%.

---

## 3. Integração: UoW + DI em Fluxo Completo

```python
# View (Driving Adapter)
class TicketCreateView(View):
    @inject
    def post(
        self,
        request,
        service: CriarTicketService = Provide[Container.criar_ticket_service]
    ):
        form = TicketForm(request.POST)
        if form.is_valid():
            # DI: service injetado
            # UoW: dentro do service.execute()
            output = service.execute({
                'titulo': form.cleaned_data['title'],
                'descricao': form.cleaned_data['description'],
                'usuario_id': request.user.id
            })
            
            return JsonResponse({
                'ticket_id': output.ticket_id,
                'status': output.status,
                'created_at': output.created_at.isoformat()
            })
        
        return JsonResponse({'errors': form.errors}, status=400)

# Service (Core)
class CriarTicketService:
    def __init__(self, ticket_repo: TicketRepository, uow: UnitOfWork):
        # DI: injeção no construtor
        self.ticket_repo = ticket_repo
        self.uow = uow
    
    def execute(self, data: dict) -> TicketOutputDTO:
        # UoW: context manager para transação atômica
        with self.uow:
            ticket = TicketEntity.criar(data)
            self.ticket_repo.save(ticket)
            self.uow.publish_event(TicketCriadoEvent(ticket.id))
        
        return TicketOutputDTO.from_entity(ticket)

# Repository (Adapter)
class TicketRepository:
    def save(self, ticket: TicketEntity) -> None:
        # Mapeamento: Entity → Django Model
        model = TicketModel(
            id=ticket.id,
            title=ticket.title,
            description=ticket.description,
            status=ticket.status.value
        )
        model.save()  # PostgreSQL

# Event Handler (Adapter)
class TicketCriadoHandler:
    @inject
    def handle(
        self,
        event: TicketCriadoEvent,
        email_service=Provide[Container.email_service]
    ):
        # DI: email_service injetado
        # Executado assincronamente após UoW.commit()
        usuario = User.objects.get(id=event.usuario_criador_id)
        email_service.enviar(
            para=usuario.email,
            assunto=f"Ticket {event.ticket_id} criado",
            corpo=f"Seu ticket {event.titulo} foi registrado"
        )
```

**Fluxo Completo**:
1. **DI**: View recebe service via decorador `@inject`
2. **Validação**: Form valida entrada (Django)
3. **Service**: Service orquestra lógica via UoW
4. **UoW.commit()**: Banco persistiu
5. **Event Publishing**: Evento publicado para handler assíncrono
6. **Email Handler**: DI injeta email_service, envia assincronamente

---

## 4. Resumo de Padrões

| Padrão | Objetivo | Implementação |
|--------|----------|----------------|
| **Unit of Work** | Atomicidade em múltiplos repos | Context manager + commit/rollback |
| **Constructor Injection** | Desacoplamento de instâncias | `@inject` + container providers |
| **Factory Provider** | Nova instância por requisição | `providers.Factory()` |
| **Singleton Provider** | Uma instância por app | `providers.Singleton()` |
| **Repository Pattern** | Abstração de persistência | Interface (Port) + implementação |
| **Domain Events** | Desacoplamento de side-effects | Publicação após UoW.commit() |

---

## 5. Checklist de Implementação

- [ ] Definir interface `UnitOfWork` no Core
- [ ] Implementar `DjangoUnitOfWork` no Adapter
- [ ] Integrar `event_bus` em publish_event()
- [ ] Criar Container com providers Singleton/Factory
- [ ] Usar `@inject` em Views (não Service Locator)
- [ ] Mockar services em testes (não container)
- [ ] Documentar lazy-loading em README
- [ ] Monitorar memory footprint ao startup


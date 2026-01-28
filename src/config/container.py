"""
Dependency Injection Container.

Configura e gerencia todas as dependências da aplicação.
Usa dependency-injector para lazy-loading e injeção automática.

Benefícios:
- Dependências explícitas
- Testabilidade (fácil mockar)
- Lazy-loading (criado sob demanda)
- Thread-safe

Padrões:
- Singleton: Uma instância para toda app (repositories)
- Factory: Nova instância por chamada (services, UoW)
- Provider: Configuração lazy

Escalabilidade:
- Fácil adicionar novos domínios
- Suporta múltiplas implementações por interface
- Prepared para diferentes ambientes (dev, prod, test)
"""

from dependency_injector import containers, providers
from typing import Optional


class Container(containers.DeclarativeContainer):
    """
    Container principal de Dependency Injection.
    
    Organização:
    - Configuration: Variáveis de ambiente/settings
    - Infrastructure: Conexões, clients
    - Repositories: Persistência
    - Unit of Work: Transações
    - Services: Use Cases
    
    Example:
        from src.config.container import Container
        
        container = Container()
        container.config.from_dict({'debug': True})
        
        # Usar service
        service = container.criar_ticket_service()
        result = service.execute(input_dto)
    """
    
    # =========================================================================
    # Configuration
    # =========================================================================
    
    config = providers.Configuration()
    
    # =========================================================================
    # Infrastructure (Lazy - criado sob demanda)
    # =========================================================================
    
    # Event Publisher placeholder (será implementado na Etapa 4)
    event_publisher = providers.Singleton(
        lambda: None  # Será: CeleryEventPublisher
    )
    
    # Event Store
    event_store = providers.Singleton(
        # Lazy import para evitar circular imports
        providers.Factory(
            lambda: __import__(
                'src.adapters.django_app.tickets.repositories',
                fromlist=['DjangoEventStore']
            ).DjangoEventStore()
        )
    )
    
    # =========================================================================
    # Repositories (Singleton - uma instância por app)
    # =========================================================================
    
    ticket_repository = providers.Singleton(
        # Lazy import
        providers.Factory(
            lambda: __import__(
                'src.adapters.django_app.tickets.repositories',
                fromlist=['DjangoTicketRepository']
            ).DjangoTicketRepository()
        )
    )
    
    # =========================================================================
    # Unit of Work (Factory - nova instância por operação)
    # =========================================================================
    
    unit_of_work = providers.Factory(
        # Lazy import
        lambda event_publisher, event_store: __import__(
            'src.adapters.django_app.shared.unit_of_work',
            fromlist=['DjangoUnitOfWork']
        ).DjangoUnitOfWork(
            event_publisher=event_publisher,
            event_store=event_store,
        ),
        event_publisher=event_publisher,
        event_store=event_store,
    )
    
    # =========================================================================
    # Services / Use Cases (Factory - nova instância por chamada)
    # =========================================================================
    
    # Criar Ticket
    criar_ticket_service = providers.Factory(
        lambda ticket_repo, uow: __import__(
            'src.core.tickets.use_cases',
            fromlist=['CriarTicketService']
        ).CriarTicketService(
            ticket_repo=ticket_repo,
            uow=uow,
        ),
        ticket_repo=ticket_repository,
        uow=unit_of_work,
    )
    
    # Atribuir Ticket
    atribuir_ticket_service = providers.Factory(
        lambda ticket_repo, uow: __import__(
            'src.core.tickets.use_cases',
            fromlist=['AtribuirTicketService']
        ).AtribuirTicketService(
            ticket_repo=ticket_repo,
            uow=uow,
        ),
        ticket_repo=ticket_repository,
        uow=unit_of_work,
    )
    
    # Fechar Ticket
    fechar_ticket_service = providers.Factory(
        lambda ticket_repo, uow: __import__(
            'src.core.tickets.use_cases',
            fromlist=['FecharTicketService']
        ).FecharTicketService(
            ticket_repo=ticket_repo,
            uow=uow,
        ),
        ticket_repo=ticket_repository,
        uow=unit_of_work,
    )
    
    # Reabrir Ticket
    reabrir_ticket_service = providers.Factory(
        lambda ticket_repo, uow: __import__(
            'src.core.tickets.use_cases',
            fromlist=['ReabrirTicketService']
        ).ReabrirTicketService(
            ticket_repo=ticket_repo,
            uow=uow,
        ),
        ticket_repo=ticket_repository,
        uow=unit_of_work,
    )
    
    # Listar Tickets (sem UoW - leitura)
    listar_tickets_service = providers.Factory(
        lambda ticket_repo: __import__(
            'src.core.tickets.use_cases',
            fromlist=['ListarTicketsService']
        ).ListarTicketsService(
            ticket_repo=ticket_repo,
        ),
        ticket_repo=ticket_repository,
    )
    
    # Obter Ticket
    obter_ticket_service = providers.Factory(
        lambda ticket_repo: __import__(
            'src.core.tickets.use_cases',
            fromlist=['ObterTicketService']
        ).ObterTicketService(
            ticket_repo=ticket_repo,
        ),
        ticket_repo=ticket_repository,
    )
    
    # Alterar Prioridade
    alterar_prioridade_service = providers.Factory(
        lambda ticket_repo, uow: __import__(
            'src.core.tickets.use_cases',
            fromlist=['AlterarPrioridadeService']
        ).AlterarPrioridadeService(
            ticket_repo=ticket_repo,
            uow=uow,
        ),
        ticket_repo=ticket_repository,
        uow=unit_of_work,
    )
    
    # Contar Tickets
    contar_tickets_service = providers.Factory(
        lambda ticket_repo: __import__(
            'src.core.tickets.use_cases',
            fromlist=['ContarTicketsService']
        ).ContarTicketsService(
            ticket_repo=ticket_repo,
        ),
        ticket_repo=ticket_repository,
    )


# =============================================================================
# Container Global (Singleton)
# =============================================================================

_container: Optional[Container] = None


def get_container() -> Container:
    """
    Retorna instância global do container.
    
    Cria se não existir (lazy initialization).
    
    Returns:
        Container configurado
    """
    global _container
    
    if _container is None:
        _container = Container()
    
    return _container


def reset_container() -> None:
    """
    Reset do container (para testes).
    
    Permite criar novo container limpo.
    """
    global _container
    _container = None


# =============================================================================
# Testing Container
# =============================================================================

class TestingContainer(containers.DeclarativeContainer):
    """
    Container para testes com mocks.
    
    Usa InMemory implementations para testes rápidos.
    
    Example:
        container = TestingContainer()
        container.ticket_repository.override(
            providers.Singleton(InMemoryTicketRepository)
        )
    """
    
    config = providers.Configuration()
    
    # InMemory implementations
    ticket_repository = providers.Singleton(
        lambda: __import__(
            'src.core.tickets.ports',
            fromlist=['InMemoryTicketRepository']
        ).InMemoryTicketRepository()
    )
    
    unit_of_work = providers.Factory(
        lambda: __import__(
            'src.adapters.django_app.shared.unit_of_work',
            fromlist=['InMemoryUnitOfWork']
        ).InMemoryUnitOfWork()
    )
    
    # Services com InMemory dependencies
    criar_ticket_service = providers.Factory(
        lambda ticket_repo, uow: __import__(
            'src.core.tickets.use_cases',
            fromlist=['CriarTicketService']
        ).CriarTicketService(
            ticket_repo=ticket_repo,
            uow=uow,
        ),
        ticket_repo=ticket_repository,
        uow=unit_of_work,
    )

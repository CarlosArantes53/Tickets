"""
Dependency Injection Container - Implementação Completa.

Usa dependency-injector para gerenciar todas as dependências da aplicação
de forma declarativa, testável e thread-safe.

Benefícios:
- Inversão de Controle (IoC) completa
- Lazy loading de dependências
- Fácil substituição para testes
- Thread-safe por padrão
- Wiring automático com decorators

Padrões de Vida:
- Singleton: Uma instância para toda app (repositories, connections)
- Factory: Nova instância por chamada (services, UoW)
- Resource: Gerenciado com init/shutdown (connections)

Estrutura:
- CoreContainer: Entidades e interfaces do Core
- InfrastructureContainer: Adapters e conexões
- ServiceContainer: Use Cases / Application Services
- Container: Aggregador principal
"""

from dependency_injector import containers, providers
from dependency_injector.wiring import Provide, inject
from typing import Optional, Type, Callable, Any
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions (definido primeiro para uso nos containers)
# =============================================================================

def _import_class(module_path: str, class_name: str) -> Type:
    """
    Importa classe dinamicamente.
    
    Usado para lazy loading e evitar circular imports.
    """
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


# =============================================================================
# Core Container - Entidades e Interfaces Puras
# =============================================================================

class CoreContainer(containers.DeclarativeContainer):
    """
    Container para componentes do Core Domain.
    
    Contém:
    - Configurações de domínio
    - Factories de entidades (se necessário)
    """
    
    config = providers.Configuration()


# =============================================================================
# Infrastructure Container - Adapters e Conexões
# =============================================================================

class InfrastructureContainer(containers.DeclarativeContainer):
    """
    Container para componentes de infraestrutura.
    
    Contém:
    - Repositories (Django ORM)
    - Event Store
    - Event Publisher
    - Database connections
    """
    
    config = providers.Configuration()
    
    # -------------------------------------------------------------------------
    # Repositories
    # -------------------------------------------------------------------------
    
    @staticmethod
    def _create_ticket_repository():
        """Factory para criar ticket repository."""
        from src.adapters.django_app.tickets.repositories import DjangoTicketRepository
        return DjangoTicketRepository()
    
    ticket_repository = providers.Singleton(_create_ticket_repository)
    
    # -------------------------------------------------------------------------
    # Event Infrastructure
    # -------------------------------------------------------------------------
    
    @staticmethod
    def _create_event_store():
        """Factory para criar event store."""
        from src.adapters.django_app.tickets.repositories import DjangoEventStore
        return DjangoEventStore()
    
    event_store = providers.Singleton(_create_event_store)
    
    @staticmethod
    def _create_event_publisher():
        """Factory para criar event publisher."""
        from src.adapters.django_app.events.publishers import LoggingEventPublisher
        return LoggingEventPublisher()
    
    event_publisher = providers.Singleton(_create_event_publisher)
    
    # -------------------------------------------------------------------------
    # Unit of Work Factory
    # -------------------------------------------------------------------------
    
    @staticmethod
    def _create_unit_of_work(event_publisher, event_store):
        """Factory para criar Unit of Work."""
        from src.adapters.django_app.shared.unit_of_work import DjangoUnitOfWork
        return DjangoUnitOfWork(
            event_publisher=event_publisher,
            event_store=event_store,
        )
    
    unit_of_work_factory = providers.Factory(
        _create_unit_of_work,
        event_publisher=event_publisher,
        event_store=event_store,
    )


# =============================================================================
# Service Container - Use Cases / Application Services
# =============================================================================

class ServiceContainer(containers.DeclarativeContainer):
    """
    Container para Use Cases / Application Services.
    
    Cada service é uma Factory que cria nova instância por chamada,
    injetando as dependências necessárias.
    """
    
    config = providers.Configuration()
    infrastructure = providers.DependenciesContainer()
    
    # -------------------------------------------------------------------------
    # Ticket Services - Write Operations
    # -------------------------------------------------------------------------
    
    @staticmethod
    def _create_criar_ticket_service(ticket_repo, uow):
        """Factory para CriarTicketService."""
        from src.core.tickets.use_cases import CriarTicketService
        return CriarTicketService(ticket_repo=ticket_repo, uow=uow)
    
    criar_ticket_service = providers.Factory(
        _create_criar_ticket_service,
        ticket_repo=infrastructure.ticket_repository,
        uow=infrastructure.unit_of_work_factory,
    )
    
    @staticmethod
    def _create_atribuir_ticket_service(ticket_repo, uow):
        """Factory para AtribuirTicketService."""
        from src.core.tickets.use_cases import AtribuirTicketService
        return AtribuirTicketService(ticket_repo=ticket_repo, uow=uow)
    
    atribuir_ticket_service = providers.Factory(
        _create_atribuir_ticket_service,
        ticket_repo=infrastructure.ticket_repository,
        uow=infrastructure.unit_of_work_factory,
    )
    
    @staticmethod
    def _create_fechar_ticket_service(ticket_repo, uow):
        """Factory para FecharTicketService."""
        from src.core.tickets.use_cases import FecharTicketService
        return FecharTicketService(ticket_repo=ticket_repo, uow=uow)
    
    fechar_ticket_service = providers.Factory(
        _create_fechar_ticket_service,
        ticket_repo=infrastructure.ticket_repository,
        uow=infrastructure.unit_of_work_factory,
    )
    
    @staticmethod
    def _create_reabrir_ticket_service(ticket_repo, uow):
        """Factory para ReabrirTicketService."""
        from src.core.tickets.use_cases import ReabrirTicketService
        return ReabrirTicketService(ticket_repo=ticket_repo, uow=uow)
    
    reabrir_ticket_service = providers.Factory(
        _create_reabrir_ticket_service,
        ticket_repo=infrastructure.ticket_repository,
        uow=infrastructure.unit_of_work_factory,
    )
    
    @staticmethod
    def _create_alterar_prioridade_service(ticket_repo, uow):
        """Factory para AlterarPrioridadeService."""
        from src.core.tickets.use_cases import AlterarPrioridadeService
        return AlterarPrioridadeService(ticket_repo=ticket_repo, uow=uow)
    
    alterar_prioridade_service = providers.Factory(
        _create_alterar_prioridade_service,
        ticket_repo=infrastructure.ticket_repository,
        uow=infrastructure.unit_of_work_factory,
    )
    
    # -------------------------------------------------------------------------
    # Ticket Services - Read Operations (sem UoW)
    # -------------------------------------------------------------------------
    
    @staticmethod
    def _create_listar_tickets_service(ticket_repo):
        """Factory para ListarTicketsService."""
        from src.core.tickets.use_cases import ListarTicketsService
        return ListarTicketsService(ticket_repo=ticket_repo)
    
    listar_tickets_service = providers.Factory(
        _create_listar_tickets_service,
        ticket_repo=infrastructure.ticket_repository,
    )
    
    @staticmethod
    def _create_obter_ticket_service(ticket_repo):
        """Factory para ObterTicketService."""
        from src.core.tickets.use_cases import ObterTicketService
        return ObterTicketService(ticket_repo=ticket_repo)
    
    obter_ticket_service = providers.Factory(
        _create_obter_ticket_service,
        ticket_repo=infrastructure.ticket_repository,
    )
    
    @staticmethod
    def _create_contar_tickets_service(ticket_repo):
        """Factory para ContarTicketsService."""
        from src.core.tickets.use_cases import ContarTicketsService
        return ContarTicketsService(ticket_repo=ticket_repo)
    
    contar_tickets_service = providers.Factory(
        _create_contar_tickets_service,
        ticket_repo=infrastructure.ticket_repository,
    )


# =============================================================================
# Main Container - Aggregador
# =============================================================================

class Container(containers.DeclarativeContainer):
    """
    Container principal que agrega todos os sub-containers.
    
    Este é o ponto de entrada para Dependency Injection em toda a aplicação.
    
    Usage:
        from src.config.container import get_container
        
        container = get_container()
        
        # Obter service
        service = container.services.criar_ticket_service()
        
        # Ou com wiring e @inject decorator
        @inject
        def my_view(
            service: CriarTicketService = Provide[Container.services.criar_ticket_service]
        ):
            ...
    """
    
    # Configuration
    config = providers.Configuration()
    
    # Sub-containers
    core = providers.Container(
        CoreContainer,
        config=config,
    )
    
    infrastructure = providers.Container(
        InfrastructureContainer,
        config=config,
    )
    
    services = providers.Container(
        ServiceContainer,
        config=config,
        infrastructure=infrastructure,
    )


# =============================================================================
# Global Container Instance
# =============================================================================

_container: Optional[Container] = None


def get_container() -> Container:
    """
    Retorna instância global do container.
    
    Cria e configura se não existir (lazy initialization).
    Thread-safe por padrão do dependency-injector.
    
    Returns:
        Container configurado
    """
    global _container
    
    if _container is None:
        _container = Container()
        _configure_container(_container)
    
    return _container


def _configure_container(container: Container) -> None:
    """
    Configura container com settings do Django.
    """
    try:
        from django.conf import settings
        
        container.config.from_dict({
            'debug': getattr(settings, 'DEBUG', True),
            'sla_critica_horas': getattr(settings, 'SLA_HOURS', {}).get('CRITICA', 4),
            'sla_alta_horas': getattr(settings, 'SLA_HOURS', {}).get('ALTA', 24),
            'sla_media_horas': getattr(settings, 'SLA_HOURS', {}).get('MEDIA', 72),
            'sla_baixa_horas': getattr(settings, 'SLA_HOURS', {}).get('BAIXA', 168),
        })
    except Exception as e:
        logger.warning(f"Could not configure container from Django settings: {e}")
        # Configuração padrão
        container.config.from_dict({
            'debug': True,
            'sla_critica_horas': 4,
            'sla_alta_horas': 24,
            'sla_media_horas': 72,
            'sla_baixa_horas': 168,
        })


def reset_container() -> None:
    """
    Reset do container (principalmente para testes).
    
    Permite criar novo container limpo entre testes.
    """
    global _container
    
    if _container is not None:
        _container = None
    
    logger.debug("Container reset")


def wire_container(modules: list = None) -> None:
    """
    Faz wiring do container com módulos especificados.
    
    Permite usar @inject decorator em views e handlers.
    
    Args:
        modules: Lista de módulos para wiring (opcional)
    """
    container = get_container()
    
    default_modules = [
        'src.adapters.django_app.tickets.views',
        'src.adapters.django_app.tickets.api_views',
    ]
    
    target_modules = modules if modules else default_modules
    
    try:
        container.wire(modules=target_modules)
        logger.info(f"Container wired with modules: {target_modules}")
    except Exception as e:
        logger.warning(f"Could not wire container: {e}")


# =============================================================================
# Testing Utilities
# =============================================================================

class TestingContainer(containers.DeclarativeContainer):
    """
    Container para testes com implementações in-memory.
    
    Substitui todos os adapters por versões fake/mock para
    testes rápidos sem dependências externas.
    
    Usage:
        def test_something():
            container = TestingContainer()
            service = container.criar_ticket_service()
            ...
    """
    
    config = providers.Configuration()
    
    # In-memory repository
    @staticmethod
    def _create_in_memory_repository():
        """Factory para criar in-memory repository."""
        from src.core.tickets.ports import InMemoryTicketRepository
        return InMemoryTicketRepository()
    
    ticket_repository = providers.Singleton(_create_in_memory_repository)
    
    # In-memory UoW
    @staticmethod
    def _create_in_memory_uow():
        """Factory para criar in-memory UoW."""
        from src.adapters.django_app.shared.unit_of_work import InMemoryUnitOfWork
        return InMemoryUnitOfWork()
    
    unit_of_work_factory = providers.Factory(_create_in_memory_uow)
    
    # Services com in-memory dependencies
    @staticmethod
    def _create_criar_ticket_service_test(ticket_repo, uow):
        """Factory para CriarTicketService em testes."""
        from src.core.tickets.use_cases import CriarTicketService
        return CriarTicketService(ticket_repo=ticket_repo, uow=uow)
    
    criar_ticket_service = providers.Factory(
        _create_criar_ticket_service_test,
        ticket_repo=ticket_repository,
        uow=unit_of_work_factory,
    )
    
    @staticmethod
    def _create_listar_tickets_service_test(ticket_repo):
        """Factory para ListarTicketsService em testes."""
        from src.core.tickets.use_cases import ListarTicketsService
        return ListarTicketsService(ticket_repo=ticket_repo)
    
    listar_tickets_service = providers.Factory(
        _create_listar_tickets_service_test,
        ticket_repo=ticket_repository,
    )
    
    @staticmethod
    def _create_obter_ticket_service_test(ticket_repo):
        """Factory para ObterTicketService em testes."""
        from src.core.tickets.use_cases import ObterTicketService
        return ObterTicketService(ticket_repo=ticket_repo)
    
    obter_ticket_service = providers.Factory(
        _create_obter_ticket_service_test,
        ticket_repo=ticket_repository,
    )


def create_test_container() -> TestingContainer:
    """
    Cria container configurado para testes.
    
    Returns:
        TestingContainer pronto para uso
    """
    container = TestingContainer()
    container.config.from_dict({
        'debug': True,
        'sla_critica_horas': 4,
        'sla_alta_horas': 24,
        'sla_media_horas': 72,
        'sla_baixa_horas': 168,
    })
    return container

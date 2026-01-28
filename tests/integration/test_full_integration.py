"""
Testes de Integração End-to-End.

Testes que validam o fluxo completo da aplicação:
- Request HTTP → View → Use Case → Repository → Database
- Domain Events → Publisher → Handler

Usa fixtures para setup/teardown de dados de teste.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import List

from src.core.tickets.entities import TicketEntity, TicketStatus, TicketPriority
from src.core.tickets.dtos import (
    CriarTicketInputDTO,
    AtribuirTicketInputDTO,
    FecharTicketInputDTO,
    TicketOutputDTO,
)
from src.core.tickets.events import (
    TicketCriadoEvent,
    TicketAtribuidoEvent,
    TicketFechadoEvent,
)
from src.core.shared.exceptions import (
    ValidationError,
    EntityNotFoundError,
    BusinessRuleViolationError,
)
from src.core.tickets.ports import InMemoryTicketRepository
from src.adapters.django_app.shared.unit_of_work import InMemoryUnitOfWork
from src.adapters.django_app.events.publishers import InMemoryEventPublisher


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def repository():
    """Repositório em memória para testes."""
    return InMemoryTicketRepository()


@pytest.fixture
def event_publisher():
    """Publisher em memória para testes."""
    return InMemoryEventPublisher()


@pytest.fixture
def unit_of_work(event_publisher):
    """UoW em memória para testes."""
    return InMemoryUnitOfWork(event_publisher=event_publisher)


@pytest.fixture
def criar_ticket_service(repository, unit_of_work):
    """Service de criação de tickets."""
    from src.core.tickets.use_cases import CriarTicketService
    return CriarTicketService(ticket_repo=repository, uow=unit_of_work)


@pytest.fixture
def atribuir_ticket_service(repository, unit_of_work):
    """Service de atribuição de tickets."""
    from src.core.tickets.use_cases import AtribuirTicketService
    return AtribuirTicketService(ticket_repo=repository, uow=unit_of_work)


@pytest.fixture
def fechar_ticket_service(repository, unit_of_work):
    """Service de fechamento de tickets."""
    from src.core.tickets.use_cases import FecharTicketService
    return FecharTicketService(ticket_repo=repository, uow=unit_of_work)


@pytest.fixture
def listar_tickets_service(repository):
    """Service de listagem de tickets."""
    from src.core.tickets.use_cases import ListarTicketsService
    return ListarTicketsService(ticket_repo=repository)


@pytest.fixture
def sample_ticket_data():
    """Dados de exemplo para criação de ticket."""
    return {
        'titulo': 'Bug no sistema de login',
        'descricao': 'O sistema não aceita senha com caracteres especiais',
        'criador_id': 'user-123',
        'prioridade': 'ALTA',
        'categoria': 'Autenticação',
    }


# =============================================================================
# Testes de Fluxo Completo
# =============================================================================

class TestTicketLifecycleIntegration:
    """Testes do ciclo de vida completo de um ticket."""
    
    def test_criar_ticket_fluxo_completo(
        self,
        criar_ticket_service,
        repository,
        event_publisher,
        sample_ticket_data
    ):
        """Deve criar ticket e publicar evento."""
        # Arrange
        input_dto = CriarTicketInputDTO(**sample_ticket_data)
        
        # Act
        output = criar_ticket_service.execute(input_dto)
        
        # Assert - Ticket criado
        assert output.id is not None
        assert output.titulo == sample_ticket_data['titulo']
        assert output.status == 'Aberto'
        assert output.prioridade == 'Alta'
        
        # Assert - Persistido no repositório
        saved = repository.get_by_id(output.id)
        assert saved is not None
        assert saved.titulo == sample_ticket_data['titulo']
        
        # Assert - Evento publicado
        events = event_publisher.get_events_by_type('TicketCriadoEvent')
        assert len(events) == 1
        assert events[0].aggregate_id == output.id
    
    def test_ciclo_completo_criar_atribuir_fechar(
        self,
        criar_ticket_service,
        atribuir_ticket_service,
        fechar_ticket_service,
        repository,
        event_publisher,
        sample_ticket_data
    ):
        """Deve completar ciclo: criar → atribuir → fechar."""
        # 1. Criar ticket
        input_criar = CriarTicketInputDTO(**sample_ticket_data)
        ticket = criar_ticket_service.execute(input_criar)
        
        assert ticket.status == 'Aberto'
        
        # 2. Atribuir ticket
        input_atribuir = AtribuirTicketInputDTO(
            ticket_id=ticket.id,
            tecnico_id='tech-456',
            atribuido_por_id='admin-789'
        )
        ticket = atribuir_ticket_service.execute(input_atribuir)
        
        assert ticket.status == 'Em Progresso'
        assert ticket.atribuido_a_id == 'tech-456'
        
        # 3. Fechar ticket
        input_fechar = FecharTicketInputDTO(
            ticket_id=ticket.id,
            fechado_por_id='tech-456',
            resolucao='Problema corrigido na versão 2.0'
        )
        ticket = fechar_ticket_service.execute(input_fechar)
        
        assert ticket.status == 'Fechado'
        
        # Verificar eventos
        assert len(event_publisher.get_events_by_type('TicketCriadoEvent')) == 1
        assert len(event_publisher.get_events_by_type('TicketAtribuidoEvent')) == 1
        assert len(event_publisher.get_events_by_type('TicketFechadoEvent')) == 1
    
    def test_nao_pode_fechar_ticket_nao_atribuido(
        self,
        criar_ticket_service,
        fechar_ticket_service,
        sample_ticket_data
    ):
        """Não deve permitir fechar ticket sem atribuição."""
        # Criar ticket
        input_criar = CriarTicketInputDTO(**sample_ticket_data)
        ticket = criar_ticket_service.execute(input_criar)
        
        # Tentar fechar sem atribuir
        input_fechar = FecharTicketInputDTO(
            ticket_id=ticket.id,
            fechado_por_id='admin'
        )
        
        with pytest.raises(BusinessRuleViolationError, match="atribuído"):
            fechar_ticket_service.execute(input_fechar)
    
    def test_sla_calculado_corretamente_por_prioridade(
        self,
        criar_ticket_service,
    ):
        """Deve calcular SLA baseado na prioridade."""
        prioridades_horas = {
            'CRITICA': 4,
            'ALTA': 24,
            'MEDIA': 72,
            'BAIXA': 168,
        }
        
        for prioridade, horas_esperadas in prioridades_horas.items():
            input_dto = CriarTicketInputDTO(
                titulo=f'Ticket {prioridade}',
                descricao='Descrição com pelo menos 10 caracteres',
                criador_id='user-123',
                prioridade=prioridade,
            )
            
            ticket = criar_ticket_service.execute(input_dto)
            
            # Verificar SLA
            diferenca = ticket.sla_prazo - ticket.criado_em
            horas_calculadas = diferenca.total_seconds() / 3600
            
            assert abs(horas_calculadas - horas_esperadas) < 0.1, \
                f"SLA para {prioridade}: esperado {horas_esperadas}h, obtido {horas_calculadas}h"


class TestValidationIntegration:
    """Testes de validação em fluxos de integração."""
    
    def test_titulo_muito_curto(self, criar_ticket_service):
        """Deve rejeitar título com menos de 3 caracteres."""
        input_dto = CriarTicketInputDTO(
            titulo='AB',
            descricao='Descrição válida com mais de 10 caracteres',
            criador_id='user-123'
        )
        
        with pytest.raises(ValidationError, match="3 caracteres"):
            criar_ticket_service.execute(input_dto)
    
    def test_descricao_muito_curta(self, criar_ticket_service):
        """Deve rejeitar descrição com menos de 10 caracteres."""
        input_dto = CriarTicketInputDTO(
            titulo='Título válido',
            descricao='Curta',
            criador_id='user-123'
        )
        
        with pytest.raises(ValidationError, match="10 caracteres"):
            criar_ticket_service.execute(input_dto)
    
    def test_ticket_inexistente(self, atribuir_ticket_service):
        """Deve retornar erro para ticket não encontrado."""
        input_dto = AtribuirTicketInputDTO(
            ticket_id='ticket-inexistente',
            tecnico_id='tech-456'
        )
        
        with pytest.raises(EntityNotFoundError):
            atribuir_ticket_service.execute(input_dto)


class TestListagemIntegration:
    """Testes de listagem e filtros."""
    
    def test_listar_todos_tickets(
        self,
        criar_ticket_service,
        listar_tickets_service
    ):
        """Deve listar todos os tickets criados."""
        # Criar 3 tickets
        for i in range(3):
            input_dto = CriarTicketInputDTO(
                titulo=f'Ticket {i+1}',
                descricao=f'Descrição do ticket número {i+1}',
                criador_id=f'user-{i}'
            )
            criar_ticket_service.execute(input_dto)
        
        # Listar
        tickets = listar_tickets_service.execute()
        
        assert len(tickets) == 3
    
    def test_listar_por_status(
        self,
        criar_ticket_service,
        atribuir_ticket_service,
        listar_tickets_service
    ):
        """Deve filtrar tickets por status."""
        # Criar 2 tickets
        input1 = CriarTicketInputDTO(
            titulo='Ticket 1',
            descricao='Descrição válida do ticket 1',
            criador_id='user-1'
        )
        ticket1 = criar_ticket_service.execute(input1)
        
        input2 = CriarTicketInputDTO(
            titulo='Ticket 2',
            descricao='Descrição válida do ticket 2',
            criador_id='user-2'
        )
        ticket2 = criar_ticket_service.execute(input2)
        
        # Atribuir ticket 1 (muda para Em Progresso)
        atribuir_input = AtribuirTicketInputDTO(
            ticket_id=ticket1.id,
            tecnico_id='tech-1'
        )
        atribuir_ticket_service.execute(atribuir_input)
        
        # Listar apenas abertos
        abertos = listar_tickets_service.execute(status='Aberto')
        assert len(abertos) == 1
        assert abertos[0].id == ticket2.id
        
        # Listar apenas em progresso
        em_progresso = listar_tickets_service.execute(status='Em Progresso')
        assert len(em_progresso) == 1
        assert em_progresso[0].id == ticket1.id


# =============================================================================
# Testes de Event Handlers
# =============================================================================

class TestEventHandlers:
    """Testes para handlers de eventos."""
    
    def test_handler_ticket_criado(self):
        """Deve processar evento TicketCriadoEvent."""
        from src.adapters.django_app.events.handlers import handle_ticket_criado
        
        event_data = {
            'aggregate_id': 'ticket-123',
            'criador_id': 'user-456',
            'titulo': 'Teste de evento',
            'prioridade': 'ALTA',
        }
        
        # Executar handler (não deve lançar exceção)
        with patch('src.adapters.django_app.events.handlers.notify_support_team') as mock_notify:
            with patch('src.adapters.django_app.events.handlers.record_metric') as mock_metric:
                mock_notify.delay = Mock()
                mock_metric.delay = Mock()
                
                handle_ticket_criado(event_data)
                
                # Verificar que notificação foi chamada (prioridade ALTA)
                mock_notify.delay.assert_called_once()
                mock_metric.delay.assert_called_once()
    
    def test_handler_ticket_atribuido(self):
        """Deve processar evento TicketAtribuidoEvent."""
        from src.adapters.django_app.events.handlers import handle_ticket_atribuido
        
        event_data = {
            'aggregate_id': 'ticket-123',
            'tecnico_id': 'tech-456',
        }
        
        with patch('src.adapters.django_app.events.handlers.notify_user') as mock_notify:
            with patch('src.adapters.django_app.events.handlers.update_technician_workload') as mock_workload:
                mock_notify.delay = Mock()
                mock_workload.delay = Mock()
                
                handle_ticket_atribuido(event_data)
                
                mock_notify.delay.assert_called_once()
                mock_workload.delay.assert_called_once()
    
    def test_dispatcher_roteia_eventos(self):
        """Dispatcher deve rotear eventos para handlers corretos."""
        from src.adapters.django_app.events.handlers import dispatch_domain_event
        
        event_data = {
            'aggregate_id': 'ticket-123',
            'criador_id': 'user-456',
            'titulo': 'Teste',
        }
        
        with patch('src.adapters.django_app.events.handlers.handle_ticket_criado') as mock_handler:
            mock_handler.delay = Mock()
            
            dispatch_domain_event('TicketCriadoEvent', event_data)
            
            mock_handler.delay.assert_called_once_with(event_data)


# =============================================================================
# Testes de Publisher
# =============================================================================

class TestEventPublisher:
    """Testes para publishers de eventos."""
    
    def test_in_memory_publisher_armazena_eventos(self):
        """InMemoryPublisher deve armazenar eventos."""
        from src.adapters.django_app.events.publishers import InMemoryEventPublisher
        
        publisher = InMemoryEventPublisher()
        
        event = TicketCriadoEvent(
            ticket_id='ticket-123',
            criador_id='user-456',
            titulo='Teste'
        )
        
        publisher.publish(event)
        
        assert len(publisher.published_events) == 1
        assert publisher.published_events[0].aggregate_id == 'ticket-123'
    
    def test_in_memory_publisher_filtra_por_tipo(self):
        """InMemoryPublisher deve filtrar eventos por tipo."""
        from src.adapters.django_app.events.publishers import InMemoryEventPublisher
        
        publisher = InMemoryEventPublisher()
        
        event1 = TicketCriadoEvent('ticket-1', 'user-1', 'Titulo 1')
        event2 = TicketAtribuidoEvent('ticket-2', 'tech-1')
        event3 = TicketCriadoEvent('ticket-3', 'user-2', 'Titulo 3')
        
        publisher.publish(event1)
        publisher.publish(event2)
        publisher.publish(event3)
        
        criados = publisher.get_events_by_type('TicketCriadoEvent')
        assert len(criados) == 2
        
        atribuidos = publisher.get_events_by_type('TicketAtribuidoEvent')
        assert len(atribuidos) == 1
    
    def test_logging_publisher_com_handler(self):
        """LoggingPublisher deve executar handlers registrados."""
        from src.adapters.django_app.events.publishers import LoggingEventPublisher
        
        publisher = LoggingEventPublisher()
        
        handler_called = []
        
        def test_handler(event):
            handler_called.append(event)
        
        publisher.register_handler('TicketCriadoEvent', test_handler)
        
        event = TicketCriadoEvent('ticket-123', 'user-456', 'Teste')
        publisher.publish(event)
        
        assert len(handler_called) == 1
        assert handler_called[0].aggregate_id == 'ticket-123'
    
    def test_composite_publisher_propaga_para_todos(self):
        """CompositePublisher deve publicar em todos os publishers."""
        from src.adapters.django_app.events.publishers import (
            CompositeEventPublisher,
            InMemoryEventPublisher
        )
        
        pub1 = InMemoryEventPublisher()
        pub2 = InMemoryEventPublisher()
        
        composite = CompositeEventPublisher([pub1, pub2])
        
        event = TicketCriadoEvent('ticket-123', 'user-456', 'Teste')
        composite.publish(event)
        
        assert len(pub1.published_events) == 1
        assert len(pub2.published_events) == 1


# =============================================================================
# Testes de Unit of Work
# =============================================================================

class TestUnitOfWork:
    """Testes para Unit of Work."""
    
    def test_commit_publica_eventos(self, event_publisher):
        """UoW deve publicar eventos após commit."""
        uow = InMemoryUnitOfWork(event_publisher=event_publisher)
        
        event = TicketCriadoEvent('ticket-123', 'user-456', 'Teste')
        
        with uow:
            uow.publish_event(event)
        
        # Evento publicado após commit (saindo do with)
        assert len(event_publisher.published_events) == 1
    
    def test_rollback_descarta_eventos(self, event_publisher):
        """UoW deve descartar eventos em rollback."""
        uow = InMemoryUnitOfWork(event_publisher=event_publisher)
        
        event = TicketCriadoEvent('ticket-123', 'user-456', 'Teste')
        
        try:
            with uow:
                uow.publish_event(event)
                raise Exception("Erro simulado")
        except Exception:
            pass
        
        # Evento NÃO deve ter sido publicado
        assert len(event_publisher.published_events) == 0


# =============================================================================
# Testes de Repository
# =============================================================================

class TestRepository:
    """Testes para repositório."""
    
    def test_save_and_get(self, repository):
        """Deve salvar e recuperar ticket."""
        ticket = TicketEntity.criar(
            titulo='Teste de repositório',
            descricao='Descrição com mais de 10 caracteres',
            criador_id='user-123'
        )
        
        repository.save(ticket)
        
        retrieved = repository.get_by_id(ticket.id)
        
        assert retrieved is not None
        assert retrieved.id == ticket.id
        assert retrieved.titulo == ticket.titulo
    
    def test_list_by_status(self, repository):
        """Deve listar tickets por status."""
        # Criar tickets
        ticket1 = TicketEntity.criar(
            titulo='Ticket 1',
            descricao='Descrição válida 1',
            criador_id='user-1'
        )
        ticket2 = TicketEntity.criar(
            titulo='Ticket 2',
            descricao='Descrição válida 2',
            criador_id='user-2'
        )
        
        repository.save(ticket1)
        repository.save(ticket2)
        
        # Atribuir ticket1
        ticket1.atribuir_a('tech-1')
        repository.save(ticket1)
        
        # Listar por status
        abertos = repository.list_by_status(TicketStatus.ABERTO)
        em_progresso = repository.list_by_status(TicketStatus.EM_PROGRESSO)
        
        assert len(abertos) == 1
        assert len(em_progresso) == 1
    
    def test_delete(self, repository):
        """Deve deletar ticket."""
        ticket = TicketEntity.criar(
            titulo='Ticket para deletar',
            descricao='Este ticket será deletado',
            criador_id='user-123'
        )
        
        repository.save(ticket)
        assert repository.exists(ticket.id)
        
        repository.delete(ticket.id)
        assert not repository.exists(ticket.id)
    
    def test_count_by_status(self, repository):
        """Deve contar tickets por status."""
        for i in range(3):
            ticket = TicketEntity.criar(
                titulo=f'Ticket {i}',
                descricao=f'Descrição do ticket {i}',
                criador_id=f'user-{i}'
            )
            repository.save(ticket)
        
        count = repository.count_by_status(TicketStatus.ABERTO)
        assert count == 3

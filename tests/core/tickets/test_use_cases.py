"""
Testes Unitários para Use Cases do Domínio de Tickets.

Testa os serviços de aplicação (use cases) que orquestram
a lógica de negócio do domínio de tickets.

Estratégia de Teste:
- Usa InMemoryTicketRepository (fake) para isolamento
- Usa FakeUnitOfWork para testar transações
- Verifica eventos publicados
- Testa cenários de sucesso e erro

Coverage:
- CriarTicketService
- AtribuirTicketService
- FecharTicketService
- ReabrirTicketService
- ListarTicketsService
- ObterTicketService
"""

import pytest
from unittest.mock import Mock, MagicMock
from typing import List

from src.core.tickets.use_cases import (
    CriarTicketService,
    AtribuirTicketService,
    FecharTicketService,
    ReabrirTicketService,
    ListarTicketsService,
    ObterTicketService,
    AlterarPrioridadeService,
    ContarTicketsService,
)
from src.core.tickets.dtos import (
    CriarTicketInputDTO,
    AtribuirTicketInputDTO,
    FecharTicketInputDTO,
    AlterarPrioridadeInputDTO,
)
from src.core.tickets.entities import TicketEntity, TicketStatus, TicketPriority
from src.core.tickets.events import (
    TicketCriadoEvent,
    TicketAtribuidoEvent,
    TicketFechadoEvent,
)
from src.core.tickets.ports import InMemoryTicketRepository
from src.core.shared.exceptions import (
    EntityNotFoundError,
    ValidationError,
    BusinessRuleViolationError,
)
from src.core.shared.events import DomainEvent


class FakeUnitOfWork:
    """
    Fake Unit of Work para testes.
    
    Permite testar:
    - Comportamento de commit/rollback
    - Eventos publicados
    - Isolamento de transações
    """
    
    def __init__(self):
        self._events: List[DomainEvent] = []
        self._committed = False
        self._rolled_back = False
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        return False
    
    def _begin_transaction(self):
        pass
    
    def commit(self):
        self._committed = True
    
    def rollback(self):
        self._rolled_back = True
        self._events.clear()
    
    def publish_event(self, event: DomainEvent):
        self._events.append(event)
    
    def collect_events(self) -> List[DomainEvent]:
        return list(self._events)
    
    @property
    def committed(self) -> bool:
        return self._committed
    
    @property
    def rolled_back(self) -> bool:
        return self._rolled_back


@pytest.fixture
def ticket_repo():
    """Fixture para repositório em memória."""
    return InMemoryTicketRepository()


@pytest.fixture
def uow():
    """Fixture para Unit of Work fake."""
    return FakeUnitOfWork()


@pytest.fixture
def sample_ticket(ticket_repo):
    """Fixture para ticket de exemplo."""
    ticket = TicketEntity.criar(
        titulo="Bug de exemplo",
        descricao="Este é um ticket de exemplo para testes",
        criador_id="user-123",
        prioridade=TicketPriority.MEDIA,
    )
    ticket_repo.save(ticket)
    return ticket


class TestCriarTicketService:
    """Testes para CriarTicketService."""
    
    def test_criar_ticket_sucesso(self, ticket_repo, uow):
        """Deve criar ticket com sucesso."""
        service = CriarTicketService(ticket_repo, uow)
        
        input_dto = CriarTicketInputDTO(
            titulo="Bug no sistema",
            descricao="O sistema está apresentando erro ao salvar",
            criador_id="user-123",
            prioridade="ALTA",
            categoria="Sistema",
        )
        
        output = service.execute(input_dto)
        
        assert output.id is not None
        assert output.titulo == "Bug no sistema"
        assert output.status == "Aberto"
        assert output.prioridade == "Alta"
        assert output.categoria == "Sistema"
        assert output.sla_prazo is not None
    
    def test_criar_ticket_persiste_no_repositorio(self, ticket_repo, uow):
        """Deve persistir ticket no repositório."""
        service = CriarTicketService(ticket_repo, uow)
        
        input_dto = CriarTicketInputDTO(
            titulo="Bug para persistir",
            descricao="Este ticket deve ser persistido no repositório",
            criador_id="user-123",
        )
        
        output = service.execute(input_dto)
        
        # Verificar persistência
        ticket_persistido = ticket_repo.get_by_id(output.id)
        assert ticket_persistido is not None
        assert ticket_persistido.titulo == "Bug para persistir"
    
    def test_criar_ticket_publica_evento(self, ticket_repo, uow):
        """Deve publicar evento TicketCriadoEvent."""
        service = CriarTicketService(ticket_repo, uow)
        
        input_dto = CriarTicketInputDTO(
            titulo="Bug com evento",
            descricao="Este ticket deve disparar evento de criação",
            criador_id="user-123",
        )
        
        service.execute(input_dto)
        
        # Verificar eventos
        events = uow.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], TicketCriadoEvent)
        assert events[0].criador_id == "user-123"
    
    def test_criar_ticket_commit_executado(self, ticket_repo, uow):
        """Deve executar commit da transação."""
        service = CriarTicketService(ticket_repo, uow)
        
        input_dto = CriarTicketInputDTO(
            titulo="Bug para commit",
            descricao="Verificar que commit é executado",
            criador_id="user-123",
        )
        
        service.execute(input_dto)
        
        assert uow.committed is True
    
    def test_criar_ticket_prioridade_invalida_erro(self, ticket_repo, uow):
        """Deve lançar erro para prioridade inválida."""
        service = CriarTicketService(ticket_repo, uow)
        
        input_dto = CriarTicketInputDTO(
            titulo="Bug prioridade inválida",
            descricao="Este ticket tem prioridade inválida",
            criador_id="user-123",
            prioridade="INVALIDA",
        )
        
        with pytest.raises(ValidationError) as exc_info:
            service.execute(input_dto)
        
        assert "prioridade" in str(exc_info.value).lower()
    
    def test_criar_ticket_titulo_invalido_erro(self, ticket_repo, uow):
        """Deve lançar erro para título inválido."""
        service = CriarTicketService(ticket_repo, uow)
        
        input_dto = CriarTicketInputDTO(
            titulo="AB",  # Muito curto
            descricao="Descrição válida com mais de 10 caracteres",
            criador_id="user-123",
        )
        
        with pytest.raises(ValidationError):
            service.execute(input_dto)


class TestAtribuirTicketService:
    """Testes para AtribuirTicketService."""
    
    def test_atribuir_ticket_sucesso(self, ticket_repo, uow, sample_ticket):
        """Deve atribuir ticket a técnico."""
        service = AtribuirTicketService(ticket_repo, uow)
        
        input_dto = AtribuirTicketInputDTO(
            ticket_id=sample_ticket.id,
            tecnico_id="tecnico-456",
            atribuido_por_id="admin-789",
        )
        
        output = service.execute(input_dto)
        
        assert output.atribuido_a_id == "tecnico-456"
        assert output.status == "Em Progresso"
    
    def test_atribuir_ticket_publica_evento(self, ticket_repo, uow, sample_ticket):
        """Deve publicar evento TicketAtribuidoEvent."""
        service = AtribuirTicketService(ticket_repo, uow)
        
        input_dto = AtribuirTicketInputDTO(
            ticket_id=sample_ticket.id,
            tecnico_id="tecnico-456",
        )
        
        service.execute(input_dto)
        
        events = uow.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], TicketAtribuidoEvent)
        assert events[0].tecnico_id == "tecnico-456"
    
    def test_atribuir_ticket_nao_encontrado_erro(self, ticket_repo, uow):
        """Deve lançar erro se ticket não existe."""
        service = AtribuirTicketService(ticket_repo, uow)
        
        input_dto = AtribuirTicketInputDTO(
            ticket_id="id-inexistente",
            tecnico_id="tecnico-456",
        )
        
        with pytest.raises(EntityNotFoundError) as exc_info:
            service.execute(input_dto)
        
        assert "não encontrado" in str(exc_info.value).lower()


class TestFecharTicketService:
    """Testes para FecharTicketService."""
    
    def test_fechar_ticket_sucesso(self, ticket_repo, uow, sample_ticket):
        """Deve fechar ticket atribuído."""
        # Primeiro atribuir
        sample_ticket.atribuir_a("tecnico-123")
        ticket_repo.save(sample_ticket)
        
        service = FecharTicketService(ticket_repo, uow)
        
        input_dto = FecharTicketInputDTO(
            ticket_id=sample_ticket.id,
            fechado_por_id="tecnico-123",
        )
        
        output = service.execute(input_dto)
        
        assert output.status == "Fechado"
    
    def test_fechar_ticket_publica_evento(self, ticket_repo, uow, sample_ticket):
        """Deve publicar evento TicketFechadoEvent."""
        sample_ticket.atribuir_a("tecnico-123")
        ticket_repo.save(sample_ticket)
        
        service = FecharTicketService(ticket_repo, uow)
        
        input_dto = FecharTicketInputDTO(
            ticket_id=sample_ticket.id,
            fechado_por_id="tecnico-123",
        )
        
        service.execute(input_dto)
        
        events = uow.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], TicketFechadoEvent)
    
    def test_fechar_ticket_nao_atribuido_erro(self, ticket_repo, uow, sample_ticket):
        """Deve lançar erro se ticket não está atribuído."""
        service = FecharTicketService(ticket_repo, uow)
        
        input_dto = FecharTicketInputDTO(
            ticket_id=sample_ticket.id,
            fechado_por_id="user-123",
        )
        
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            service.execute(input_dto)
        
        assert "atribuído" in str(exc_info.value).lower()


class TestReabrirTicketService:
    """Testes para ReabrirTicketService."""
    
    def test_reabrir_ticket_sucesso(self, ticket_repo, uow, sample_ticket):
        """Deve reabrir ticket fechado."""
        sample_ticket.atribuir_a("tecnico-123")
        sample_ticket.fechar()
        ticket_repo.save(sample_ticket)
        
        service = ReabrirTicketService(ticket_repo, uow)
        
        output = service.execute(
            ticket_id=sample_ticket.id,
            reaberto_por_id="user-123",
            motivo="Problema não foi resolvido",
        )
        
        assert output.status == "Aberto"
        assert output.atribuido_a_id is None
    
    def test_reabrir_ticket_nao_fechado_erro(self, ticket_repo, uow, sample_ticket):
        """Deve lançar erro se ticket não está fechado."""
        service = ReabrirTicketService(ticket_repo, uow)
        
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            service.execute(
                ticket_id=sample_ticket.id,
                reaberto_por_id="user-123",
            )
        
        assert "fechado" in str(exc_info.value).lower()


class TestListarTicketsService:
    """Testes para ListarTicketsService."""
    
    def test_listar_todos_tickets(self, ticket_repo):
        """Deve listar todos os tickets."""
        # Criar tickets
        for i in range(3):
            ticket = TicketEntity.criar(
                titulo=f"Bug número {i}",
                descricao=f"Descrição do bug número {i}",
                criador_id="user-123",
            )
            ticket_repo.save(ticket)
        
        service = ListarTicketsService(ticket_repo)
        
        tickets = service.execute()
        
        assert len(tickets) == 3
    
    def test_listar_tickets_por_status(self, ticket_repo):
        """Deve filtrar tickets por status."""
        # Criar tickets com diferentes status
        ticket_aberto = TicketEntity.criar(
            titulo="Ticket aberto",
            descricao="Este ticket está aberto",
            criador_id="user-123",
        )
        ticket_repo.save(ticket_aberto)
        
        ticket_progresso = TicketEntity.criar(
            titulo="Ticket em progresso",
            descricao="Este ticket está em progresso",
            criador_id="user-123",
        )
        ticket_progresso.atribuir_a("tecnico-123")
        ticket_repo.save(ticket_progresso)
        
        service = ListarTicketsService(ticket_repo)
        
        tickets_abertos = service.execute(status="ABERTO")
        tickets_progresso = service.execute(status="EM_PROGRESSO")
        
        assert len(tickets_abertos) == 1
        assert len(tickets_progresso) == 1
    
    def test_listar_tickets_por_criador(self, ticket_repo):
        """Deve filtrar tickets por criador."""
        # Criar tickets de diferentes usuários
        ticket1 = TicketEntity.criar(
            titulo="Ticket do user1",
            descricao="Este ticket é do primeiro usuário",
            criador_id="user-001",
        )
        ticket_repo.save(ticket1)
        
        ticket2 = TicketEntity.criar(
            titulo="Ticket do user2",
            descricao="Este ticket é do segundo usuário",
            criador_id="user-002",
        )
        ticket_repo.save(ticket2)
        
        service = ListarTicketsService(ticket_repo)
        
        tickets_user1 = service.execute(criador_id="user-001")
        
        assert len(tickets_user1) == 1
        assert tickets_user1[0].criador_id == "user-001"


class TestObterTicketService:
    """Testes para ObterTicketService."""
    
    def test_obter_ticket_existente(self, ticket_repo, sample_ticket):
        """Deve retornar ticket existente."""
        service = ObterTicketService(ticket_repo)
        
        output = service.execute(sample_ticket.id)
        
        assert output.id == sample_ticket.id
        assert output.titulo == sample_ticket.titulo
    
    def test_obter_ticket_inexistente_erro(self, ticket_repo):
        """Deve lançar erro se ticket não existe."""
        service = ObterTicketService(ticket_repo)
        
        with pytest.raises(EntityNotFoundError) as exc_info:
            service.execute("id-inexistente")
        
        assert "não encontrado" in str(exc_info.value).lower()


class TestAlterarPrioridadeService:
    """Testes para AlterarPrioridadeService."""
    
    def test_alterar_prioridade_sucesso(self, ticket_repo, uow, sample_ticket):
        """Deve alterar prioridade com sucesso."""
        service = AlterarPrioridadeService(ticket_repo, uow)
        
        input_dto = AlterarPrioridadeInputDTO(
            ticket_id=sample_ticket.id,
            nova_prioridade="CRITICA",
            alterado_por_id="admin-123",
        )
        
        output = service.execute(input_dto)
        
        assert output.prioridade == "Crítica"
    
    def test_alterar_prioridade_invalida_erro(self, ticket_repo, uow, sample_ticket):
        """Deve lançar erro para prioridade inválida."""
        service = AlterarPrioridadeService(ticket_repo, uow)
        
        input_dto = AlterarPrioridadeInputDTO(
            ticket_id=sample_ticket.id,
            nova_prioridade="INVALIDA",
            alterado_por_id="admin-123",
        )
        
        with pytest.raises(ValidationError):
            service.execute(input_dto)


class TestContarTicketsService:
    """Testes para ContarTicketsService."""
    
    def test_contar_tickets(self, ticket_repo):
        """Deve contar tickets corretamente."""
        # Criar tickets
        for i in range(5):
            ticket = TicketEntity.criar(
                titulo=f"Ticket {i}",
                descricao=f"Descrição do ticket número {i}",
                criador_id="user-123",
            )
            ticket_repo.save(ticket)
        
        service = ContarTicketsService(ticket_repo)
        
        resultado = service.execute()
        
        assert resultado["total"] == 5
        assert "por_status" in resultado
        assert resultado["por_status"]["Aberto"] == 5


class TestUnitOfWorkIntegration:
    """Testes de integração do UoW com services."""
    
    def test_rollback_em_erro(self, ticket_repo):
        """Deve fazer rollback se ocorrer erro."""
        uow = FakeUnitOfWork()
        
        # Mock do repositório que lança erro
        repo_mock = Mock(spec=InMemoryTicketRepository)
        repo_mock.save.side_effect = Exception("Erro de persistência")
        
        service = CriarTicketService(repo_mock, uow)
        
        input_dto = CriarTicketInputDTO(
            titulo="Bug que vai falhar",
            descricao="Este ticket vai causar erro na persistência",
            criador_id="user-123",
        )
        
        with pytest.raises(Exception):
            service.execute(input_dto)
        
        # Verificar que rollback foi chamado
        assert uow.rolled_back is True
        assert len(uow.collect_events()) == 0  # Eventos descartados
    
    def test_eventos_publicados_apos_commit(self, ticket_repo, uow):
        """Eventos só devem ser publicados após commit."""
        service = CriarTicketService(ticket_repo, uow)
        
        input_dto = CriarTicketInputDTO(
            titulo="Bug com eventos",
            descricao="Verificar publicação de eventos",
            criador_id="user-123",
        )
        
        service.execute(input_dto)
        
        # Commit foi executado
        assert uow.committed is True
        
        # Evento foi publicado
        events = uow.collect_events()
        assert len(events) == 1

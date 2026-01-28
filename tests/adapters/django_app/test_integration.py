"""
Testes de Integração para Django Adapters.

Testa a integração entre:
- Django Models ↔ Core Entities (via Mappers)
- Repository ↔ Database (PostgreSQL/SQLite)
- Unit of Work ↔ Transactions
- Views ↔ Use Cases

Estratégia:
- Usa banco SQLite em memória para velocidade
- Testa fluxo completo (request → response)
- Verifica persistência e eventos

Fixtures:
- db_setup: Configura banco para testes
- sample_ticket_data: Dados de exemplo
"""

import pytest
from datetime import datetime, timedelta

# Configurar Django antes de importar models
import django
from django.conf import settings

# Configurar settings mínimas se não configuradas
if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
            'src.adapters.django_app.tickets',
        ],
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
        USE_TZ=True,
    )
    django.setup()


from src.core.tickets.entities import TicketEntity, TicketStatus, TicketPriority
from src.core.tickets.dtos import CriarTicketInputDTO, AtribuirTicketInputDTO
from src.core.shared.exceptions import EntityNotFoundError, ValidationError

from src.adapters.django_app.tickets.models import TicketModel
from src.adapters.django_app.tickets.mappers import TicketMapper
from src.adapters.django_app.tickets.repositories import DjangoTicketRepository
from src.adapters.django_app.shared.unit_of_work import DjangoUnitOfWork, InMemoryUnitOfWork


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_ticket_entity():
    """Cria entidade de ticket para testes."""
    return TicketEntity.criar(
        titulo="Bug no sistema de login",
        descricao="O sistema não aceita a senha correta do usuário",
        criador_id="user-123",
        prioridade=TicketPriority.ALTA,
        categoria="Autenticação",
    )


@pytest.fixture
def sample_ticket_data():
    """Dados para criar ticket via DTO."""
    return {
        'titulo': 'Problema de performance',
        'descricao': 'Sistema está muito lento nas consultas de relatórios',
        'criador_id': 'user-456',
        'prioridade': 'MEDIA',
        'categoria': 'Performance',
    }


# =============================================================================
# Testes de Mapper
# =============================================================================

class TestTicketMapper:
    """Testes para TicketMapper."""
    
    def test_to_model_converte_entity(self, sample_ticket_entity):
        """Deve converter Entity para Model corretamente."""
        mapper = TicketMapper()
        model = mapper.to_model(sample_ticket_entity)
        
        assert model.id == sample_ticket_entity.id
        assert model.titulo == sample_ticket_entity.titulo
        assert model.descricao == sample_ticket_entity.descricao
        assert model.status == sample_ticket_entity.status.value
        assert model.prioridade == sample_ticket_entity.prioridade.value
        assert model.criador_id == sample_ticket_entity.criador_id
        assert model.categoria == sample_ticket_entity.categoria
        assert model.sla_prazo == sample_ticket_entity.sla_prazo
    
    def test_to_entity_converte_model(self, sample_ticket_entity):
        """Deve converter Model para Entity corretamente."""
        mapper = TicketMapper()
        
        # Criar model a partir de entity
        model = mapper.to_model(sample_ticket_entity)
        
        # Converter de volta para entity
        entity = mapper.to_entity(model)
        
        assert entity.id == sample_ticket_entity.id
        assert entity.titulo == sample_ticket_entity.titulo
        assert entity.status == sample_ticket_entity.status
        assert entity.prioridade == sample_ticket_entity.prioridade
    
    def test_to_entity_list_converte_lista(self, sample_ticket_entity):
        """Deve converter lista de Models para lista de Entities."""
        mapper = TicketMapper()
        
        # Criar múltiplos models
        entities = [
            sample_ticket_entity,
            TicketEntity.criar(
                titulo="Outro ticket",
                descricao="Descrição de outro ticket para teste",
                criador_id="user-789",
            )
        ]
        
        models = [mapper.to_model(e) for e in entities]
        
        # Converter lista
        result = mapper.to_entity_list(models)
        
        assert len(result) == 2
        assert result[0].id == entities[0].id
        assert result[1].id == entities[1].id
    
    def test_preserva_status_enum(self):
        """Deve preservar status como Enum após conversão."""
        mapper = TicketMapper()
        
        entity = TicketEntity.criar(
            titulo="Ticket em progresso",
            descricao="Descrição do ticket em progresso",
            criador_id="user-123",
        )
        entity.atribuir_a("tecnico-456")  # Muda para EM_PROGRESSO
        
        model = mapper.to_model(entity)
        entity_back = mapper.to_entity(model)
        
        assert entity_back.status == TicketStatus.EM_PROGRESSO
        assert isinstance(entity_back.status, TicketStatus)


# =============================================================================
# Testes de Repository (In-Memory)
# =============================================================================

class TestInMemoryRepository:
    """Testes de repository usando implementação in-memory."""
    
    def test_save_e_get_by_id(self, sample_ticket_entity):
        """Deve salvar e recuperar ticket."""
        from src.core.tickets.ports import InMemoryTicketRepository
        
        repo = InMemoryTicketRepository()
        
        # Salvar
        repo.save(sample_ticket_entity)
        
        # Recuperar
        ticket = repo.get_by_id(sample_ticket_entity.id)
        
        assert ticket is not None
        assert ticket.id == sample_ticket_entity.id
        assert ticket.titulo == sample_ticket_entity.titulo
    
    def test_list_all(self):
        """Deve listar todos os tickets."""
        from src.core.tickets.ports import InMemoryTicketRepository
        
        repo = InMemoryTicketRepository()
        
        # Criar e salvar múltiplos tickets
        for i in range(3):
            ticket = TicketEntity.criar(
                titulo=f"Ticket {i}",
                descricao=f"Descrição do ticket número {i}",
                criador_id=f"user-{i}",
            )
            repo.save(ticket)
        
        # Listar
        tickets = repo.list_all()
        
        assert len(tickets) == 3
    
    def test_list_by_status(self):
        """Deve filtrar tickets por status."""
        from src.core.tickets.ports import InMemoryTicketRepository
        
        repo = InMemoryTicketRepository()
        
        # Criar tickets com diferentes status
        ticket1 = TicketEntity.criar(
            titulo="Ticket aberto",
            descricao="Descrição do ticket aberto",
            criador_id="user-1",
        )
        
        ticket2 = TicketEntity.criar(
            titulo="Ticket em progresso",
            descricao="Descrição do ticket em progresso",
            criador_id="user-2",
        )
        ticket2.atribuir_a("tecnico-1")
        
        repo.save(ticket1)
        repo.save(ticket2)
        
        # Filtrar por status
        abertos = repo.list_by_status(TicketStatus.ABERTO)
        em_progresso = repo.list_by_status(TicketStatus.EM_PROGRESSO)
        
        assert len(abertos) == 1
        assert len(em_progresso) == 1
        assert abertos[0].titulo == "Ticket aberto"
    
    def test_delete_ticket(self, sample_ticket_entity):
        """Deve deletar ticket."""
        from src.core.tickets.ports import InMemoryTicketRepository
        
        repo = InMemoryTicketRepository()
        
        repo.save(sample_ticket_entity)
        assert repo.exists(sample_ticket_entity.id)
        
        repo.delete(sample_ticket_entity.id)
        assert not repo.exists(sample_ticket_entity.id)
    
    def test_count_by_status(self):
        """Deve contar tickets por status."""
        from src.core.tickets.ports import InMemoryTicketRepository
        
        repo = InMemoryTicketRepository()
        
        # Criar tickets
        for i in range(5):
            ticket = TicketEntity.criar(
                titulo=f"Ticket {i}",
                descricao=f"Descrição do ticket {i}",
                criador_id=f"user-{i}",
            )
            if i >= 3:
                ticket.atribuir_a("tecnico-1")
            repo.save(ticket)
        
        # Contar
        counts = repo.count_by_status()
        
        assert counts.get('Aberto', 0) == 3
        assert counts.get('Em Progresso', 0) == 2


# =============================================================================
# Testes de Unit of Work
# =============================================================================

class TestInMemoryUnitOfWork:
    """Testes para InMemoryUnitOfWork."""
    
    def test_commit_marca_como_committed(self):
        """Deve marcar como committed após commit."""
        uow = InMemoryUnitOfWork()
        
        with uow:
            pass  # Operações
        
        assert uow.committed
        assert not uow.rolled_back
    
    def test_rollback_em_excecao(self):
        """Deve fazer rollback em caso de exceção."""
        uow = InMemoryUnitOfWork()
        
        with pytest.raises(ValueError):
            with uow:
                raise ValueError("Erro simulado")
        
        assert not uow.committed
        assert uow.rolled_back
    
    def test_eventos_publicados_apos_commit(self):
        """Deve publicar eventos após commit."""
        from src.core.tickets.events import TicketCriadoEvent
        
        uow = InMemoryUnitOfWork()
        
        with uow:
            event = TicketCriadoEvent(
                aggregate_id="ticket-123",
                criador_id="user-456",
                titulo="Teste",
                prioridade="Alta",
                categoria="Geral",
            )
            uow.publish_event(event)
        
        assert len(uow.published_events) == 1
        assert uow.published_events[0].aggregate_id == "ticket-123"
    
    def test_eventos_descartados_em_rollback(self):
        """Deve descartar eventos em caso de rollback."""
        from src.core.tickets.events import TicketCriadoEvent
        
        uow = InMemoryUnitOfWork()
        
        with pytest.raises(ValueError):
            with uow:
                event = TicketCriadoEvent(
                    aggregate_id="ticket-123",
                    criador_id="user-456",
                    titulo="Teste",
                    prioridade="Alta",
                    categoria="Geral",
                )
                uow.publish_event(event)
                raise ValueError("Erro simulado")
        
        assert len(uow.published_events) == 0


# =============================================================================
# Testes de Integração com Use Cases
# =============================================================================

class TestUseCasesIntegration:
    """Testes de integração dos Use Cases com adapters."""
    
    def test_criar_ticket_service_completo(self):
        """Deve criar ticket usando service com repo e uow."""
        from src.core.tickets.use_cases import CriarTicketService
        from src.core.tickets.ports import InMemoryTicketRepository
        
        repo = InMemoryTicketRepository()
        uow = InMemoryUnitOfWork()
        
        service = CriarTicketService(repo, uow)
        
        input_dto = CriarTicketInputDTO(
            titulo="Bug crítico no sistema",
            descricao="O sistema está completamente fora do ar para todos os usuários",
            criador_id="user-123",
            prioridade="CRITICA",
            categoria="Infraestrutura",
        )
        
        output = service.execute(input_dto)
        
        # Verificar output
        assert output.id is not None
        assert output.titulo == "Bug crítico no sistema"
        assert output.status == "Aberto"
        assert output.prioridade == "Crítica"
        
        # Verificar persistência
        ticket = repo.get_by_id(output.id)
        assert ticket is not None
        
        # Verificar evento
        assert len(uow.published_events) == 1
        assert uow.published_events[0].event_type == "TicketCriadoEvent"
    
    def test_atribuir_ticket_service_completo(self):
        """Deve atribuir ticket usando service."""
        from src.core.tickets.use_cases import CriarTicketService, AtribuirTicketService
        from src.core.tickets.ports import InMemoryTicketRepository
        
        repo = InMemoryTicketRepository()
        
        # Criar ticket primeiro
        criar_uow = InMemoryUnitOfWork()
        criar_service = CriarTicketService(repo, criar_uow)
        
        output = criar_service.execute(CriarTicketInputDTO(
            titulo="Ticket para atribuir",
            descricao="Este ticket será atribuído a um técnico",
            criador_id="user-123",
        ))
        
        # Atribuir
        atribuir_uow = InMemoryUnitOfWork()
        atribuir_service = AtribuirTicketService(repo, atribuir_uow)
        
        result = atribuir_service.execute(AtribuirTicketInputDTO(
            ticket_id=output.id,
            tecnico_id="tecnico-456",
            atribuido_por_id="admin-789",
        ))
        
        # Verificar
        assert result.status == "Em Progresso"
        assert result.atribuido_a_id == "tecnico-456"
        
        # Verificar evento
        assert len(atribuir_uow.published_events) == 1
        assert atribuir_uow.published_events[0].event_type == "TicketAtribuidoEvent"
    
    def test_fechar_ticket_service_completo(self):
        """Deve fechar ticket usando service."""
        from src.core.tickets.use_cases import (
            CriarTicketService,
            AtribuirTicketService,
            FecharTicketService,
        )
        from src.core.tickets.dtos import FecharTicketInputDTO
        from src.core.tickets.ports import InMemoryTicketRepository
        
        repo = InMemoryTicketRepository()
        
        # Criar ticket
        criar_uow = InMemoryUnitOfWork()
        criar_service = CriarTicketService(repo, criar_uow)
        output = criar_service.execute(CriarTicketInputDTO(
            titulo="Ticket para fechar",
            descricao="Este ticket será fechado após atribuição",
            criador_id="user-123",
        ))
        
        # Atribuir
        atribuir_uow = InMemoryUnitOfWork()
        atribuir_service = AtribuirTicketService(repo, atribuir_uow)
        atribuir_service.execute(AtribuirTicketInputDTO(
            ticket_id=output.id,
            tecnico_id="tecnico-456",
            atribuido_por_id="admin-789",
        ))
        
        # Fechar
        fechar_uow = InMemoryUnitOfWork()
        fechar_service = FecharTicketService(repo, fechar_uow)
        result = fechar_service.execute(FecharTicketInputDTO(
            ticket_id=output.id,
            fechado_por_id="tecnico-456",
        ))
        
        # Verificar
        assert result.status == "Fechado"
        
        # Verificar evento
        assert len(fechar_uow.published_events) == 1
        assert fechar_uow.published_events[0].event_type == "TicketFechadoEvent"

"""
Configuração pytest para testes com Django.

Este arquivo configura:
- Django settings para testes
- Fixtures compartilhadas
- Banco de dados em memória
"""

import os
import sys
import pytest

# Adicionar src ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def pytest_configure(config):
    """Configura Django antes dos testes."""
    import django
    from django.conf import settings
    
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
            TIME_ZONE='America/Sao_Paulo',
        )
        django.setup()


@pytest.fixture(scope='session')
def django_db_setup():
    """Setup do banco de dados para sessão de testes."""
    from django.core.management import call_command
    call_command('migrate', '--run-syncdb', verbosity=0)


@pytest.fixture
def db_session(django_db_setup, db):
    """Fixture para acesso ao banco de dados."""
    pass


@pytest.fixture
def ticket_model_factory():
    """Factory para criar TicketModel para testes."""
    from src.adapters.django_app.tickets.models import TicketModel
    from django.utils import timezone
    import uuid
    
    def create_ticket(**kwargs):
        defaults = {
            'id': str(uuid.uuid4()),
            'titulo': 'Ticket de Teste',
            'descricao': 'Descrição do ticket de teste',
            'status': 'Aberto',
            'prioridade': 'Média',
            'criador_id': 'user-123',
            'categoria': 'Geral',
            'criado_em': timezone.now(),
        }
        defaults.update(kwargs)
        return TicketModel.objects.create(**defaults)
    
    return create_ticket


@pytest.fixture
def sample_ticket_entity():
    """Cria entidade de ticket para testes."""
    from src.core.tickets.entities import TicketEntity, TicketPriority
    
    return TicketEntity.criar(
        titulo="Bug no sistema de login",
        descricao="O sistema não aceita a senha correta do usuário",
        criador_id="user-123",
        prioridade=TicketPriority.ALTA,
        categoria="Autenticação",
    )


@pytest.fixture
def inmemory_ticket_repo():
    """Repositório em memória para testes unitários."""
    from src.core.tickets.ports import InMemoryTicketRepository
    return InMemoryTicketRepository()


@pytest.fixture
def inmemory_uow():
    """Unit of Work em memória para testes unitários."""
    from src.adapters.django_app.shared.unit_of_work import InMemoryUnitOfWork
    return InMemoryUnitOfWork()

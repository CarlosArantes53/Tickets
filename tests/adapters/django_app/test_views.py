"""
Testes para Views e API do domínio de Tickets.

Testa:
- Views HTML (rendering, redirects, forms)
- API JSON (CRUD, validações, erros)
- Integração com Container DI
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock

# Configurar Django para testes
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
            'django.contrib.messages',
            'django.contrib.sessions',
            'src.adapters.django_app.tickets',
        ],
        ROOT_URLCONF='src.adapters.django_app.tickets.urls',
        TEMPLATES=[{
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
            'APP_DIRS': True,
            'OPTIONS': {
                'context_processors': [
                    'django.template.context_processors.request',
                    'django.contrib.messages.context_processors.messages',
                ],
            },
        }],
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
        USE_TZ=True,
        MIDDLEWARE=[
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware',
        ],
        SECRET_KEY='test-secret-key',
    )
    django.setup()

from django.test import RequestFactory, Client
from django.http import JsonResponse

from src.core.tickets.dtos import TicketOutputDTO, CriarTicketInputDTO
from src.core.shared.exceptions import ValidationError, EntityNotFoundError
from src.config.container import get_container, reset_container


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def rf():
    """Request Factory para criar requests."""
    return RequestFactory()


@pytest.fixture
def client():
    """Django test client."""
    return Client()


@pytest.fixture
def mock_ticket_output():
    """DTO de saída mockado."""
    from datetime import datetime
    now = datetime.now()
    return TicketOutputDTO(
        id='12345678-1234-1234-1234-123456789012',
        titulo='Ticket de Teste',
        descricao='Descrição do ticket de teste com mais de 10 caracteres',
        status='Aberto',
        prioridade='Média',
        criador_id='user-123',
        atribuido_a_id=None,
        categoria='Geral',
        criado_em=now,
        atualizado_em=now,
        sla_prazo=None,
        esta_atrasado=False,
    )


@pytest.fixture(autouse=True)
def reset_di_container():
    """Reset container entre testes."""
    reset_container()
    yield
    reset_container()


# =============================================================================
# Testes de API Views
# =============================================================================

class TestTicketAPIListView:
    """Testes para TicketAPIListView."""
    
    def test_get_lista_tickets(self, rf, mock_ticket_output):
        """GET deve retornar lista de tickets."""
        from src.adapters.django_app.tickets.api_views import TicketAPIListView
        
        # Mock do service
        mock_service = Mock()
        mock_service.execute.return_value = [mock_ticket_output]
        
        # Mock do container
        with patch('src.adapters.django_app.tickets.api_views.get_container') as mock_container:
            mock_container.return_value.services.listar_tickets_service.return_value = mock_service
            
            request = rf.get('/tickets/api/')
            view = TicketAPIListView()
            response = view.get(request)
        
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['success'] is True
        assert len(data['data']) == 1
        assert data['meta']['total'] == 1
    
    def test_post_cria_ticket(self, rf, mock_ticket_output):
        """POST deve criar novo ticket."""
        from src.adapters.django_app.tickets.api_views import TicketAPIListView
        
        mock_service = Mock()
        mock_service.execute.return_value = mock_ticket_output
        
        with patch('src.adapters.django_app.tickets.api_views.get_container') as mock_container:
            mock_container.return_value.services.criar_ticket_service.return_value = mock_service
            
            request = rf.post(
                '/tickets/api/',
                data=json.dumps({
                    'titulo': 'Novo Ticket',
                    'descricao': 'Descrição do novo ticket com mais de 10 caracteres',
                }),
                content_type='application/json'
            )
            view = TicketAPIListView()
            response = view.post(request)
        
        assert response.status_code == 201
        data = json.loads(response.content)
        assert data['success'] is True
    
    def test_post_validacao_erro(self, rf):
        """POST com dados inválidos deve retornar erro."""
        from src.adapters.django_app.tickets.api_views import TicketAPIListView
        
        mock_service = Mock()
        mock_service.execute.side_effect = ValidationError("Título deve ter pelo menos 3 caracteres")
        
        with patch('src.adapters.django_app.tickets.api_views.get_container') as mock_container:
            mock_container.return_value.services.criar_ticket_service.return_value = mock_service
            
            request = rf.post(
                '/tickets/api/',
                data=json.dumps({
                    'titulo': 'AB',
                    'descricao': 'Descrição válida com mais de dez caracteres',
                }),
                content_type='application/json'
            )
            view = TicketAPIListView()
            response = view.post(request)
        
        assert response.status_code == 400
        data = json.loads(response.content)
        assert data['success'] is False
        assert 'erro' in data['error'].lower() or 'caracteres' in data['error'].lower()


class TestTicketAPIDetailView:
    """Testes para TicketAPIDetailView."""
    
    def test_get_ticket_existente(self, rf, mock_ticket_output):
        """GET deve retornar ticket existente."""
        from src.adapters.django_app.tickets.api_views import TicketAPIDetailView
        
        mock_service = Mock()
        mock_service.execute.return_value = mock_ticket_output
        
        with patch('src.adapters.django_app.tickets.api_views.get_container') as mock_container:
            mock_container.return_value.services.obter_ticket_service.return_value = mock_service
            
            request = rf.get('/tickets/api/12345/')
            view = TicketAPIDetailView()
            response = view.get(request, pk='12345678-1234-1234-1234-123456789012')
        
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['success'] is True
        assert data['data']['id'] == mock_ticket_output.id
    
    def test_get_ticket_nao_encontrado(self, rf):
        """GET para ticket inexistente deve retornar 404."""
        from src.adapters.django_app.tickets.api_views import TicketAPIDetailView
        
        mock_service = Mock()
        mock_service.execute.side_effect = EntityNotFoundError("Ticket", "nonexistent")
        
        with patch('src.adapters.django_app.tickets.api_views.get_container') as mock_container:
            mock_container.return_value.services.obter_ticket_service.return_value = mock_service
            
            request = rf.get('/tickets/api/nonexistent/')
            view = TicketAPIDetailView()
            response = view.get(request, pk='nonexistent')
        
        assert response.status_code == 404
        data = json.loads(response.content)
        assert data['success'] is False


class TestTicketAPIAtribuirView:
    """Testes para TicketAPIAtribuirView."""
    
    def test_post_atribui_ticket(self, rf, mock_ticket_output):
        """POST deve atribuir ticket."""
        from src.adapters.django_app.tickets.api_views import TicketAPIAtribuirView
        
        mock_ticket_output.atribuido_a_id = 'tecnico-456'
        mock_ticket_output.status = 'Em Progresso'
        
        mock_service = Mock()
        mock_service.execute.return_value = mock_ticket_output
        
        with patch('src.adapters.django_app.tickets.api_views.get_container') as mock_container:
            mock_container.return_value.services.atribuir_ticket_service.return_value = mock_service
            
            request = rf.post(
                '/tickets/api/12345/atribuir/',
                data=json.dumps({'tecnico_id': 'tecnico-456'}),
                content_type='application/json'
            )
            view = TicketAPIAtribuirView()
            response = view.post(request, pk='12345')
        
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['success'] is True
    
    def test_post_sem_tecnico_id(self, rf):
        """POST sem tecnico_id deve retornar erro."""
        from src.adapters.django_app.tickets.api_views import TicketAPIAtribuirView
        
        request = rf.post(
            '/tickets/api/12345/atribuir/',
            data=json.dumps({}),
            content_type='application/json'
        )
        view = TicketAPIAtribuirView()
        response = view.post(request, pk='12345')
        
        assert response.status_code == 400
        data = json.loads(response.content)
        assert data['success'] is False
        assert 'tecnico_id' in data['error'].lower()


# =============================================================================
# Testes de Container DI
# =============================================================================

class TestContainer:
    """Testes para o Container de DI."""
    
    def test_get_container_retorna_instancia(self):
        """get_container deve retornar instância do container."""
        container = get_container()
        assert container is not None
    
    def test_get_container_singleton(self):
        """get_container deve retornar mesma instância."""
        container1 = get_container()
        container2 = get_container()
        assert container1 is container2
    
    def test_reset_container(self):
        """reset_container deve criar nova instância."""
        container1 = get_container()
        reset_container()
        container2 = get_container()
        assert container1 is not container2


# =============================================================================
# Testes de JSON Response Helper
# =============================================================================

class TestJsonResponseHelper:
    """Testes para funções auxiliares de resposta JSON."""
    
    def test_json_response_success(self):
        """json_response com success=True deve formatar corretamente."""
        from src.adapters.django_app.tickets.api_views import json_response
        
        response = json_response(
            success=True,
            data={'id': '123'},
            status=200
        )
        
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['success'] is True
        assert data['data']['id'] == '123'
    
    def test_json_response_error(self):
        """json_response com error deve formatar corretamente."""
        from src.adapters.django_app.tickets.api_views import json_response
        
        response = json_response(
            success=False,
            error='Algo deu errado',
            status=400
        )
        
        assert response.status_code == 400
        data = json.loads(response.content)
        assert data['success'] is False
        assert data['error'] == 'Algo deu errado'
    
    def test_json_response_with_meta(self):
        """json_response com meta deve incluir metadados."""
        from src.adapters.django_app.tickets.api_views import json_response
        
        response = json_response(
            success=True,
            data=[],
            meta={'total': 0, 'page': 1}
        )
        
        data = json.loads(response.content)
        assert data['meta']['total'] == 0
        assert data['meta']['page'] == 1


# =============================================================================
# Testes de Mixins
# =============================================================================

class TestContainerMixin:
    """Testes para ContainerMixin."""
    
    def test_get_container(self):
        """get_container deve retornar container."""
        from src.adapters.django_app.tickets.views import ContainerMixin
        
        class TestView(ContainerMixin):
            pass
        
        view = TestView()
        container = view.get_container()
        
        assert container is not None
    
    def test_get_service(self):
        """get_service deve retornar service do container."""
        from src.adapters.django_app.tickets.views import ContainerMixin
        
        class TestView(ContainerMixin):
            pass
        
        view = TestView()
        
        with patch.object(view, 'get_container') as mock_get:
            mock_container = Mock()
            mock_service = Mock()
            mock_container.services.listar_tickets_service.return_value = mock_service
            mock_get.return_value = mock_container
            
            service = view.get_service('listar_tickets_service')
            
            assert service == mock_service

"""
URL patterns para o domínio de Tickets.

Endpoints HTML:
- GET /tickets/ - Listar tickets
- GET /tickets/criar/ - Formulário de criação
- POST /tickets/criar/ - Criar ticket
- GET /tickets/dashboard/ - Dashboard
- GET /tickets/<id>/ - Detalhes do ticket
- POST /tickets/<id>/atribuir/ - Atribuir ticket
- POST /tickets/<id>/fechar/ - Fechar ticket
- POST /tickets/<id>/reabrir/ - Reabrir ticket
- POST /tickets/<id>/prioridade/ - Alterar prioridade

Endpoints API JSON:
- GET /tickets/api/ - Listar tickets
- POST /tickets/api/ - Criar ticket
- GET /tickets/api/estatisticas/ - Estatísticas
- GET /tickets/api/<id>/ - Obter ticket
- PATCH /tickets/api/<id>/ - Atualizar ticket
- POST /tickets/api/<id>/atribuir/ - Atribuir ticket
- POST /tickets/api/<id>/fechar/ - Fechar ticket
- POST /tickets/api/<id>/reabrir/ - Reabrir ticket
"""

from django.urls import path
from . import views
from . import api_views

app_name = 'tickets'

urlpatterns = [
    # =========================================================================
    # Views HTML (Templates)
    # =========================================================================
    
    # Dashboard
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    
    # Listagem
    path('', views.TicketListView.as_view(), name='list'),
    
    # Criação
    path('criar/', views.TicketCreateView.as_view(), name='create'),
    
    # Detalhes
    path('<str:pk>/', views.TicketDetailView.as_view(), name='detail'),
    
    # Ações
    path('<str:pk>/atribuir/', views.TicketAtribuirView.as_view(), name='atribuir'),
    path('<str:pk>/fechar/', views.TicketFecharView.as_view(), name='fechar'),
    path('<str:pk>/reabrir/', views.TicketReabrirView.as_view(), name='reabrir'),
    path('<str:pk>/prioridade/', views.TicketAlterarPrioridadeView.as_view(), name='prioridade'),
    
    # =========================================================================
    # API JSON
    # =========================================================================
    
    # Listagem e criação
    path('api/', api_views.TicketAPIListView.as_view(), name='api_list'),
    
    # Estatísticas (antes do <pk> para não conflitar)
    path('api/estatisticas/', api_views.TicketAPIEstatisticasView.as_view(), name='api_estatisticas'),
    
    # Detalhes e atualização
    path('api/<str:pk>/', api_views.TicketAPIDetailView.as_view(), name='api_detail'),
    
    # Ações via API
    path('api/<str:pk>/atribuir/', api_views.TicketAPIAtribuirView.as_view(), name='api_atribuir'),
    path('api/<str:pk>/fechar/', api_views.TicketAPIFecharView.as_view(), name='api_fechar'),
    path('api/<str:pk>/reabrir/', api_views.TicketAPIReabrirView.as_view(), name='api_reabrir'),
]

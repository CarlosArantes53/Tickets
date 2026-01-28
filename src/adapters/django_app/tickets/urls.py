"""
URL patterns para o domínio de Tickets.

Endpoints:
- GET /tickets/ - Listar tickets
- POST /tickets/ - Criar ticket
- GET /tickets/<id>/ - Obter ticket
- PUT /tickets/<id>/ - Atualizar ticket
- DELETE /tickets/<id>/ - Deletar ticket
- POST /tickets/<id>/atribuir/ - Atribuir ticket
- POST /tickets/<id>/fechar/ - Fechar ticket
- POST /tickets/<id>/reabrir/ - Reabrir ticket

API:
- GET /api/tickets/ - API JSON (futuro)
"""

from django.urls import path
from . import views

app_name = 'tickets'

urlpatterns = [
    # Views HTML
    path('', views.TicketListView.as_view(), name='list'),
    path('criar/', views.TicketCreateView.as_view(), name='create'),
    path('<str:pk>/', views.TicketDetailView.as_view(), name='detail'),
    path('<str:pk>/atribuir/', views.TicketAtribuirView.as_view(), name='atribuir'),
    path('<str:pk>/fechar/', views.TicketFecharView.as_view(), name='fechar'),
    path('<str:pk>/reabrir/', views.TicketReabrirView.as_view(), name='reabrir'),
    
    # API JSON (simplificada)
    path('api/', views.TicketAPIListView.as_view(), name='api_list'),
    path('api/<str:pk>/', views.TicketAPIDetailView.as_view(), name='api_detail'),
]

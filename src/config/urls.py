"""
URL Configuration para TechSupport Manager.

Estrutura:
- /admin/ - Django Admin
- /api/tickets/ - API de Tickets (futuro)
- /tickets/ - Views de Tickets
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),
    
    # Tickets App
    path('tickets/', include('src.adapters.django_app.tickets.urls')),
    
    # Health check
    path('health/', lambda r: __import__('django.http', fromlist=['JsonResponse']).JsonResponse({'status': 'ok'})),
]

# Adicionar URLs de debug em desenvolvimento
from django.conf import settings
if settings.DEBUG:
    urlpatterns += [
        # Debug toolbar, etc (futuro)
    ]

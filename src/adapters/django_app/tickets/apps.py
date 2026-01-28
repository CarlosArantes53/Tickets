"""
Configuração do Django App para Tickets.

Configura o app e inicializa Dependency Injection wiring.
"""

from django.apps import AppConfig


class TicketsConfig(AppConfig):
    """Configuração do app Tickets."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'src.adapters.django_app.tickets'
    label = 'tickets'
    verbose_name = 'Gestão de Tickets'
    
    def ready(self):
        """
        Executado quando o app está pronto.
        
        Configura:
        - Dependency Injection wiring
        - Signal handlers
        """
        # Importar signals (quando implementados)
        # from . import signals
        
        # Nota: O wiring do dependency-injector será configurado
        # no container quando necessário usar @inject em views
        pass

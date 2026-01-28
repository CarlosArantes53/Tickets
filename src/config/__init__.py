"""
Configuração do projeto TechSupport Manager.

Módulos:
- settings: Configurações Django
- urls: Rotas principais
- wsgi: WSGI application
- celery: Configuração Celery para tarefas assíncronas
- container: Dependency Injection Container
"""

# Importar app Celery para que seja carregado com Django
try:
    from .celery import app as celery_app
    __all__ = ('celery_app',)
except ImportError:
    # Celery não instalado (em desenvolvimento sem broker)
    celery_app = None
    __all__ = ()

"""
Configuração do Celery para processamento assíncrono.

O Celery é usado para:
- Processar Domain Events de forma assíncrona
- Tarefas agendadas (limpeza, relatórios, etc)
- Notificações (email, push, etc)
- Processamento pesado fora do request/response

Arquitetura:
- Broker: RabbitMQ (mensagens entre Django e Workers)
- Backend: Redis (resultados de tarefas)
- Workers: Processos que executam as tarefas

Uso:
    # Iniciar worker
    celery -A src.config.celery worker -l INFO
    
    # Iniciar beat (tarefas agendadas)
    celery -A src.config.celery beat -l INFO
"""

import os
from celery import Celery
from kombu import Queue, Exchange

# Definir módulo de settings do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'src.config.settings')

# Criar aplicação Celery
app = Celery('techsupport')

# Carregar configurações do Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Configurações do Celery
app.conf.update(
    # Broker (RabbitMQ)
    broker_url=os.environ.get('CELERY_BROKER_URL', 'amqp://guest:guest@localhost:5672//'),
    
    # Backend de resultados (Redis)
    result_backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1'),
    
    # Serialização
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Timezone
    timezone='America/Sao_Paulo',
    enable_utc=True,
    
    # Configurações de execução
    task_acks_late=True,  # ACK após execução (mais seguro)
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # Uma tarefa por vez (mais justo)
    
    # Retry
    task_default_retry_delay=60,  # 1 minuto
    task_max_retries=3,
    
    # Resultados
    result_expires=3600,  # 1 hora
    
    # Monitoramento
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Definir filas
app.conf.task_queues = (
    Queue('default', Exchange('default'), routing_key='default'),
    Queue('events', Exchange('events'), routing_key='events.#'),
    Queue('notifications', Exchange('notifications'), routing_key='notifications.#'),
    Queue('reports', Exchange('reports'), routing_key='reports.#'),
)

# Roteamento de tarefas para filas
app.conf.task_routes = {
    'src.adapters.django_app.events.handlers.*': {'queue': 'events'},
    'src.adapters.django_app.notifications.*': {'queue': 'notifications'},
    'src.adapters.django_app.reports.*': {'queue': 'reports'},
}

# Auto-descoberta de tarefas nos apps Django
app.autodiscover_tasks([
    'src.adapters.django_app.events',
    'src.adapters.django_app.tickets',
])

# Tarefas agendadas (beat)
app.conf.beat_schedule = {
    # Verificar tickets atrasados a cada hora
    'check-overdue-tickets': {
        'task': 'src.adapters.django_app.events.handlers.check_overdue_tickets',
        'schedule': 3600.0,  # 1 hora em segundos
    },
    
    # Relatório diário às 8h
    'daily-report': {
        'task': 'src.adapters.django_app.events.handlers.generate_daily_report',
        'schedule': {
            'hour': 8,
            'minute': 0,
        },
    },
    
    # Limpar eventos antigos semanalmente
    'cleanup-old-events': {
        'task': 'src.adapters.django_app.events.handlers.cleanup_old_events',
        'schedule': 604800.0,  # 7 dias em segundos
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Tarefa de debug para testar Celery."""
    print(f'Request: {self.request!r}')

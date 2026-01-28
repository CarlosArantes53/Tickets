"""
Event Handlers - Processadores de Eventos de Domínio.

Handlers são executados de forma assíncrona via Celery quando
Domain Events são publicados. Isso permite:

- Desacoplamento: Produtores não conhecem consumidores
- Escalabilidade: Processamento distribuído em workers
- Resiliência: Retry automático em falhas
- Auditoria: Registro de todos os eventos processados

Tipos de Handlers:
- Notificação: Enviar emails, push, SMS
- Integração: Sincronizar com sistemas externos
- Agregação: Atualizar dashboards, métricas
- Workflow: Disparar ações automáticas

Padrão:
    @app.task(bind=True, ...)
    def handle_<evento>(self, event_data: dict) -> None:
        # Processar evento
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

logger = logging.getLogger(__name__)


# =============================================================================
# Event Handlers - Tickets
# =============================================================================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    acks_late=True,
)
def handle_ticket_criado(self, event_data: Dict[str, Any]) -> None:
    """
    Handler para evento TicketCriadoEvent.
    
    Ações:
    - Notificar equipe de suporte
    - Criar registro de auditoria
    - Atualizar métricas
    
    Args:
        event_data: Dados do evento serializado
    """
    try:
        ticket_id = event_data.get('aggregate_id')
        criador_id = event_data.get('criador_id')
        titulo = event_data.get('titulo')
        prioridade = event_data.get('prioridade', 'MEDIA')
        
        logger.info(
            f"[HANDLER] TicketCriado: {ticket_id} | "
            f"Criador: {criador_id} | Título: {titulo}"
        )
        
        # Notificar equipe se prioridade alta/crítica
        if prioridade in ('ALTA', 'CRITICA'):
            notify_support_team.delay(
                ticket_id=ticket_id,
                message=f"Novo ticket {prioridade}: {titulo}",
                priority='high' if prioridade == 'CRITICA' else 'normal'
            )
        
        # Registrar métrica
        record_metric.delay(
            metric_name='tickets_created',
            value=1,
            tags={'prioridade': prioridade}
        )
        
    except Exception as e:
        logger.error(f"Erro no handler TicketCriado: {e}", exc_info=True)
        raise


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def handle_ticket_atribuido(self, event_data: Dict[str, Any]) -> None:
    """
    Handler para evento TicketAtribuidoEvent.
    
    Ações:
    - Notificar técnico atribuído
    - Atualizar workload do técnico
    
    Args:
        event_data: Dados do evento serializado
    """
    try:
        ticket_id = event_data.get('aggregate_id')
        tecnico_id = event_data.get('tecnico_id')
        
        logger.info(
            f"[HANDLER] TicketAtribuido: {ticket_id} | "
            f"Técnico: {tecnico_id}"
        )
        
        # Notificar técnico
        notify_user.delay(
            user_id=tecnico_id,
            message=f"Você foi atribuído ao ticket {ticket_id[:8]}...",
            channel='email'
        )
        
        # Atualizar workload
        update_technician_workload.delay(tecnico_id=tecnico_id)
        
    except Exception as e:
        logger.error(f"Erro no handler TicketAtribuido: {e}", exc_info=True)
        raise


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def handle_ticket_fechado(self, event_data: Dict[str, Any]) -> None:
    """
    Handler para evento TicketFechadoEvent.
    
    Ações:
    - Notificar criador
    - Calcular tempo de resolução
    - Atualizar métricas de SLA
    
    Args:
        event_data: Dados do evento serializado
    """
    try:
        ticket_id = event_data.get('aggregate_id')
        fechado_por_id = event_data.get('fechado_por_id')
        
        logger.info(
            f"[HANDLER] TicketFechado: {ticket_id} | "
            f"Fechado por: {fechado_por_id}"
        )
        
        # Calcular tempo de resolução e atualizar métricas
        calculate_resolution_time.delay(ticket_id=ticket_id)
        
        # Registrar métrica
        record_metric.delay(
            metric_name='tickets_closed',
            value=1,
            tags={}
        )
        
    except Exception as e:
        logger.error(f"Erro no handler TicketFechado: {e}", exc_info=True)
        raise


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def handle_ticket_reaberto(self, event_data: Dict[str, Any]) -> None:
    """
    Handler para evento TicketReabertoEvent.
    
    Ações:
    - Notificar equipe
    - Registrar reabertura para análise
    
    Args:
        event_data: Dados do evento serializado
    """
    try:
        ticket_id = event_data.get('aggregate_id')
        reaberto_por_id = event_data.get('reaberto_por_id')
        motivo = event_data.get('motivo', '')
        
        logger.info(
            f"[HANDLER] TicketReaberto: {ticket_id} | "
            f"Reaberto por: {reaberto_por_id} | Motivo: {motivo}"
        )
        
        # Registrar métrica de reabertura
        record_metric.delay(
            metric_name='tickets_reopened',
            value=1,
            tags={'motivo': 'informado' if motivo else 'nao_informado'}
        )
        
    except Exception as e:
        logger.error(f"Erro no handler TicketReaberto: {e}", exc_info=True)
        raise


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def handle_prioridade_alterada(self, event_data: Dict[str, Any]) -> None:
    """
    Handler para evento PrioridadeAlteradaEvent.
    
    Ações:
    - Recalcular SLA se prioridade aumentou
    - Notificar técnico atribuído
    
    Args:
        event_data: Dados do evento serializado
    """
    try:
        ticket_id = event_data.get('aggregate_id')
        prioridade_anterior = event_data.get('prioridade_anterior')
        nova_prioridade = event_data.get('nova_prioridade')
        
        logger.info(
            f"[HANDLER] PrioridadeAlterada: {ticket_id} | "
            f"{prioridade_anterior} -> {nova_prioridade}"
        )
        
        # Se prioridade aumentou, notificar
        prioridades_ordem = ['BAIXA', 'MEDIA', 'ALTA', 'CRITICA']
        if (prioridades_ordem.index(nova_prioridade) > 
            prioridades_ordem.index(prioridade_anterior)):
            
            notify_support_team.delay(
                ticket_id=ticket_id,
                message=f"Ticket escalado para {nova_prioridade}",
                priority='high' if nova_prioridade == 'CRITICA' else 'normal'
            )
        
    except Exception as e:
        logger.error(f"Erro no handler PrioridadeAlterada: {e}", exc_info=True)
        raise


# =============================================================================
# Event Dispatcher (Router)
# =============================================================================

@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def dispatch_domain_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
    """
    Dispatcher central para Domain Events.
    
    Roteia eventos para os handlers apropriados.
    Este é o ponto de entrada para todos os eventos.
    
    Args:
        event_type: Tipo do evento (ex: 'TicketCriadoEvent')
        event_data: Dados do evento serializado
    """
    handlers = {
        'TicketCriadoEvent': handle_ticket_criado,
        'TicketAtribuidoEvent': handle_ticket_atribuido,
        'TicketFechadoEvent': handle_ticket_fechado,
        'TicketReabertoEvent': handle_ticket_reaberto,
        'PrioridadeAlteradaEvent': handle_prioridade_alterada,
    }
    
    handler = handlers.get(event_type)
    
    if handler:
        logger.info(f"[DISPATCHER] Roteando {event_type} para handler")
        handler.delay(event_data)
    else:
        logger.warning(f"[DISPATCHER] Handler não encontrado para {event_type}")


# =============================================================================
# Notification Tasks
# =============================================================================

@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def notify_user(
    self,
    user_id: str,
    message: str,
    channel: str = 'email',
    **kwargs
) -> None:
    """
    Notifica usuário por canal especificado.
    
    Args:
        user_id: ID do usuário
        message: Mensagem a enviar
        channel: Canal (email, push, sms)
    """
    logger.info(f"[NOTIFICATION] {channel.upper()} para {user_id}: {message}")
    
    # TODO: Implementar envio real
    # if channel == 'email':
    #     send_email(user_id, message)
    # elif channel == 'push':
    #     send_push(user_id, message)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_support_team(
    self,
    ticket_id: str,
    message: str,
    priority: str = 'normal'
) -> None:
    """
    Notifica equipe de suporte.
    
    Args:
        ticket_id: ID do ticket
        message: Mensagem
        priority: Prioridade da notificação
    """
    logger.info(
        f"[NOTIFICATION] Equipe de suporte [{priority}]: "
        f"Ticket {ticket_id[:8]}... - {message}"
    )
    
    # TODO: Implementar envio real (Slack, Teams, Email group)


# =============================================================================
# Metric Tasks
# =============================================================================

@shared_task(bind=True, ignore_result=True)
def record_metric(
    self,
    metric_name: str,
    value: float,
    tags: Dict[str, str] = None
) -> None:
    """
    Registra métrica para monitoramento.
    
    Args:
        metric_name: Nome da métrica
        value: Valor
        tags: Tags para dimensões
    """
    logger.info(
        f"[METRIC] {metric_name}={value} | tags={tags or {}}"
    )
    
    # TODO: Integrar com sistema de métricas (Prometheus, StatsD, etc)


@shared_task(bind=True)
def update_technician_workload(self, tecnico_id: str) -> None:
    """
    Atualiza métricas de workload do técnico.
    
    Args:
        tecnico_id: ID do técnico
    """
    logger.info(f"[WORKLOAD] Atualizando workload de {tecnico_id}")
    
    # TODO: Calcular tickets em aberto atribuídos ao técnico


@shared_task(bind=True)
def calculate_resolution_time(self, ticket_id: str) -> None:
    """
    Calcula tempo de resolução do ticket.
    
    Args:
        ticket_id: ID do ticket
    """
    logger.info(f"[METRIC] Calculando tempo de resolução: {ticket_id}")
    
    # TODO: Buscar ticket e calcular diferença entre criado_em e fechado_em


# =============================================================================
# Scheduled Tasks (Beat)
# =============================================================================

@shared_task(bind=True)
def check_overdue_tickets(self) -> int:
    """
    Verifica tickets atrasados e envia alertas.
    
    Executada periodicamente pelo Celery Beat.
    
    Returns:
        Número de tickets atrasados encontrados
    """
    logger.info("[SCHEDULED] Verificando tickets atrasados...")
    
    try:
        # Importação tardia para evitar circular import
        from src.config.container import get_container
        
        container = get_container()
        listar_service = container.services.listar_tickets_service()
        
        # Buscar todos os tickets
        tickets = listar_service.execute()
        
        # Filtrar atrasados
        atrasados = [t for t in tickets if t.esta_atrasado]
        
        logger.info(f"[SCHEDULED] Encontrados {len(atrasados)} tickets atrasados")
        
        # Notificar para cada ticket atrasado
        for ticket in atrasados:
            notify_support_team.delay(
                ticket_id=ticket.id,
                message=f"Ticket atrasado: {ticket.titulo}",
                priority='high'
            )
        
        # Registrar métrica
        record_metric.delay(
            metric_name='tickets_overdue',
            value=len(atrasados),
            tags={}
        )
        
        return len(atrasados)
        
    except Exception as e:
        logger.error(f"Erro ao verificar tickets atrasados: {e}", exc_info=True)
        return 0


@shared_task(bind=True)
def generate_daily_report(self) -> Dict[str, Any]:
    """
    Gera relatório diário de tickets.
    
    Executada diariamente pelo Celery Beat.
    
    Returns:
        Dados do relatório
    """
    logger.info("[SCHEDULED] Gerando relatório diário...")
    
    try:
        from src.config.container import get_container
        
        container = get_container()
        contar_service = container.services.contar_tickets_service()
        
        estatisticas = contar_service.execute()
        
        report = {
            'data': datetime.now().isoformat(),
            'total_tickets': estatisticas.get('total', 0),
            'por_status': estatisticas.get('por_status', {}),
        }
        
        logger.info(f"[SCHEDULED] Relatório gerado: {report}")
        
        # TODO: Enviar relatório por email
        
        return report
        
    except Exception as e:
        logger.error(f"Erro ao gerar relatório: {e}", exc_info=True)
        return {}


@shared_task(bind=True)
def cleanup_old_events(self, days: int = 90) -> int:
    """
    Limpa eventos antigos do Event Store.
    
    Executada semanalmente pelo Celery Beat.
    
    Args:
        days: Número de dias para manter eventos
        
    Returns:
        Número de eventos removidos
    """
    logger.info(f"[SCHEDULED] Limpando eventos com mais de {days} dias...")
    
    try:
        from src.adapters.django_app.tickets.models import DomainEventModel
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        deleted, _ = DomainEventModel.objects.filter(
            occurred_at__lt=cutoff_date
        ).delete()
        
        logger.info(f"[SCHEDULED] {deleted} eventos removidos")
        
        return deleted
        
    except Exception as e:
        logger.error(f"Erro ao limpar eventos: {e}", exc_info=True)
        return 0

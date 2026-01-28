"""
Event Publishers - Publicadores de Eventos de Domínio.

Responsável por publicar eventos para handlers assíncronos.
Implementações:
- LoggingEventPublisher: Apenas loga (desenvolvimento)
- CeleryEventPublisher: Publica via Celery (produção)
- InMemoryEventPublisher: Para testes

Padrão Observer/Pub-Sub para desacoplamento.
"""

from abc import ABC, abstractmethod
from typing import List, Callable, Dict, Any, Optional
import logging
import json

from src.core.shared.events import DomainEvent

logger = logging.getLogger(__name__)


class EventPublisher(ABC):
    """
    Interface abstrata para publicadores de eventos.
    
    Define contrato que todas as implementações devem seguir.
    """
    
    @abstractmethod
    def publish(self, event: DomainEvent) -> None:
        """
        Publica um único evento.
        
        Args:
            event: Evento de domínio a publicar
        """
        raise NotImplementedError
    
    @abstractmethod
    def publish_batch(self, events: List[DomainEvent]) -> None:
        """
        Publica múltiplos eventos.
        
        Args:
            events: Lista de eventos a publicar
        """
        raise NotImplementedError


class LoggingEventPublisher(EventPublisher):
    """
    Publisher que apenas loga eventos.
    
    Usado em desenvolvimento para visualizar eventos
    sem necessidade de infraestrutura de mensageria.
    """
    
    def __init__(self, log_level: int = logging.INFO, dispatch_to_celery: bool = False):
        """
        Inicializa publisher.
        
        Args:
            log_level: Nível de log para eventos
            dispatch_to_celery: Se deve também despachar para Celery
        """
        self._log_level = log_level
        self._dispatch_to_celery = dispatch_to_celery
        self._handlers: Dict[str, List[Callable]] = {}
    
    def publish(self, event: DomainEvent) -> None:
        """
        Loga evento e opcionalmente despacha para Celery.
        
        Args:
            event: Evento a publicar
        """
        event_data = event.to_dict()
        
        logger.log(
            self._log_level,
            f"[EVENT] {event.event_type} | "
            f"aggregate={event.aggregate_id} | "
            f"data={json.dumps(event_data, default=str)}"
        )
        
        # Despachar para Celery se configurado
        if self._dispatch_to_celery:
            self._dispatch_to_celery_handler(event)
        
        # Executar handlers síncronos locais
        self._dispatch_to_handlers(event)
    
    def publish_batch(self, events: List[DomainEvent]) -> None:
        """Loga múltiplos eventos."""
        for event in events:
            self.publish(event)
    
    def _dispatch_to_celery_handler(self, event: DomainEvent) -> None:
        """Despacha evento para Celery."""
        try:
            from src.adapters.django_app.events.handlers import dispatch_domain_event
            dispatch_domain_event.delay(event.event_type, event.to_dict())
        except Exception as e:
            logger.warning(f"Falha ao despachar para Celery: {e}")
    
    def register_handler(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], None]
    ) -> None:
        """Registra handler para tipo de evento."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    def _dispatch_to_handlers(self, event: DomainEvent) -> None:
        """Despacha evento para handlers registrados."""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Erro em handler para {event.event_type}: {e}")


class CeleryEventPublisher(EventPublisher):
    """
    Publisher que envia eventos para Celery.
    
    Usado em produção para processamento assíncrono.
    """
    
    def __init__(self, also_log: bool = True):
        """
        Inicializa publisher.
        
        Args:
            also_log: Se deve também logar eventos
        """
        self._also_log = also_log
    
    def publish(self, event: DomainEvent) -> None:
        """
        Publica evento via Celery.
        
        Args:
            event: Evento a publicar
        """
        event_data = event.to_dict()
        
        if self._also_log:
            logger.info(
                f"[EVENT->CELERY] {event.event_type} | "
                f"aggregate={event.aggregate_id}"
            )
        
        try:
            from src.adapters.django_app.events.handlers import dispatch_domain_event
            dispatch_domain_event.delay(event.event_type, event_data)
        except Exception as e:
            logger.error(f"Falha ao publicar evento no Celery: {e}", exc_info=True)
            # Em caso de falha, não quebra o fluxo principal
    
    def publish_batch(self, events: List[DomainEvent]) -> None:
        """Publica múltiplos eventos via Celery."""
        for event in events:
            self.publish(event)


class InMemoryEventPublisher(EventPublisher):
    """
    Publisher em memória para testes.
    
    Armazena eventos publicados para verificação em testes.
    """
    
    def __init__(self):
        """Inicializa publisher."""
        self._published_events: List[DomainEvent] = []
        self._handlers: Dict[str, List[Callable]] = {}
    
    def publish(self, event: DomainEvent) -> None:
        """Armazena evento na lista."""
        self._published_events.append(event)
        self._dispatch_to_handlers(event)
    
    def publish_batch(self, events: List[DomainEvent]) -> None:
        """Armazena múltiplos eventos."""
        for event in events:
            self.publish(event)
    
    @property
    def published_events(self) -> List[DomainEvent]:
        """Retorna eventos publicados."""
        return self._published_events.copy()
    
    def clear(self) -> None:
        """Limpa eventos armazenados."""
        self._published_events.clear()
    
    def get_events_by_type(self, event_type: str) -> List[DomainEvent]:
        """Filtra eventos por tipo."""
        return [e for e in self._published_events if e.event_type == event_type]
    
    def register_handler(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], None]
    ) -> None:
        """Registra handler para tipo de evento."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    def _dispatch_to_handlers(self, event: DomainEvent) -> None:
        """Despacha evento para handlers."""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Erro em handler de teste: {e}")


class CompositeEventPublisher(EventPublisher):
    """
    Publisher que delega para múltiplos publishers.
    
    Útil para publicar em múltiplos destinos simultaneamente.
    """
    
    def __init__(self, publishers: List[EventPublisher] = None):
        """Inicializa com lista de publishers."""
        self._publishers = publishers or []
    
    def add_publisher(self, publisher: EventPublisher) -> None:
        """Adiciona publisher à lista."""
        self._publishers.append(publisher)
    
    def publish(self, event: DomainEvent) -> None:
        """Publica em todos os publishers."""
        for publisher in self._publishers:
            try:
                publisher.publish(event)
            except Exception as e:
                logger.error(
                    f"Erro ao publicar em {publisher.__class__.__name__}: {e}"
                )
    
    def publish_batch(self, events: List[DomainEvent]) -> None:
        """Publica batch em todos os publishers."""
        for publisher in self._publishers:
            try:
                publisher.publish_batch(events)
            except Exception as e:
                logger.error(
                    f"Erro ao publicar batch em {publisher.__class__.__name__}: {e}"
                )


def get_event_publisher(use_celery: bool = False) -> EventPublisher:
    """
    Factory para obter publisher apropriado.
    
    Args:
        use_celery: Se deve usar Celery para processamento assíncrono
        
    Returns:
        Publisher configurado
    """
    if use_celery:
        return CeleryEventPublisher()
    return LoggingEventPublisher(dispatch_to_celery=False)

"""
Event Publishers - Publicadores de Eventos de Domínio.

Responsável por publicar eventos para handlers assíncronos.
Implementações:
- LoggingEventPublisher: Apenas loga (desenvolvimento)
- CeleryEventPublisher: Publica via Celery (produção - Etapa 4)
- RabbitMQEventPublisher: Publica via RabbitMQ (produção - Etapa 4)

Padrão Observer/Pub-Sub para desacoplamento.
"""

from abc import ABC, abstractmethod
from typing import List, Callable, Dict, Any
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
    
    def __init__(self, log_level: int = logging.INFO):
        """
        Inicializa publisher.
        
        Args:
            log_level: Nível de log para eventos
        """
        self._log_level = log_level
        self._handlers: Dict[str, List[Callable]] = {}
    
    def publish(self, event: DomainEvent) -> None:
        """
        Loga evento e executa handlers registrados.
        
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
        
        # Executar handlers síncronos (para desenvolvimento)
        self._dispatch_to_handlers(event)
    
    def publish_batch(self, events: List[DomainEvent]) -> None:
        """
        Loga múltiplos eventos.
        
        Args:
            events: Lista de eventos
        """
        for event in events:
            self.publish(event)
    
    def register_handler(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], None]
    ) -> None:
        """
        Registra handler para tipo de evento.
        
        Permite executar handlers síncronos em desenvolvimento.
        
        Args:
            event_type: Tipo do evento (ex: 'TicketCriadoEvent')
            handler: Função que processa o evento
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        
        self._handlers[event_type].append(handler)
        logger.debug(f"Handler registered for {event_type}")
    
    def _dispatch_to_handlers(self, event: DomainEvent) -> None:
        """
        Despacha evento para handlers registrados.
        
        Args:
            event: Evento a despachar
        """
        handlers = self._handlers.get(event.event_type, [])
        
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    f"Error in handler for {event.event_type}: {e}",
                    exc_info=True
                )


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
        """
        Armazena evento na lista.
        
        Args:
            event: Evento a armazenar
        """
        self._published_events.append(event)
        self._dispatch_to_handlers(event)
    
    def publish_batch(self, events: List[DomainEvent]) -> None:
        """
        Armazena múltiplos eventos.
        
        Args:
            events: Lista de eventos
        """
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
        """
        Filtra eventos por tipo.
        
        Args:
            event_type: Tipo do evento
            
        Returns:
            Lista de eventos do tipo especificado
        """
        return [e for e in self._published_events if e.event_type == event_type]
    
    def register_handler(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], None]
    ) -> None:
        """
        Registra handler para tipo de evento.
        
        Args:
            event_type: Tipo do evento
            handler: Função handler
        """
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
                logger.error(f"Error in test handler: {e}")


class CompositeEventPublisher(EventPublisher):
    """
    Publisher que delega para múltiplos publishers.
    
    Útil para publicar em múltiplos destinos simultaneamente
    (ex: log + message broker).
    """
    
    def __init__(self, publishers: List[EventPublisher] = None):
        """
        Inicializa com lista de publishers.
        
        Args:
            publishers: Lista de publishers para delegar
        """
        self._publishers = publishers or []
    
    def add_publisher(self, publisher: EventPublisher) -> None:
        """
        Adiciona publisher à lista.
        
        Args:
            publisher: Publisher a adicionar
        """
        self._publishers.append(publisher)
    
    def publish(self, event: DomainEvent) -> None:
        """
        Publica em todos os publishers.
        
        Args:
            event: Evento a publicar
        """
        for publisher in self._publishers:
            try:
                publisher.publish(event)
            except Exception as e:
                logger.error(
                    f"Error publishing to {publisher.__class__.__name__}: {e}",
                    exc_info=True
                )
    
    def publish_batch(self, events: List[DomainEvent]) -> None:
        """
        Publica batch em todos os publishers.
        
        Args:
            events: Lista de eventos
        """
        for publisher in self._publishers:
            try:
                publisher.publish_batch(events)
            except Exception as e:
                logger.error(
                    f"Error publishing batch to {publisher.__class__.__name__}: {e}",
                    exc_info=True
                )

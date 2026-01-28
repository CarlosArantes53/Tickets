"""
Domain Events - Comunicação Assíncrona entre Domínios.

Este módulo define a infraestrutura base para Domain Events,
permitindo comunicação desacoplada entre diferentes partes do sistema.

Características:
- Imutáveis após criação
- Auto-geração de ID e timestamp
- Serializáveis para persistência/transporte
- Rastreáveis via aggregate_id

Pattern: Event Sourcing Simplificado
    - Eventos são publicados após commit do UoW
    - Handlers assíncronos processam eventos
    - Event Store persiste histórico (opcional)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, ClassVar
import uuid


@dataclass(frozen=False)  # frozen=False para permitir inicialização customizada
class DomainEvent(ABC):
    """
    Classe base abstrata para Domain Events.
    
    Um Domain Event representa algo significativo que aconteceu
    no domínio e que pode ser relevante para outras partes do sistema.
    
    Características:
    - Nomeados no passado (TicketCriado, não CriarTicket)
    - Imutáveis (representam fatos históricos)
    - Contêm dados necessários para reconstruir o que aconteceu
    
    Attributes:
        event_id: Identificador único do evento
        aggregate_id: ID do agregado que gerou o evento
        aggregate_type: Tipo do agregado (ex: "Ticket")
        occurred_at: Momento em que o evento ocorreu
        version: Versão do schema do evento (para evolução)
    
    Example:
        @dataclass
        class TicketCriadoEvent(DomainEvent):
            criador_id: str
            titulo: str
            
            @property
            def aggregate_type(self) -> str:
                return "Ticket"
    """
    
    # Campos comuns a todos os eventos
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    aggregate_id: str = ""
    occurred_at: datetime = field(default_factory=datetime.now)
    version: int = 1  # Para versionamento de schema
    
    # Metadata para serialização
    _event_type: ClassVar[str] = ""
    
    def __post_init__(self):
        """Validação após inicialização."""
        if not self.aggregate_id:
            raise ValueError("aggregate_id é obrigatório")
    
    @property
    @abstractmethod
    def aggregate_type(self) -> str:
        """
        Retorna o tipo do agregado que gerou este evento.
        
        Deve ser implementado por subclasses.
        
        Returns:
            Nome do tipo do agregado (ex: "Ticket", "Agendamento")
        """
        ...
    
    @property
    def event_type(self) -> str:
        """
        Retorna o tipo do evento (nome da classe).
        
        Returns:
            Nome da classe do evento
        """
        return self.__class__.__name__
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serializa evento para dicionário.
        
        Útil para:
        - Persistência em Event Store
        - Envio via message broker
        - Logging estruturado
        
        Returns:
            Dicionário com dados do evento
        """
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "occurred_at": self.occurred_at.isoformat(),
            "version": self.version,
            "data": self._get_event_data(),
        }
    
    def _get_event_data(self) -> Dict[str, Any]:
        """
        Retorna dados específicos do evento (para override em subclasses).
        
        Subclasses devem sobrescrever para incluir seus campos específicos.
        
        Returns:
            Dicionário com dados específicos do evento
        """
        # Pega todos os campos que não são os da classe base
        base_fields = {"event_id", "aggregate_id", "occurred_at", "version"}
        return {
            key: value
            for key, value in self.__dict__.items()
            if key not in base_fields and not key.startswith("_")
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DomainEvent":
        """
        Reconstrói evento a partir de dicionário.
        
        Factory method para deserialização de eventos persistidos.
        
        Args:
            data: Dicionário com dados do evento
            
        Returns:
            Instância do evento reconstruída
            
        Note:
            Subclasses devem implementar sua própria versão se tiverem
            campos adicionais que precisam de tratamento especial.
        """
        event_data = data.get("data", {})
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            aggregate_id=data["aggregate_id"],
            occurred_at=datetime.fromisoformat(data["occurred_at"]),
            version=data.get("version", 1),
            **event_data,
        )
    
    def __repr__(self) -> str:
        """Representação string do evento para debugging."""
        return (
            f"{self.event_type}("
            f"event_id={self.event_id[:8]}..., "
            f"aggregate_id={self.aggregate_id}, "
            f"occurred_at={self.occurred_at.isoformat()}"
            f")"
        )


class EventMetadata:
    """
    Metadata adicional para rastreamento de eventos.
    
    Útil para:
    - Correlation ID (rastrear cadeia de eventos)
    - Causation ID (evento que causou este)
    - User ID (quem gerou o evento)
    
    Attributes:
        correlation_id: ID para rastrear fluxo de eventos relacionados
        causation_id: ID do evento que causou este
        user_id: ID do usuário que iniciou a ação
        timestamp: Momento do registro (pode diferir de occurred_at)
    """
    
    def __init__(
        self,
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.causation_id = causation_id
        self.user_id = user_id
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializa metadata para dicionário."""
        return {
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
        }

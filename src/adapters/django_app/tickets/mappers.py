"""
Mappers para conversão entre Entities (Core) e Models (Django).

Responsabilidades:
- Converter TicketEntity → TicketModel (para persistência)
- Converter TicketModel → TicketEntity (para uso no Core)
- Converter DomainEvent → DomainEventModel (para Event Store)

Princípios:
- Mappers são stateless
- Não contêm lógica de negócio
- Tratam apenas conversão de dados

Por que Mappers separados?
- Evita vazamento de detalhes do ORM para o Core
- Permite evolução independente de Entity e Model
- Facilita migração para outro ORM/banco
"""

from datetime import datetime
from typing import Optional, List

from src.core.tickets.entities import (
    TicketEntity,
    TicketStatus,
    TicketPriority,
)
from src.core.shared.events import DomainEvent

from .models import (
    TicketModel,
    TicketHistoryModel,
    DomainEventModel,
)


class TicketMapper:
    """
    Mapper para conversão entre TicketEntity e TicketModel.
    
    Responsável por:
    - to_model(): Entity → Model
    - to_entity(): Model → Entity
    - to_entity_list(): List[Model] → List[Entity]
    """
    
    @staticmethod
    def to_model(entity: TicketEntity) -> TicketModel:
        """
        Converte TicketEntity para TicketModel.
        
        Usado para persistência de novas entidades ou atualizações.
        
        Args:
            entity: Entidade de domínio
            
        Returns:
            Model Django pronto para salvar
            
        Note:
            Não chama .save() - deixa isso para o Repository
        """
        return TicketModel(
            id=entity.id,
            titulo=entity.titulo,
            descricao=entity.descricao,
            categoria=entity.categoria,
            status=entity.status.value,
            prioridade=entity.prioridade.value,
            criador_id=entity.criador_id,
            atribuido_a_id=entity.atribuido_a_id,
            criado_em=entity.criado_em,
            atualizado_em=entity.atualizado_em,
            sla_prazo=entity.sla_prazo,
            tags=entity.tags,
        )
    
    @staticmethod
    def to_entity(model: TicketModel) -> TicketEntity:
        """
        Converte TicketModel para TicketEntity.
        
        Usado para carregar entidades do banco para uso no Core.
        
        Args:
            model: Model Django carregado do banco
            
        Returns:
            Entidade de domínio
            
        Note:
            Bypassa validações do factory method .criar()
            pois dados já foram validados na criação original
        """
        # Converter strings para Enums
        status = TicketStatus(model.status)
        prioridade = TicketPriority(model.prioridade)
        
        # Criar entity diretamente (sem validações - dados já validados)
        entity = TicketEntity(
            id=model.id,
            titulo=model.titulo,
            descricao=model.descricao,
            categoria=model.categoria,
            status=status,
            prioridade=prioridade,
            criador_id=model.criador_id,
            atribuido_a_id=model.atribuido_a_id,
            criado_em=model.criado_em,
            atualizado_em=model.atualizado_em,
            sla_prazo=model.sla_prazo,
            tags=list(model.tags) if model.tags else [],
        )
        
        return entity
    
    @staticmethod
    def to_entity_list(models: List[TicketModel]) -> List[TicketEntity]:
        """
        Converte lista de Models para lista de Entities.
        
        Args:
            models: Lista de models Django
            
        Returns:
            Lista de entidades de domínio
        """
        return [TicketMapper.to_entity(model) for model in models]
    
    @staticmethod
    def update_model(model: TicketModel, entity: TicketEntity) -> TicketModel:
        """
        Atualiza Model existente com dados da Entity.
        
        Usado para updates parciais sem criar novo model.
        
        Args:
            model: Model existente no banco
            entity: Entity com dados atualizados
            
        Returns:
            Model atualizado (não salvo)
        """
        model.titulo = entity.titulo
        model.descricao = entity.descricao
        model.categoria = entity.categoria
        model.status = entity.status.value
        model.prioridade = entity.prioridade.value
        model.atribuido_a_id = entity.atribuido_a_id
        model.atualizado_em = entity.atualizado_em
        model.sla_prazo = entity.sla_prazo
        model.tags = entity.tags
        
        return model


class DomainEventMapper:
    """
    Mapper para conversão entre DomainEvent e DomainEventModel.
    
    Usado para persistir eventos no Event Store.
    """
    
    @staticmethod
    def to_model(
        event: DomainEvent,
        sequence: int = 0,
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> DomainEventModel:
        """
        Converte DomainEvent para DomainEventModel.
        
        Args:
            event: Evento de domínio
            sequence: Número de sequência no agregado
            correlation_id: ID de correlação (opcional)
            causation_id: ID do evento causador (opcional)
            user_id: ID do usuário (opcional)
            
        Returns:
            Model pronto para persistência
        """
        return DomainEventModel(
            event_id=event.event_id,
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            event_data=event._get_event_data(),
            version=event.version,
            sequence=sequence,
            occurred_at=event.occurred_at,
            correlation_id=correlation_id,
            causation_id=causation_id,
            user_id=user_id,
        )
    
    @staticmethod
    def to_history_model(
        event: DomainEvent,
        ticket_id: str,
        user_id: Optional[str] = None,
    ) -> TicketHistoryModel:
        """
        Converte DomainEvent para TicketHistoryModel.
        
        Usado para histórico específico de tickets.
        
        Args:
            event: Evento de domínio
            ticket_id: ID do ticket
            user_id: ID do usuário
            
        Returns:
            Model de histórico
        """
        return TicketHistoryModel(
            ticket_id=ticket_id,
            event_type=event.event_type,
            event_data=event.to_dict(),
            user_id=user_id,
        )

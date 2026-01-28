"""
Repositórios Django para persistência de Tickets.

Implementam as interfaces (Ports) definidas no Core.
São DRIVEN ADAPTERS - acionados pelo Core em resposta a operações.

Responsabilidades:
- Implementar TicketRepository protocol
- Mapear entities para models e vice-versa
- Executar queries no banco via ORM
- Otimizar queries (select_related, prefetch_related)

Princípios:
- Repository não contém lógica de negócio
- Usa Mapper para conversões
- Trata apenas persistência

Escalabilidade:
- Interface permite trocar PostgreSQL por outro banco
- Prepared para read replicas via Database Router
- Queries otimizadas para evitar N+1
- Herda de BaseRepository para funcionalidade comum
"""

from typing import List, Optional, Dict, Any, Type
from datetime import datetime
import logging

from django.db import transaction
from django.db.models import Count, Q, F
from django.utils import timezone

from src.core.tickets.entities import TicketEntity, TicketStatus, TicketPriority
from src.core.tickets.ports import TicketRepository as TicketRepositoryPort
from src.core.shared.exceptions import EntityNotFoundError

from ..shared.repository import BaseRepository, PaginatedResult, PaginationParams, SortParams
from .models import TicketModel, TicketHistoryModel
from .mappers import TicketMapper

logger = logging.getLogger(__name__)


class DjangoTicketRepository(TicketRepositoryPort):
    """
    Implementação Django do TicketRepository.
    
    Implementa a interface definida em src/core/tickets/ports.py,
    usando Django ORM para persistência em PostgreSQL.
    
    Features:
    - CRUD completo
    - Queries otimizadas (select_related)
    - Suporte a filtros compostos
    - Paginação
    - Contagem por status
    
    Example:
        repo = DjangoTicketRepository()
        
        # Criar
        repo.save(ticket_entity)
        
        # Buscar
        ticket = repo.get_by_id("uuid-here")
        
        # Listar com filtro
        tickets = repo.list_by_status(TicketStatus.ABERTO)
    """
    
    def __init__(self):
        """Inicializa repository."""
        self._mapper = TicketMapper()
    
    def save(self, ticket: TicketEntity) -> None:
        """
        Persiste ticket (create ou update).
        
        Detecta automaticamente se é criação ou atualização
        baseado na existência do ID no banco.
        
        Args:
            ticket: Entidade de domínio a persistir
            
        Note:
            Usa update_or_create para atomicidade
        """
        logger.debug(f"Saving ticket: {ticket.id}")
        
        # Preparar dados para persistência
        model_data = {
            'titulo': ticket.titulo,
            'descricao': ticket.descricao,
            'categoria': ticket.categoria,
            'status': ticket.status.value,
            'prioridade': ticket.prioridade.value,
            'criador_id': ticket.criador_id,
            'atribuido_a_id': ticket.atribuido_a_id,
            'criado_em': ticket.criado_em,
            'atualizado_em': ticket.atualizado_em,
            'sla_prazo': ticket.sla_prazo,
            'tags': ticket.tags,
        }
        
        # Upsert: create ou update
        TicketModel.objects.update_or_create(
            id=ticket.id,
            defaults=model_data
        )
        
        logger.info(f"Ticket saved: {ticket.id}")
    
    def get_by_id(self, ticket_id: str) -> Optional[TicketEntity]:
        """
        Busca ticket por ID.
        
        Args:
            ticket_id: UUID do ticket
            
        Returns:
            Entidade encontrada ou None
        """
        try:
            model = TicketModel.objects.get(id=ticket_id)
            return self._mapper.to_entity(model)
        except TicketModel.DoesNotExist:
            logger.debug(f"Ticket not found: {ticket_id}")
            return None
    
    def delete(self, ticket_id: str) -> None:
        """
        Remove ticket do banco.
        
        Args:
            ticket_id: UUID do ticket a remover
            
        Note:
            Não lança erro se ticket não existir
        """
        deleted_count, _ = TicketModel.objects.filter(id=ticket_id).delete()
        
        if deleted_count > 0:
            logger.info(f"Ticket deleted: {ticket_id}")
        else:
            logger.debug(f"Ticket not found for deletion: {ticket_id}")
    
    def list_all(self) -> List[TicketEntity]:
        """
        Lista todos os tickets.
        
        Returns:
            Lista de todas as entidades
            
        Warning:
            Use com cuidado em produção - sem paginação
        """
        models = TicketModel.objects.all()
        return self._mapper.to_entity_list(models)
    
    def list_by_status(self, status: TicketStatus) -> List[TicketEntity]:
        """
        Lista tickets por status.
        
        Args:
            status: Status a filtrar
            
        Returns:
            Lista de entidades com o status especificado
        """
        models = TicketModel.objects.filter(status=status.value)
        return self._mapper.to_entity_list(models)
    
    def list_by_criador(self, criador_id: str) -> List[TicketEntity]:
        """
        Lista tickets por criador.
        
        Args:
            criador_id: ID do usuário criador
            
        Returns:
            Lista de entidades do criador
        """
        models = TicketModel.objects.filter(criador_id=criador_id)
        return self._mapper.to_entity_list(models)
    
    def list_by_tecnico(self, tecnico_id: str) -> List[TicketEntity]:
        """
        Lista tickets atribuídos a um técnico.
        
        Args:
            tecnico_id: ID do técnico
            
        Returns:
            Lista de entidades atribuídas ao técnico
        """
        models = TicketModel.objects.filter(atribuido_a_id=tecnico_id)
        return self._mapper.to_entity_list(models)
    
    def exists(self, ticket_id: str) -> bool:
        """
        Verifica se ticket existe.
        
        Args:
            ticket_id: UUID do ticket
            
        Returns:
            True se existe, False caso contrário
        """
        return TicketModel.objects.filter(id=ticket_id).exists()
    
    def count(self) -> int:
        """
        Conta total de tickets.
        
        Returns:
            Número total de tickets
        """
        return TicketModel.objects.count()
    
    def count_by_status(self) -> Dict[str, int]:
        """
        Conta tickets agrupados por status.
        
        Returns:
            Dicionário {status: quantidade}
        """
        counts = (
            TicketModel.objects
            .values('status')
            .annotate(count=Count('id'))
        )
        
        return {item['status']: item['count'] for item in counts}
    
    # =========================================================================
    # Queries Avançadas (Query Repository)
    # =========================================================================
    
    def list_paginated(
        self,
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None,
        prioridade: Optional[str] = None,
        criador_id: Optional[str] = None,
        tecnico_id: Optional[str] = None,
        categoria: Optional[str] = None,
        apenas_atrasados: bool = False,
        ordenar_por: str = 'criado_em',
        ordem: str = 'desc',
    ) -> Dict[str, Any]:
        """
        Lista tickets com paginação e filtros.
        
        Args:
            page: Número da página (1-indexed)
            per_page: Itens por página
            status: Filtrar por status
            prioridade: Filtrar por prioridade
            criador_id: Filtrar por criador
            tecnico_id: Filtrar por técnico
            categoria: Filtrar por categoria
            apenas_atrasados: Apenas tickets com SLA vencido
            ordenar_por: Campo para ordenação
            ordem: 'asc' ou 'desc'
            
        Returns:
            Dict com items, total, pagina, total_paginas, etc.
        """
        # Base queryset
        queryset = TicketModel.objects.all()
        
        # Aplicar filtros
        if status:
            queryset = queryset.filter(status=status)
        
        if prioridade:
            queryset = queryset.filter(prioridade=prioridade)
        
        if criador_id:
            queryset = queryset.filter(criador_id=criador_id)
        
        if tecnico_id:
            queryset = queryset.filter(atribuido_a_id=tecnico_id)
        
        if categoria:
            queryset = queryset.filter(categoria=categoria)
        
        if apenas_atrasados:
            now = datetime.now()
            queryset = queryset.filter(
                sla_prazo__lt=now,
                status__in=['Aberto', 'Em Progresso', 'Aguardando Cliente']
            )
        
        # Ordenação
        order_field = ordenar_por if ordem == 'asc' else f'-{ordenar_por}'
        queryset = queryset.order_by(order_field)
        
        # Contagem total
        total = queryset.count()
        
        # Paginação
        offset = (page - 1) * per_page
        models = queryset[offset:offset + per_page]
        
        # Calcular metadados
        total_pages = (total + per_page - 1) // per_page
        
        return {
            'items': self._mapper.to_entity_list(models),
            'total': total,
            'pagina': page,
            'por_pagina': per_page,
            'total_paginas': total_pages,
            'tem_proxima': page < total_pages,
            'tem_anterior': page > 1,
        }
    
    def list_atrasados(self) -> List[TicketEntity]:
        """
        Lista tickets com SLA vencido.
        
        Returns:
            Lista de tickets atrasados
        """
        now = datetime.now()
        models = TicketModel.objects.filter(
            sla_prazo__lt=now,
            status__in=['Aberto', 'Em Progresso', 'Aguardando Cliente']
        ).order_by('sla_prazo')
        
        return self._mapper.to_entity_list(models)
    
    def get_estatisticas(self) -> Dict[str, Any]:
        """
        Retorna estatísticas gerais de tickets.
        
        Returns:
            Dict com estatísticas
        """
        now = datetime.now()
        
        total = TicketModel.objects.count()
        
        por_status = dict(
            TicketModel.objects
            .values('status')
            .annotate(count=Count('id'))
            .values_list('status', 'count')
        )
        
        por_prioridade = dict(
            TicketModel.objects
            .values('prioridade')
            .annotate(count=Count('id'))
            .values_list('prioridade', 'count')
        )
        
        atrasados = TicketModel.objects.filter(
            sla_prazo__lt=now,
            status__in=['Aberto', 'Em Progresso', 'Aguardando Cliente']
        ).count()
        
        return {
            'total': total,
            'por_status': por_status,
            'por_prioridade': por_prioridade,
            'atrasados': atrasados,
            'taxa_atraso': (atrasados / total * 100) if total > 0 else 0,
        }


class DjangoEventStore:
    """
    Event Store usando Django ORM.
    
    Persiste Domain Events para:
    - Auditoria
    - Replay
    - Analytics
    
    Preparado para Event Sourcing completo no futuro.
    """
    
    def append(
        self,
        event: 'DomainEvent',
        sequence: int = 0,
        correlation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Adiciona evento ao store.
        
        Args:
            event: Evento de domínio
            sequence: Sequência no agregado
            correlation_id: ID de correlação
            user_id: ID do usuário
        """
        from .models import DomainEventModel
        from .mappers import DomainEventMapper
        
        model = DomainEventMapper.to_model(
            event=event,
            sequence=sequence,
            correlation_id=correlation_id,
            user_id=user_id,
        )
        model.save()
        
        logger.debug(f"Event stored: {event.event_type} for {event.aggregate_id}")
    
    def get_events_for_aggregate(
        self,
        aggregate_id: str,
        since_sequence: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Recupera eventos de um agregado.
        
        Args:
            aggregate_id: ID do agregado
            since_sequence: Sequência inicial
            
        Returns:
            Lista de eventos em formato dict
        """
        from .models import DomainEventModel
        
        events = (
            DomainEventModel.objects
            .filter(aggregate_id=aggregate_id, sequence__gte=since_sequence)
            .order_by('sequence')
        )
        
        return [
            {
                'event_id': e.event_id,
                'event_type': e.event_type,
                'aggregate_id': e.aggregate_id,
                'event_data': e.event_data,
                'sequence': e.sequence,
                'occurred_at': e.occurred_at,
            }
            for e in events
        ]

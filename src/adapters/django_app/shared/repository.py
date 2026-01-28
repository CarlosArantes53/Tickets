"""
Repository Base - Implementação base de repositórios com Django ORM.

Fornece funcionalidades comuns para todos os repositórios:
- CRUD básico
- Paginação
- Ordenação
- Filtros genéricos
- Otimização de queries (select_related, prefetch_related)

Princípios:
- Repositórios são stateless
- Não contêm lógica de negócio
- Apenas persistência e queries

Escalabilidade:
- Interface permite trocar implementação
- Prepared para read replicas
- Suporte a cache transparente
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from dataclasses import dataclass
import logging

from django.db import models
from django.db.models import QuerySet, Q, Count

logger = logging.getLogger(__name__)

# Type variables
T = TypeVar("T")  # Entity type
M = TypeVar("M", bound=models.Model)  # Model type


@dataclass
class PaginationParams:
    """Parâmetros de paginação."""
    page: int = 1
    per_page: int = 20
    
    @property
    def offset(self) -> int:
        """Calcula offset para query."""
        return (self.page - 1) * self.per_page


@dataclass
class SortParams:
    """Parâmetros de ordenação."""
    field: str = "criado_em"
    direction: str = "desc"  # asc ou desc
    
    @property
    def order_by(self) -> str:
        """Retorna string para QuerySet.order_by()."""
        prefix = "-" if self.direction == "desc" else ""
        return f"{prefix}{self.field}"


@dataclass
class PaginatedResult(Generic[T]):
    """Resultado paginado."""
    items: List[T]
    total: int
    page: int
    per_page: int
    
    @property
    def total_pages(self) -> int:
        """Calcula total de páginas."""
        return (self.total + self.per_page - 1) // self.per_page
    
    @property
    def has_next(self) -> bool:
        """Verifica se tem próxima página."""
        return self.page < self.total_pages
    
    @property
    def has_prev(self) -> bool:
        """Verifica se tem página anterior."""
        return self.page > 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dict."""
        return {
            "items": [
                item.to_dict() if hasattr(item, "to_dict") else item
                for item in self.items
            ],
            "total": self.total,
            "page": self.page,
            "per_page": self.per_page,
            "total_pages": self.total_pages,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
        }


class BaseRepository(ABC, Generic[T, M]):
    """
    Classe base abstrata para repositórios Django.
    
    Fornece implementação padrão para operações comuns,
    permitindo que repositórios específicos sobrescrevam
    apenas o necessário.
    
    Type Parameters:
        T: Tipo da entidade de domínio
        M: Tipo do Model Django
    
    Example:
        class TicketRepository(BaseRepository[TicketEntity, TicketModel]):
            model_class = TicketModel
            
            def to_entity(self, model):
                return TicketMapper.to_entity(model)
            
            def to_model(self, entity):
                return TicketMapper.to_model(entity)
    """
    
    # Classe do model Django (definir na subclasse)
    model_class: Type[M]
    
    # Campos para select_related (otimização N+1)
    select_related_fields: List[str] = []
    
    # Campos para prefetch_related (M2M, reverse FK)
    prefetch_related_fields: List[str] = []
    
    # Campo padrão de ordenação
    default_order_field: str = "-criado_em"
    
    @abstractmethod
    def to_entity(self, model: M) -> T:
        """
        Converte Model Django para Entity de domínio.
        
        Args:
            model: Model Django
            
        Returns:
            Entity de domínio
        """
        raise NotImplementedError
    
    @abstractmethod
    def to_model(self, entity: T) -> M:
        """
        Converte Entity de domínio para Model Django.
        
        Args:
            entity: Entity de domínio
            
        Returns:
            Model Django (não salvo)
        """
        raise NotImplementedError
    
    def _get_base_queryset(self) -> QuerySet[M]:
        """
        Retorna queryset base com otimizações.
        
        Aplica select_related e prefetch_related para evitar N+1.
        """
        qs = self.model_class.objects.all()
        
        if self.select_related_fields:
            qs = qs.select_related(*self.select_related_fields)
        
        if self.prefetch_related_fields:
            qs = qs.prefetch_related(*self.prefetch_related_fields)
        
        return qs
    
    def save(self, entity: T) -> None:
        """
        Persiste entidade (create ou update).
        
        Usa update_or_create para atomicidade.
        
        Args:
            entity: Entidade a persistir
        """
        model = self.to_model(entity)
        
        # Obter campos para update
        model_dict = {}
        for field in model._meta.fields:
            if field.name != "id" and not field.primary_key:
                model_dict[field.name] = getattr(model, field.name)
        
        self.model_class.objects.update_or_create(
            id=getattr(entity, "id"),
            defaults=model_dict,
        )
        
        logger.debug(f"{self.model_class.__name__} saved: {entity.id}")
    
    def get_by_id(self, entity_id: str) -> Optional[T]:
        """
        Busca entidade por ID.
        
        Args:
            entity_id: ID da entidade
            
        Returns:
            Entidade encontrada ou None
        """
        try:
            model = self._get_base_queryset().get(id=entity_id)
            return self.to_entity(model)
        except self.model_class.DoesNotExist:
            return None
    
    def delete(self, entity_id: str) -> bool:
        """
        Remove entidade.
        
        Args:
            entity_id: ID da entidade
            
        Returns:
            True se removido, False se não existia
        """
        deleted_count, _ = self.model_class.objects.filter(id=entity_id).delete()
        return deleted_count > 0
    
    def exists(self, entity_id: str) -> bool:
        """
        Verifica se entidade existe.
        
        Args:
            entity_id: ID da entidade
            
        Returns:
            True se existe
        """
        return self.model_class.objects.filter(id=entity_id).exists()
    
    def count(self) -> int:
        """
        Conta total de entidades.
        
        Returns:
            Número total
        """
        return self.model_class.objects.count()
    
    def list_all(self) -> List[T]:
        """
        Lista todas as entidades.
        
        Warning:
            Use com cuidado em produção - sem paginação!
            
        Returns:
            Lista de todas as entidades
        """
        models = self._get_base_queryset().order_by(self.default_order_field)
        return [self.to_entity(m) for m in models]
    
    def list_paginated(
        self,
        pagination: PaginationParams,
        sort: Optional[SortParams] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> PaginatedResult[T]:
        """
        Lista entidades com paginação e filtros.
        
        Args:
            pagination: Parâmetros de paginação
            sort: Parâmetros de ordenação (opcional)
            filters: Filtros como dict (opcional)
            
        Returns:
            Resultado paginado
        """
        qs = self._get_base_queryset()
        
        # Aplicar filtros
        if filters:
            qs = self._apply_filters(qs, filters)
        
        # Ordenação
        order_by = sort.order_by if sort else self.default_order_field
        qs = qs.order_by(order_by)
        
        # Contagem total
        total = qs.count()
        
        # Paginação
        models = qs[pagination.offset:pagination.offset + pagination.per_page]
        entities = [self.to_entity(m) for m in models]
        
        return PaginatedResult(
            items=entities,
            total=total,
            page=pagination.page,
            per_page=pagination.per_page,
        )
    
    def _apply_filters(self, qs: QuerySet[M], filters: Dict[str, Any]) -> QuerySet[M]:
        """
        Aplica filtros ao queryset.
        
        Suporta filtros especiais:
        - __in: Lista de valores
        - __contains: Busca parcial (case-insensitive)
        - __gt, __lt, __gte, __lte: Comparações
        - __isnull: Verifica null
        
        Args:
            qs: QuerySet base
            filters: Dict com filtros
            
        Returns:
            QuerySet filtrado
        """
        for key, value in filters.items():
            if value is None:
                continue
            
            # Filtro especial: lista de valores
            if isinstance(value, list):
                qs = qs.filter(**{f"{key}__in": value})
            # Filtro normal
            else:
                qs = qs.filter(**{key: value})
        
        return qs
    
    def bulk_create(self, entities: List[T], batch_size: int = 1000) -> int:
        """
        Cria múltiplas entidades em batch.
        
        Muito mais eficiente que save() em loop.
        
        Args:
            entities: Lista de entidades
            batch_size: Tamanho do batch
            
        Returns:
            Número de entidades criadas
        """
        models = [self.to_model(e) for e in entities]
        created = self.model_class.objects.bulk_create(models, batch_size=batch_size)
        return len(created)
    
    def bulk_update(
        self,
        entities: List[T],
        fields: List[str],
        batch_size: int = 1000
    ) -> int:
        """
        Atualiza múltiplas entidades em batch.
        
        Args:
            entities: Lista de entidades
            fields: Campos a atualizar
            batch_size: Tamanho do batch
            
        Returns:
            Número de entidades atualizadas
        """
        models = [self.to_model(e) for e in entities]
        updated = self.model_class.objects.bulk_update(
            models, fields, batch_size=batch_size
        )
        return updated


class CachingRepositoryMixin:
    """
    Mixin para adicionar cache ao repositório.
    
    Usa Django cache framework para cache transparente.
    
    Example:
        class CachedTicketRepository(CachingRepositoryMixin, TicketRepository):
            cache_timeout = 300  # 5 minutos
    """
    
    cache_timeout: int = 60  # segundos
    cache_prefix: str = "repo"
    
    def _get_cache_key(self, entity_id: str) -> str:
        """Gera chave de cache."""
        return f"{self.cache_prefix}:{self.model_class.__name__}:{entity_id}"
    
    def get_by_id(self, entity_id: str) -> Optional[T]:
        """Busca com cache."""
        from django.core.cache import cache
        
        cache_key = self._get_cache_key(entity_id)
        cached = cache.get(cache_key)
        
        if cached is not None:
            logger.debug(f"Cache hit: {cache_key}")
            return cached
        
        # Cache miss - buscar do banco
        entity = super().get_by_id(entity_id)
        
        if entity is not None:
            cache.set(cache_key, entity, self.cache_timeout)
        
        return entity
    
    def save(self, entity: T) -> None:
        """Salva e invalida cache."""
        from django.core.cache import cache
        
        super().save(entity)
        
        # Invalidar cache
        cache_key = self._get_cache_key(entity.id)
        cache.delete(cache_key)
    
    def delete(self, entity_id: str) -> bool:
        """Remove e invalida cache."""
        from django.core.cache import cache
        
        result = super().delete(entity_id)
        
        # Invalidar cache
        cache_key = self._get_cache_key(entity_id)
        cache.delete(cache_key)
        
        return result

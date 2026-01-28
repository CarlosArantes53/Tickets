"""
Unit of Work - Implementação Django.

Gerencia transações atômicas entre múltiplos repositórios,
garantindo consistência de dados.

Responsabilidades:
- Iniciar/finalizar transações
- Commit/Rollback coordenado
- Publicar eventos após commit bem-sucedido
- Persistir eventos no Event Store

ACID Guarantees:
- Atomicidade: Tudo ou nada
- Consistência: Eventos refletem estado persistido
- Isolamento: Cada request tem sua transação
- Durabilidade: PostgreSQL garante

Escalabilidade:
- Interface abstrata permite trocar implementação
- Event Store pode escalar independentemente
- Preparado para distributed transactions (futuro)
"""

from typing import List, Optional, Callable
from contextlib import contextmanager
import logging

from django.db import transaction, connection

from src.core.shared.interfaces import UnitOfWork
from src.core.shared.events import DomainEvent

logger = logging.getLogger(__name__)


class DjangoUnitOfWork(UnitOfWork):
    """
    Implementação Django do Unit of Work.
    
    Usa django.db.transaction para gerenciar transações PostgreSQL.
    Eventos são publicados apenas após commit bem-sucedido.
    
    Features:
    - Context manager (with statement)
    - Auto-commit/rollback
    - Event buffering
    - Event Store integration (opcional)
    - Event Publisher integration (opcional)
    
    Example:
        with DjangoUnitOfWork() as uow:
            repo.save(entity1)
            repo.save(entity2)
            uow.publish_event(MyEvent(...))
        # Commit automático + eventos publicados
        
    Example com rollback:
        with DjangoUnitOfWork() as uow:
            repo.save(entity)
            uow.publish_event(MyEvent(...))
            raise Exception("Erro!")
        # Rollback automático, eventos descartados
    """
    
    def __init__(
        self,
        event_publisher: Optional['EventPublisher'] = None,
        event_store: Optional['EventStore'] = None,
        auto_commit: bool = True,
    ):
        """
        Inicializa Unit of Work.
        
        Args:
            event_publisher: Publicador de eventos (Celery, RabbitMQ, etc)
            event_store: Store para persistência de eventos
            auto_commit: Se True, commit automático ao sair do contexto
        """
        super().__init__()
        self._event_publisher = event_publisher
        self._event_store = event_store
        self._auto_commit = auto_commit
        self._transaction_started = False
        self._committed = False
        self._rolled_back = False
        self._sequence_counters = {}  # aggregate_id -> sequence
    
    def _begin_transaction(self) -> None:
        """
        Inicia transação PostgreSQL.
        
        Desabilita auto-commit para controle manual.
        """
        if not self._transaction_started:
            transaction.set_autocommit(False)
            self._transaction_started = True
            logger.debug("Transaction started")
    
    def commit(self) -> None:
        """
        Persiste todas as mudanças e publica eventos.
        
        Ordem de execução:
        1. Persistir eventos no Event Store (se configurado)
        2. Commit da transação no banco
        3. Publicar eventos para handlers assíncronos
        4. Limpar estado interno
        
        Raises:
            Exception: Se commit falhar, re-lança exceção
        """
        if self._committed or self._rolled_back:
            logger.warning("Transaction already finalized")
            return
        
        try:
            # 1. Persistir eventos no Event Store (antes do commit principal)
            if self._event_store and self._events:
                self._persist_events()
            
            # 2. Commit da transação
            if self._transaction_started:
                transaction.commit()
                logger.debug("Transaction committed")
            
            self._committed = True
            
            # 3. Publicar eventos para handlers (após commit)
            if self._events:
                self._publish_events()
            
        except Exception as e:
            logger.error(f"Commit failed: {e}")
            self.rollback()
            raise
        finally:
            # 4. Restaurar auto-commit
            self._finalize()
    
    def rollback(self) -> None:
        """
        Desfaz todas as mudanças e descarta eventos.
        
        Chamado automaticamente se exceção ocorrer dentro do contexto.
        """
        if self._committed or self._rolled_back:
            return
        
        try:
            if self._transaction_started:
                transaction.rollback()
                logger.debug("Transaction rolled back")
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
        finally:
            self._rolled_back = True
            self.clear_events()
            self._finalize()
    
    def _finalize(self) -> None:
        """Restaura estado da conexão."""
        if self._transaction_started:
            try:
                transaction.set_autocommit(True)
            except Exception:
                pass
            self._transaction_started = False
    
    def _persist_events(self) -> None:
        """Persiste eventos no Event Store."""
        for event in self._events:
            # Obter sequência para o agregado
            sequence = self._get_next_sequence(event.aggregate_id)
            
            self._event_store.append(
                event=event,
                sequence=sequence,
            )
    
    def _publish_events(self) -> None:
        """
        Publica eventos para handlers assíncronos.
        
        Eventos só são publicados após commit bem-sucedido.
        Se event_publisher não estiver configurado, apenas loga.
        """
        for event in self._events:
            logger.info(
                f"Publishing event: {event.event_type} "
                f"for aggregate {event.aggregate_id}"
            )
            
            if self._event_publisher:
                try:
                    self._event_publisher.publish(event)
                except Exception as e:
                    # Log mas não falha - eventos podem ser reprocessados
                    logger.error(f"Failed to publish event: {e}")
        
        self.clear_events()
    
    def _get_next_sequence(self, aggregate_id: str) -> int:
        """
        Obtém próximo número de sequência para um agregado.
        
        Usado para ordenação de eventos no Event Store.
        """
        if aggregate_id not in self._sequence_counters:
            # Buscar última sequência do banco (se Event Store configurado)
            self._sequence_counters[aggregate_id] = 0
        
        self._sequence_counters[aggregate_id] += 1
        return self._sequence_counters[aggregate_id]
    
    @property
    def is_committed(self) -> bool:
        """Verifica se transação foi comitada."""
        return self._committed
    
    @property
    def is_rolled_back(self) -> bool:
        """Verifica se transação foi revertida."""
        return self._rolled_back


class InMemoryUnitOfWork(UnitOfWork):
    """
    Unit of Work em memória para testes.
    
    Não persiste nada - apenas simula comportamento
    para testes unitários sem banco de dados.
    
    Example:
        uow = InMemoryUnitOfWork()
        with uow:
            # operações
            uow.publish_event(event)
        
        assert uow.committed
        assert len(uow.collected_events) == 1
    """
    
    def __init__(self):
        """Inicializa UoW em memória."""
        super().__init__()
        self._committed = False
        self._rolled_back = False
        self._published_events: List[DomainEvent] = []
    
    def _begin_transaction(self) -> None:
        """Simula início de transação."""
        pass
    
    def commit(self) -> None:
        """Simula commit."""
        self._committed = True
        self._published_events.extend(self._events)
        self.clear_events()
    
    def rollback(self) -> None:
        """Simula rollback."""
        self._rolled_back = True
        self.clear_events()
    
    @property
    def committed(self) -> bool:
        """Verifica se foi comitado."""
        return self._committed
    
    @property
    def rolled_back(self) -> bool:
        """Verifica se foi revertido."""
        return self._rolled_back
    
    @property
    def published_events(self) -> List[DomainEvent]:
        """Retorna eventos que foram 'publicados'."""
        return self._published_events
    
    def reset(self) -> None:
        """Reset para próximo teste."""
        self._committed = False
        self._rolled_back = False
        self._published_events.clear()
        self.clear_events()


# =============================================================================
# Context Manager Helper
# =============================================================================

@contextmanager
def atomic_operation(
    uow: Optional[UnitOfWork] = None,
    event_publisher: Optional['EventPublisher'] = None,
    event_store: Optional['EventStore'] = None,
):
    """
    Context manager para operações atômicas.
    
    Cria UoW se não fornecido, ou usa o existente.
    
    Example:
        with atomic_operation() as uow:
            repo.save(entity)
            uow.publish_event(event)
    
    Args:
        uow: UoW existente (opcional)
        event_publisher: Publicador de eventos
        event_store: Store de eventos
        
    Yields:
        UnitOfWork configurado
    """
    if uow is None:
        uow = DjangoUnitOfWork(
            event_publisher=event_publisher,
            event_store=event_store,
        )
        own_uow = True
    else:
        own_uow = False
    
    try:
        with uow:
            yield uow
    except Exception:
        if own_uow:
            uow.rollback()
        raise

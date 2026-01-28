"""
Interfaces (Ports) - Contratos entre Core e Adapters.

Este módulo define as interfaces que os Adapters devem implementar.
São os "Ports" da Arquitetura Hexagonal.

Tipos de Ports:
- Driven Ports (lado direito): Repository, UnitOfWork, EventPublisher
- Driving Ports (lado esquerdo): Definidos nos Use Cases

Princípio: Core define interfaces; Adapters implementam.
O fluxo de dependência sempre aponta para o Core.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, TypeVar, Generic, Protocol
from contextlib import contextmanager

from .events import DomainEvent


# Type variable para entidades genéricas
T = TypeVar("T")


class UnitOfWork(ABC):
    """
    Unit of Work - Coordena transações atômicas.
    
    Garante que múltiplas operações de persistência sejam
    executadas como uma única unidade: ou todas são persistidas
    ou nenhuma é (garantia ACID).
    
    Pattern: Context Manager
        with uow:
            repo.save(entity1)
            repo.save(entity2)
            uow.publish_event(event)
        # Commit automático ao sair sem erro
        # Rollback automático se exceção
    
    Responsabilidades:
    - Gerenciar início/fim de transação
    - Commit/Rollback coordenado
    - Enfileirar eventos para publicação pós-commit
    - Garantir que eventos só são publicados após commit bem-sucedido
    
    Example:
        class DjangoUnitOfWork(UnitOfWork):
            def commit(self):
                transaction.commit()
                self._publish_events()
    """
    
    def __init__(self):
        self._events: List[DomainEvent] = []
    
    def __enter__(self) -> "UnitOfWork":
        """
        Inicia contexto de transação.
        
        Returns:
            Self para permitir uso como context manager
        """
        self._begin_transaction()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """
        Finaliza contexto de transação.
        
        Args:
            exc_type: Tipo da exceção (None se sucesso)
            exc_val: Valor da exceção
            exc_tb: Traceback da exceção
            
        Returns:
            False para propagar exceções
        """
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        return False  # Não suprime exceções
    
    @abstractmethod
    def _begin_transaction(self) -> None:
        """
        Inicia uma nova transação.
        
        Deve ser implementado pelo adapter específico
        (Django: transaction.set_autocommit(False))
        """
        raise NotImplementedError
    
    @abstractmethod
    def commit(self) -> None:
        """
        Persiste todas as mudanças e publica eventos.
        
        Ordem de execução:
        1. Commit da transação no banco
        2. Publicação de eventos enfileirados
        3. Limpeza de estado interno
        
        Note:
            Eventos só são publicados após commit bem-sucedido.
            Se commit falhar, eventos são descartados.
        """
        raise NotImplementedError
    
    @abstractmethod
    def rollback(self) -> None:
        """
        Desfaz todas as mudanças e descarta eventos.
        
        Chamado automaticamente se exceção ocorrer dentro
        do bloco `with`.
        """
        raise NotImplementedError
    
    def publish_event(self, event: DomainEvent) -> None:
        """
        Enfileira evento para publicação após commit.
        
        Eventos não são publicados imediatamente. São
        armazenados e publicados apenas após commit
        bem-sucedido da transação.
        
        Args:
            event: Evento de domínio a ser publicado
            
        Example:
            with uow:
                ticket = Ticket.criar(...)
                repo.save(ticket)
                uow.publish_event(TicketCriadoEvent(ticket.id))
            # Evento publicado aqui, após commit
        """
        self._events.append(event)
    
    def collect_events(self) -> List[DomainEvent]:
        """
        Retorna eventos enfileirados (para testing/debugging).
        
        Returns:
            Lista de eventos pendentes
        """
        return list(self._events)
    
    def clear_events(self) -> None:
        """Limpa fila de eventos."""
        self._events.clear()


class Repository(Protocol, Generic[T]):
    """
    Interface genérica para repositórios.
    
    Define operações básicas de persistência que todos
    os repositórios devem implementar.
    
    Type Parameters:
        T: Tipo da entidade gerenciada pelo repositório
    
    Note:
        Usando Protocol para permitir duck typing.
        Adapters não precisam herdar explicitamente.
    """
    
    def save(self, entity: T) -> None:
        """
        Persiste entidade (create ou update).
        
        Args:
            entity: Entidade a ser persistida
        """
        ...
    
    def get_by_id(self, entity_id: str) -> Optional[T]:
        """
        Busca entidade por ID.
        
        Args:
            entity_id: Identificador único da entidade
            
        Returns:
            Entidade encontrada ou None
        """
        ...
    
    def delete(self, entity_id: str) -> None:
        """
        Remove entidade.
        
        Args:
            entity_id: Identificador da entidade a remover
        """
        ...
    
    def list_all(self) -> List[T]:
        """
        Lista todas as entidades.
        
        Returns:
            Lista de todas as entidades do repositório
        """
        ...


class EventPublisher(ABC):
    """
    Interface para publicação de eventos.
    
    Adapters implementam para integrar com diferentes
    sistemas de mensageria (RabbitMQ, Celery, Kafka, etc.)
    
    Example:
        class CeleryEventPublisher(EventPublisher):
            def publish(self, event):
                celery_app.send_task('handle_event', args=[event.to_dict()])
    """
    
    @abstractmethod
    def publish(self, event: DomainEvent) -> None:
        """
        Publica evento para consumidores.
        
        Args:
            event: Evento de domínio a ser publicado
        """
        raise NotImplementedError
    
    @abstractmethod
    def publish_batch(self, events: List[DomainEvent]) -> None:
        """
        Publica múltiplos eventos em batch.
        
        Args:
            events: Lista de eventos a serem publicados
        """
        raise NotImplementedError


class EventStore(ABC):
    """
    Interface para persistência de eventos (Event Sourcing).
    
    Permite armazenar histórico completo de eventos para
    auditoria, replay e reconstrução de estado.
    
    Example:
        class PostgresEventStore(EventStore):
            def append(self, event, aggregate_id, version):
                DomainEventModel.objects.create(
                    event_id=event.event_id,
                    aggregate_id=aggregate_id,
                    ...
                )
    """
    
    @abstractmethod
    def append(
        self,
        event: DomainEvent,
        aggregate_id: str,
        expected_version: int
    ) -> None:
        """
        Adiciona evento ao store.
        
        Args:
            event: Evento a ser persistido
            aggregate_id: ID do agregado
            expected_version: Versão esperada para controle de concorrência
            
        Raises:
            ConcurrencyError: Se versão não corresponde
        """
        raise NotImplementedError
    
    @abstractmethod
    def get_events_for_aggregate(
        self,
        aggregate_id: str,
        since_version: int = 0
    ) -> List[DomainEvent]:
        """
        Recupera eventos de um agregado.
        
        Args:
            aggregate_id: ID do agregado
            since_version: Versão inicial (para replay parcial)
            
        Returns:
            Lista de eventos ordenados por versão
        """
        raise NotImplementedError


# Type alias para facilitar tipagem
UoW = UnitOfWork

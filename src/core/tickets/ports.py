"""
Ports (Interfaces) do Domínio de Tickets.

Define os contratos que os Adapters de infraestrutura devem implementar
para persistência e consulta de tickets.

Tipos de Ports:
- TicketRepository: Interface para CRUD de tickets
- TicketQueryService: Interface para consultas complexas (CQRS opcional)

Princípio:
    Core define interfaces → Adapters implementam
    Dependências sempre apontam para o Core
    
Example:
    # No Adapter (Django)
    class DjangoTicketRepository(TicketRepository):
        def save(self, ticket: TicketEntity) -> None:
            model = TicketModel.from_entity(ticket)
            model.save()
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Protocol, runtime_checkable

from .entities import TicketEntity, TicketStatus, TicketPriority
from .dtos import TicketListItemDTO, ListarTicketsQueryDTO, PaginatedResultDTO


@runtime_checkable
class TicketRepository(Protocol):
    """
    Interface para persistência de Tickets.
    
    Define operações CRUD que qualquer implementação de repositório
    deve fornecer. Usando Protocol para duck typing.
    
    Implementações:
    - DjangoTicketRepository (PostgreSQL via ORM)
    - InMemoryTicketRepository (para testes)
    - SQLAlchemyTicketRepository (alternativa)
    
    Methods:
        save: Persiste ticket (create ou update)
        get_by_id: Busca por ID
        delete: Remove ticket
        list_all: Lista todos
        list_by_status: Filtra por status
        list_by_criador: Filtra por criador
        list_by_tecnico: Filtra por técnico atribuído
        exists: Verifica se existe
        count: Conta total de tickets
    
    Example:
        class DjangoTicketRepository:
            def save(self, ticket: TicketEntity) -> None:
                model = TicketMapper.to_model(ticket)
                model.save()
    """
    
    def save(self, ticket: TicketEntity) -> None:
        """
        Persiste ticket no repositório.
        
        Se ticket.id já existe, atualiza. Caso contrário, cria novo.
        
        Args:
            ticket: Entidade a ser persistida
            
        Raises:
            RepositoryError: Se falha na persistência
        """
        ...
    
    def get_by_id(self, ticket_id: str) -> Optional[TicketEntity]:
        """
        Busca ticket por ID.
        
        Args:
            ticket_id: Identificador único do ticket
            
        Returns:
            Entidade encontrada ou None se não existir
        """
        ...
    
    def delete(self, ticket_id: str) -> None:
        """
        Remove ticket do repositório.
        
        Args:
            ticket_id: Identificador do ticket a remover
            
        Raises:
            EntityNotFoundError: Se ticket não existe
        """
        ...
    
    def list_all(self) -> List[TicketEntity]:
        """
        Lista todos os tickets.
        
        Atenção: Em produção com muitos dados, prefira métodos
        com paginação.
        
        Returns:
            Lista de todos os tickets
        """
        ...
    
    def list_by_status(self, status: TicketStatus) -> List[TicketEntity]:
        """
        Lista tickets por status.
        
        Args:
            status: Status para filtrar
            
        Returns:
            Lista de tickets com o status especificado
        """
        ...
    
    def list_by_criador(self, criador_id: str) -> List[TicketEntity]:
        """
        Lista tickets de um criador.
        
        Args:
            criador_id: ID do usuário criador
            
        Returns:
            Lista de tickets criados pelo usuário
        """
        ...
    
    def list_by_tecnico(self, tecnico_id: str) -> List[TicketEntity]:
        """
        Lista tickets atribuídos a um técnico.
        
        Args:
            tecnico_id: ID do técnico
            
        Returns:
            Lista de tickets atribuídos ao técnico
        """
        ...
    
    def exists(self, ticket_id: str) -> bool:
        """
        Verifica se ticket existe.
        
        Args:
            ticket_id: ID do ticket
            
        Returns:
            True se existe, False caso contrário
        """
        ...
    
    def count(self) -> int:
        """
        Conta total de tickets.
        
        Returns:
            Número total de tickets no repositório
        """
        ...
    
    def count_by_status(self, status: TicketStatus) -> int:
        """
        Conta tickets por status.
        
        Args:
            status: Status para filtrar
            
        Returns:
            Número de tickets com o status
        """
        ...


class TicketQueryRepository(Protocol):
    """
    Interface para consultas otimizadas de tickets (Read Model - CQRS).
    
    Separada do TicketRepository para permitir otimizações
    específicas de leitura sem afetar operações de escrita.
    
    Benefícios:
    - Consultas otimizadas com select_related/prefetch
    - DTOs já montados (evita N+1)
    - Paginação eficiente
    - Filtros complexos
    
    Example:
        class DjangoTicketQueryRepository:
            def list_with_users(self, query: ListarTicketsQueryDTO):
                return TicketModel.objects.select_related('criador', 'tecnico')
    """
    
    def list_paginated(
        self,
        query: ListarTicketsQueryDTO
    ) -> PaginatedResultDTO:
        """
        Lista tickets com paginação e filtros.
        
        Args:
            query: DTO com parâmetros de filtro e paginação
            
        Returns:
            Resultado paginado com DTOs otimizados
        """
        ...
    
    def list_atrasados(self) -> List[TicketListItemDTO]:
        """
        Lista todos os tickets atrasados (SLA violado).
        
        Returns:
            Lista de tickets atrasados como DTOs
        """
        ...
    
    def get_estatisticas_por_status(self) -> dict:
        """
        Retorna contagem de tickets por status.
        
        Returns:
            Dict com status como chave e contagem como valor
            Ex: {"Aberto": 10, "Em Progresso": 5, ...}
        """
        ...
    
    def get_estatisticas_por_tecnico(self) -> List[dict]:
        """
        Retorna estatísticas de tickets por técnico.
        
        Returns:
            Lista de dicts com estatísticas por técnico
            Ex: [{"tecnico_id": "123", "total": 10, "abertos": 3}, ...]
        """
        ...


class InMemoryTicketRepository:
    """
    Implementação em memória do TicketRepository.
    
    Útil para:
    - Testes unitários
    - Prototipagem
    - Desenvolvimento local
    
    Não usar em produção!
    
    Example:
        repo = InMemoryTicketRepository()
        repo.save(ticket)
        found = repo.get_by_id(ticket.id)
    """
    
    def __init__(self):
        self._tickets: dict[str, TicketEntity] = {}
    
    def save(self, ticket: TicketEntity) -> None:
        """Salva ticket em memória."""
        self._tickets[ticket.id] = ticket
    
    def get_by_id(self, ticket_id: str) -> Optional[TicketEntity]:
        """Busca ticket por ID."""
        return self._tickets.get(ticket_id)
    
    def delete(self, ticket_id: str) -> None:
        """Remove ticket."""
        if ticket_id in self._tickets:
            del self._tickets[ticket_id]
    
    def list_all(self) -> List[TicketEntity]:
        """Lista todos os tickets."""
        return list(self._tickets.values())
    
    def list_by_status(self, status: TicketStatus) -> List[TicketEntity]:
        """Filtra por status."""
        return [t for t in self._tickets.values() if t.status == status]
    
    def list_by_criador(self, criador_id: str) -> List[TicketEntity]:
        """Filtra por criador."""
        return [t for t in self._tickets.values() if t.criador_id == criador_id]
    
    def list_by_tecnico(self, tecnico_id: str) -> List[TicketEntity]:
        """Filtra por técnico."""
        return [
            t for t in self._tickets.values()
            if t.atribuido_a_id == tecnico_id
        ]
    
    def exists(self, ticket_id: str) -> bool:
        """Verifica existência."""
        return ticket_id in self._tickets
    
    def count(self) -> int:
        """Conta total."""
        return len(self._tickets)
    
    def count_by_status(self, status: TicketStatus) -> int:
        """Conta por status."""
        return len([t for t in self._tickets.values() if t.status == status])
    
    def clear(self) -> None:
        """Limpa todos os dados (útil para testes)."""
        self._tickets.clear()

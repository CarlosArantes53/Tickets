"""
Domínio de Tickets - Gerenciamento de Incidentes.

Este módulo contém toda a lógica de negócio relacionada a tickets
de suporte técnico, incluindo:
- Entidades (TicketEntity, TicketStatus, TicketPriority)
- Use Cases (CriarTicket, AtribuirTicket, ListarTickets)
- Domain Events (TicketCriado, TicketAtribuido, TicketFechado)
- DTOs (Input/Output Data Transfer Objects)
- Ports (Interfaces para repositórios)

Características do Domínio:
- SLA calculado automaticamente por prioridade
- Validações de regras de negócio na entidade
- Transições de status controladas
- Eventos disparados para side-effects assíncronos
"""

from .entities import TicketEntity, TicketStatus, TicketPriority
from .events import (
    TicketCriadoEvent,
    TicketAtribuidoEvent,
    TicketFechadoEvent,
    TicketReabertoEvent,
)
from .dtos import (
    CriarTicketInputDTO,
    AtribuirTicketInputDTO,
    TicketOutputDTO,
    TicketListItemDTO,
)
from .ports import TicketRepository
from .use_cases import (
    CriarTicketService,
    AtribuirTicketService,
    ListarTicketsService,
    ObterTicketService,
    FecharTicketService,
)

__all__ = [
    # Entities
    "TicketEntity",
    "TicketStatus",
    "TicketPriority",
    # Events
    "TicketCriadoEvent",
    "TicketAtribuidoEvent",
    "TicketFechadoEvent",
    "TicketReabertoEvent",
    # DTOs
    "CriarTicketInputDTO",
    "AtribuirTicketInputDTO",
    "TicketOutputDTO",
    "TicketListItemDTO",
    # Ports
    "TicketRepository",
    # Use Cases
    "CriarTicketService",
    "AtribuirTicketService",
    "ListarTicketsService",
    "ObterTicketService",
    "FecharTicketService",
]

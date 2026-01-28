"""
Shared Domain Components.

Contém componentes compartilhados entre todos os domínios:
- Exceções de domínio
- Interfaces (Ports) 
- Base classes para Domain Events
"""

from .exceptions import (
    DomainException,
    ValidationError,
    EntityNotFoundError,
    BusinessRuleViolationError,
)
from .events import DomainEvent
from .interfaces import UnitOfWork

__all__ = [
    "DomainException",
    "ValidationError",
    "EntityNotFoundError",
    "BusinessRuleViolationError",
    "DomainEvent",
    "UnitOfWork",
]

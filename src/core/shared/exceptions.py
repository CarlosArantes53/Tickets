"""
Exceções de Domínio do TechSupport Manager.

Este módulo define exceções específicas do domínio que permitem
comunicar erros de forma clara e tipada entre as camadas.

Hierarquia:
    DomainException (base)
    ├── ValidationError (validação de entrada)
    ├── EntityNotFoundError (entidade não existe)
    └── BusinessRuleViolationError (regra de negócio violada)
"""


class DomainException(Exception):
    """
    Exceção base para todos os erros de domínio.
    
    Todas as exceções específicas do domínio devem herdar desta classe.
    Isso permite capturar qualquer erro de domínio de forma genérica.
    
    Example:
        try:
            ticket.fechar()
        except DomainException as e:
            logger.error(f"Erro de domínio: {e}")
    """
    
    def __init__(self, message: str, code: str = None):
        self.message = message
        self.code = code or self.__class__.__name__
        super().__init__(self.message)
    
    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"
    
    def to_dict(self) -> dict:
        """Serializa exceção para dicionário (útil para APIs)."""
        return {
            "error": self.code,
            "message": self.message,
        }


class ValidationError(DomainException):
    """
    Erro de validação de dados de entrada.
    
    Lançada quando dados fornecidos não atendem aos requisitos
    mínimos para processamento.
    
    Example:
        if len(titulo) < 3:
            raise ValidationError("Título deve ter pelo menos 3 caracteres")
    """
    
    def __init__(self, message: str, field: str = None):
        self.field = field
        code = f"VALIDATION_ERROR_{field.upper()}" if field else "VALIDATION_ERROR"
        super().__init__(message, code)
    
    def to_dict(self) -> dict:
        result = super().to_dict()
        if self.field:
            result["field"] = self.field
        return result


class EntityNotFoundError(DomainException):
    """
    Entidade não encontrada no repositório.
    
    Lançada quando uma busca por ID não retorna resultado.
    
    Example:
        ticket = repo.get_by_id(ticket_id)
        if not ticket:
            raise EntityNotFoundError(f"Ticket {ticket_id} não encontrado")
    """
    
    def __init__(self, message: str, entity_type: str = None, entity_id: str = None):
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(message, "ENTITY_NOT_FOUND")
    
    def to_dict(self) -> dict:
        result = super().to_dict()
        if self.entity_type:
            result["entity_type"] = self.entity_type
        if self.entity_id:
            result["entity_id"] = self.entity_id
        return result


class BusinessRuleViolationError(DomainException):
    """
    Violação de regra de negócio.
    
    Lançada quando uma operação viola uma regra de negócio
    estabelecida no domínio.
    
    Example:
        if ticket.status == TicketStatus.FECHADO:
            raise BusinessRuleViolationError(
                "Não é possível atribuir ticket fechado"
            )
    """
    
    def __init__(self, message: str, rule: str = None):
        self.rule = rule
        super().__init__(message, "BUSINESS_RULE_VIOLATION")
    
    def to_dict(self) -> dict:
        result = super().to_dict()
        if self.rule:
            result["rule"] = self.rule
        return result


class ConcurrencyError(DomainException):
    """
    Erro de concorrência/conflito de versão.
    
    Lançada quando uma operação falha devido a modificação
    concorrente da entidade.
    
    Example:
        if entity.version != expected_version:
            raise ConcurrencyError("Entidade foi modificada por outro processo")
    """
    
    def __init__(self, message: str):
        super().__init__(message, "CONCURRENCY_ERROR")

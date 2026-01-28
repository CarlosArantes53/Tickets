"""
Data Transfer Objects (DTOs) do Domínio de Tickets.

DTOs são estruturas simples para transportar dados entre camadas,
evitando vazamento de modelos internos (entidades) para camadas externas.

Tipos de DTOs:
- Input DTOs: Recebem dados de entrada validados (de Forms/APIs)
- Output DTOs: Formatam dados para resposta (para Views/APIs)
- Query DTOs: Otimizados para listagens (sem carregar entidades completas)

Benefícios:
- Desacoplamento entre camadas
- Controle do que é exposto externamente
- Performance em listagens (Query DTOs)
- Versionamento de API facilitado
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

from .entities import TicketEntity, TicketStatus, TicketPriority


# =============================================================================
# INPUT DTOs (Entrada)
# =============================================================================

@dataclass(frozen=True)
class CriarTicketInputDTO:
    """
    DTO de entrada para criar ticket.
    
    Imutável (frozen=True) para garantir que dados
    validados não sejam alterados acidentalmente.
    
    Attributes:
        titulo: Título do ticket
        descricao: Descrição detalhada
        criador_id: ID do usuário criador
        prioridade: Prioridade (nome do enum, ex: "ALTA")
        categoria: Categoria do ticket
        tags: Lista de tags opcional
    """
    
    titulo: str
    descricao: str
    criador_id: str
    prioridade: str = "MEDIA"
    categoria: str = "Geral"
    tags: tuple = field(default_factory=tuple)  # tuple para ser hashable
    
    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return {
            "titulo": self.titulo,
            "descricao": self.descricao,
            "criador_id": self.criador_id,
            "prioridade": self.prioridade,
            "categoria": self.categoria,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class AtribuirTicketInputDTO:
    """
    DTO de entrada para atribuir ticket.
    
    Attributes:
        ticket_id: ID do ticket
        tecnico_id: ID do técnico a ser atribuído
        atribuido_por_id: ID de quem está fazendo a atribuição
    """
    
    ticket_id: str
    tecnico_id: str
    atribuido_por_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "ticket_id": self.ticket_id,
            "tecnico_id": self.tecnico_id,
            "atribuido_por_id": self.atribuido_por_id,
        }


@dataclass(frozen=True)
class FecharTicketInputDTO:
    """
    DTO de entrada para fechar ticket.
    
    Attributes:
        ticket_id: ID do ticket
        fechado_por_id: ID de quem está fechando
        resolucao: Descrição da resolução (opcional)
    """
    
    ticket_id: str
    fechado_por_id: str
    resolucao: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "ticket_id": self.ticket_id,
            "fechado_por_id": self.fechado_por_id,
            "resolucao": self.resolucao,
        }


@dataclass(frozen=True)
class AlterarPrioridadeInputDTO:
    """
    DTO de entrada para alterar prioridade.
    
    Attributes:
        ticket_id: ID do ticket
        nova_prioridade: Nova prioridade (nome do enum)
        alterado_por_id: ID de quem está alterando
    """
    
    ticket_id: str
    nova_prioridade: str
    alterado_por_id: str
    
    def to_dict(self) -> dict:
        return {
            "ticket_id": self.ticket_id,
            "nova_prioridade": self.nova_prioridade,
            "alterado_por_id": self.alterado_por_id,
        }


# =============================================================================
# OUTPUT DTOs (Saída)
# =============================================================================

@dataclass
class TicketOutputDTO:
    """
    DTO de saída completo com dados do ticket.
    
    Usado para resposta detalhada de um único ticket.
    Inclui todos os dados necessários para exibição.
    
    Attributes:
        id: Identificador único
        titulo: Título do ticket
        descricao: Descrição detalhada
        status: Status atual (valor do enum, ex: "Aberto")
        prioridade: Prioridade (valor do enum, ex: "Alta")
        criador_id: ID do criador
        atribuido_a_id: ID do técnico (se atribuído)
        categoria: Categoria
        criado_em: Data/hora de criação
        atualizado_em: Data/hora da última atualização
        sla_prazo: Prazo do SLA
        esta_atrasado: Se está fora do SLA
        tags: Lista de tags
    """
    
    id: str
    titulo: str
    descricao: str
    status: str
    prioridade: str
    criador_id: str
    atribuido_a_id: Optional[str]
    categoria: str
    criado_em: datetime
    atualizado_em: datetime
    sla_prazo: Optional[datetime]
    esta_atrasado: bool
    tags: List[str] = field(default_factory=list)
    
    @classmethod
    def from_entity(cls, entity: TicketEntity) -> "TicketOutputDTO":
        """
        Factory method para converter entidade em DTO.
        
        Args:
            entity: Entidade TicketEntity
            
        Returns:
            DTO com dados da entidade
        """
        return cls(
            id=entity.id,
            titulo=entity.titulo,
            descricao=entity.descricao,
            status=entity.status.value,
            prioridade=entity.prioridade.value,
            criador_id=entity.criador_id,
            atribuido_a_id=entity.atribuido_a_id,
            categoria=entity.categoria,
            criado_em=entity.criado_em,
            atualizado_em=entity.atualizado_em,
            sla_prazo=entity.sla_prazo,
            esta_atrasado=entity.esta_atrasado,
            tags=entity.tags.copy(),
        )
    
    def to_dict(self) -> dict:
        """Converte para dicionário (serialização JSON)."""
        return {
            "id": self.id,
            "titulo": self.titulo,
            "descricao": self.descricao,
            "status": self.status,
            "prioridade": self.prioridade,
            "criador_id": self.criador_id,
            "atribuido_a_id": self.atribuido_a_id,
            "categoria": self.categoria,
            "criado_em": self.criado_em.isoformat(),
            "atualizado_em": self.atualizado_em.isoformat(),
            "sla_prazo": self.sla_prazo.isoformat() if self.sla_prazo else None,
            "esta_atrasado": self.esta_atrasado,
            "tags": self.tags,
        }


@dataclass
class TicketListItemDTO:
    """
    DTO otimizado para listagens de tickets.
    
    Contém apenas campos necessários para exibição em lista,
    reduzindo overhead de transferência de dados.
    
    Attributes:
        id: Identificador único
        titulo: Título do ticket
        status: Status atual
        prioridade: Prioridade
        criado_em: Data de criação
        esta_atrasado: Se está fora do SLA
        atribuido_a_nome: Nome do técnico (se atribuído)
    """
    
    id: str
    titulo: str
    status: str
    prioridade: str
    criado_em: datetime
    esta_atrasado: bool
    atribuido_a_nome: Optional[str] = None
    
    @classmethod
    def from_entity(
        cls,
        entity: TicketEntity,
        atribuido_a_nome: Optional[str] = None
    ) -> "TicketListItemDTO":
        """
        Factory method para converter entidade em DTO de lista.
        
        Args:
            entity: Entidade TicketEntity
            atribuido_a_nome: Nome do técnico (opcional, para evitar N+1)
            
        Returns:
            DTO otimizado para lista
        """
        return cls(
            id=entity.id,
            titulo=entity.titulo,
            status=entity.status.value,
            prioridade=entity.prioridade.value,
            criado_em=entity.criado_em,
            esta_atrasado=entity.esta_atrasado,
            atribuido_a_nome=atribuido_a_nome,
        )
    
    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return {
            "id": self.id,
            "titulo": self.titulo,
            "status": self.status,
            "prioridade": self.prioridade,
            "criado_em": self.criado_em.isoformat(),
            "esta_atrasado": self.esta_atrasado,
            "atribuido_a_nome": self.atribuido_a_nome,
        }


# =============================================================================
# QUERY DTOs (Filtros de Busca)
# =============================================================================

@dataclass(frozen=True)
class ListarTicketsQueryDTO:
    """
    DTO para parâmetros de busca/filtro de tickets.
    
    Attributes:
        status: Filtrar por status (opcional)
        prioridade: Filtrar por prioridade (opcional)
        criador_id: Filtrar por criador (opcional)
        tecnico_id: Filtrar por técnico atribuído (opcional)
        categoria: Filtrar por categoria (opcional)
        apenas_atrasados: Mostrar apenas atrasados
        ordenar_por: Campo para ordenação
        ordem: Ascendente ou descendente
        pagina: Número da página (1-indexed)
        por_pagina: Itens por página
    """
    
    status: Optional[str] = None
    prioridade: Optional[str] = None
    criador_id: Optional[str] = None
    tecnico_id: Optional[str] = None
    categoria: Optional[str] = None
    apenas_atrasados: bool = False
    ordenar_por: str = "criado_em"
    ordem: str = "desc"
    pagina: int = 1
    por_pagina: int = 20
    
    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "prioridade": self.prioridade,
            "criador_id": self.criador_id,
            "tecnico_id": self.tecnico_id,
            "categoria": self.categoria,
            "apenas_atrasados": self.apenas_atrasados,
            "ordenar_por": self.ordenar_por,
            "ordem": self.ordem,
            "pagina": self.pagina,
            "por_pagina": self.por_pagina,
        }


@dataclass
class PaginatedResultDTO:
    """
    DTO para resultados paginados.
    
    Attributes:
        items: Lista de itens da página atual
        total: Total de itens (sem paginação)
        pagina: Página atual
        por_pagina: Itens por página
        total_paginas: Total de páginas
    """
    
    items: List[TicketListItemDTO]
    total: int
    pagina: int
    por_pagina: int
    
    @property
    def total_paginas(self) -> int:
        """Calcula total de páginas."""
        if self.por_pagina <= 0:
            return 0
        return (self.total + self.por_pagina - 1) // self.por_pagina
    
    @property
    def tem_proxima(self) -> bool:
        """Verifica se há próxima página."""
        return self.pagina < self.total_paginas
    
    @property
    def tem_anterior(self) -> bool:
        """Verifica se há página anterior."""
        return self.pagina > 1
    
    def to_dict(self) -> dict:
        return {
            "items": [item.to_dict() for item in self.items],
            "total": self.total,
            "pagina": self.pagina,
            "por_pagina": self.por_pagina,
            "total_paginas": self.total_paginas,
            "tem_proxima": self.tem_proxima,
            "tem_anterior": self.tem_anterior,
        }

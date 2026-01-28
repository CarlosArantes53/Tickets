"""
Domain Events do Domínio de Tickets.

Este módulo define os eventos de domínio que são disparados
quando algo significativo acontece com tickets.

Eventos:
- TicketCriadoEvent: Novo ticket foi criado
- TicketAtribuidoEvent: Ticket foi atribuído a técnico
- TicketFechadoEvent: Ticket foi fechado
- TicketReabertoEvent: Ticket foi reaberto
- TicketPrioridadeAlteradaEvent: Prioridade foi alterada

Uso:
    Eventos são criados nas entidades ou use cases e publicados
    através do UnitOfWork após commit bem-sucedido.
    
    with uow:
        ticket = TicketEntity.criar(...)
        repo.save(ticket)
        uow.publish_event(TicketCriadoEvent(...))
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.core.shared.events import DomainEvent


@dataclass
class TicketCriadoEvent(DomainEvent):
    """
    Evento: Ticket foi criado.
    
    Disparado quando um novo ticket é criado no sistema.
    
    Handlers típicos:
    - Enviar email de confirmação ao criador
    - Notificar equipe de suporte
    - Registrar em analytics
    
    Attributes:
        criador_id: ID do usuário que criou
        titulo: Título do ticket
        prioridade: Prioridade do ticket
        categoria: Categoria do ticket
    """
    
    criador_id: str = ""
    titulo: str = ""
    prioridade: str = ""
    categoria: str = ""
    
    def __post_init__(self):
        """Validação e inicialização."""
        # Não chamar super().__post_init__() pois aggregate_id já está setado
        pass
    
    @property
    def aggregate_type(self) -> str:
        return "Ticket"
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "criador_id": self.criador_id,
            "titulo": self.titulo,
            "prioridade": self.prioridade,
            "categoria": self.categoria,
        }


@dataclass
class TicketAtribuidoEvent(DomainEvent):
    """
    Evento: Ticket foi atribuído a técnico.
    
    Disparado quando um ticket é atribuído a um técnico.
    
    Handlers típicos:
    - Notificar técnico por email/push
    - Atualizar dashboard de carga
    - Criar agendamento automático
    
    Attributes:
        tecnico_id: ID do técnico atribuído
        atribuido_por_id: ID de quem fez a atribuição (opcional)
    """
    
    tecnico_id: str = ""
    atribuido_por_id: Optional[str] = None
    
    def __post_init__(self):
        pass
    
    @property
    def aggregate_type(self) -> str:
        return "Ticket"
    
    def _get_event_data(self) -> Dict[str, Any]:
        data = {"tecnico_id": self.tecnico_id}
        if self.atribuido_por_id:
            data["atribuido_por_id"] = self.atribuido_por_id
        return data


@dataclass
class TicketFechadoEvent(DomainEvent):
    """
    Evento: Ticket foi fechado.
    
    Disparado quando um ticket é fechado/resolvido.
    
    Handlers típicos:
    - Enviar pesquisa de satisfação
    - Atualizar métricas de SLA
    - Liberar recursos do técnico
    
    Attributes:
        fechado_por_id: ID do usuário que fechou
        tempo_resolucao_horas: Tempo total para resolver (em horas)
        dentro_sla: Se foi resolvido dentro do SLA
    """
    
    fechado_por_id: str = ""
    tempo_resolucao_horas: Optional[float] = None
    dentro_sla: bool = True
    
    def __post_init__(self):
        pass
    
    @property
    def aggregate_type(self) -> str:
        return "Ticket"
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "fechado_por_id": self.fechado_por_id,
            "tempo_resolucao_horas": self.tempo_resolucao_horas,
            "dentro_sla": self.dentro_sla,
        }


@dataclass
class TicketReabertoEvent(DomainEvent):
    """
    Evento: Ticket foi reaberto.
    
    Disparado quando um ticket fechado é reaberto.
    
    Handlers típicos:
    - Notificar equipe de suporte
    - Alertar gerência (possível problema recorrente)
    - Registrar para análise de qualidade
    
    Attributes:
        reaberto_por_id: ID do usuário que reabriu
        motivo: Motivo da reabertura (opcional)
    """
    
    reaberto_por_id: str = ""
    motivo: Optional[str] = None
    
    def __post_init__(self):
        pass
    
    @property
    def aggregate_type(self) -> str:
        return "Ticket"
    
    def _get_event_data(self) -> Dict[str, Any]:
        data = {"reaberto_por_id": self.reaberto_por_id}
        if self.motivo:
            data["motivo"] = self.motivo
        return data


@dataclass
class TicketPrioridadeAlteradaEvent(DomainEvent):
    """
    Evento: Prioridade do ticket foi alterada.
    
    Disparado quando a prioridade de um ticket muda.
    
    Handlers típicos:
    - Notificar técnico se escalonado
    - Recalcular fila de atendimento
    - Alertar gerência para prioridade crítica
    
    Attributes:
        prioridade_anterior: Prioridade antes da mudança
        prioridade_nova: Prioridade após mudança
        alterado_por_id: ID de quem alterou
    """
    
    prioridade_anterior: str = ""
    prioridade_nova: str = ""
    alterado_por_id: str = ""
    
    def __post_init__(self):
        pass
    
    @property
    def aggregate_type(self) -> str:
        return "Ticket"
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "prioridade_anterior": self.prioridade_anterior,
            "prioridade_nova": self.prioridade_nova,
            "alterado_por_id": self.alterado_por_id,
        }


@dataclass
class TicketComentarioAdicionadoEvent(DomainEvent):
    """
    Evento: Comentário foi adicionado ao ticket.
    
    Attributes:
        autor_id: ID do autor do comentário
        conteudo_preview: Preview do conteúdo (primeiros 100 chars)
        e_interno: Se é comentário interno (não visível ao cliente)
    """
    
    autor_id: str = ""
    conteudo_preview: str = ""
    e_interno: bool = False
    
    def __post_init__(self):
        pass
    
    @property
    def aggregate_type(self) -> str:
        return "Ticket"
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "autor_id": self.autor_id,
            "conteudo_preview": self.conteudo_preview,
            "e_interno": self.e_interno,
        }


@dataclass
class TicketSLAVioladoEvent(DomainEvent):
    """
    Evento: SLA do ticket foi violado (atrasou).
    
    Disparado quando um ticket passa do prazo de SLA
    sem ser resolvido.
    
    Handlers típicos:
    - Alertar gerência
    - Escalar ticket automaticamente
    - Registrar para relatórios
    
    Attributes:
        prazo_sla: Prazo original do SLA
        horas_atraso: Quantas horas de atraso
        tecnico_responsavel_id: ID do técnico (se atribuído)
    """
    
    prazo_sla: datetime = field(default_factory=datetime.now)
    horas_atraso: float = 0.0
    tecnico_responsavel_id: Optional[str] = None
    
    def __post_init__(self):
        pass
    
    @property
    def aggregate_type(self) -> str:
        return "Ticket"
    
    def _get_event_data(self) -> Dict[str, Any]:
        data = {
            "prazo_sla": self.prazo_sla.isoformat(),
            "horas_atraso": self.horas_atraso,
        }
        if self.tecnico_responsavel_id:
            data["tecnico_responsavel_id"] = self.tecnico_responsavel_id
        return data

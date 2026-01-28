"""
Entidades do Domínio de Tickets.

Este módulo define as entidades de domínio que encapsulam
regras de negócio relacionadas a tickets de suporte.

Entidades:
- TicketEntity: Agregado principal do domínio
- TicketStatus: Estados possíveis de um ticket
- TicketPriority: Níveis de prioridade

Regras de Negócio Encapsuladas:
- Validação de dados na criação
- Cálculo automático de SLA por prioridade
- Transições de status controladas
- Verificação de atraso baseada em SLA
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List
import uuid

from src.core.shared.exceptions import (
    ValidationError,
    BusinessRuleViolationError,
)


class TicketStatus(Enum):
    """
    Estados possíveis de um ticket.
    
    Fluxo de Estados:
        ABERTO → EM_PROGRESSO → RESOLVIDO → FECHADO
                      ↓              ↑
              AGUARDANDO_CLIENTE ────┘
        
        FECHADO → ABERTO (reabrir)
    """
    
    ABERTO = "Aberto"
    EM_PROGRESSO = "Em Progresso"
    AGUARDANDO_CLIENTE = "Aguardando Cliente"
    RESOLVIDO = "Resolvido"
    FECHADO = "Fechado"
    
    @classmethod
    def from_string(cls, value: str) -> "TicketStatus":
        """
        Converte string para enum.
        
        Args:
            value: Valor string (nome ou valor do enum)
            
        Returns:
            TicketStatus correspondente
            
        Raises:
            ValueError: Se valor inválido
        """
        # Tenta pelo nome (ABERTO)
        try:
            return cls[value.upper().replace(" ", "_")]
        except KeyError:
            pass
        
        # Tenta pelo valor ("Aberto")
        for status in cls:
            if status.value.lower() == value.lower():
                return status
        
        raise ValueError(f"Status inválido: {value}")


class TicketPriority(Enum):
    """
    Níveis de prioridade com SLA associado.
    
    SLA por Prioridade:
        CRÍTICA: 4 horas
        ALTA: 24 horas (1 dia)
        MÉDIA: 72 horas (3 dias)
        BAIXA: 168 horas (7 dias)
    """
    
    BAIXA = "Baixa"
    MEDIA = "Média"
    ALTA = "Alta"
    CRITICA = "Crítica"
    
    @property
    def sla_horas(self) -> int:
        """Retorna horas de SLA para esta prioridade."""
        sla_map = {
            TicketPriority.CRITICA: 4,
            TicketPriority.ALTA: 24,
            TicketPriority.MEDIA: 72,
            TicketPriority.BAIXA: 168,
        }
        return sla_map[self]
    
    @classmethod
    def from_string(cls, value: str) -> "TicketPriority":
        """
        Converte string para enum.
        
        Args:
            value: Valor string (nome ou valor do enum)
            
        Returns:
            TicketPriority correspondente
            
        Raises:
            ValueError: Se valor inválido
        """
        # Tenta pelo nome (MEDIA)
        try:
            return cls[value.upper()]
        except KeyError:
            pass
        
        # Tenta pelo valor ("Média")
        for priority in cls:
            if priority.value.lower() == value.lower():
                return priority
        
        raise ValueError(f"Prioridade inválida: {value}")


@dataclass
class TicketEntity:
    """
    Entidade de Domínio: Ticket.
    
    Agregado principal do domínio de suporte técnico.
    Encapsula todas as regras de negócio relacionadas a tickets.
    
    Invariantes:
    - Título deve ter pelo menos 3 caracteres
    - Descrição deve ter pelo menos 10 caracteres
    - Ticket fechado não pode ser modificado (exceto reabrir)
    - Ticket só pode ser fechado se estiver atribuído
    - SLA é calculado automaticamente na criação
    
    Attributes:
        id: Identificador único (UUID)
        titulo: Título descritivo do ticket
        descricao: Descrição detalhada do problema
        status: Estado atual do ticket
        prioridade: Nível de prioridade
        criador_id: ID do usuário que criou
        atribuido_a_id: ID do técnico responsável
        categoria: Categoria do ticket
        criado_em: Data/hora de criação
        atualizado_em: Data/hora da última atualização
        sla_prazo: Prazo máximo para resolução
        tags: Lista de tags para categorização
    
    Example:
        ticket = TicketEntity.criar(
            titulo="Sistema lento",
            descricao="O sistema está demorando mais de 10s para responder",
            criador_id="user123",
            prioridade=TicketPriority.ALTA
        )
        
        ticket.atribuir_a("tecnico456")
        ticket.fechar()
    """
    
    # Identificação
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Dados principais
    titulo: str = ""
    descricao: str = ""
    categoria: str = "Geral"
    
    # Estado
    status: TicketStatus = field(default=TicketStatus.ABERTO)
    prioridade: TicketPriority = field(default=TicketPriority.MEDIA)
    
    # Relacionamentos
    criador_id: str = ""
    atribuido_a_id: Optional[str] = None
    
    # Timestamps
    criado_em: datetime = field(default_factory=datetime.now)
    atualizado_em: datetime = field(default_factory=datetime.now)
    
    # SLA
    sla_prazo: Optional[datetime] = None
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    
    # Constantes de validação
    TITULO_MIN_LENGTH: int = 3
    TITULO_MAX_LENGTH: int = 200
    DESCRICAO_MIN_LENGTH: int = 10
    DESCRICAO_MAX_LENGTH: int = 5000
    
    @classmethod
    def criar(
        cls,
        titulo: str,
        descricao: str,
        criador_id: str,
        prioridade: TicketPriority = TicketPriority.MEDIA,
        categoria: str = "Geral",
        tags: Optional[List[str]] = None,
    ) -> "TicketEntity":
        """
        Factory method para criar ticket com validações.
        
        Este método é o ponto de entrada recomendado para criar tickets,
        pois executa todas as validações de negócio necessárias.
        
        Args:
            titulo: Título do ticket (min 3 caracteres)
            descricao: Descrição detalhada (min 10 caracteres)
            criador_id: ID do usuário criador
            prioridade: Nível de prioridade (default: MEDIA)
            categoria: Categoria do ticket (default: "Geral")
            tags: Lista de tags opcional
            
        Returns:
            Nova instância de TicketEntity
            
        Raises:
            ValidationError: Se dados de entrada inválidos
            
        Example:
            ticket = TicketEntity.criar(
                titulo="Bug no login",
                descricao="Usuário não consegue fazer login com senha correta",
                criador_id="user123",
                prioridade=TicketPriority.ALTA,
                categoria="Autenticação"
            )
        """
        # Validações de entrada
        cls._validar_titulo(titulo)
        cls._validar_descricao(descricao)
        cls._validar_criador(criador_id)
        
        # Criar instância
        ticket = cls(
            titulo=titulo.strip(),
            descricao=descricao.strip(),
            criador_id=criador_id,
            prioridade=prioridade,
            categoria=categoria.strip() if categoria else "Geral",
            status=TicketStatus.ABERTO,
            tags=tags or [],
        )
        
        # Calcular SLA baseado em prioridade
        ticket._calcular_sla()
        
        return ticket
    
    @classmethod
    def _validar_titulo(cls, titulo: str) -> None:
        """Valida título do ticket."""
        if not titulo:
            raise ValidationError(
                "Título é obrigatório",
                field="titulo"
            )
        
        titulo_limpo = titulo.strip()
        
        if len(titulo_limpo) < cls.TITULO_MIN_LENGTH:
            raise ValidationError(
                f"Título deve ter pelo menos {cls.TITULO_MIN_LENGTH} caracteres",
                field="titulo"
            )
        
        if len(titulo_limpo) > cls.TITULO_MAX_LENGTH:
            raise ValidationError(
                f"Título deve ter no máximo {cls.TITULO_MAX_LENGTH} caracteres",
                field="titulo"
            )
    
    @classmethod
    def _validar_descricao(cls, descricao: str) -> None:
        """Valida descrição do ticket."""
        if not descricao:
            raise ValidationError(
                "Descrição é obrigatória",
                field="descricao"
            )
        
        descricao_limpa = descricao.strip()
        
        if len(descricao_limpa) < cls.DESCRICAO_MIN_LENGTH:
            raise ValidationError(
                f"Descrição deve ter pelo menos {cls.DESCRICAO_MIN_LENGTH} caracteres",
                field="descricao"
            )
        
        if len(descricao_limpa) > cls.DESCRICAO_MAX_LENGTH:
            raise ValidationError(
                f"Descrição deve ter no máximo {cls.DESCRICAO_MAX_LENGTH} caracteres",
                field="descricao"
            )
    
    @classmethod
    def _validar_criador(cls, criador_id: str) -> None:
        """Valida ID do criador."""
        if not criador_id:
            raise ValidationError(
                "Criador é obrigatório",
                field="criador_id"
            )
    
    def _calcular_sla(self) -> None:
        """
        Calcula prazo de SLA baseado em prioridade.
        
        O SLA é calculado a partir do momento de criação,
        usando as horas definidas para cada prioridade.
        """
        horas_sla = self.prioridade.sla_horas
        self.sla_prazo = self.criado_em + timedelta(hours=horas_sla)
    
    def atribuir_a(self, tecnico_id: str) -> None:
        """
        Atribui ticket a um técnico.
        
        Regras:
        - Ticket fechado não pode ser atribuído
        - Atribuição muda status para EM_PROGRESSO
        - Atualiza timestamp de modificação
        
        Args:
            tecnico_id: ID do técnico responsável
            
        Raises:
            BusinessRuleViolationError: Se ticket fechado
            ValidationError: Se tecnico_id vazio
        """
        if not tecnico_id:
            raise ValidationError(
                "ID do técnico é obrigatório",
                field="tecnico_id"
            )
        
        if self.status == TicketStatus.FECHADO:
            raise BusinessRuleViolationError(
                "Não é possível atribuir ticket fechado",
                rule="ticket_fechado_imutavel"
            )
        
        self.atribuido_a_id = tecnico_id
        self.status = TicketStatus.EM_PROGRESSO
        self._atualizar_timestamp()
    
    def alterar_status(self, novo_status: TicketStatus) -> None:
        """
        Altera status do ticket com validação de transição.
        
        Transições válidas:
        - ABERTO → EM_PROGRESSO, AGUARDANDO_CLIENTE
        - EM_PROGRESSO → AGUARDANDO_CLIENTE, RESOLVIDO
        - AGUARDANDO_CLIENTE → EM_PROGRESSO, RESOLVIDO
        - RESOLVIDO → FECHADO, EM_PROGRESSO
        - FECHADO → ABERTO (reabrir)
        
        Args:
            novo_status: Novo status desejado
            
        Raises:
            BusinessRuleViolationError: Se transição inválida
        """
        transicoes_validas = {
            TicketStatus.ABERTO: [
                TicketStatus.EM_PROGRESSO,
                TicketStatus.AGUARDANDO_CLIENTE,
            ],
            TicketStatus.EM_PROGRESSO: [
                TicketStatus.AGUARDANDO_CLIENTE,
                TicketStatus.RESOLVIDO,
            ],
            TicketStatus.AGUARDANDO_CLIENTE: [
                TicketStatus.EM_PROGRESSO,
                TicketStatus.RESOLVIDO,
            ],
            TicketStatus.RESOLVIDO: [
                TicketStatus.FECHADO,
                TicketStatus.EM_PROGRESSO,
            ],
            TicketStatus.FECHADO: [
                TicketStatus.ABERTO,  # Reabrir
            ],
        }
        
        if novo_status not in transicoes_validas.get(self.status, []):
            raise BusinessRuleViolationError(
                f"Transição de {self.status.value} para {novo_status.value} não é permitida",
                rule="transicao_status_invalida"
            )
        
        self.status = novo_status
        self._atualizar_timestamp()
    
    def fechar(self) -> None:
        """
        Fecha o ticket.
        
        Regras:
        - Ticket deve estar atribuído
        - Ticket não pode já estar fechado
        
        Raises:
            BusinessRuleViolationError: Se regras violadas
        """
        if not self.atribuido_a_id:
            raise BusinessRuleViolationError(
                "Ticket deve ser atribuído antes de ser fechado",
                rule="atribuicao_obrigatoria_para_fechar"
            )
        
        if self.status == TicketStatus.FECHADO:
            raise BusinessRuleViolationError(
                "Ticket já está fechado",
                rule="ticket_ja_fechado"
            )
        
        self.status = TicketStatus.FECHADO
        self._atualizar_timestamp()
    
    def reabrir(self) -> None:
        """
        Reabre um ticket fechado.
        
        Regras:
        - Apenas tickets fechados podem ser reabertos
        - Atribuição é removida
        - Status volta para ABERTO
        
        Raises:
            BusinessRuleViolationError: Se ticket não está fechado
        """
        if self.status != TicketStatus.FECHADO:
            raise BusinessRuleViolationError(
                "Apenas tickets fechados podem ser reabertos",
                rule="apenas_fechado_pode_reabrir"
            )
        
        self.status = TicketStatus.ABERTO
        self.atribuido_a_id = None
        self._atualizar_timestamp()
    
    def alterar_prioridade(self, nova_prioridade: TicketPriority) -> None:
        """
        Altera prioridade e recalcula SLA.
        
        Args:
            nova_prioridade: Nova prioridade desejada
            
        Raises:
            BusinessRuleViolationError: Se ticket fechado
        """
        if self.status == TicketStatus.FECHADO:
            raise BusinessRuleViolationError(
                "Não é possível alterar prioridade de ticket fechado",
                rule="ticket_fechado_imutavel"
            )
        
        self.prioridade = nova_prioridade
        self._calcular_sla()
        self._atualizar_timestamp()
    
    def adicionar_tag(self, tag: str) -> None:
        """
        Adiciona tag ao ticket.
        
        Args:
            tag: Tag a ser adicionada
        """
        tag_limpa = tag.strip().lower()
        if tag_limpa and tag_limpa not in self.tags:
            self.tags.append(tag_limpa)
            self._atualizar_timestamp()
    
    def remover_tag(self, tag: str) -> None:
        """
        Remove tag do ticket.
        
        Args:
            tag: Tag a ser removida
        """
        tag_limpa = tag.strip().lower()
        if tag_limpa in self.tags:
            self.tags.remove(tag_limpa)
            self._atualizar_timestamp()
    
    def _atualizar_timestamp(self) -> None:
        """Atualiza timestamp de modificação."""
        self.atualizado_em = datetime.now()
    
    @property
    def esta_atrasado(self) -> bool:
        """
        Verifica se ticket está atrasado baseado no SLA.
        
        Um ticket é considerado atrasado se:
        - Tem SLA definido
        - Não está fechado
        - Data atual passou do prazo de SLA
        
        Returns:
            True se atrasado, False caso contrário
        """
        if not self.sla_prazo:
            return False
        
        if self.status == TicketStatus.FECHADO:
            return False
        
        return datetime.now() > self.sla_prazo
    
    @property
    def tempo_restante_sla(self) -> Optional[timedelta]:
        """
        Calcula tempo restante até prazo do SLA.
        
        Returns:
            Timedelta positivo se dentro do prazo, negativo se atrasado.
            None se sem SLA ou fechado.
        """
        if not self.sla_prazo or self.status == TicketStatus.FECHADO:
            return None
        
        return self.sla_prazo - datetime.now()
    
    @property
    def esta_atribuido(self) -> bool:
        """Verifica se ticket está atribuído a alguém."""
        return self.atribuido_a_id is not None
    
    def __repr__(self) -> str:
        """Representação string para debugging."""
        return (
            f"TicketEntity("
            f"id={self.id[:8]}..., "
            f"titulo='{self.titulo[:20]}...', "
            f"status={self.status.value}, "
            f"prioridade={self.prioridade.value}"
            f")"
        )
    
    def __eq__(self, other: object) -> bool:
        """Comparação por ID (identidade de entidade)."""
        if not isinstance(other, TicketEntity):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        """Hash baseado em ID."""
        return hash(self.id)

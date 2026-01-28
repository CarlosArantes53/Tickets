"""
Django Models para o domínio de Tickets.

Estes models são ADAPTERS - implementam a persistência para as
entidades de domínio definidas em src/core/tickets/entities.py.

IMPORTANTE:
- Models NÃO contêm lógica de negócio
- Lógica de negócio fica nas Entities do Core
- Models são mapeados para/de Entities via Mappers

Relacionamentos:
- TicketModel: Tabela principal de tickets
- TicketCommentModel: Comentários em tickets (futuro)
- TicketHistoryModel: Histórico de alterações (Event Store simplificado)
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid


class TicketStatusChoices(models.TextChoices):
    """Choices para status de ticket (espelha TicketStatus do Core)."""
    ABERTO = 'Aberto', 'Aberto'
    EM_PROGRESSO = 'Em Progresso', 'Em Progresso'
    AGUARDANDO_CLIENTE = 'Aguardando Cliente', 'Aguardando Cliente'
    RESOLVIDO = 'Resolvido', 'Resolvido'
    FECHADO = 'Fechado', 'Fechado'


class TicketPriorityChoices(models.TextChoices):
    """Choices para prioridade de ticket (espelha TicketPriority do Core)."""
    BAIXA = 'Baixa', 'Baixa'
    MEDIA = 'Média', 'Média'
    ALTA = 'Alta', 'Alta'
    CRITICA = 'Crítica', 'Crítica'


class TicketModel(models.Model):
    """
    Model Django para persistência de Tickets.
    
    Este model é um ADAPTER que persiste dados do TicketEntity.
    NÃO contém lógica de negócio - apenas estrutura de dados.
    
    Fields:
        id: UUID como primary key (gerado pela Entity)
        titulo: Título do ticket
        descricao: Descrição detalhada
        status: Estado atual (choices)
        prioridade: Nível de prioridade (choices)
        categoria: Categoria do ticket
        criador_id: ID do usuário criador (string para flexibilidade)
        atribuido_a_id: ID do técnico responsável
        criado_em: Timestamp de criação
        atualizado_em: Timestamp de última atualização
        sla_prazo: Deadline de SLA
        tags: Lista de tags (JSONField)
    """
    
    # Primary Key - UUID gerado pela Entity
    id = models.CharField(
        max_length=36,
        primary_key=True,
        editable=False,
        help_text="UUID único do ticket"
    )
    
    # Dados principais
    titulo = models.CharField(
        max_length=200,
        db_index=True,
        help_text="Título descritivo do ticket"
    )
    
    descricao = models.TextField(
        help_text="Descrição detalhada do problema"
    )
    
    categoria = models.CharField(
        max_length=100,
        default='Geral',
        db_index=True,
        help_text="Categoria do ticket"
    )
    
    # Estado
    status = models.CharField(
        max_length=50,
        choices=TicketStatusChoices.choices,
        default=TicketStatusChoices.ABERTO,
        db_index=True,
        help_text="Estado atual do ticket"
    )
    
    prioridade = models.CharField(
        max_length=20,
        choices=TicketPriorityChoices.choices,
        default=TicketPriorityChoices.MEDIA,
        db_index=True,
        help_text="Nível de prioridade"
    )
    
    # Relacionamentos (strings para flexibilidade de integração)
    # Em produção, pode ser ForeignKey para User model
    criador_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="ID do usuário criador"
    )
    
    atribuido_a_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="ID do técnico responsável"
    )
    
    # Timestamps
    criado_em = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Data/hora de criação"
    )
    
    atualizado_em = models.DateTimeField(
        auto_now=True,
        help_text="Data/hora da última atualização"
    )
    
    # SLA
    sla_prazo = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Prazo máximo para resolução"
    )
    
    # Metadata
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de tags para categorização"
    )
    
    class Meta:
        db_table = 'tickets'
        verbose_name = 'Ticket'
        verbose_name_plural = 'Tickets'
        ordering = ['-criado_em']
        indexes = [
            # Índices compostos para queries frequentes
            models.Index(fields=['status', 'criado_em']),
            models.Index(fields=['atribuido_a_id', 'status']),
            models.Index(fields=['prioridade', 'sla_prazo']),
            models.Index(fields=['criador_id', 'criado_em']),
        ]
    
    def __str__(self):
        return f"[{self.id[:8]}] {self.titulo}"
    
    def __repr__(self):
        return f"<TicketModel id={self.id[:8]} status={self.status}>"


class TicketHistoryModel(models.Model):
    """
    Event Store simplificado para histórico de tickets.
    
    Registra todas as alterações em tickets para:
    - Auditoria
    - Debugging
    - Analytics
    - Potencial Event Sourcing futuro
    
    Fields:
        id: Auto-incrementing PK
        ticket: Referência ao ticket
        event_type: Tipo do evento (TicketCriado, TicketAtribuido, etc)
        event_data: Dados do evento em JSON
        user_id: Usuário que causou o evento
        created_at: Timestamp do evento
    """
    
    id = models.BigAutoField(primary_key=True)
    
    ticket = models.ForeignKey(
        TicketModel,
        on_delete=models.CASCADE,
        related_name='history',
        help_text="Ticket relacionado"
    )
    
    event_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Tipo do evento de domínio"
    )
    
    event_data = models.JSONField(
        default=dict,
        help_text="Dados serializados do evento"
    )
    
    user_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Usuário que causou o evento"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp do evento"
    )
    
    class Meta:
        db_table = 'ticket_history'
        verbose_name = 'Histórico de Ticket'
        verbose_name_plural = 'Histórico de Tickets'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ticket', 'created_at']),
            models.Index(fields=['event_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.ticket_id[:8]} @ {self.created_at}"


class DomainEventModel(models.Model):
    """
    Event Store genérico para Domain Events.
    
    Persiste todos os eventos de domínio para:
    - Auditoria completa
    - Replay de eventos
    - Integração com outros sistemas
    - Analytics
    
    Preparado para Event Sourcing completo no futuro.
    """
    
    # Identificação
    event_id = models.CharField(
        max_length=36,
        primary_key=True,
        help_text="UUID único do evento"
    )
    
    event_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Tipo do evento (ex: TicketCriadoEvent)"
    )
    
    aggregate_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Tipo do agregado (ex: Ticket)"
    )
    
    aggregate_id = models.CharField(
        max_length=36,
        db_index=True,
        help_text="ID do agregado que gerou o evento"
    )
    
    # Dados do evento
    event_data = models.JSONField(
        default=dict,
        help_text="Dados serializados do evento"
    )
    
    # Versionamento
    version = models.IntegerField(
        default=1,
        help_text="Versão do schema do evento"
    )
    
    sequence = models.BigIntegerField(
        default=0,
        help_text="Sequência do evento no agregado"
    )
    
    # Metadata
    occurred_at = models.DateTimeField(
        help_text="Quando o evento ocorreu"
    )
    
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Quando o evento foi persistido"
    )
    
    # Correlation (para rastreamento)
    correlation_id = models.CharField(
        max_length=36,
        null=True,
        blank=True,
        db_index=True,
        help_text="ID para rastrear fluxo de eventos relacionados"
    )
    
    causation_id = models.CharField(
        max_length=36,
        null=True,
        blank=True,
        help_text="ID do evento que causou este"
    )
    
    user_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="Usuário que iniciou a ação"
    )
    
    class Meta:
        db_table = 'domain_events'
        verbose_name = 'Evento de Domínio'
        verbose_name_plural = 'Eventos de Domínio'
        ordering = ['recorded_at']
        indexes = [
            models.Index(fields=['aggregate_id', 'sequence']),
            models.Index(fields=['aggregate_type', 'recorded_at']),
            models.Index(fields=['event_type', 'recorded_at']),
            models.Index(fields=['correlation_id']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.aggregate_id[:8]} @ {self.occurred_at}"

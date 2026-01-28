"""
Django Admin para o domínio de Tickets.

Configuração do admin para gerenciamento de tickets via interface web.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from .models import TicketModel, TicketHistoryModel, DomainEventModel


@admin.register(TicketModel)
class TicketAdmin(admin.ModelAdmin):
    """Admin para TicketModel."""
    
    list_display = [
        'id_curto',
        'titulo',
        'status_badge',
        'prioridade_badge',
        'categoria',
        'criador_id',
        'atribuido_a_id',
        'criado_em',
        'sla_status',
    ]
    
    list_filter = [
        'status',
        'prioridade',
        'categoria',
        'criado_em',
    ]
    
    search_fields = [
        'id',
        'titulo',
        'descricao',
        'criador_id',
        'atribuido_a_id',
    ]
    
    readonly_fields = [
        'id',
        'criado_em',
        'atualizado_em',
    ]
    
    fieldsets = [
        ('Identificação', {
            'fields': ['id', 'titulo', 'descricao', 'categoria', 'tags'],
        }),
        ('Status', {
            'fields': ['status', 'prioridade', 'sla_prazo'],
        }),
        ('Responsáveis', {
            'fields': ['criador_id', 'atribuido_a_id'],
        }),
        ('Timestamps', {
            'fields': ['criado_em', 'atualizado_em'],
            'classes': ['collapse'],
        }),
    ]
    
    ordering = ['-criado_em']
    
    date_hierarchy = 'criado_em'
    
    def id_curto(self, obj):
        """Exibe ID curto (primeiros 8 caracteres)."""
        return obj.id[:8] + '...'
    id_curto.short_description = 'ID'
    
    def status_badge(self, obj):
        """Exibe status com badge colorido."""
        colors = {
            'Aberto': '#17a2b8',
            'Em Progresso': '#ffc107',
            'Aguardando Cliente': '#6c757d',
            'Resolvido': '#28a745',
            'Fechado': '#343a40',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.status
        )
    status_badge.short_description = 'Status'
    
    def prioridade_badge(self, obj):
        """Exibe prioridade com badge colorido."""
        colors = {
            'Baixa': '#28a745',
            'Média': '#ffc107',
            'Alta': '#fd7e14',
            'Crítica': '#dc3545',
        }
        color = colors.get(obj.prioridade, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.prioridade
        )
    prioridade_badge.short_description = 'Prioridade'
    
    def sla_status(self, obj):
        """Exibe status do SLA."""
        if not obj.sla_prazo:
            return '-'
        
        if obj.status == 'Fechado':
            return format_html(
                '<span style="color: #28a745;">✓ Fechado</span>'
            )
        
        now = timezone.now()
        if now > obj.sla_prazo:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">⚠ Atrasado</span>'
            )
        
        return format_html(
            '<span style="color: #28a745;">✓ No prazo</span>'
        )
    sla_status.short_description = 'SLA'


@admin.register(TicketHistoryModel)
class TicketHistoryAdmin(admin.ModelAdmin):
    """Admin para histórico de tickets."""
    
    list_display = [
        'id',
        'ticket_id_curto',
        'event_type',
        'user_id',
        'created_at',
    ]
    
    list_filter = [
        'event_type',
        'created_at',
    ]
    
    search_fields = [
        'ticket__id',
        'event_type',
        'user_id',
    ]
    
    readonly_fields = [
        'id',
        'ticket',
        'event_type',
        'event_data',
        'user_id',
        'created_at',
    ]
    
    def ticket_id_curto(self, obj):
        """Exibe ID do ticket curto."""
        return obj.ticket_id[:8] + '...'
    ticket_id_curto.short_description = 'Ticket'


@admin.register(DomainEventModel)
class DomainEventAdmin(admin.ModelAdmin):
    """Admin para eventos de domínio."""
    
    list_display = [
        'event_id_curto',
        'event_type',
        'aggregate_type',
        'aggregate_id_curto',
        'occurred_at',
        'user_id',
    ]
    
    list_filter = [
        'event_type',
        'aggregate_type',
        'occurred_at',
    ]
    
    search_fields = [
        'event_id',
        'aggregate_id',
        'event_type',
        'user_id',
        'correlation_id',
    ]
    
    readonly_fields = [
        'event_id',
        'event_type',
        'aggregate_type',
        'aggregate_id',
        'event_data',
        'version',
        'sequence',
        'occurred_at',
        'recorded_at',
        'correlation_id',
        'causation_id',
        'user_id',
    ]
    
    def event_id_curto(self, obj):
        """Exibe ID do evento curto."""
        return obj.event_id[:8] + '...'
    event_id_curto.short_description = 'Event ID'
    
    def aggregate_id_curto(self, obj):
        """Exibe ID do agregado curto."""
        return obj.aggregate_id[:8] + '...'
    aggregate_id_curto.short_description = 'Aggregate'

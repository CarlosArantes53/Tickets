"""
Migration inicial para o domínio de Tickets.

Cria as tabelas:
- tickets: Tabela principal de tickets
- ticket_history: Histórico de alterações
- domain_events: Event Store
"""

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    """Migration inicial."""

    initial = True

    dependencies = [
    ]

    operations = [
        # =================================================================
        # Tabela: tickets
        # =================================================================
        migrations.CreateModel(
            name='TicketModel',
            fields=[
                ('id', models.CharField(
                    max_length=36,
                    primary_key=True,
                    serialize=False,
                    editable=False,
                    help_text='UUID único do ticket'
                )),
                ('titulo', models.CharField(
                    max_length=200,
                    db_index=True,
                    help_text='Título descritivo do ticket'
                )),
                ('descricao', models.TextField(
                    help_text='Descrição detalhada do problema'
                )),
                ('categoria', models.CharField(
                    max_length=100,
                    default='Geral',
                    db_index=True,
                    help_text='Categoria do ticket'
                )),
                ('status', models.CharField(
                    max_length=50,
                    choices=[
                        ('Aberto', 'Aberto'),
                        ('Em Progresso', 'Em Progresso'),
                        ('Aguardando Cliente', 'Aguardando Cliente'),
                        ('Resolvido', 'Resolvido'),
                        ('Fechado', 'Fechado'),
                    ],
                    default='Aberto',
                    db_index=True,
                    help_text='Estado atual do ticket'
                )),
                ('prioridade', models.CharField(
                    max_length=20,
                    choices=[
                        ('Baixa', 'Baixa'),
                        ('Média', 'Média'),
                        ('Alta', 'Alta'),
                        ('Crítica', 'Crítica'),
                    ],
                    default='Média',
                    db_index=True,
                    help_text='Nível de prioridade'
                )),
                ('criador_id', models.CharField(
                    max_length=100,
                    db_index=True,
                    help_text='ID do usuário criador'
                )),
                ('atribuido_a_id', models.CharField(
                    max_length=100,
                    null=True,
                    blank=True,
                    db_index=True,
                    help_text='ID do técnico responsável'
                )),
                ('criado_em', models.DateTimeField(
                    default=django.utils.timezone.now,
                    db_index=True,
                    help_text='Data/hora de criação'
                )),
                ('atualizado_em', models.DateTimeField(
                    auto_now=True,
                    help_text='Data/hora da última atualização'
                )),
                ('sla_prazo', models.DateTimeField(
                    null=True,
                    blank=True,
                    db_index=True,
                    help_text='Prazo máximo para resolução'
                )),
                ('tags', models.JSONField(
                    default=list,
                    blank=True,
                    help_text='Lista de tags para categorização'
                )),
            ],
            options={
                'db_table': 'tickets',
                'verbose_name': 'Ticket',
                'verbose_name_plural': 'Tickets',
                'ordering': ['-criado_em'],
            },
        ),
        
        # Índices compostos para tickets
        migrations.AddIndex(
            model_name='ticketmodel',
            index=models.Index(
                fields=['status', 'criado_em'],
                name='idx_ticket_status_criado'
            ),
        ),
        migrations.AddIndex(
            model_name='ticketmodel',
            index=models.Index(
                fields=['atribuido_a_id', 'status'],
                name='idx_ticket_tecnico_status'
            ),
        ),
        migrations.AddIndex(
            model_name='ticketmodel',
            index=models.Index(
                fields=['prioridade', 'sla_prazo'],
                name='idx_ticket_prio_sla'
            ),
        ),
        migrations.AddIndex(
            model_name='ticketmodel',
            index=models.Index(
                fields=['criador_id', 'criado_em'],
                name='idx_ticket_criador_data'
            ),
        ),
        
        # =================================================================
        # Tabela: ticket_history
        # =================================================================
        migrations.CreateModel(
            name='TicketHistoryModel',
            fields=[
                ('id', models.BigAutoField(
                    primary_key=True,
                    serialize=False
                )),
                ('event_type', models.CharField(
                    max_length=100,
                    db_index=True,
                    help_text='Tipo do evento de domínio'
                )),
                ('event_data', models.JSONField(
                    default=dict,
                    help_text='Dados serializados do evento'
                )),
                ('user_id', models.CharField(
                    max_length=100,
                    null=True,
                    blank=True,
                    help_text='Usuário que causou o evento'
                )),
                ('created_at', models.DateTimeField(
                    auto_now_add=True,
                    db_index=True,
                    help_text='Timestamp do evento'
                )),
                ('ticket', models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name='history',
                    to='tickets.ticketmodel',
                    help_text='Ticket relacionado'
                )),
            ],
            options={
                'db_table': 'ticket_history',
                'verbose_name': 'Histórico de Ticket',
                'verbose_name_plural': 'Histórico de Tickets',
                'ordering': ['-created_at'],
            },
        ),
        
        # Índices para histórico
        migrations.AddIndex(
            model_name='tickethistorymodel',
            index=models.Index(
                fields=['ticket', 'created_at'],
                name='idx_history_ticket_data'
            ),
        ),
        migrations.AddIndex(
            model_name='tickethistorymodel',
            index=models.Index(
                fields=['event_type', 'created_at'],
                name='idx_history_type_data'
            ),
        ),
        
        # =================================================================
        # Tabela: domain_events (Event Store)
        # =================================================================
        migrations.CreateModel(
            name='DomainEventModel',
            fields=[
                ('event_id', models.CharField(
                    max_length=36,
                    primary_key=True,
                    serialize=False,
                    help_text='UUID único do evento'
                )),
                ('event_type', models.CharField(
                    max_length=100,
                    db_index=True,
                    help_text='Tipo do evento (ex: TicketCriadoEvent)'
                )),
                ('aggregate_type', models.CharField(
                    max_length=100,
                    db_index=True,
                    help_text='Tipo do agregado (ex: Ticket)'
                )),
                ('aggregate_id', models.CharField(
                    max_length=36,
                    db_index=True,
                    help_text='ID do agregado que gerou o evento'
                )),
                ('event_data', models.JSONField(
                    default=dict,
                    help_text='Dados serializados do evento'
                )),
                ('version', models.IntegerField(
                    default=1,
                    help_text='Versão do schema do evento'
                )),
                ('sequence', models.BigIntegerField(
                    default=0,
                    help_text='Sequência do evento no agregado'
                )),
                ('occurred_at', models.DateTimeField(
                    help_text='Quando o evento ocorreu'
                )),
                ('recorded_at', models.DateTimeField(
                    auto_now_add=True,
                    help_text='Quando o evento foi persistido'
                )),
                ('correlation_id', models.CharField(
                    max_length=36,
                    null=True,
                    blank=True,
                    db_index=True,
                    help_text='ID para rastrear fluxo de eventos relacionados'
                )),
                ('causation_id', models.CharField(
                    max_length=36,
                    null=True,
                    blank=True,
                    help_text='ID do evento que causou este'
                )),
                ('user_id', models.CharField(
                    max_length=100,
                    null=True,
                    blank=True,
                    db_index=True,
                    help_text='Usuário que iniciou a ação'
                )),
            ],
            options={
                'db_table': 'domain_events',
                'verbose_name': 'Evento de Domínio',
                'verbose_name_plural': 'Eventos de Domínio',
                'ordering': ['recorded_at'],
            },
        ),
        
        # Índices para domain_events
        migrations.AddIndex(
            model_name='domaineventmodel',
            index=models.Index(
                fields=['aggregate_id', 'sequence'],
                name='idx_event_aggregate_seq'
            ),
        ),
        migrations.AddIndex(
            model_name='domaineventmodel',
            index=models.Index(
                fields=['aggregate_type', 'recorded_at'],
                name='idx_event_type_recorded'
            ),
        ),
        migrations.AddIndex(
            model_name='domaineventmodel',
            index=models.Index(
                fields=['event_type', 'recorded_at'],
                name='idx_event_etype_recorded'
            ),
        ),
        migrations.AddIndex(
            model_name='domaineventmodel',
            index=models.Index(
                fields=['correlation_id'],
                name='idx_event_correlation'
            ),
        ),
    ]

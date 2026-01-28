"""
Django Forms para validação de entrada.

Forms são DRIVING ADAPTERS que validam dados antes de
passar para os Use Cases.

Responsabilidades:
- Validação estrutural (campos obrigatórios, tipos)
- Sanitização de entrada
- Mensagens de erro amigáveis

Princípios:
- Forms NÃO contêm lógica de negócio
- Lógica de negócio fica nas Entities/Use Cases
- Forms são apenas para validação de entrada
"""

from django import forms
from django.core.exceptions import ValidationError

from .models import TicketPriorityChoices


class TicketCreateForm(forms.Form):
    """
    Form para criação de ticket.
    
    Valida dados básicos antes de passar para CriarTicketService.
    """
    
    titulo = forms.CharField(
        label='Título',
        max_length=200,
        min_length=3,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Título do ticket...',
        }),
        error_messages={
            'required': 'Título é obrigatório',
            'min_length': 'Título deve ter pelo menos 3 caracteres',
            'max_length': 'Título deve ter no máximo 200 caracteres',
        },
    )
    
    descricao = forms.CharField(
        label='Descrição',
        min_length=10,
        max_length=5000,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Descreva o problema detalhadamente...',
        }),
        error_messages={
            'required': 'Descrição é obrigatória',
            'min_length': 'Descrição deve ter pelo menos 10 caracteres',
            'max_length': 'Descrição deve ter no máximo 5000 caracteres',
        },
    )
    
    prioridade = forms.ChoiceField(
        label='Prioridade',
        choices=[
            ('BAIXA', 'Baixa'),
            ('MEDIA', 'Média'),
            ('ALTA', 'Alta'),
            ('CRITICA', 'Crítica'),
        ],
        initial='MEDIA',
        widget=forms.Select(attrs={
            'class': 'form-control',
        }),
    )
    
    categoria = forms.CharField(
        label='Categoria',
        max_length=100,
        required=False,
        initial='Geral',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Categoria...',
        }),
    )
    
    tags = forms.CharField(
        label='Tags',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tags separadas por vírgula...',
        }),
        help_text='Separe as tags por vírgula',
    )
    
    def clean_titulo(self):
        """Validação adicional do título."""
        titulo = self.cleaned_data['titulo']
        return titulo.strip()
    
    def clean_descricao(self):
        """Validação adicional da descrição."""
        descricao = self.cleaned_data['descricao']
        return descricao.strip()
    
    def clean_tags(self):
        """Converte string de tags para lista."""
        tags_str = self.cleaned_data.get('tags', '')
        if not tags_str:
            return []
        
        return [tag.strip().lower() for tag in tags_str.split(',') if tag.strip()]


class TicketAtribuirForm(forms.Form):
    """
    Form para atribuição de ticket.
    
    Valida ID do técnico antes de passar para AtribuirTicketService.
    """
    
    tecnico_id = forms.CharField(
        label='Técnico',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ID do técnico...',
        }),
        error_messages={
            'required': 'Técnico é obrigatório',
        },
    )
    
    def clean_tecnico_id(self):
        """Validação do ID do técnico."""
        tecnico_id = self.cleaned_data['tecnico_id']
        return tecnico_id.strip()


class TicketFecharForm(forms.Form):
    """
    Form para fechamento de ticket.
    
    Opcionalmente coleta resolução antes de passar para FecharTicketService.
    """
    
    resolucao = forms.CharField(
        label='Resolução',
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Descreva como o problema foi resolvido...',
        }),
    )


class TicketReabrirForm(forms.Form):
    """
    Form para reabertura de ticket.
    
    Coleta motivo da reabertura antes de passar para ReabrirTicketService.
    """
    
    motivo = forms.CharField(
        label='Motivo',
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Por que o ticket está sendo reaberto?',
        }),
    )


class TicketFiltroForm(forms.Form):
    """
    Form para filtros de listagem.
    
    Usado na view de listagem para filtrar tickets.
    """
    
    status = forms.ChoiceField(
        label='Status',
        required=False,
        choices=[
            ('', 'Todos'),
            ('Aberto', 'Aberto'),
            ('Em Progresso', 'Em Progresso'),
            ('Aguardando Cliente', 'Aguardando Cliente'),
            ('Resolvido', 'Resolvido'),
            ('Fechado', 'Fechado'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control',
        }),
    )
    
    prioridade = forms.ChoiceField(
        label='Prioridade',
        required=False,
        choices=[
            ('', 'Todas'),
            ('Baixa', 'Baixa'),
            ('Média', 'Média'),
            ('Alta', 'Alta'),
            ('Crítica', 'Crítica'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control',
        }),
    )
    
    categoria = forms.CharField(
        label='Categoria',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Categoria...',
        }),
    )
    
    apenas_atrasados = forms.BooleanField(
        label='Apenas atrasados',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
    )

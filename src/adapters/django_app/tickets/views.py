"""
Views Django para o domínio de Tickets.

DRIVING ADAPTERS - direcionam requisições HTTP para o Core.

Responsabilidades:
- Receber requisições HTTP
- Validar entrada (Forms/JSON)
- Invocar Use Cases via Container DI
- Formatar resposta (HTML/JSON)

Padrões:
- Constructor Injection via Container
- Form validation para entrada
- DTO conversion para saída

Princípios:
- Views são THIN (lógica mínima)
- Lógica de negócio fica nos Use Cases
- Views não acessam Models diretamente
"""

import json
import logging
from typing import Any, Dict

from django.views import View
from django.views.generic import ListView, DetailView, CreateView
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from src.core.tickets.dtos import (
    CriarTicketInputDTO,
    AtribuirTicketInputDTO,
    FecharTicketInputDTO,
    TicketOutputDTO,
)
from src.core.shared.exceptions import (
    ValidationError,
    EntityNotFoundError,
    BusinessRuleViolationError,
    DomainException,
)
from src.config.container import get_container

from .models import TicketModel
from .forms import TicketCreateForm, TicketAtribuirForm

logger = logging.getLogger(__name__)


# =============================================================================
# Views HTML (Templates)
# =============================================================================

class TicketListView(View):
    """
    Lista tickets com filtros e paginação.
    
    GET /tickets/
    GET /tickets/?status=Aberto&page=2
    """
    
    template_name = 'tickets/list.html'
    
    def get(self, request: HttpRequest) -> HttpResponse:
        """Lista tickets."""
        container = get_container()
        service = container.listar_tickets_service()
        
        # Extrair filtros da query string
        status = request.GET.get('status')
        criador_id = request.GET.get('criador_id')
        tecnico_id = request.GET.get('tecnico_id')
        
        # Executar use case
        tickets = service.execute(
            status=status,
            criador_id=criador_id,
            tecnico_id=tecnico_id,
        )
        
        # Obter estatísticas
        contar_service = container.contar_tickets_service()
        estatisticas = contar_service.execute()
        
        context = {
            'tickets': tickets,
            'estatisticas': estatisticas,
            'filtros': {
                'status': status,
                'criador_id': criador_id,
                'tecnico_id': tecnico_id,
            },
        }
        
        return render(request, self.template_name, context)


class TicketDetailView(View):
    """
    Exibe detalhes de um ticket.
    
    GET /tickets/<id>/
    """
    
    template_name = 'tickets/detail.html'
    
    def get(self, request: HttpRequest, pk: str) -> HttpResponse:
        """Exibe ticket."""
        container = get_container()
        service = container.obter_ticket_service()
        
        try:
            ticket = service.execute(pk)
        except EntityNotFoundError:
            return render(request, 'tickets/not_found.html', status=404)
        
        context = {
            'ticket': ticket,
        }
        
        return render(request, self.template_name, context)


class TicketCreateView(View):
    """
    Cria novo ticket.
    
    GET /tickets/criar/ - Formulário
    POST /tickets/criar/ - Processa criação
    """
    
    template_name = 'tickets/create.html'
    
    def get(self, request: HttpRequest) -> HttpResponse:
        """Exibe formulário."""
        form = TicketCreateForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request: HttpRequest) -> HttpResponse:
        """Processa criação."""
        form = TicketCreateForm(request.POST)
        
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})
        
        container = get_container()
        service = container.criar_ticket_service()
        
        try:
            # Converter form para DTO
            input_dto = CriarTicketInputDTO(
                titulo=form.cleaned_data['titulo'],
                descricao=form.cleaned_data['descricao'],
                criador_id=str(request.user.id) if request.user.is_authenticated else 'anonymous',
                prioridade=form.cleaned_data.get('prioridade', 'MEDIA'),
                categoria=form.cleaned_data.get('categoria', 'Geral'),
            )
            
            # Executar use case
            output = service.execute(input_dto)
            
            logger.info(f"Ticket criado: {output.id}")
            return redirect('tickets:detail', pk=output.id)
            
        except ValidationError as e:
            form.add_error(e.field if hasattr(e, 'field') else None, str(e))
            return render(request, self.template_name, {'form': form})
        except DomainException as e:
            form.add_error(None, str(e))
            return render(request, self.template_name, {'form': form})


class TicketAtribuirView(View):
    """
    Atribui ticket a técnico.
    
    POST /tickets/<id>/atribuir/
    """
    
    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        """Processa atribuição."""
        form = TicketAtribuirForm(request.POST)
        
        if not form.is_valid():
            return redirect('tickets:detail', pk=pk)
        
        container = get_container()
        service = container.atribuir_ticket_service()
        
        try:
            input_dto = AtribuirTicketInputDTO(
                ticket_id=pk,
                tecnico_id=form.cleaned_data['tecnico_id'],
                atribuido_por_id=str(request.user.id) if request.user.is_authenticated else 'anonymous',
            )
            
            service.execute(input_dto)
            
            logger.info(f"Ticket {pk} atribuído a {form.cleaned_data['tecnico_id']}")
            return redirect('tickets:detail', pk=pk)
            
        except (ValidationError, BusinessRuleViolationError, EntityNotFoundError) as e:
            logger.error(f"Erro ao atribuir ticket: {e}")
            return redirect('tickets:detail', pk=pk)


class TicketFecharView(View):
    """
    Fecha ticket.
    
    POST /tickets/<id>/fechar/
    """
    
    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        """Processa fechamento."""
        container = get_container()
        service = container.fechar_ticket_service()
        
        try:
            input_dto = FecharTicketInputDTO(
                ticket_id=pk,
                fechado_por_id=str(request.user.id) if request.user.is_authenticated else 'anonymous',
                resolucao=request.POST.get('resolucao', ''),
            )
            
            service.execute(input_dto)
            
            logger.info(f"Ticket {pk} fechado")
            return redirect('tickets:detail', pk=pk)
            
        except (ValidationError, BusinessRuleViolationError, EntityNotFoundError) as e:
            logger.error(f"Erro ao fechar ticket: {e}")
            return redirect('tickets:detail', pk=pk)


class TicketReabrirView(View):
    """
    Reabre ticket fechado.
    
    POST /tickets/<id>/reabrir/
    """
    
    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        """Processa reabertura."""
        container = get_container()
        service = container.reabrir_ticket_service()
        
        try:
            output = service.execute(
                ticket_id=pk,
                reaberto_por_id=str(request.user.id) if request.user.is_authenticated else 'anonymous',
                motivo=request.POST.get('motivo', ''),
            )
            
            logger.info(f"Ticket {pk} reaberto")
            return redirect('tickets:detail', pk=pk)
            
        except (ValidationError, BusinessRuleViolationError, EntityNotFoundError) as e:
            logger.error(f"Erro ao reabrir ticket: {e}")
            return redirect('tickets:detail', pk=pk)


# =============================================================================
# Views API JSON
# =============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class TicketAPIListView(View):
    """
    API JSON para listar/criar tickets.
    
    GET /tickets/api/ - Lista tickets
    POST /tickets/api/ - Cria ticket
    """
    
    def get(self, request: HttpRequest) -> JsonResponse:
        """Lista tickets em JSON."""
        container = get_container()
        service = container.listar_tickets_service()
        
        status = request.GET.get('status')
        criador_id = request.GET.get('criador_id')
        tecnico_id = request.GET.get('tecnico_id')
        
        tickets = service.execute(
            status=status,
            criador_id=criador_id,
            tecnico_id=tecnico_id,
        )
        
        return JsonResponse({
            'success': True,
            'data': [t.to_dict() for t in tickets],
            'count': len(tickets),
        })
    
    def post(self, request: HttpRequest) -> JsonResponse:
        """Cria ticket via JSON."""
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON',
            }, status=400)
        
        container = get_container()
        service = container.criar_ticket_service()
        
        try:
            input_dto = CriarTicketInputDTO(
                titulo=data.get('titulo', ''),
                descricao=data.get('descricao', ''),
                criador_id=data.get('criador_id', 'anonymous'),
                prioridade=data.get('prioridade', 'MEDIA'),
                categoria=data.get('categoria', 'Geral'),
                tags=data.get('tags', []),
            )
            
            output = service.execute(input_dto)
            
            return JsonResponse({
                'success': True,
                'data': output.to_dict(),
            }, status=201)
            
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'field': getattr(e, 'field', None),
            }, status=400)
        except DomainException as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
            }, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class TicketAPIDetailView(View):
    """
    API JSON para operações em ticket específico.
    
    GET /tickets/api/<id>/ - Obter ticket
    PUT /tickets/api/<id>/ - Atualizar ticket (futuro)
    DELETE /tickets/api/<id>/ - Deletar ticket (futuro)
    """
    
    def get(self, request: HttpRequest, pk: str) -> JsonResponse:
        """Obtém ticket em JSON."""
        container = get_container()
        service = container.obter_ticket_service()
        
        try:
            ticket = service.execute(pk)
            
            return JsonResponse({
                'success': True,
                'data': ticket.to_dict(),
            })
            
        except EntityNotFoundError:
            return JsonResponse({
                'success': False,
                'error': f'Ticket {pk} não encontrado',
            }, status=404)

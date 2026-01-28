"""
Views Django para o domínio de Tickets.

DRIVING ADAPTERS - direcionam requisições HTTP para o Core.

Responsabilidades:
- Receber requisições HTTP
- Validar entrada (Forms/JSON)
- Invocar Use Cases via Container DI
- Formatar resposta (HTML/JSON)
- Tratamento de erros

Padrões:
- Dependency Injection via Container
- Form validation para entrada
- DTO conversion para saída
- Flash messages para feedback

Princípios:
- Views são THIN (lógica mínima)
- Lógica de negócio fica nos Use Cases
- Views não acessam Models diretamente
"""

import logging
from typing import Any, Dict, Optional

from django.views import View
from django.http import HttpResponse, HttpRequest, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from django.core.paginator import Paginator

from src.core.tickets.dtos import (
    CriarTicketInputDTO,
    AtribuirTicketInputDTO,
    FecharTicketInputDTO,
    AlterarPrioridadeInputDTO,
)
from src.core.shared.exceptions import (
    ValidationError,
    EntityNotFoundError,
    BusinessRuleViolationError,
    DomainException,
)
from src.config.container import get_container

from .forms import (
    TicketCreateForm,
    TicketAtribuirForm,
    TicketFecharForm,
    TicketReabrirForm,
    TicketFiltroForm,
    TicketAlterarPrioridadeForm,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Mixins
# =============================================================================

class ContainerMixin:
    """
    Mixin que fornece acesso ao DI Container.
    
    Permite obter services de forma consistente em todas as views.
    """
    
    def get_container(self):
        """Retorna container de DI."""
        return get_container()
    
    def get_service(self, service_name: str):
        """
        Obtém service do container.
        
        Args:
            service_name: Nome do service no container
            
        Returns:
            Instância do service
        """
        container = self.get_container()
        return getattr(container.services, service_name)()


class FlashMessageMixin:
    """
    Mixin para adicionar flash messages de forma consistente.
    """
    
    def success_message(self, request: HttpRequest, message: str) -> None:
        """Adiciona mensagem de sucesso."""
        messages.success(request, message)
    
    def error_message(self, request: HttpRequest, message: str) -> None:
        """Adiciona mensagem de erro."""
        messages.error(request, message)
    
    def warning_message(self, request: HttpRequest, message: str) -> None:
        """Adiciona mensagem de aviso."""
        messages.warning(request, message)
    
    def info_message(self, request: HttpRequest, message: str) -> None:
        """Adiciona mensagem informativa."""
        messages.info(request, message)


class UserContextMixin:
    """
    Mixin para extrair informações do usuário do request.
    """
    
    def get_user_id(self, request: HttpRequest) -> str:
        """
        Extrai ID do usuário do request.
        
        Args:
            request: Request HTTP
            
        Returns:
            ID do usuário ou 'anonymous'
        """
        if request.user.is_authenticated:
            return str(request.user.id)
        return 'anonymous'
    
    def get_user_display_name(self, request: HttpRequest) -> str:
        """
        Extrai nome de exibição do usuário.
        
        Args:
            request: Request HTTP
            
        Returns:
            Nome do usuário ou 'Anônimo'
        """
        if request.user.is_authenticated:
            return request.user.get_full_name() or request.user.username
        return 'Anônimo'


# =============================================================================
# Views HTML (Templates)
# =============================================================================

class TicketListView(ContainerMixin, FlashMessageMixin, View):
    """
    Lista tickets com filtros e paginação.
    
    GET /tickets/
    GET /tickets/?status=Aberto&page=2
    """
    
    template_name = 'tickets/list.html'
    paginate_by = 20
    
    def get(self, request: HttpRequest) -> HttpResponse:
        """Lista tickets com filtros."""
        # Obter services
        listar_service = self.get_service('listar_tickets_service')
        contar_service = self.get_service('contar_tickets_service')
        
        # Processar filtros
        filtro_form = TicketFiltroForm(request.GET)
        
        # Extrair parâmetros
        status = request.GET.get('status') or None
        prioridade = request.GET.get('prioridade') or None
        criador_id = request.GET.get('criador_id') or None
        tecnico_id = request.GET.get('tecnico_id') or None
        
        # Executar query
        try:
            tickets = listar_service.execute(
                status=status,
                criador_id=criador_id,
                tecnico_id=tecnico_id,
            )
            
            # Filtrar por prioridade (se necessário)
            if prioridade:
                tickets = [t for t in tickets if t.prioridade == prioridade]
            
        except Exception as e:
            logger.error(f"Erro ao listar tickets: {e}")
            tickets = []
            self.error_message(request, "Erro ao carregar tickets.")
        
        # Paginação
        paginator = Paginator(tickets, self.paginate_by)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        # Estatísticas
        try:
            estatisticas = contar_service.execute()
        except Exception:
            estatisticas = {'total': 0, 'por_status': {}}
        
        context = {
            'page_obj': page_obj,
            'tickets': page_obj.object_list,
            'estatisticas': estatisticas,
            'filtro_form': filtro_form,
            'filtros_ativos': {
                'status': status,
                'prioridade': prioridade,
                'criador_id': criador_id,
                'tecnico_id': tecnico_id,
            },
            'total_tickets': paginator.count,
        }
        
        return render(request, self.template_name, context)


class TicketDetailView(ContainerMixin, FlashMessageMixin, UserContextMixin, View):
    """
    Exibe detalhes de um ticket.
    
    GET /tickets/<id>/
    """
    
    template_name = 'tickets/detail.html'
    
    def get(self, request: HttpRequest, pk: str) -> HttpResponse:
        """Exibe detalhes do ticket."""
        obter_service = self.get_service('obter_ticket_service')
        
        try:
            ticket = obter_service.execute(pk)
        except EntityNotFoundError:
            self.error_message(request, f"Ticket {pk[:8]}... não encontrado.")
            return render(request, 'tickets/not_found.html', status=404)
        except Exception as e:
            logger.error(f"Erro ao obter ticket {pk}: {e}")
            self.error_message(request, "Erro ao carregar ticket.")
            return redirect('tickets:list')
        
        # Forms para ações
        atribuir_form = TicketAtribuirForm()
        fechar_form = TicketFecharForm()
        reabrir_form = TicketReabrirForm()
        prioridade_form = TicketAlterarPrioridadeForm(
            initial={'prioridade': self._normalize_priority(ticket.prioridade)}
        )
        
        context = {
            'ticket': ticket,
            'atribuir_form': atribuir_form,
            'fechar_form': fechar_form,
            'reabrir_form': reabrir_form,
            'prioridade_form': prioridade_form,
            'user_id': self.get_user_id(request),
        }
        
        return render(request, self.template_name, context)
    
    def _normalize_priority(self, prioridade: str) -> str:
        """Normaliza prioridade para o formato do form."""
        mapping = {
            'Baixa': 'BAIXA',
            'Média': 'MEDIA',
            'Alta': 'ALTA',
            'Crítica': 'CRITICA',
        }
        return mapping.get(prioridade, 'MEDIA')


class TicketCreateView(ContainerMixin, FlashMessageMixin, UserContextMixin, View):
    """
    Cria novo ticket.
    
    GET /tickets/criar/ - Formulário
    POST /tickets/criar/ - Processa criação
    """
    
    template_name = 'tickets/create.html'
    
    def get(self, request: HttpRequest) -> HttpResponse:
        """Exibe formulário de criação."""
        form = TicketCreateForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request: HttpRequest) -> HttpResponse:
        """Processa criação de ticket."""
        form = TicketCreateForm(request.POST)
        
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})
        
        criar_service = self.get_service('criar_ticket_service')
        
        try:
            # Converter form para DTO
            input_dto = CriarTicketInputDTO(
                titulo=form.cleaned_data['titulo'],
                descricao=form.cleaned_data['descricao'],
                criador_id=self.get_user_id(request),
                prioridade=form.cleaned_data.get('prioridade', 'MEDIA'),
                categoria=form.cleaned_data.get('categoria', 'Geral'),
                tags=form.cleaned_data.get('tags', []),
            )
            
            # Executar use case
            output = criar_service.execute(input_dto)
            
            logger.info(f"Ticket criado: {output.id} por {self.get_user_id(request)}")
            self.success_message(
                request,
                f"Ticket #{output.id[:8]}... criado com sucesso!"
            )
            
            return redirect('tickets:detail', pk=output.id)
            
        except ValidationError as e:
            logger.warning(f"Validação falhou ao criar ticket: {e}")
            form.add_error(getattr(e, 'field', None), str(e))
            return render(request, self.template_name, {'form': form})
            
        except DomainException as e:
            logger.error(f"Erro de domínio ao criar ticket: {e}")
            form.add_error(None, str(e))
            return render(request, self.template_name, {'form': form})
            
        except Exception as e:
            logger.exception(f"Erro inesperado ao criar ticket: {e}")
            self.error_message(request, "Erro ao criar ticket. Tente novamente.")
            return render(request, self.template_name, {'form': form})


class TicketAtribuirView(ContainerMixin, FlashMessageMixin, UserContextMixin, View):
    """
    Atribui ticket a técnico.
    
    POST /tickets/<id>/atribuir/
    """
    
    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        """Processa atribuição de ticket."""
        form = TicketAtribuirForm(request.POST)
        
        if not form.is_valid():
            self.error_message(request, "Dados de atribuição inválidos.")
            return redirect('tickets:detail', pk=pk)
        
        atribuir_service = self.get_service('atribuir_ticket_service')
        
        try:
            input_dto = AtribuirTicketInputDTO(
                ticket_id=pk,
                tecnico_id=form.cleaned_data['tecnico_id'],
                atribuido_por_id=self.get_user_id(request),
            )
            
            output = atribuir_service.execute(input_dto)
            
            logger.info(
                f"Ticket {pk} atribuído a {form.cleaned_data['tecnico_id']} "
                f"por {self.get_user_id(request)}"
            )
            self.success_message(
                request,
                f"Ticket atribuído a {form.cleaned_data['tecnico_id']}!"
            )
            
        except EntityNotFoundError:
            self.error_message(request, "Ticket não encontrado.")
            
        except BusinessRuleViolationError as e:
            self.error_message(request, str(e))
            
        except Exception as e:
            logger.exception(f"Erro ao atribuir ticket {pk}: {e}")
            self.error_message(request, "Erro ao atribuir ticket.")
        
        return redirect('tickets:detail', pk=pk)


class TicketFecharView(ContainerMixin, FlashMessageMixin, UserContextMixin, View):
    """
    Fecha ticket.
    
    POST /tickets/<id>/fechar/
    """
    
    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        """Processa fechamento de ticket."""
        form = TicketFecharForm(request.POST)
        
        fechar_service = self.get_service('fechar_ticket_service')
        
        try:
            input_dto = FecharTicketInputDTO(
                ticket_id=pk,
                fechado_por_id=self.get_user_id(request),
                resolucao=form.data.get('resolucao', ''),
            )
            
            output = fechar_service.execute(input_dto)
            
            logger.info(f"Ticket {pk} fechado por {self.get_user_id(request)}")
            self.success_message(request, "Ticket fechado com sucesso!")
            
        except EntityNotFoundError:
            self.error_message(request, "Ticket não encontrado.")
            
        except BusinessRuleViolationError as e:
            self.error_message(request, str(e))
            
        except Exception as e:
            logger.exception(f"Erro ao fechar ticket {pk}: {e}")
            self.error_message(request, "Erro ao fechar ticket.")
        
        return redirect('tickets:detail', pk=pk)


class TicketReabrirView(ContainerMixin, FlashMessageMixin, UserContextMixin, View):
    """
    Reabre ticket fechado.
    
    POST /tickets/<id>/reabrir/
    """
    
    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        """Processa reabertura de ticket."""
        form = TicketReabrirForm(request.POST)
        
        reabrir_service = self.get_service('reabrir_ticket_service')
        
        try:
            output = reabrir_service.execute(
                ticket_id=pk,
                reaberto_por_id=self.get_user_id(request),
                motivo=form.data.get('motivo', ''),
            )
            
            logger.info(f"Ticket {pk} reaberto por {self.get_user_id(request)}")
            self.success_message(request, "Ticket reaberto com sucesso!")
            
        except EntityNotFoundError:
            self.error_message(request, "Ticket não encontrado.")
            
        except BusinessRuleViolationError as e:
            self.error_message(request, str(e))
            
        except Exception as e:
            logger.exception(f"Erro ao reabrir ticket {pk}: {e}")
            self.error_message(request, "Erro ao reabrir ticket.")
        
        return redirect('tickets:detail', pk=pk)


class TicketAlterarPrioridadeView(ContainerMixin, FlashMessageMixin, UserContextMixin, View):
    """
    Altera prioridade do ticket.
    
    POST /tickets/<id>/prioridade/
    """
    
    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        """Processa alteração de prioridade."""
        form = TicketAlterarPrioridadeForm(request.POST)
        
        if not form.is_valid():
            self.error_message(request, "Prioridade inválida.")
            return redirect('tickets:detail', pk=pk)
        
        alterar_service = self.get_service('alterar_prioridade_service')
        
        try:
            input_dto = AlterarPrioridadeInputDTO(
                ticket_id=pk,
                nova_prioridade=form.cleaned_data['prioridade'],
                alterado_por_id=self.get_user_id(request),
            )
            
            output = alterar_service.execute(input_dto)
            
            logger.info(
                f"Prioridade do ticket {pk} alterada para "
                f"{form.cleaned_data['prioridade']} por {self.get_user_id(request)}"
            )
            self.success_message(
                request,
                f"Prioridade alterada para {output.prioridade}!"
            )
            
        except EntityNotFoundError:
            self.error_message(request, "Ticket não encontrado.")
            
        except BusinessRuleViolationError as e:
            self.error_message(request, str(e))
            
        except ValidationError as e:
            self.error_message(request, str(e))
            
        except Exception as e:
            logger.exception(f"Erro ao alterar prioridade do ticket {pk}: {e}")
            self.error_message(request, "Erro ao alterar prioridade.")
        
        return redirect('tickets:detail', pk=pk)


# =============================================================================
# Dashboard View
# =============================================================================

class DashboardView(ContainerMixin, View):
    """
    Dashboard com visão geral dos tickets.
    
    GET /tickets/dashboard/
    """
    
    template_name = 'tickets/dashboard.html'
    
    def get(self, request: HttpRequest) -> HttpResponse:
        """Exibe dashboard."""
        listar_service = self.get_service('listar_tickets_service')
        contar_service = self.get_service('contar_tickets_service')
        
        try:
            # Estatísticas gerais
            estatisticas = contar_service.execute()
            
            # Tickets recentes
            todos_tickets = listar_service.execute()
            tickets_recentes = todos_tickets[:5]
            
            # Tickets atrasados
            tickets_atrasados = [t for t in todos_tickets if t.esta_atrasado][:5]
            
            # Tickets por status
            tickets_abertos = [t for t in todos_tickets if t.status == 'Aberto'][:5]
            tickets_em_progresso = [
                t for t in todos_tickets if t.status == 'Em Progresso'
            ][:5]
            
        except Exception as e:
            logger.error(f"Erro ao carregar dashboard: {e}")
            estatisticas = {'total': 0, 'por_status': {}}
            tickets_recentes = []
            tickets_atrasados = []
            tickets_abertos = []
            tickets_em_progresso = []
        
        context = {
            'estatisticas': estatisticas,
            'tickets_recentes': tickets_recentes,
            'tickets_atrasados': tickets_atrasados,
            'tickets_abertos': tickets_abertos,
            'tickets_em_progresso': tickets_em_progresso,
        }
        
        return render(request, self.template_name, context)

"""
API Views JSON para o domínio de Tickets.

RESTful API para integração com frontends e sistemas externos.

Endpoints:
- GET /tickets/api/ - Listar tickets
- POST /tickets/api/ - Criar ticket
- GET /tickets/api/<id>/ - Obter ticket
- PATCH /tickets/api/<id>/ - Atualizar ticket parcial
- POST /tickets/api/<id>/atribuir/ - Atribuir ticket
- POST /tickets/api/<id>/fechar/ - Fechar ticket
- POST /tickets/api/<id>/reabrir/ - Reabrir ticket

Formato:
- Entrada: JSON
- Saída: JSON com estrutura {success, data/error, meta}

Autenticação:
- Token via header (futuro)
- Session (atual)
"""

import json
import logging
from typing import Any, Dict, Optional
from functools import wraps

from django.views import View
from django.http import JsonResponse, HttpRequest
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

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

logger = logging.getLogger(__name__)


# =============================================================================
# Decorators e Helpers
# =============================================================================

def json_response(success: bool, data: Any = None, error: str = None,
                  status: int = 200, meta: Dict = None) -> JsonResponse:
    """
    Cria resposta JSON padronizada.
    
    Args:
        success: Se operação foi bem sucedida
        data: Dados da resposta
        error: Mensagem de erro (se aplicável)
        status: HTTP status code
        meta: Metadados adicionais
        
    Returns:
        JsonResponse formatada
    """
    response = {'success': success}
    
    if data is not None:
        response['data'] = data
    
    if error is not None:
        response['error'] = error
    
    if meta is not None:
        response['meta'] = meta
    
    return JsonResponse(response, status=status)


def parse_json_body(request: HttpRequest) -> Dict:
    """
    Parseia body JSON do request.
    
    Args:
        request: HTTP request
        
    Returns:
        Dicionário com dados
        
    Raises:
        ValueError: Se JSON inválido
    """
    if not request.body:
        return {}
    
    try:
        return json.loads(request.body)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON inválido: {e}")


def get_user_id(request: HttpRequest) -> str:
    """Extrai ID do usuário do request."""
    if request.user.is_authenticated:
        return str(request.user.id)
    return 'anonymous'


# =============================================================================
# Base API View
# =============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class BaseAPIView(View):
    """
    View base para APIs JSON.
    
    Fornece:
    - Parsing de JSON
    - Acesso ao container DI
    - Tratamento de erros padronizado
    """
    
    def get_container(self):
        """Retorna container de DI."""
        return get_container()
    
    def get_service(self, service_name: str):
        """Obtém service do container."""
        container = self.get_container()
        return getattr(container.services, service_name)()
    
    def parse_body(self, request: HttpRequest) -> Dict:
        """Parseia body JSON."""
        return parse_json_body(request)
    
    def handle_exception(self, e: Exception) -> JsonResponse:
        """
        Trata exceções e retorna resposta apropriada.
        
        Args:
            e: Exceção capturada
            
        Returns:
            JsonResponse com erro
        """
        if isinstance(e, ValidationError):
            return json_response(
                success=False,
                error=str(e),
                status=400,
                meta={'field': getattr(e, 'field', None)}
            )
        
        if isinstance(e, EntityNotFoundError):
            return json_response(
                success=False,
                error=str(e),
                status=404
            )
        
        if isinstance(e, BusinessRuleViolationError):
            return json_response(
                success=False,
                error=str(e),
                status=422,
                meta={'rule': getattr(e, 'rule', None)}
            )
        
        if isinstance(e, DomainException):
            return json_response(
                success=False,
                error=str(e),
                status=400
            )
        
        if isinstance(e, ValueError):
            return json_response(
                success=False,
                error=str(e),
                status=400
            )
        
        # Erro inesperado
        logger.exception(f"Erro inesperado na API: {e}")
        return json_response(
            success=False,
            error="Erro interno do servidor",
            status=500
        )


# =============================================================================
# Ticket API Views
# =============================================================================

class TicketAPIListView(BaseAPIView):
    """
    API para listar e criar tickets.
    
    GET /tickets/api/ - Lista tickets
    POST /tickets/api/ - Cria ticket
    """
    
    def get(self, request: HttpRequest) -> JsonResponse:
        """
        Lista tickets com filtros opcionais.
        
        Query params:
        - status: Filtrar por status
        - prioridade: Filtrar por prioridade
        - criador_id: Filtrar por criador
        - tecnico_id: Filtrar por técnico
        - page: Página (default: 1)
        - per_page: Itens por página (default: 20)
        """
        try:
            listar_service = self.get_service('listar_tickets_service')
            
            # Extrair filtros
            status = request.GET.get('status') or None
            criador_id = request.GET.get('criador_id') or None
            tecnico_id = request.GET.get('tecnico_id') or None
            
            # Executar query
            tickets = listar_service.execute(
                status=status,
                criador_id=criador_id,
                tecnico_id=tecnico_id,
            )
            
            # Filtrar por prioridade (se necessário)
            prioridade = request.GET.get('prioridade')
            if prioridade:
                tickets = [t for t in tickets if t.prioridade == prioridade]
            
            # Paginação simples
            page = int(request.GET.get('page', 1))
            per_page = int(request.GET.get('per_page', 20))
            
            total = len(tickets)
            start = (page - 1) * per_page
            end = start + per_page
            paginated = tickets[start:end]
            
            return json_response(
                success=True,
                data=[t.to_dict() for t in paginated],
                meta={
                    'total': total,
                    'page': page,
                    'per_page': per_page,
                    'total_pages': (total + per_page - 1) // per_page,
                }
            )
            
        except Exception as e:
            return self.handle_exception(e)
    
    def post(self, request: HttpRequest) -> JsonResponse:
        """
        Cria novo ticket.
        
        Body JSON:
        {
            "titulo": "string (obrigatório)",
            "descricao": "string (obrigatório)",
            "prioridade": "BAIXA|MEDIA|ALTA|CRITICA (opcional)",
            "categoria": "string (opcional)",
            "tags": ["string"] (opcional)
        }
        """
        try:
            data = self.parse_body(request)
            
            criar_service = self.get_service('criar_ticket_service')
            
            input_dto = CriarTicketInputDTO(
                titulo=data.get('titulo', ''),
                descricao=data.get('descricao', ''),
                criador_id=data.get('criador_id', get_user_id(request)),
                prioridade=data.get('prioridade', 'MEDIA'),
                categoria=data.get('categoria', 'Geral'),
                tags=data.get('tags', []),
            )
            
            output = criar_service.execute(input_dto)
            
            logger.info(f"API: Ticket criado: {output.id}")
            
            return json_response(
                success=True,
                data=output.to_dict(),
                status=201
            )
            
        except Exception as e:
            return self.handle_exception(e)


class TicketAPIDetailView(BaseAPIView):
    """
    API para operações em ticket específico.
    
    GET /tickets/api/<id>/ - Obter ticket
    PATCH /tickets/api/<id>/ - Atualizar ticket
    DELETE /tickets/api/<id>/ - Deletar ticket (futuro)
    """
    
    def get(self, request: HttpRequest, pk: str) -> JsonResponse:
        """Obtém detalhes do ticket."""
        try:
            obter_service = self.get_service('obter_ticket_service')
            ticket = obter_service.execute(pk)
            
            return json_response(
                success=True,
                data=ticket.to_dict()
            )
            
        except Exception as e:
            return self.handle_exception(e)
    
    def patch(self, request: HttpRequest, pk: str) -> JsonResponse:
        """
        Atualiza ticket parcialmente.
        
        Body JSON:
        {
            "prioridade": "BAIXA|MEDIA|ALTA|CRITICA" (opcional)
        }
        """
        try:
            data = self.parse_body(request)
            
            # Por enquanto, apenas prioridade pode ser alterada via PATCH
            if 'prioridade' in data:
                alterar_service = self.get_service('alterar_prioridade_service')
                
                input_dto = AlterarPrioridadeInputDTO(
                    ticket_id=pk,
                    nova_prioridade=data['prioridade'],
                    alterado_por_id=get_user_id(request),
                )
                
                output = alterar_service.execute(input_dto)
                
                return json_response(
                    success=True,
                    data=output.to_dict()
                )
            
            # Se nenhum campo válido foi enviado
            return json_response(
                success=False,
                error="Nenhum campo válido para atualização",
                status=400
            )
            
        except Exception as e:
            return self.handle_exception(e)


class TicketAPIAtribuirView(BaseAPIView):
    """
    API para atribuir ticket.
    
    POST /tickets/api/<id>/atribuir/
    """
    
    def post(self, request: HttpRequest, pk: str) -> JsonResponse:
        """
        Atribui ticket a técnico.
        
        Body JSON:
        {
            "tecnico_id": "string (obrigatório)"
        }
        """
        try:
            data = self.parse_body(request)
            
            if 'tecnico_id' not in data:
                return json_response(
                    success=False,
                    error="tecnico_id é obrigatório",
                    status=400
                )
            
            atribuir_service = self.get_service('atribuir_ticket_service')
            
            input_dto = AtribuirTicketInputDTO(
                ticket_id=pk,
                tecnico_id=data['tecnico_id'],
                atribuido_por_id=get_user_id(request),
            )
            
            output = atribuir_service.execute(input_dto)
            
            logger.info(f"API: Ticket {pk} atribuído a {data['tecnico_id']}")
            
            return json_response(
                success=True,
                data=output.to_dict()
            )
            
        except Exception as e:
            return self.handle_exception(e)


class TicketAPIFecharView(BaseAPIView):
    """
    API para fechar ticket.
    
    POST /tickets/api/<id>/fechar/
    """
    
    def post(self, request: HttpRequest, pk: str) -> JsonResponse:
        """
        Fecha ticket.
        
        Body JSON:
        {
            "resolucao": "string (opcional)"
        }
        """
        try:
            data = self.parse_body(request)
            
            fechar_service = self.get_service('fechar_ticket_service')
            
            input_dto = FecharTicketInputDTO(
                ticket_id=pk,
                fechado_por_id=get_user_id(request),
                resolucao=data.get('resolucao', ''),
            )
            
            output = fechar_service.execute(input_dto)
            
            logger.info(f"API: Ticket {pk} fechado")
            
            return json_response(
                success=True,
                data=output.to_dict()
            )
            
        except Exception as e:
            return self.handle_exception(e)


class TicketAPIReabrirView(BaseAPIView):
    """
    API para reabrir ticket.
    
    POST /tickets/api/<id>/reabrir/
    """
    
    def post(self, request: HttpRequest, pk: str) -> JsonResponse:
        """
        Reabre ticket.
        
        Body JSON:
        {
            "motivo": "string (opcional)"
        }
        """
        try:
            data = self.parse_body(request)
            
            reabrir_service = self.get_service('reabrir_ticket_service')
            
            output = reabrir_service.execute(
                ticket_id=pk,
                reaberto_por_id=get_user_id(request),
                motivo=data.get('motivo', ''),
            )
            
            logger.info(f"API: Ticket {pk} reaberto")
            
            return json_response(
                success=True,
                data=output.to_dict()
            )
            
        except Exception as e:
            return self.handle_exception(e)


class TicketAPIEstatisticasView(BaseAPIView):
    """
    API para estatísticas de tickets.
    
    GET /tickets/api/estatisticas/
    """
    
    def get(self, request: HttpRequest) -> JsonResponse:
        """Retorna estatísticas de tickets."""
        try:
            contar_service = self.get_service('contar_tickets_service')
            estatisticas = contar_service.execute()
            
            return json_response(
                success=True,
                data=estatisticas
            )
            
        except Exception as e:
            return self.handle_exception(e)

"""
Use Cases (Application Services) do Domínio de Tickets.

Este módulo contém os casos de uso da aplicação, que orquestram
a lógica de negócio coordenando entidades, repositórios e eventos.

Use Cases implementados:
- CriarTicketService: Cria novo ticket
- AtribuirTicketService: Atribui ticket a técnico
- FecharTicketService: Fecha ticket
- ReabrirTicketService: Reabre ticket fechado
- ListarTicketsService: Lista tickets com filtros
- ObterTicketService: Obtém ticket específico
- AlterarPrioridadeService: Altera prioridade

Responsabilidades dos Use Cases:
- Validar entrada (via DTOs)
- Coordenar entidades
- Gerenciar transações (via UoW)
- Disparar eventos de domínio
- Retornar DTOs de saída

Princípios:
- Um Use Case = Uma operação de negócio
- Dependências injetadas (DI)
- Sem lógica de infraestrutura
"""

from typing import List, Optional
from datetime import datetime

from src.core.shared.interfaces import UnitOfWork
from src.core.shared.exceptions import (
    EntityNotFoundError,
    ValidationError,
    BusinessRuleViolationError,
)

from .ports import TicketRepository
from .entities import TicketEntity, TicketPriority, TicketStatus
from .dtos import (
    CriarTicketInputDTO,
    AtribuirTicketInputDTO,
    FecharTicketInputDTO,
    AlterarPrioridadeInputDTO,
    TicketOutputDTO,
    TicketListItemDTO,
    ListarTicketsQueryDTO,
)
from .events import (
    TicketCriadoEvent,
    TicketAtribuidoEvent,
    TicketFechadoEvent,
    TicketReabertoEvent,
    TicketPrioridadeAlteradaEvent,
)


class CriarTicketService:
    """
    Use Case: Criar um novo ticket.
    
    Fluxo:
    1. Validar dados de entrada
    2. Criar entidade Ticket
    3. Persistir via repositório
    4. Disparar evento TicketCriado
    5. Retornar DTO de saída
    
    Attributes:
        ticket_repo: Repositório de tickets
        uow: Unit of Work para transações
    
    Example:
        service = CriarTicketService(ticket_repo, uow)
        input_dto = CriarTicketInputDTO(
            titulo="Bug crítico",
            descricao="Sistema fora do ar",
            criador_id="user123",
            prioridade="CRITICA"
        )
        output = service.execute(input_dto)
        print(output.id)  # UUID do ticket criado
    """
    
    def __init__(self, ticket_repo: TicketRepository, uow: UnitOfWork):
        """
        Inicializa service com dependências injetadas.
        
        Args:
            ticket_repo: Repositório para persistência
            uow: Unit of Work para transação atômica
        """
        self.ticket_repo = ticket_repo
        self.uow = uow
    
    def execute(self, input_dto: CriarTicketInputDTO) -> TicketOutputDTO:
        """
        Executa criação de ticket em transação atômica.
        
        Args:
            input_dto: Dados de entrada validados
            
        Returns:
            DTO com dados do ticket criado
            
        Raises:
            ValidationError: Se dados inválidos
        """
        with self.uow:
            # Converter prioridade string para enum
            try:
                prioridade = TicketPriority[input_dto.prioridade.upper()]
            except KeyError:
                raise ValidationError(
                    f"Prioridade inválida: {input_dto.prioridade}",
                    field="prioridade"
                )
            
            # Criar entidade (validações de negócio na entidade)
            ticket = TicketEntity.criar(
                titulo=input_dto.titulo,
                descricao=input_dto.descricao,
                criador_id=input_dto.criador_id,
                prioridade=prioridade,
                categoria=input_dto.categoria,
                tags=list(input_dto.tags) if input_dto.tags else None,
            )
            
            # Persistir
            self.ticket_repo.save(ticket)
            
            # Disparar evento (publicado após commit)
            self.uow.publish_event(
                TicketCriadoEvent(
                    aggregate_id=ticket.id,
                    criador_id=ticket.criador_id,
                    titulo=ticket.titulo,
                    prioridade=ticket.prioridade.value,
                    categoria=ticket.categoria,
                )
            )
        
        return TicketOutputDTO.from_entity(ticket)


class AtribuirTicketService:
    """
    Use Case: Atribuir ticket a um técnico.
    
    Fluxo:
    1. Buscar ticket existente
    2. Validar que pode ser atribuído
    3. Executar atribuição na entidade
    4. Persistir alterações
    5. Disparar evento TicketAtribuido
    """
    
    def __init__(self, ticket_repo: TicketRepository, uow: UnitOfWork):
        self.ticket_repo = ticket_repo
        self.uow = uow
    
    def execute(self, input_dto: AtribuirTicketInputDTO) -> TicketOutputDTO:
        """
        Executa atribuição de ticket.
        
        Args:
            input_dto: Dados da atribuição
            
        Returns:
            DTO com ticket atualizado
            
        Raises:
            EntityNotFoundError: Se ticket não existe
            BusinessRuleViolationError: Se ticket não pode ser atribuído
        """
        with self.uow:
            # Buscar ticket
            ticket = self.ticket_repo.get_by_id(input_dto.ticket_id)
            
            if not ticket:
                raise EntityNotFoundError(
                    f"Ticket {input_dto.ticket_id} não encontrado",
                    entity_type="Ticket",
                    entity_id=input_dto.ticket_id
                )
            
            # Executar atribuição (validações na entidade)
            ticket.atribuir_a(input_dto.tecnico_id)
            
            # Persistir
            self.ticket_repo.save(ticket)
            
            # Disparar evento
            self.uow.publish_event(
                TicketAtribuidoEvent(
                    aggregate_id=ticket.id,
                    tecnico_id=input_dto.tecnico_id,
                    atribuido_por_id=input_dto.atribuido_por_id,
                )
            )
        
        return TicketOutputDTO.from_entity(ticket)


class FecharTicketService:
    """
    Use Case: Fechar um ticket.
    
    Fluxo:
    1. Buscar ticket existente
    2. Validar que pode ser fechado
    3. Executar fechamento
    4. Calcular métricas (tempo resolução, SLA)
    5. Disparar evento TicketFechado
    """
    
    def __init__(self, ticket_repo: TicketRepository, uow: UnitOfWork):
        self.ticket_repo = ticket_repo
        self.uow = uow
    
    def execute(self, input_dto: FecharTicketInputDTO) -> TicketOutputDTO:
        """
        Executa fechamento de ticket.
        
        Args:
            input_dto: Dados do fechamento
            
        Returns:
            DTO com ticket fechado
            
        Raises:
            EntityNotFoundError: Se ticket não existe
            BusinessRuleViolationError: Se ticket não pode ser fechado
        """
        with self.uow:
            ticket = self.ticket_repo.get_by_id(input_dto.ticket_id)
            
            if not ticket:
                raise EntityNotFoundError(
                    f"Ticket {input_dto.ticket_id} não encontrado",
                    entity_type="Ticket",
                    entity_id=input_dto.ticket_id
                )
            
            # Calcular métricas antes de fechar
            tempo_resolucao = self._calcular_tempo_resolucao(ticket)
            dentro_sla = not ticket.esta_atrasado
            
            # Fechar ticket (validações na entidade)
            ticket.fechar()
            
            # Persistir
            self.ticket_repo.save(ticket)
            
            # Disparar evento
            self.uow.publish_event(
                TicketFechadoEvent(
                    aggregate_id=ticket.id,
                    fechado_por_id=input_dto.fechado_por_id,
                    tempo_resolucao_horas=tempo_resolucao,
                    dentro_sla=dentro_sla,
                )
            )
        
        return TicketOutputDTO.from_entity(ticket)
    
    def _calcular_tempo_resolucao(self, ticket: TicketEntity) -> float:
        """Calcula tempo de resolução em horas."""
        delta = datetime.now() - ticket.criado_em
        return delta.total_seconds() / 3600


class ReabrirTicketService:
    """
    Use Case: Reabrir um ticket fechado.
    """
    
    def __init__(self, ticket_repo: TicketRepository, uow: UnitOfWork):
        self.ticket_repo = ticket_repo
        self.uow = uow
    
    def execute(
        self,
        ticket_id: str,
        reaberto_por_id: str,
        motivo: Optional[str] = None
    ) -> TicketOutputDTO:
        """
        Reabre ticket fechado.
        
        Args:
            ticket_id: ID do ticket
            reaberto_por_id: ID de quem está reabrindo
            motivo: Motivo da reabertura (opcional)
            
        Returns:
            DTO com ticket reaberto
        """
        with self.uow:
            ticket = self.ticket_repo.get_by_id(ticket_id)
            
            if not ticket:
                raise EntityNotFoundError(
                    f"Ticket {ticket_id} não encontrado",
                    entity_type="Ticket",
                    entity_id=ticket_id
                )
            
            # Reabrir (validações na entidade)
            ticket.reabrir()
            
            # Persistir
            self.ticket_repo.save(ticket)
            
            # Disparar evento
            self.uow.publish_event(
                TicketReabertoEvent(
                    aggregate_id=ticket.id,
                    reaberto_por_id=reaberto_por_id,
                    motivo=motivo,
                )
            )
        
        return TicketOutputDTO.from_entity(ticket)


class AlterarPrioridadeService:
    """
    Use Case: Alterar prioridade de um ticket.
    """
    
    def __init__(self, ticket_repo: TicketRepository, uow: UnitOfWork):
        self.ticket_repo = ticket_repo
        self.uow = uow
    
    def execute(self, input_dto: AlterarPrioridadeInputDTO) -> TicketOutputDTO:
        """
        Altera prioridade do ticket.
        
        Args:
            input_dto: Dados da alteração
            
        Returns:
            DTO com ticket atualizado
        """
        with self.uow:
            ticket = self.ticket_repo.get_by_id(input_dto.ticket_id)
            
            if not ticket:
                raise EntityNotFoundError(
                    f"Ticket {input_dto.ticket_id} não encontrado",
                    entity_type="Ticket",
                    entity_id=input_dto.ticket_id
                )
            
            # Guardar prioridade anterior
            prioridade_anterior = ticket.prioridade.value
            
            # Converter e aplicar nova prioridade
            try:
                nova_prioridade = TicketPriority[input_dto.nova_prioridade.upper()]
            except KeyError:
                raise ValidationError(
                    f"Prioridade inválida: {input_dto.nova_prioridade}",
                    field="nova_prioridade"
                )
            
            ticket.alterar_prioridade(nova_prioridade)
            
            # Persistir
            self.ticket_repo.save(ticket)
            
            # Disparar evento
            self.uow.publish_event(
                TicketPrioridadeAlteradaEvent(
                    aggregate_id=ticket.id,
                    prioridade_anterior=prioridade_anterior,
                    prioridade_nova=nova_prioridade.value,
                    alterado_por_id=input_dto.alterado_por_id,
                )
            )
        
        return TicketOutputDTO.from_entity(ticket)


class ListarTicketsService:
    """
    Use Case: Listar tickets com filtros.
    
    Não usa UoW pois é operação de leitura (não precisa de transação).
    """
    
    def __init__(self, ticket_repo: TicketRepository):
        self.ticket_repo = ticket_repo
    
    def execute(
        self,
        status: Optional[str] = None,
        criador_id: Optional[str] = None,
        tecnico_id: Optional[str] = None,
    ) -> List[TicketOutputDTO]:
        """
        Lista tickets com filtros opcionais.
        
        Args:
            status: Filtrar por status (nome do enum)
            criador_id: Filtrar por criador
            tecnico_id: Filtrar por técnico
            
        Returns:
            Lista de DTOs
        """
        # Aplicar filtros
        if status:
            try:
                ticket_status = TicketStatus[status.upper().replace(" ", "_")]
                tickets = self.ticket_repo.list_by_status(ticket_status)
            except KeyError:
                raise ValidationError(f"Status inválido: {status}", field="status")
        elif criador_id:
            tickets = self.ticket_repo.list_by_criador(criador_id)
        elif tecnico_id:
            tickets = self.ticket_repo.list_by_tecnico(tecnico_id)
        else:
            tickets = self.ticket_repo.list_all()
        
        return [TicketOutputDTO.from_entity(t) for t in tickets]


class ObterTicketService:
    """
    Use Case: Obter detalhes de um ticket específico.
    """
    
    def __init__(self, ticket_repo: TicketRepository):
        self.ticket_repo = ticket_repo
    
    def execute(self, ticket_id: str) -> TicketOutputDTO:
        """
        Obtém ticket por ID.
        
        Args:
            ticket_id: ID do ticket
            
        Returns:
            DTO com dados completos
            
        Raises:
            EntityNotFoundError: Se ticket não existe
        """
        ticket = self.ticket_repo.get_by_id(ticket_id)
        
        if not ticket:
            raise EntityNotFoundError(
                f"Ticket {ticket_id} não encontrado",
                entity_type="Ticket",
                entity_id=ticket_id
            )
        
        return TicketOutputDTO.from_entity(ticket)


class ContarTicketsService:
    """
    Use Case: Obter estatísticas de tickets.
    """
    
    def __init__(self, ticket_repo: TicketRepository):
        self.ticket_repo = ticket_repo
    
    def execute(self) -> dict:
        """
        Retorna contagem de tickets por status.
        
        Returns:
            Dict com estatísticas
        """
        return {
            "total": self.ticket_repo.count(),
            "por_status": {
                status.value: self.ticket_repo.count_by_status(status)
                for status in TicketStatus
            }
        }

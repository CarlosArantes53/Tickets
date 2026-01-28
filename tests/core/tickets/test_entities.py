"""
Testes Unitários para Entidades do Domínio de Tickets.

Testa todas as regras de negócio encapsuladas nas entidades,
incluindo validações, transições de estado e cálculos.

Coverage:
- TicketEntity.criar(): Validações de criação
- TicketEntity.atribuir_a(): Atribuição a técnico
- TicketEntity.fechar(): Fechamento de ticket
- TicketEntity.reabrir(): Reabertura de ticket
- TicketEntity.alterar_prioridade(): Alteração de prioridade
- Cálculo de SLA
- Propriedades computadas
"""

import pytest
from datetime import datetime, timedelta

from src.core.tickets.entities import (
    TicketEntity,
    TicketStatus,
    TicketPriority,
)
from src.core.shared.exceptions import (
    ValidationError,
    BusinessRuleViolationError,
)


class TestTicketEntityCriacao:
    """Testes para criação de tickets."""
    
    def test_criar_ticket_valido(self):
        """Deve criar ticket com dados válidos."""
        ticket = TicketEntity.criar(
            titulo="Bug no sistema de login",
            descricao="O sistema não aceita a senha correta do usuário",
            criador_id="user-123",
            prioridade=TicketPriority.ALTA,
            categoria="Autenticação",
        )
        
        assert ticket.id is not None
        assert len(ticket.id) == 36  # UUID
        assert ticket.titulo == "Bug no sistema de login"
        assert ticket.descricao == "O sistema não aceita a senha correta do usuário"
        assert ticket.criador_id == "user-123"
        assert ticket.prioridade == TicketPriority.ALTA
        assert ticket.categoria == "Autenticação"
        assert ticket.status == TicketStatus.ABERTO
        assert ticket.atribuido_a_id is None
        assert ticket.sla_prazo is not None
    
    def test_criar_ticket_com_valores_default(self):
        """Deve criar ticket com prioridade e categoria default."""
        ticket = TicketEntity.criar(
            titulo="Problema genérico",
            descricao="Descrição do problema com pelo menos 10 caracteres",
            criador_id="user-456",
        )
        
        assert ticket.prioridade == TicketPriority.MEDIA
        assert ticket.categoria == "Geral"
    
    def test_criar_ticket_com_tags(self):
        """Deve criar ticket com tags."""
        ticket = TicketEntity.criar(
            titulo="Bug com tags",
            descricao="Descrição do bug para teste de tags",
            criador_id="user-789",
            tags=["urgente", "cliente-vip"],
        )
        
        assert ticket.tags == ["urgente", "cliente-vip"]
    
    def test_criar_ticket_titulo_vazio_erro(self):
        """Deve rejeitar título vazio."""
        with pytest.raises(ValidationError) as exc_info:
            TicketEntity.criar(
                titulo="",
                descricao="Descrição válida com mais de 10 caracteres",
                criador_id="user-123",
            )
        
        assert "obrigatório" in str(exc_info.value).lower()
        assert exc_info.value.field == "titulo"
    
    def test_criar_ticket_titulo_muito_curto_erro(self):
        """Deve rejeitar título com menos de 3 caracteres."""
        with pytest.raises(ValidationError) as exc_info:
            TicketEntity.criar(
                titulo="AB",
                descricao="Descrição válida com mais de 10 caracteres",
                criador_id="user-123",
            )
        
        assert "3 caracteres" in str(exc_info.value)
        assert exc_info.value.field == "titulo"
    
    def test_criar_ticket_descricao_vazia_erro(self):
        """Deve rejeitar descrição vazia."""
        with pytest.raises(ValidationError) as exc_info:
            TicketEntity.criar(
                titulo="Título válido",
                descricao="",
                criador_id="user-123",
            )
        
        assert "obrigatória" in str(exc_info.value).lower()
        assert exc_info.value.field == "descricao"
    
    def test_criar_ticket_descricao_muito_curta_erro(self):
        """Deve rejeitar descrição com menos de 10 caracteres."""
        with pytest.raises(ValidationError) as exc_info:
            TicketEntity.criar(
                titulo="Título válido",
                descricao="Curta",
                criador_id="user-123",
            )
        
        assert "10 caracteres" in str(exc_info.value)
        assert exc_info.value.field == "descricao"
    
    def test_criar_ticket_criador_vazio_erro(self):
        """Deve rejeitar criador vazio."""
        with pytest.raises(ValidationError) as exc_info:
            TicketEntity.criar(
                titulo="Título válido",
                descricao="Descrição válida com mais de 10 caracteres",
                criador_id="",
            )
        
        assert "obrigatório" in str(exc_info.value).lower()
        assert exc_info.value.field == "criador_id"
    
    def test_criar_ticket_remove_espacos_extras(self):
        """Deve remover espaços extras do título e descrição."""
        ticket = TicketEntity.criar(
            titulo="  Título com espaços  ",
            descricao="  Descrição com espaços extras  ",
            criador_id="user-123",
        )
        
        assert ticket.titulo == "Título com espaços"
        assert ticket.descricao == "Descrição com espaços extras"


class TestTicketEntitySLA:
    """Testes para cálculo de SLA."""
    
    def test_sla_prioridade_critica(self):
        """SLA para prioridade crítica deve ser 4 horas."""
        ticket = TicketEntity.criar(
            titulo="Sistema fora do ar",
            descricao="Produção completamente parada urgente",
            criador_id="user-123",
            prioridade=TicketPriority.CRITICA,
        )
        
        diferenca = ticket.sla_prazo - ticket.criado_em
        assert diferenca == timedelta(hours=4)
    
    def test_sla_prioridade_alta(self):
        """SLA para prioridade alta deve ser 24 horas."""
        ticket = TicketEntity.criar(
            titulo="Bug crítico",
            descricao="Funcionalidade principal com problema",
            criador_id="user-123",
            prioridade=TicketPriority.ALTA,
        )
        
        diferenca = ticket.sla_prazo - ticket.criado_em
        assert diferenca == timedelta(hours=24)
    
    def test_sla_prioridade_media(self):
        """SLA para prioridade média deve ser 72 horas (3 dias)."""
        ticket = TicketEntity.criar(
            titulo="Melhoria solicitada",
            descricao="Sugestão de melhoria na interface",
            criador_id="user-123",
            prioridade=TicketPriority.MEDIA,
        )
        
        diferenca = ticket.sla_prazo - ticket.criado_em
        assert diferenca == timedelta(hours=72)
    
    def test_sla_prioridade_baixa(self):
        """SLA para prioridade baixa deve ser 168 horas (7 dias)."""
        ticket = TicketEntity.criar(
            titulo="Dúvida sobre sistema",
            descricao="Como faço para exportar relatório",
            criador_id="user-123",
            prioridade=TicketPriority.BAIXA,
        )
        
        diferenca = ticket.sla_prazo - ticket.criado_em
        assert diferenca == timedelta(hours=168)
    
    def test_ticket_atrasado_apos_prazo(self):
        """Ticket deve ser considerado atrasado após prazo SLA."""
        # Criar ticket no passado
        ticket = TicketEntity.criar(
            titulo="Ticket antigo",
            descricao="Este ticket foi criado há muito tempo",
            criador_id="user-123",
            prioridade=TicketPriority.CRITICA,  # 4 horas
        )
        
        # Simular criação no passado
        ticket.criado_em = datetime.now() - timedelta(hours=5)
        ticket.sla_prazo = ticket.criado_em + timedelta(hours=4)
        
        assert ticket.esta_atrasado is True
    
    def test_ticket_nao_atrasado_dentro_prazo(self):
        """Ticket não deve ser considerado atrasado dentro do prazo."""
        ticket = TicketEntity.criar(
            titulo="Ticket recente",
            descricao="Este ticket acabou de ser criado",
            criador_id="user-123",
            prioridade=TicketPriority.BAIXA,  # 7 dias
        )
        
        assert ticket.esta_atrasado is False
    
    def test_ticket_fechado_nao_e_atrasado(self):
        """Ticket fechado não deve ser considerado atrasado."""
        ticket = TicketEntity.criar(
            titulo="Ticket fechado",
            descricao="Este ticket foi resolvido e fechado",
            criador_id="user-123",
            prioridade=TicketPriority.CRITICA,
        )
        
        # Simular atraso
        ticket.criado_em = datetime.now() - timedelta(hours=10)
        ticket.sla_prazo = ticket.criado_em + timedelta(hours=4)
        
        # Atribuir e fechar
        ticket.atribuir_a("tecnico-123")
        ticket.fechar()
        
        assert ticket.esta_atrasado is False


class TestTicketEntityAtribuicao:
    """Testes para atribuição de tickets."""
    
    def test_atribuir_ticket_sucesso(self):
        """Deve atribuir ticket a técnico."""
        ticket = TicketEntity.criar(
            titulo="Bug para atribuir",
            descricao="Este ticket será atribuído a um técnico",
            criador_id="user-123",
        )
        
        ticket.atribuir_a("tecnico-456")
        
        assert ticket.atribuido_a_id == "tecnico-456"
        assert ticket.status == TicketStatus.EM_PROGRESSO
    
    def test_atribuir_ticket_atualiza_timestamp(self):
        """Deve atualizar timestamp ao atribuir."""
        ticket = TicketEntity.criar(
            titulo="Bug para timestamp",
            descricao="Verificar atualização de timestamp",
            criador_id="user-123",
        )
        
        criado_em = ticket.atualizado_em
        ticket.atribuir_a("tecnico-456")
        
        assert ticket.atualizado_em >= criado_em
    
    def test_atribuir_ticket_fechado_erro(self):
        """Não deve atribuir ticket fechado."""
        ticket = TicketEntity.criar(
            titulo="Bug fechado",
            descricao="Este ticket está fechado e não pode ser atribuído",
            criador_id="user-123",
        )
        
        ticket.atribuir_a("tecnico-123")
        ticket.fechar()
        
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            ticket.atribuir_a("outro-tecnico")
        
        assert "fechado" in str(exc_info.value).lower()
    
    def test_atribuir_ticket_tecnico_vazio_erro(self):
        """Não deve atribuir a técnico vazio."""
        ticket = TicketEntity.criar(
            titulo="Bug teste",
            descricao="Verificar validação de técnico vazio",
            criador_id="user-123",
        )
        
        with pytest.raises(ValidationError) as exc_info:
            ticket.atribuir_a("")
        
        assert "obrigatório" in str(exc_info.value).lower()


class TestTicketEntityFechamento:
    """Testes para fechamento de tickets."""
    
    def test_fechar_ticket_atribuido_sucesso(self):
        """Deve fechar ticket atribuído."""
        ticket = TicketEntity.criar(
            titulo="Bug para fechar",
            descricao="Este ticket será fechado após atribuição",
            criador_id="user-123",
        )
        
        ticket.atribuir_a("tecnico-456")
        ticket.fechar()
        
        assert ticket.status == TicketStatus.FECHADO
    
    def test_fechar_ticket_nao_atribuido_erro(self):
        """Não deve fechar ticket não atribuído."""
        ticket = TicketEntity.criar(
            titulo="Bug sem atribuição",
            descricao="Este ticket não foi atribuído ainda",
            criador_id="user-123",
        )
        
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            ticket.fechar()
        
        assert "atribuído" in str(exc_info.value).lower()
    
    def test_fechar_ticket_ja_fechado_erro(self):
        """Não deve fechar ticket já fechado."""
        ticket = TicketEntity.criar(
            titulo="Bug já fechado",
            descricao="Este ticket já está fechado",
            criador_id="user-123",
        )
        
        ticket.atribuir_a("tecnico-456")
        ticket.fechar()
        
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            ticket.fechar()
        
        assert "fechado" in str(exc_info.value).lower()


class TestTicketEntityReabertura:
    """Testes para reabertura de tickets."""
    
    def test_reabrir_ticket_fechado_sucesso(self):
        """Deve reabrir ticket fechado."""
        ticket = TicketEntity.criar(
            titulo="Bug para reabrir",
            descricao="Este ticket será reaberto após fechamento",
            criador_id="user-123",
        )
        
        ticket.atribuir_a("tecnico-456")
        ticket.fechar()
        ticket.reabrir()
        
        assert ticket.status == TicketStatus.ABERTO
        assert ticket.atribuido_a_id is None
    
    def test_reabrir_ticket_nao_fechado_erro(self):
        """Não deve reabrir ticket que não está fechado."""
        ticket = TicketEntity.criar(
            titulo="Bug aberto",
            descricao="Este ticket está aberto e não pode ser reaberto",
            criador_id="user-123",
        )
        
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            ticket.reabrir()
        
        assert "fechado" in str(exc_info.value).lower()


class TestTicketEntityPrioridade:
    """Testes para alteração de prioridade."""
    
    def test_alterar_prioridade_sucesso(self):
        """Deve alterar prioridade e recalcular SLA."""
        ticket = TicketEntity.criar(
            titulo="Bug para escalonar",
            descricao="Este ticket terá prioridade alterada",
            criador_id="user-123",
            prioridade=TicketPriority.BAIXA,
        )
        
        sla_original = ticket.sla_prazo
        ticket.alterar_prioridade(TicketPriority.CRITICA)
        
        assert ticket.prioridade == TicketPriority.CRITICA
        assert ticket.sla_prazo != sla_original
    
    def test_alterar_prioridade_ticket_fechado_erro(self):
        """Não deve alterar prioridade de ticket fechado."""
        ticket = TicketEntity.criar(
            titulo="Bug fechado",
            descricao="Este ticket está fechado",
            criador_id="user-123",
        )
        
        ticket.atribuir_a("tecnico-123")
        ticket.fechar()
        
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            ticket.alterar_prioridade(TicketPriority.CRITICA)
        
        assert "fechado" in str(exc_info.value).lower()


class TestTicketEntityTags:
    """Testes para gerenciamento de tags."""
    
    def test_adicionar_tag(self):
        """Deve adicionar tag ao ticket."""
        ticket = TicketEntity.criar(
            titulo="Bug com tags",
            descricao="Este ticket terá tags adicionadas",
            criador_id="user-123",
        )
        
        ticket.adicionar_tag("urgente")
        
        assert "urgente" in ticket.tags
    
    def test_adicionar_tag_normaliza_lowercase(self):
        """Deve normalizar tag para lowercase."""
        ticket = TicketEntity.criar(
            titulo="Bug com tags",
            descricao="Este ticket terá tags normalizadas",
            criador_id="user-123",
        )
        
        ticket.adicionar_tag("URGENTE")
        
        assert "urgente" in ticket.tags
    
    def test_adicionar_tag_duplicada_ignora(self):
        """Não deve adicionar tag duplicada."""
        ticket = TicketEntity.criar(
            titulo="Bug com tags",
            descricao="Este ticket não terá tags duplicadas",
            criador_id="user-123",
        )
        
        ticket.adicionar_tag("urgente")
        ticket.adicionar_tag("urgente")
        
        assert ticket.tags.count("urgente") == 1
    
    def test_remover_tag(self):
        """Deve remover tag do ticket."""
        ticket = TicketEntity.criar(
            titulo="Bug com tags",
            descricao="Este ticket terá tag removida",
            criador_id="user-123",
            tags=["urgente", "cliente-vip"],
        )
        
        ticket.remover_tag("urgente")
        
        assert "urgente" not in ticket.tags
        assert "cliente-vip" in ticket.tags


class TestTicketEntityPropriedades:
    """Testes para propriedades computadas."""
    
    def test_esta_atribuido_true(self):
        """esta_atribuido deve retornar True se atribuído."""
        ticket = TicketEntity.criar(
            titulo="Bug atribuído",
            descricao="Este ticket está atribuído a alguém",
            criador_id="user-123",
        )
        
        ticket.atribuir_a("tecnico-123")
        
        assert ticket.esta_atribuido is True
    
    def test_esta_atribuido_false(self):
        """esta_atribuido deve retornar False se não atribuído."""
        ticket = TicketEntity.criar(
            titulo="Bug não atribuído",
            descricao="Este ticket não está atribuído",
            criador_id="user-123",
        )
        
        assert ticket.esta_atribuido is False
    
    def test_tempo_restante_sla_positivo(self):
        """tempo_restante_sla deve ser positivo dentro do prazo."""
        ticket = TicketEntity.criar(
            titulo="Bug recente",
            descricao="Este ticket acabou de ser criado",
            criador_id="user-123",
            prioridade=TicketPriority.BAIXA,  # 7 dias
        )
        
        tempo_restante = ticket.tempo_restante_sla
        
        assert tempo_restante is not None
        assert tempo_restante.total_seconds() > 0
    
    def test_tempo_restante_sla_none_se_fechado(self):
        """tempo_restante_sla deve ser None se ticket fechado."""
        ticket = TicketEntity.criar(
            titulo="Bug fechado",
            descricao="Este ticket está fechado",
            criador_id="user-123",
        )
        
        ticket.atribuir_a("tecnico-123")
        ticket.fechar()
        
        assert ticket.tempo_restante_sla is None


class TestTicketEntityIgualdade:
    """Testes para comparação e hash de entidades."""
    
    def test_tickets_com_mesmo_id_sao_iguais(self):
        """Tickets com mesmo ID devem ser considerados iguais."""
        ticket1 = TicketEntity.criar(
            titulo="Bug 1",
            descricao="Descrição do primeiro ticket",
            criador_id="user-123",
        )
        
        ticket2 = TicketEntity(
            id=ticket1.id,
            titulo="Bug diferente",
            descricao="Descrição diferente",
            criador_id="user-456",
        )
        
        assert ticket1 == ticket2
    
    def test_tickets_com_ids_diferentes_sao_diferentes(self):
        """Tickets com IDs diferentes não devem ser iguais."""
        ticket1 = TicketEntity.criar(
            titulo="Bug 1",
            descricao="Descrição do primeiro ticket",
            criador_id="user-123",
        )
        
        ticket2 = TicketEntity.criar(
            titulo="Bug 1",  # Mesmo título
            descricao="Descrição do primeiro ticket",  # Mesma descrição
            criador_id="user-123",  # Mesmo criador
        )
        
        assert ticket1 != ticket2
    
    def test_ticket_pode_ser_usado_em_set(self):
        """Ticket deve poder ser usado em sets."""
        ticket = TicketEntity.criar(
            titulo="Bug único",
            descricao="Este ticket deve ser único no set",
            criador_id="user-123",
        )
        
        ticket_set = {ticket}
        ticket_set.add(ticket)  # Adicionar novamente
        
        assert len(ticket_set) == 1


class TestTicketStatus:
    """Testes para enum TicketStatus."""
    
    def test_from_string_nome(self):
        """Deve converter nome do enum para TicketStatus."""
        status = TicketStatus.from_string("ABERTO")
        assert status == TicketStatus.ABERTO
    
    def test_from_string_valor(self):
        """Deve converter valor do enum para TicketStatus."""
        status = TicketStatus.from_string("Em Progresso")
        assert status == TicketStatus.EM_PROGRESSO
    
    def test_from_string_invalido(self):
        """Deve lançar erro para status inválido."""
        with pytest.raises(ValueError):
            TicketStatus.from_string("Invalido")


class TestTicketPriority:
    """Testes para enum TicketPriority."""
    
    def test_from_string_nome(self):
        """Deve converter nome do enum para TicketPriority."""
        prioridade = TicketPriority.from_string("ALTA")
        assert prioridade == TicketPriority.ALTA
    
    def test_from_string_valor(self):
        """Deve converter valor do enum para TicketPriority."""
        prioridade = TicketPriority.from_string("Crítica")
        assert prioridade == TicketPriority.CRITICA
    
    def test_sla_horas_property(self):
        """Deve retornar horas de SLA corretas."""
        assert TicketPriority.CRITICA.sla_horas == 4
        assert TicketPriority.ALTA.sla_horas == 24
        assert TicketPriority.MEDIA.sla_horas == 72
        assert TicketPriority.BAIXA.sla_horas == 168

# Diagramas Arquiteturais - TechSupport Manager

## 1. Visão Geral: Hexagonal Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DRIVING ADAPTERS                             │
│                      (Lado Esquerdo do Hexágono)                     │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │  Django      │  │   CLI        │  │   Webhooks   │                │
│  │  Views       │  │  Commands    │  │   (HTTP)     │                │
│  │  (HTTP)      │  │              │  │              │                │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                │
│         │                  │                  │                       │
│         │         Validação via Forms        │                       │
│         │         Input DTO                  │                       │
│         │                                    │                       │
└─────────┼────────────────────────────────────┼──────────────────────┘
          │                                    │
          └────────────────────┬───────────────┘
                               │
                     ┌─────────▼─────────┐
                     │   CONTAINER (DI)  │
                     │  (@inject injetar)│
                     └─────────┬─────────┘
                               │
          ┌────────────────────┴────────────────────┐
          │                                         │
          ▼                                         ▼
    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃                    O HEXÁGONO                       ┃
    ┃              (Core Domain - Puro)                   ┃
    ┃                                                     ┃
    ┃  ┌──────────────────────────────────────────────┐  ┃
    ┃  │          USE CASES (Services)                │  ┃
    ┃  │  CriarTicketService                          │  ┃
    ┃  │  ListarTicketsService                        │  ┃
    ┃  │  AtribuirTicketService                       │  ┃
    ┃  └──────────────────────────────────────────────┘  ┃
    ┃                      │                              ┃
    ┃              ┌───────┴────────┐                     ┃
    ┃              │                │                     ┃
    ┃              ▼                ▼                     ┃
    ┃  ┌──────────────────┐  ┌─────────────────┐         ┃
    ┃  │   ENTITIES       │  │   PORTS         │         ┃
    ┃  │ TicketEntity     │  │ (Interfaces)    │         ┃
    ┃  │ AgendamentoEntity│  │                 │         ┃
    ┃  │ InventarioEntity │  │ TicketRepository│         ┃
    ┃  │                  │  │ UnitOfWork      │         ┃
    ┃  │ Regras:          │  │ EventBus        │         ┃
    ┃  │ - SLA cálculo    │  │                 │         ┃
    ┃  │ - Validações     │  │ DTOs            │         ┃
    ┃  │ - Eventos        │  │                 │         ┃
    ┃  └──────────────────┘  └─────────────────┘         ┃
    ┃                                                     ┃
    ┃  ✅ Zero dependências de frameworks               ┃
    ┃  ✅ 100% testável sem banco                        ┃
    ┃  ✅ Agnóstico a infraestrutura                     ┃
    ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
          │                                   │
          │         Implementa Ports         │
          │                                   │
    ┌─────┴─────────────────────────────────┴──────┐
    │                                               │
    ▼                                               ▼
┌─────────────────────────────────┐    ┌──────────────────────────────┐
│  DRIVEN ADAPTERS                │    │  DRIVEN ADAPTERS             │
│  (Lado Direito - Persistência)  │    │  (Lado Direito - Eventos)    │
│                                 │    │                              │
│ ┌─────────────────────────────┐ │    │ ┌──────────────────────────┐ │
│ │  Repositories               │ │    │ │  Event Handlers          │ │
│ │  (TicketRepository impl.)   │ │    │ │  (Event Bus Celery)      │ │
│ │                             │ │    │ │                          │ │
│ │  Mappers                    │ │    │ │  TicketCriadoHandler     │ │
│ │  (Model ↔ Entity)           │ │    │ │  TicketAtribuidoHandler  │ │
│ │                             │ │    │ │  (Email, SMS, Webhooks)  │ │
│ │  ┌───────────────────────┐  │ │    │ └──────────────────────────┘ │
│ │  │  Django Models        │  │ │    │                              │
│ │  │  (TicketModel)        │  │ │    │ ┌──────────────────────────┐ │
│ │  │  (PostgreSQL ORM)     │  │ │    │ │  Event Store             │ │
│ │  └───────────────────────┘  │ │    │ │  (Domain Events persistido)
│ │                             │ │    │ │  (Auditoria completa)    │ │
│ └─────────────────────────────┘ │    │ └──────────────────────────┘ │
│           │                      │    │           │                   │
│           ▼                      │    │           ▼                   │
│    PostgreSQL (Banco)           │    │  RabbitMQ / Celery / Redis   │
│                                 │    │                              │
└─────────────────────────────────┘    └──────────────────────────────┘
```

---

## 2. Fluxo de Dados: Criar Ticket (Completo)

```
USER
  │
  │ HTTP POST /tickets/
  │
  ▼
┌──────────────────────────────────────┐
│   1. VALIDAÇÃO (Driving Adapter)     │
│   ┌────────────────────────────────┐ │
│   │ TicketForm.is_valid()          │ │ ← HTML Form validation
│   │ - Checa campos obrigatórios    │ │
│   │ - Checa tipos                  │ │
│   └────────────────────────────────┘ │
└──────────────────────────────────────┘
  │
  │ form.cleaned_data
  │
  ▼
┌──────────────────────────────────────┐
│   2. INJECTING (Container DI)        │
│   ┌────────────────────────────────┐ │
│   │ @inject                        │ │
│   │ service = CriarTicketService() │ │ ← Constructor Injection
│   │ (uow, repo injetados)          │ │
│   └────────────────────────────────┘ │
└──────────────────────────────────────┘
  │
  │ InputDTO
  │
  ▼
┌──────────────────────────────────────────────────────────┐
│   3. PROCESSAMENTO (Core - Use Case)                     │
│   ┌────────────────────────────────────────────────────┐ │
│   │ with self.uow:  ← TRANSAÇÃO ATÔMICA               │ │
│   │   ticket = TicketEntity.criar(data)               │ │
│   │   - Validar título                                │ │
│   │   - Inicializar status = "Aberto"                 │ │
│   │   - Calcular SLA                                  │ │
│   │   - Gerar ID único                                │ │
│   │                                                    │ │
│   │   self.repo.save(ticket)  ← Interface (não impl.) │ │
│   │   ← Repositório implementa                        │ │
│   │                                                    │ │
│   │   self.uow.publish_event(TicketCriadoEvent(...))  │ │
│   │   ← Evento enfileirado (não publicado ainda)      │ │
│   └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
  │
  │ Sai do with
  │
  ▼
┌──────────────────────────────────────────────────────────┐
│   4. PERSISTÊNCIA (Driven Adapter - Repository)          │
│   ┌────────────────────────────────────────────────────┐ │
│   │ TicketModel.objects.create(                        │ │
│   │   id=entity.id,                                    │ │
│   │   title=entity.title,      ← Mapper               │ │
│   │   status=entity.status.value,                      │ │
│   │   assigned_to=entity.assigned_to_id,              │ │
│   │   ...                                              │ │
│   │ ).save()  ← PostgreSQL                             │ │
│   └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
  │
  │ transaction.commit()  ← Banco persistiu
  │
  ▼
┌──────────────────────────────────────────────────────────┐
│   5. PUBLICAÇÃO DE EVENTOS (Event Bus)                   │
│   ┌────────────────────────────────────────────────────┐ │
│   │ uow._publish_events()                              │ │
│   │   → TicketCriadoEvent publicado para consumidores │ │
│   │   (apenas após commit bem-sucedido)                │ │
│   └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
  │
  │ Event publicado
  │
  ▼
┌──────────────────────────────────────────────────────────┐
│   6. HANDLERS ASSÍNCRONOS (Driven Adapters - Eventos)    │
│   ┌────────────────────────────────────────────────────┐ │
│   │ Celery Worker executa:                             │ │
│   │                                                    │ │
│   │ TicketCriadoHandler.handle(event)                 │ │
│   │   - Busca usuário criador                          │ │
│   │   - Envia email                                    │ │
│   │   - Cria notificação                               │ │
│   │   - Webhook para sistema externo                   │ │
│   │   (Tudo desacoplado, em background)               │ │
│   └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
  │
  │ Side-effects completos
  │
  ▼
┌──────────────────────────────────────────────────────────┐
│   7. RESPOSTA (View)                                     │
│   ┌────────────────────────────────────────────────────┐ │
│   │ OutputDTO = TicketOutputDTO.from_entity(ticket)   │ │
│   │ return JsonResponse({                              │ │
│   │   'ticket_id': output.ticket_id,                  │ │
│   │   'status': 'Aberto',                             │ │
│   │   'created_at': '2026-01-27T10:00:00Z'           │ │
│   │ })                                                 │ │
│   └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
  │
  │ JSON response
  │
  ▼
USER
```

---

## 3. Unit of Work - Context Manager

```
Fluxo de Execução com Context Manager

service.execute(data):
    │
    ├─ with self.uow:          ← __enter__()
    │  │                           ↓
    │  │                   transaction.set_autocommit(False)
    │  │
    │  ├─ ticket = TicketEntity.criar(data)
    │  │
    │  ├─ self.repo.save(ticket)  ← Não comita ainda
    │  │
    │  ├─ self.uow.publish_event(event)  ← Enfileira evento
    │  │
    │  └─ Sai do bloco             ← __exit__()
    │                                  ↓
    │                           ┌──────────────────┐
    │                           │ exc_type is None?│
    │                           └────────┬─────────┘
    │                                    │
    │                        ┌───────────┴───────────┐
    │                        │                       │
    │                   NÃO (erro)              SIM (sucesso)
    │                        │                       │
    │                        ▼                       ▼
    │                  rollback()                commit()
    │                  ├─ transaction.rollback()│
    │                  ├─ _events.clear()      ├─ transaction.commit()
    │                  └─ set_autocommit(True) ├─ _publish_events()
    │                                          └─ set_autocommit(True)
    │
    └─ return OutputDTO


Garantias:

✅ Atomicidade: Tudo ou nada
   - Se erro em line N: rollback de tudo persistido até line N-1
   - Se sucesso: ambos dados e eventos são consistentes

✅ Consistência: Eventos publicados ≡ Estado do banco
   - Eventos só publicados após transaction.commit()
   - Sem risco de side-effects parciais

✅ Isolamento: Thread-safe
   - Cada requisição HTTP tem seu próprio UoW
   - Transações isoladas por conexão ao banco

✅ Durabilidade: Banco garantido
   - transaction.commit() → ACID garantido pelo PostgreSQL
```

---

## 4. Dependency Injection - Resolução de Dependências

```
Container (Configuração Centralizada)

class Container:
    │
    ├─ Providers (Lazy):
    │  │
    │  ├─ ticket_repo = Singleton(TicketRepository)
    │  │                    ↓
    │  │  Primeira chamada: cria TicketRepository()
    │  │  Chamadas posteriores: reutiliza mesma instância
    │  │
    │  ├─ uow = Singleton(DjangoUnitOfWork)
    │  │        (Mesmo comportamento)
    │  │
    │  └─ criar_ticket_service = Factory(
    │                          CriarTicketService,
    │                          repo=ticket_repo,
    │                          uow=uow
    │                        )
    │                            ↓
    │  Cada chamada: nova instância com deps injetadas
    │
    └─ Wire (@inject decorator)
       └─ Conecta providers às assinaturas de método


USO NA PRÁTICA:

class TicketCreateView(View):
    @inject
    def post(self, request, 
             service: CriarTicketService = Provide[Container.criar_ticket_service]):
        
        service.execute(...)
        
        │
        ├─ Decorador @inject intercepta
        ├─ Resolve Container.criar_ticket_service (Factory)
        ├─ Chama Factory → cria nova CriarTicketService
        ├─ Injeta dependências:
        │  ├─ ticket_repo=Container.ticket_repo() [Singleton]
        │  └─ uow=Container.uow() [Singleton]
        └─ Passa como argumento 'service'


VANTAGENS:

✅ Lazy-loading: Providers criados sob demanda
✅ Singleton: Uma instância para toda app
✅ Factory: Nova instância por requisição (thread-safe)
✅ Testável: Fácil mockar com override()
✅ Explícito: Dependências visíveis na assinatura
```

---

## 5. Vertical Slicing - Organização de Código

```
Estrutura Horizontal (❌ Evitar)

adapters/
├── models/
│   ├── ticket.py
│   ├── agendamento.py
│   └── inventario.py
├── views/
│   ├── ticket.py
│   ├── agendamento.py
│   └── inventario.py
├── forms/
│   ├── ticket.py
│   ├── agendamento.py
│   └── inventario.py
└── repositories/
    ├── ticket.py
    ├── agendamento.py
    └── inventario.py

Problema:
- Developer buscando "criar ticket" navega 4 pastas
- Mudança em ticket afeta estrutura inteira
- Difícil repartilhar trabalho por feature


Estrutura Vertical (✅ Recomendado)

adapters/django_app/
├── tickets/              ← SLICE 1
│   ├── models.py        │
│   ├── repositories.py   │ Tudo junto
│   ├── views.py         │ Focused
│   ├── forms.py         │
│   └── urls.py          │
├── agendamento/         ← SLICE 2
│   ├── models.py        │
│   ├── repositories.py   │ Tudo junto
│   ├── views.py         │ Focused
│   ├── forms.py         │
│   └── urls.py          │
└── inventario/          ← SLICE 3
    ├── models.py        │
    ├── repositories.py   │ Tudo junto
    ├── views.py         │ Focused
    ├── forms.py         │
    └── urls.py          │

Benefícios:
✅ Developer "criar ticket" navega apenas tickets/
✅ Mudança em ticket isolada a esse slice
✅ Escalabilidade: múltiplos devs em paralelo
✅ Ownership: um dev/squad responsável por slice
```

---

## 6. Padrão Event Sourcing Simplificado

```
Sem Event Store:

Ticket.status = "Fechado"
Ticket.save()

Problema: Perdemos histórico de "Como chegou aqui?"


Com Event Store:

Estado Atual (Ticket table)  +  Histórico de Eventos (Events table)

┌─────────────────────────┐    ┌──────────────────────────────┐
│  Ticket                 │    │  DomainEventModel            │
├─────────────────────────┤    ├──────────────────────────────┤
│ id: 123                 │    │ event_id: uuid-1             │
│ title: "Bug login"      │    │ aggregate_id: 123            │
│ status: "Fechado"       │    │ event_type: TicketCriadoEvent
│ assigned_to: Carlos     │    │ data: JSON                   │
│ updated_at: 2026-01-27  │    │ recorded_at: 2026-01-27 10:00│
└─────────────────────────┘    │                              │
                               │ event_id: uuid-2             │
                               │ aggregate_id: 123            │
                               │ event_type: TicketAtribuidoEvent
                               │ data: JSON                   │
                               │ recorded_at: 2026-01-27 10:15│
                               │                              │
                               │ event_id: uuid-3             │
                               │ aggregate_id: 123            │
                               │ event_type: TicketFechadoEvent
                               │ data: JSON                   │
                               │ recorded_at: 2026-01-27 11:00│
                               └──────────────────────────────┘

Query de Auditoria:

SELECT * FROM domain_events
WHERE aggregate_id = 123
ORDER BY recorded_at ASC

Resultado:
1. Ticket criado por João (10:00)
2. Atribuído a Carlos (10:15)
3. 3 comentários adicionados (10:20, 10:25, 10:30)
4. Status alterado para "Em Progresso" (10:35)
5. Ticket fechado por Carlos (11:00)

Histórico completo e imutável! ✅
```

---

## 7. N+1 Queries Problem & Solution

```
SEM OTIMIZAÇÃO (❌ N+1):

Service.execute() → lista_tickets = repo.list_all()

query_1: SELECT * FROM ticket LIMIT 10
         ↓ Retorna 10 registros

for ticket in lista_tickets:
    user_name = ticket.assigned_user.name
    
    query_2: SELECT * FROM auth_user WHERE id = ticket.assigned_to
    query_3: SELECT * FROM auth_user WHERE id = ticket.assigned_to
    ...
    query_11: SELECT * FROM auth_user WHERE id = ticket.assigned_to

Total: 1 + 10 = 11 queries ❌


COM OTIMIZAÇÃO (✅ 2 queries):

Service.execute() → lista_tickets = repo.list_with_users()

Repositório otimizado:

def list_with_users(self):
    models = TicketModel.objects.select_related(
        'assigned_user'  ← Carrega em 1 query adicional
    )
    
    query_1: SELECT t.*, u.* 
             FROM ticket t
             LEFT JOIN auth_user u ON t.assigned_to = u.id

return [
    TicketWithUserDTO(
        ...
        assigned_user_name=m.assigned_user.name  ← Já em memória!
    )
    for m in models
]

Total: 1 + 1 = 2 queries ✅ (99.9% redução)


Técnicas:

select_related()        → OneToOne, ForeignKey (INNER/LEFT JOIN)
prefetch_related()      → ManyToMany, reverse ForeignKey (subquery)
values()                → Seleciona apenas colunas necessárias
only()                  → Defer loading de campos grandes (Text, JSON)
```

---

## 8. Mapa Mental Completo

```
                         TechSupport Manager
                                │
                    ┌───────────┼───────────┐
                    │           │           │
              ┌─────▼──┐  ┌────▼─────┐  ┌──▼──────┐
              │  CORE  │  │ ADAPTERS │  │   TEST  │
              └─────┬──┘  └────┬─────┘  └──┬──────┘
                    │          │          │
         ┌──────────┼──────────┼──────────┤
         │          │          │          │
      USE CASES  ENTITIES   PORTS    Views/Forms
         │          │          │     Repositories
      Services   Domain      Interfaces  Models
         │        Logic      Contracts
         │          │
    (Orquestração)  │
                 (Negócio)
                    │
         ┌──────────┼──────────┐
         │          │          │
      CORE       ADAPTER      ADAPTER
    (Puro)      (Django)      (Event Bus)
         │          │          │
      DTOs      Django ORM   Handlers
    Exceptions  Forms         Email
    Events      Views         Webhooks
               Serializers

              O FLUXO COMPLETO:

         View (HTTP)
            │
            ├─ Validação (Form)
            │
            ├─ DI Container (@inject)
            │
            ├─ Service (Core)
            │    ├─ with UoW (transação)
            │    │  ├─ Entity (negócio)
            │    │  ├─ Repository.save()
            │    │  └─ Event.publish()
            │    │
            │    └─ Commit + Event Bus
            │
            └─ Response (JSON/HTML)
```

---

## Convenções de Leitura

```
✅ Verde: Padrão correto, implementar assim
❌ Vermelho: Anti-pattern, evitar
⚠️  Laranja: Trade-off, contextual
🔵 Azul: Informação importante

─── Linha contínua: Fluxo normal
┊┊┊ Linha pontilhada: Comunicação assíncrona
═══ Linha grossa: Limite arquitetural
```


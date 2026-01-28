# TechSupport Manager

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Sistema de Gerenciamento de Suporte Técnico desenvolvido com **Arquitetura Hexagonal (Ports & Adapters)**, seguindo princípios de **Domain-Driven Design (DDD)**.

---

## 📋 Índice

- [Arquitetura](#-arquitetura)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Instalação](#-instalação)
- [Configuração](#-configuração)
- [Uso](#-uso)
- [Testes](#-testes)
- [Próximas Etapas](#-próximas-etapas)

---

## 🏗 Arquitetura

Este projeto implementa a **Arquitetura Hexagonal**, garantindo:

- **Core Domain puro**: Sem dependências de frameworks
- **Testabilidade**: 100% testável sem banco de dados
- **Flexibilidade**: Fácil troca de infraestrutura
- **Manutenibilidade**: Separação clara de responsabilidades

```
┌─────────────────────────────────────────────────────────────────┐
│                         DRIVING ADAPTERS                         │
│                      (Views, CLI, Webhooks)                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃                    CORE DOMAIN (HEXÁGONO)                    ┃
    ┃                                                              ┃
    ┃  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐   ┃
    ┃  │   USE CASES    │  │   ENTITIES     │  │    PORTS     │   ┃
    ┃  │   (Services)   │  │   (Domain)     │  │  (Interfaces)│   ┃
    ┃  └────────────────┘  └────────────────┘  └──────────────┘   ┃
    ┃                                                              ┃
    ┃  ✅ Zero dependências de frameworks                         ┃
    ┃  ✅ 100% testável sem banco                                  ┃
    ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        DRIVEN ADAPTERS                           │
│                  (Repositories, Event Bus, Cache)                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Estrutura do Projeto

```
techsupport/
├── src/
│   ├── core/                          # 🎯 HEXÁGONO (Pure Domain)
│   │   ├── shared/                    # Componentes compartilhados
│   │   │   ├── __init__.py
│   │   │   ├── exceptions.py          # Exceções de domínio
│   │   │   ├── events.py              # DomainEvent base
│   │   │   └── interfaces.py          # UnitOfWork, Repository protocols
│   │   │
│   │   └── tickets/                   # Domínio de Tickets
│   │       ├── __init__.py
│   │       ├── entities.py            # TicketEntity, Status, Priority
│   │       ├── use_cases.py           # CriarTicket, Atribuir, Fechar...
│   │       ├── ports.py               # TicketRepository interface
│   │       ├── dtos.py                # Input/Output DTOs
│   │       └── events.py              # TicketCriado, TicketFechado...
│   │
│   └── adapters/                      # 🔌 ADAPTADORES (Etapa 2+)
│       └── django_app/                # Implementação Django
│           ├── tickets/
│           │   ├── models.py
│           │   ├── repositories.py
│           │   ├── views.py
│           │   └── urls.py
│           └── unit_of_work.py
│
├── tests/
│   └── core/
│       └── tickets/
│           ├── test_entities.py       # Testes de entidades
│           └── test_use_cases.py      # Testes de use cases
│
├── config/                            # Configurações
├── .env.example                       # Template de variáveis de ambiente
├── .gitignore
├── pyproject.toml                     # Configuração do projeto
├── requirements.txt                   # Dependências
└── README.md
```

---

## 🚀 Instalação

### Pré-requisitos

- Python 3.10+
- pip ou pipx

### Passos

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/techsupport-manager.git
cd techsupport-manager

# 2. Crie um ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente
cp .env.example .env
# Edite .env com suas configurações
```

---

## ⚙️ Configuração

### Variáveis de Ambiente

Copie `.env.example` para `.env` e configure:

```bash
# Ambiente
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# Segurança (gere uma chave única!)
SECRET_KEY=sua-chave-secreta-aqui

# Banco de Dados (Etapa 2+)
DATABASE_URL=postgresql://user:pass@localhost:5432/techsupport_db

# Message Broker (Etapa 4+)
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
REDIS_URL=redis://localhost:6379/0
```

### Gerar SECRET_KEY

```python
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

## 💻 Uso

### Exemplo: Criar Ticket (Core Domain)

```python
from src.core.tickets.entities import TicketEntity, TicketPriority
from src.core.tickets.dtos import CriarTicketInputDTO
from src.core.tickets.use_cases import CriarTicketService

# 1. Criar entidade diretamente (para testes)
ticket = TicketEntity.criar(
    titulo="Sistema lento",
    descricao="O sistema está demorando mais de 10s para responder",
    criador_id="user-123",
    prioridade=TicketPriority.ALTA,
    categoria="Performance"
)

print(f"Ticket criado: {ticket.id}")
print(f"Status: {ticket.status.value}")
print(f"SLA: {ticket.sla_prazo}")
print(f"Atrasado: {ticket.esta_atrasado}")

# 2. Atribuir a técnico
ticket.atribuir_a("tecnico-456")
print(f"Novo status: {ticket.status.value}")  # "Em Progresso"

# 3. Fechar ticket
ticket.fechar()
print(f"Status final: {ticket.status.value}")  # "Fechado"
```

### Exemplo: Usar Use Case com Repositório In-Memory

```python
from src.core.tickets.ports import InMemoryTicketRepository
from src.core.tickets.use_cases import CriarTicketService
from src.core.tickets.dtos import CriarTicketInputDTO

# Fake UoW para testes
class FakeUnitOfWork:
    def __init__(self):
        self._events = []
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass
    
    def commit(self):
        pass
    
    def rollback(self):
        pass
    
    def publish_event(self, event):
        self._events.append(event)

# Setup
repo = InMemoryTicketRepository()
uow = FakeUnitOfWork()
service = CriarTicketService(repo, uow)

# Executar
input_dto = CriarTicketInputDTO(
    titulo="Bug crítico",
    descricao="Sistema não aceita login de usuários",
    criador_id="user-789",
    prioridade="CRITICA"
)

output = service.execute(input_dto)
print(f"Ticket ID: {output.id}")
print(f"Status: {output.status}")
```

---

## 🧪 Testes

### Executar Todos os Testes

```bash
# Instalar dependências de teste
pip install pytest pytest-cov pytest-mock

# Executar testes com cobertura
pytest tests/ -v --cov=src/core --cov-report=term-missing

# Apenas testes rápidos (sem markers)
pytest tests/ -v -m "not slow"
```

### Estrutura de Testes

```
tests/
├── core/
│   └── tickets/
│       ├── test_entities.py      # Testes de regras de negócio
│       │   ├── TestTicketEntityCriacao
│       │   ├── TestTicketEntitySLA
│       │   ├── TestTicketEntityAtribuicao
│       │   └── ...
│       └── test_use_cases.py     # Testes de casos de uso
│           ├── TestCriarTicketService
│           ├── TestAtribuirTicketService
│           └── ...
└── conftest.py                   # Fixtures compartilhadas
```

### Cobertura Esperada

| Módulo | Cobertura |
|--------|-----------|
| `src/core/shared` | 100% |
| `src/core/tickets/entities.py` | 100% |
| `src/core/tickets/use_cases.py` | 100% |
| **Total** | **>90%** |

---

## 📅 Próximas Etapas

### ✅ Etapa 1: Core Domain (ATUAL)
- [x] Entidades de domínio
- [x] Use Cases / Services
- [x] Ports (interfaces)
- [x] Domain Events
- [x] DTOs
- [x] Testes unitários

### ⏳ Etapa 2: Django Adapters
- [ ] Models (PostgreSQL)
- [ ] Repositories (implementação)
- [ ] DjangoUnitOfWork
- [ ] Migrations

### ⏳ Etapa 3: Views + Dependency Injection
- [ ] Django Views
- [ ] Forms
- [ ] Container DI (dependency-injector)
- [ ] Constructor Injection

### ⏳ Etapa 4: Event Handlers
- [ ] Celery Tasks
- [ ] Event Bus (RabbitMQ/Redis)
- [ ] Email Notifications
- [ ] Testes de integração

---

## 🤝 Contribuindo

1. Fork o projeto
2. Crie sua feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

---

## 📄 Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

---

## 📞 Suporte

- **Issues**: [GitHub Issues](https://github.com/seu-usuario/techsupport-manager/issues)
- **Docs**: [Documentação](./docs/)

---

**Desenvolvido com ❤️ seguindo Clean Architecture e DDD**

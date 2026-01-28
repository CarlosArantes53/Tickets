"""
Database Adapter - Abstração de conexão de banco de dados.

Este módulo fornece uma camada de abstração sobre diferentes
engines de banco de dados, facilitando:
- Troca entre SQLite (dev) e PostgreSQL (prod)
- Futuro suporte a outros bancos (MySQL, MongoDB, etc.)
- Database sharding e routing
- Connection pooling configurável

Padrão: Strategy Pattern
    - DatabaseAdapter: Interface abstrata
    - PostgreSQLAdapter: Implementação PostgreSQL
    - SQLiteAdapter: Implementação SQLite (dev/test)

Escalabilidade Futura:
    - Read replicas
    - Sharding por domínio
    - Multi-tenancy
    - Connection pooling distribuído
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
from dataclasses import dataclass, field
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """
    Configuração de conexão de banco de dados.
    
    Independente de engine - pode ser convertida para
    diferentes formatos (Django DATABASES, SQLAlchemy URL, etc.)
    """
    
    engine: str = "postgresql"  # postgresql, sqlite, mysql, mongodb
    name: str = "techsupport_db"
    user: str = "techsupport_user"
    password: str = ""
    host: str = "localhost"
    port: int = 5432
    
    # Opções de conexão
    conn_max_age: int = 60  # Connection pooling (segundos)
    connect_timeout: int = 10
    
    # Opções avançadas
    options: Dict[str, Any] = field(default_factory=dict)
    
    # Read replica (para queries de leitura)
    read_replica_host: Optional[str] = None
    read_replica_port: Optional[int] = None
    
    @classmethod
    def from_url(cls, url: str) -> "DatabaseConfig":
        """
        Cria configuração a partir de DATABASE_URL.
        
        Formatos suportados:
        - postgresql://user:pass@host:port/dbname
        - sqlite:///path/to/db.sqlite3
        - mysql://user:pass@host:port/dbname
        
        Args:
            url: URL de conexão
            
        Returns:
            Instância configurada
        """
        import re
        
        # SQLite
        if url.startswith("sqlite"):
            match = re.match(r"sqlite:///(.+)", url)
            if match:
                return cls(
                    engine="sqlite",
                    name=match.group(1),
                    host="",
                    port=0,
                )
        
        # PostgreSQL / MySQL
        pattern = r"(postgresql|postgres|mysql)://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)"
        match = re.match(pattern, url)
        
        if match:
            engine, user, password, host, port, name = match.groups()
            return cls(
                engine="postgresql" if engine in ("postgresql", "postgres") else engine,
                name=name,
                user=user,
                password=password,
                host=host,
                port=int(port),
            )
        
        raise ValueError(f"URL de banco inválida: {url}")
    
    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """
        Cria configuração a partir de variáveis de ambiente.
        
        Variáveis:
        - DATABASE_URL: URL completa (prioridade)
        - DATABASE_ENGINE: Engine (postgresql, sqlite)
        - DATABASE_NAME: Nome do banco
        - DATABASE_USER: Usuário
        - DATABASE_PASSWORD: Senha
        - DATABASE_HOST: Host
        - DATABASE_PORT: Porta
        """
        import os
        
        # Prioridade para DATABASE_URL
        url = os.getenv("DATABASE_URL")
        if url:
            return cls.from_url(url)
        
        return cls(
            engine=os.getenv("DATABASE_ENGINE", "postgresql"),
            name=os.getenv("DATABASE_NAME", "techsupport_db"),
            user=os.getenv("DATABASE_USER", "techsupport_user"),
            password=os.getenv("DATABASE_PASSWORD", "techsupport_pass"),
            host=os.getenv("DATABASE_HOST", "localhost"),
            port=int(os.getenv("DATABASE_PORT", "5432")),
        )
    
    def to_django_config(self) -> Dict[str, Any]:
        """
        Converte para formato Django DATABASES.
        
        Returns:
            Dict compatível com Django settings.DATABASES
        """
        engines = {
            "postgresql": "django.db.backends.postgresql",
            "sqlite": "django.db.backends.sqlite3",
            "mysql": "django.db.backends.mysql",
        }
        
        config = {
            "ENGINE": engines.get(self.engine, engines["postgresql"]),
            "NAME": self.name,
        }
        
        if self.engine != "sqlite":
            config.update({
                "USER": self.user,
                "PASSWORD": self.password,
                "HOST": self.host,
                "PORT": str(self.port),
                "CONN_MAX_AGE": self.conn_max_age,
                "OPTIONS": {
                    "connect_timeout": self.connect_timeout,
                    **self.options,
                },
            })
        
        return config
    
    def to_sqlalchemy_url(self) -> str:
        """
        Converte para URL SQLAlchemy.
        
        Útil para futuras integrações ou scripts.
        
        Returns:
            URL no formato SQLAlchemy
        """
        if self.engine == "sqlite":
            return f"sqlite:///{self.name}"
        
        return f"{self.engine}://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class DatabaseAdapter(ABC):
    """
    Interface abstrata para adaptadores de banco de dados.
    
    Permite trocar implementações sem afetar o código de negócio.
    
    Implementações:
    - DjangoDatabaseAdapter: Usa Django ORM
    - SQLAlchemyDatabaseAdapter: Usa SQLAlchemy (futuro)
    - MongoDBAdapter: Usa PyMongo (futuro)
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._connected = False
    
    @abstractmethod
    def connect(self) -> None:
        """Estabelece conexão com o banco."""
        raise NotImplementedError
    
    @abstractmethod
    def disconnect(self) -> None:
        """Fecha conexão com o banco."""
        raise NotImplementedError
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Verifica se está conectado."""
        raise NotImplementedError
    
    @abstractmethod
    def health_check(self) -> bool:
        """
        Verifica saúde da conexão.
        
        Returns:
            True se conexão está saudável
        """
        raise NotImplementedError
    
    @abstractmethod
    @contextmanager
    def transaction(self):
        """
        Context manager para transações.
        
        Yields:
            Conexão com transação ativa
        """
        raise NotImplementedError
    
    @abstractmethod
    def execute_raw(self, sql: str, params: Optional[tuple] = None) -> Any:
        """
        Executa SQL raw (para migrations/scripts).
        
        Args:
            sql: Query SQL
            params: Parâmetros da query
            
        Returns:
            Resultado da query
        """
        raise NotImplementedError


class DjangoDatabaseAdapter(DatabaseAdapter):
    """
    Adaptador de banco usando Django ORM.
    
    Wrapper sobre django.db.connection para fornecer
    interface consistente com outros adaptadores.
    """
    
    def connect(self) -> None:
        """Garante que Django está configurado."""
        import django
        from django.conf import settings
        
        if not settings.configured:
            raise RuntimeError(
                "Django não configurado. "
                "Chame django.setup() antes de usar o adapter."
            )
        
        self._connected = True
        logger.info(f"Database connected: {self.config.engine}://{self.config.host}")
    
    def disconnect(self) -> None:
        """Fecha conexões do pool."""
        from django.db import connections
        connections.close_all()
        self._connected = False
        logger.info("Database disconnected")
    
    def is_connected(self) -> bool:
        """Verifica conexão."""
        return self._connected
    
    def health_check(self) -> bool:
        """Verifica saúde da conexão."""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    @contextmanager
    def transaction(self):
        """Context manager para transações Django."""
        from django.db import transaction
        
        with transaction.atomic():
            yield
    
    def execute_raw(self, sql: str, params: Optional[tuple] = None) -> Any:
        """Executa SQL raw via Django."""
        from django.db import connection
        
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            
            # Se é SELECT, retorna resultados
            if sql.strip().upper().startswith("SELECT"):
                return cursor.fetchall()
            
            return cursor.rowcount


class DatabaseAdapterFactory:
    """
    Factory para criar adaptadores de banco.
    
    Centraliza criação e configuração de adaptadores.
    
    Example:
        config = DatabaseConfig.from_env()
        adapter = DatabaseAdapterFactory.create(config)
        adapter.connect()
    """
    
    _adapters: Dict[str, Type[DatabaseAdapter]] = {
        "django": DjangoDatabaseAdapter,
    }
    
    @classmethod
    def register(cls, name: str, adapter_class: Type[DatabaseAdapter]) -> None:
        """
        Registra novo tipo de adaptador.
        
        Args:
            name: Nome identificador
            adapter_class: Classe do adaptador
        """
        cls._adapters[name] = adapter_class
    
    @classmethod
    def create(
        cls,
        config: DatabaseConfig,
        adapter_type: str = "django"
    ) -> DatabaseAdapter:
        """
        Cria adaptador de banco.
        
        Args:
            config: Configuração do banco
            adapter_type: Tipo de adaptador (django, sqlalchemy, etc.)
            
        Returns:
            Instância do adaptador configurado
            
        Raises:
            ValueError: Se tipo não registrado
        """
        adapter_class = cls._adapters.get(adapter_type)
        
        if adapter_class is None:
            raise ValueError(
                f"Adaptador '{adapter_type}' não registrado. "
                f"Disponíveis: {list(cls._adapters.keys())}"
            )
        
        return adapter_class(config)


# =============================================================================
# Database Router para Sharding Futuro
# =============================================================================

class DomainDatabaseRouter:
    """
    Router para direcionar queries por domínio.
    
    Permite escalar horizontalmente separando domínios
    em bancos diferentes.
    
    Configuração no Django settings:
        DATABASE_ROUTERS = ['src.adapters.django_app.shared.database.DomainDatabaseRouter']
        
        DATABASES = {
            'default': {...},           # Tickets (principal)
            'scheduling': {...},        # Agendamentos
            'inventory': {...},         # Inventário
        }
    
    O router decide qual banco usar baseado no app_label do model.
    """
    
    # Mapeamento: app_label -> database alias
    ROUTE_MAP = {
        'tickets': 'default',
        'agendamento': 'scheduling',
        'inventario': 'inventory',
    }
    
    def db_for_read(self, model, **hints) -> Optional[str]:
        """Determina banco para leitura."""
        app_label = model._meta.app_label
        return self.ROUTE_MAP.get(app_label, 'default')
    
    def db_for_write(self, model, **hints) -> Optional[str]:
        """Determina banco para escrita."""
        return self.db_for_read(model, **hints)
    
    def allow_relation(self, obj1, obj2, **hints) -> Optional[bool]:
        """
        Determina se relação entre objetos é permitida.
        
        Só permite relações entre objetos do mesmo banco.
        """
        db1 = self.db_for_read(type(obj1))
        db2 = self.db_for_read(type(obj2))
        
        if db1 and db2:
            return db1 == db2
        
        return None
    
    def allow_migrate(self, db, app_label, model_name=None, **hints) -> Optional[bool]:
        """
        Determina se migration deve rodar no banco.
        
        Garante que migrations rodem apenas no banco correto.
        """
        target_db = self.ROUTE_MAP.get(app_label, 'default')
        return db == target_db


# =============================================================================
# Helpers de Conexão
# =============================================================================

def get_database_adapter(config: Optional[DatabaseConfig] = None) -> DatabaseAdapter:
    """
    Helper para obter adaptador configurado.
    
    Usa variáveis de ambiente se config não fornecido.
    
    Args:
        config: Configuração opcional
        
    Returns:
        Adaptador pronto para uso
    """
    if config is None:
        config = DatabaseConfig.from_env()
    
    return DatabaseAdapterFactory.create(config)


def check_database_connection() -> Dict[str, Any]:
    """
    Verifica conexão e retorna informações do banco.
    
    Útil para health checks e debugging.
    
    Returns:
        Dict com informações da conexão
    """
    try:
        config = DatabaseConfig.from_env()
        adapter = DatabaseAdapterFactory.create(config)
        adapter.connect()
        
        healthy = adapter.health_check()
        
        return {
            "status": "connected" if healthy else "unhealthy",
            "engine": config.engine,
            "host": config.host,
            "port": config.port,
            "database": config.name,
            "healthy": healthy,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "healthy": False,
        }

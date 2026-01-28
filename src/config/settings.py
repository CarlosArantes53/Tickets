"""
Django Settings para TechSupport Manager.

Configurações organizadas por ambiente (development, production).
Usa variáveis de ambiente para configurações sensíveis.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# =============================================================================
# Caminhos Base
# =============================================================================

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# src/ directory
SRC_DIR = BASE_DIR / 'src'

# =============================================================================
# Segurança
# =============================================================================

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv(
    'SECRET_KEY',
    'django-insecure-dev-key-change-in-production-please'
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# =============================================================================
# Aplicações
# =============================================================================

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    # 'rest_framework',  # Futuro: API REST
]

LOCAL_APPS = [
    'src.adapters.django_app.tickets',
    # 'src.adapters.django_app.agendamento',  # Futuro
    # 'src.adapters.django_app.inventario',   # Futuro
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# =============================================================================
# Middleware
# =============================================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'src.config.urls'

# =============================================================================
# Templates
# =============================================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'src.config.wsgi.application'

# =============================================================================
# Banco de Dados
# =============================================================================

# Configuração flexível: suporta DATABASE_URL ou variáveis individuais
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # Parse DATABASE_URL (formato: postgresql://user:pass@host:port/dbname)
    import re
    match = re.match(
        r'postgres(?:ql)?://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)',
        DATABASE_URL
    )
    if match:
        DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME = match.groups()
    else:
        # Fallback para SQLite se URL inválida
        DB_USER = DB_PASSWORD = DB_HOST = DB_PORT = DB_NAME = None
else:
    DB_USER = os.getenv('DATABASE_USER', 'techsupport_user')
    DB_PASSWORD = os.getenv('DATABASE_PASSWORD', 'techsupport_pass')
    DB_HOST = os.getenv('DATABASE_HOST', 'localhost')
    DB_PORT = os.getenv('DATABASE_PORT', '5432')
    DB_NAME = os.getenv('DATABASE_NAME', 'techsupport_db')

# Determinar engine baseado na configuração
if DB_NAME and DB_HOST:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': DB_NAME,
            'USER': DB_USER,
            'PASSWORD': DB_PASSWORD,
            'HOST': DB_HOST,
            'PORT': DB_PORT,
            'CONN_MAX_AGE': 60,  # Connection pooling
            'OPTIONS': {
                'connect_timeout': 10,
            },
        }
    }
else:
    # Fallback para SQLite (desenvolvimento/testes)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# =============================================================================
# Abstração de Database Router (para escalabilidade futura)
# =============================================================================

# Descomente para usar múltiplos bancos por domínio
# DATABASE_ROUTERS = ['src.config.routers.DomainDatabaseRouter']

# Configuração para sharding futuro
# DATABASES['tickets'] = { ... }
# DATABASES['scheduling'] = { ... }
# DATABASES['inventory'] = { ... }

# =============================================================================
# Cache (preparado para Redis)
# =============================================================================

REDIS_URL = os.getenv('REDIS_URL')

if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }

# =============================================================================
# Validação de Senha
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# =============================================================================
# Internacionalização
# =============================================================================

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# =============================================================================
# Arquivos Estáticos
# =============================================================================

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
] if (BASE_DIR / 'static').exists() else []

# =============================================================================
# Default Primary Key
# =============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# Logging
# =============================================================================

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'src.core': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'src.adapters': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# =============================================================================
# Configurações de SLA (Domain)
# =============================================================================

SLA_HOURS = {
    'CRITICA': int(os.getenv('SLA_CRITICA_HORAS', 4)),
    'ALTA': int(os.getenv('SLA_ALTA_HORAS', 24)),
    'MEDIA': int(os.getenv('SLA_MEDIA_HORAS', 72)),
    'BAIXA': int(os.getenv('SLA_BAIXA_HORAS', 168)),
}

# =============================================================================
# Celery / Event Bus
# =============================================================================

# Broker URL (RabbitMQ)
CELERY_BROKER_URL = os.getenv(
    'CELERY_BROKER_URL',
    os.getenv('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672//')
)

# Backend de resultados (Redis)
CELERY_RESULT_BACKEND = os.getenv(
    'CELERY_RESULT_BACKEND',
    REDIS_URL + '/1' if REDIS_URL else 'redis://localhost:6379/1'
)

# Serialização
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# Timezone
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Configurações de execução
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Retry
CELERY_TASK_DEFAULT_RETRY_DELAY = 60
CELERY_TASK_MAX_RETRIES = 3

# Resultados
CELERY_RESULT_EXPIRES = 3600  # 1 hora

# Event Publisher mode
# 'sync' = LoggingEventPublisher (desenvolvimento)
# 'celery' = CeleryEventPublisher (produção)
EVENT_PUBLISHER_MODE = os.getenv('EVENT_PUBLISHER_MODE', 'sync')

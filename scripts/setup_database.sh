#!/bin/bash
# =============================================================================
# TechSupport Manager - Setup do Banco de Dados
# =============================================================================
# Este script configura o PostgreSQL para desenvolvimento local.
# 
# Pré-requisitos:
# - PostgreSQL instalado e rodando
# - psql disponível no PATH
# - Permissões para criar banco e usuário
#
# Uso:
#   chmod +x scripts/setup_database.sh
#   ./scripts/setup_database.sh
#
# Ou com variáveis customizadas:
#   DB_NAME=mydb DB_USER=myuser ./scripts/setup_database.sh
# =============================================================================

set -e  # Sair em caso de erro

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configurações (podem ser sobrescritas por variáveis de ambiente)
DB_NAME="${DB_NAME:-techsupport_db}"
DB_USER="${DB_USER:-techsupport_user}"
DB_PASSWORD="${DB_PASSWORD:-techsupport_pass}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

echo -e "${GREEN}=== TechSupport Manager - Setup do Banco de Dados ===${NC}"
echo ""
echo "Configurações:"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo "  Host: $DB_HOST:$DB_PORT"
echo ""

# Função para executar comandos SQL
execute_sql() {
    local sql="$1"
    local description="$2"
    
    echo -e "${YELLOW}→ $description${NC}"
    
    if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U postgres -c "$sql" 2>/dev/null; then
        echo -e "${GREEN}  ✓ Sucesso${NC}"
    else
        # Tentar sem senha (autenticação peer/trust)
        if psql -h "$DB_HOST" -p "$DB_PORT" -U postgres -c "$sql" 2>/dev/null; then
            echo -e "${GREEN}  ✓ Sucesso${NC}"
        else
            echo -e "${RED}  ✗ Falhou (pode já existir ou erro de permissão)${NC}"
        fi
    fi
}

# 1. Criar usuário (se não existir)
execute_sql "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" \
    "Criando usuário $DB_USER"

# 2. Criar banco de dados
execute_sql "CREATE DATABASE $DB_NAME OWNER $DB_USER;" \
    "Criando banco de dados $DB_NAME"

# 3. Conceder privilégios
execute_sql "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" \
    "Concedendo privilégios"

# 4. Habilitar extensões úteis
echo -e "${YELLOW}→ Habilitando extensões...${NC}"
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";" 2>/dev/null || \
psql -h "$DB_HOST" -p "$DB_PORT" -U postgres -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";" 2>/dev/null || \
echo -e "${YELLOW}  ⚠ Não foi possível criar extensão uuid-ossp${NC}"

echo ""
echo -e "${GREEN}=== Setup Concluído ===${NC}"
echo ""
echo "Próximos passos:"
echo ""
echo "1. Atualize seu .env com as credenciais:"
echo "   DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
echo ""
echo "2. Execute as migrations:"
echo "   python manage.py migrate"
echo ""
echo "3. Crie um superusuário (opcional):"
echo "   python manage.py createsuperuser"
echo ""
echo "4. Inicie o servidor:"
echo "   python manage.py runserver"
echo ""

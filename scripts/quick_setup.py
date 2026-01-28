#!/usr/bin/env python
"""
Setup rápido para desenvolvimento local.

Este script:
1. Configura Django settings
2. Cria banco de dados SQLite
3. Executa migrations
4. Cria dados de exemplo (opcional)

Uso:
    python scripts/quick_setup.py
    python scripts/quick_setup.py --with-sample-data
"""

import os
import sys
import argparse

# Adicionar src ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def setup_django():
    """Configura Django para uso standalone."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'src.config.settings')
    
    # Forçar SQLite para desenvolvimento rápido
    os.environ['DATABASE_URL'] = 'sqlite:///db.sqlite3'
    
    import django
    django.setup()


def run_migrations():
    """Executa migrations."""
    from django.core.management import call_command
    
    print("📦 Executando migrations...")
    call_command('migrate', verbosity=1)
    print("✅ Migrations concluídas!")


def create_sample_data():
    """Cria dados de exemplo."""
    from src.core.tickets.entities import TicketEntity, TicketPriority
    from src.adapters.django_app.tickets.repositories import DjangoTicketRepository
    
    repo = DjangoTicketRepository()
    
    sample_tickets = [
        {
            'titulo': 'Sistema fora do ar',
            'descricao': 'O sistema está completamente inacessível para todos os usuários. Erro 503 em todas as páginas.',
            'criador_id': 'user-001',
            'prioridade': TicketPriority.CRITICA,
            'categoria': 'Infraestrutura',
        },
        {
            'titulo': 'Bug no login com Google',
            'descricao': 'Usuários não conseguem fazer login usando conta Google. O botão não responde ao clicar.',
            'criador_id': 'user-002',
            'prioridade': TicketPriority.ALTA,
            'categoria': 'Autenticação',
        },
        {
            'titulo': 'Relatório exportando dados incorretos',
            'descricao': 'O relatório de vendas está mostrando valores negativos em algumas colunas.',
            'criador_id': 'user-003',
            'prioridade': TicketPriority.MEDIA,
            'categoria': 'Relatórios',
        },
        {
            'titulo': 'Sugestão de melhoria no layout',
            'descricao': 'Seria interessante ter um modo escuro na aplicação.',
            'criador_id': 'user-001',
            'prioridade': TicketPriority.BAIXA,
            'categoria': 'UX/UI',
        },
        {
            'titulo': 'Performance lenta nas consultas',
            'descricao': 'A tela de listagem de clientes está demorando mais de 10 segundos para carregar.',
            'criador_id': 'user-004',
            'prioridade': TicketPriority.ALTA,
            'categoria': 'Performance',
        },
    ]
    
    print("📝 Criando tickets de exemplo...")
    
    for ticket_data in sample_tickets:
        ticket = TicketEntity.criar(**ticket_data)
        repo.save(ticket)
        print(f"   ✓ {ticket.titulo[:50]}...")
    
    # Atribuir alguns tickets
    tickets = repo.list_all()
    if len(tickets) >= 2:
        tickets[0].atribuir_a('tecnico-001')
        repo.save(tickets[0])
        
        tickets[1].atribuir_a('tecnico-002')
        repo.save(tickets[1])
    
    print(f"✅ {len(sample_tickets)} tickets criados!")


def check_connection():
    """Verifica conexão com o banco."""
    from django.db import connection
    
    print("🔍 Verificando conexão com o banco...")
    
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        print("✅ Conexão OK!")
        return True
    except Exception as e:
        print(f"❌ Erro de conexão: {e}")
        return False


def show_info():
    """Mostra informações do setup."""
    from django.conf import settings
    
    print("\n" + "=" * 60)
    print("📊 Informações do Setup")
    print("=" * 60)
    print(f"  Database Engine: {settings.DATABASES['default']['ENGINE']}")
    print(f"  Database Name: {settings.DATABASES['default']['NAME']}")
    print(f"  Debug Mode: {settings.DEBUG}")
    print("=" * 60)
    print("\n🚀 Próximos passos:")
    print("   1. python manage.py runserver")
    print("   2. Acesse: http://localhost:8000/admin/")
    print("   3. Acesse: http://localhost:8000/tickets/")
    print("\n")


def main():
    parser = argparse.ArgumentParser(description='Setup rápido para desenvolvimento')
    parser.add_argument(
        '--with-sample-data',
        action='store_true',
        help='Criar dados de exemplo'
    )
    parser.add_argument(
        '--check-only',
        action='store_true',
        help='Apenas verificar conexão'
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("🔧 TechSupport Manager - Quick Setup")
    print("=" * 60 + "\n")
    
    # Configurar Django
    setup_django()
    
    if args.check_only:
        check_connection()
        return
    
    # Verificar conexão
    if not check_connection():
        print("\n⚠️  Certifique-se de que o banco de dados está rodando.")
        print("   Para usar SQLite, defina: DATABASE_URL=sqlite:///db.sqlite3")
        return
    
    # Executar migrations
    run_migrations()
    
    # Criar dados de exemplo
    if args.with_sample_data:
        create_sample_data()
    
    # Mostrar informações
    show_info()


if __name__ == '__main__':
    main()

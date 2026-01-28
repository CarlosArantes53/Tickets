"""
Configurações globais do Pytest para TechSupport Manager.

Este arquivo é carregado automaticamente pelo pytest e
fornece fixtures e configurações compartilhadas.
"""

import pytest
import sys
from pathlib import Path

# Adicionar src ao path para imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture(scope="session")
def project_root():
    """Retorna o caminho raiz do projeto."""
    return Path(__file__).parent.parent


@pytest.fixture(autouse=True)
def reset_singletons():
    """
    Reset de singletons entre testes.
    
    Garante que cada teste inicia com estado limpo.
    """
    yield
    # Cleanup após cada teste se necessário


def pytest_configure(config):
    """Configuração do pytest."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )


def pytest_collection_modifyitems(config, items):
    """Modifica coleção de testes."""
    # Adicionar skip para testes de integração se não houver banco
    skip_integration = pytest.mark.skip(reason="Integration tests require database")
    
    for item in items:
        if "integration" in item.keywords:
            # Apenas pular se não estivermos em modo de integração
            if not config.getoption("--run-integration", default=False):
                item.add_marker(skip_integration)


def pytest_addoption(parser):
    """Adiciona opções de linha de comando."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run integration tests",
    )

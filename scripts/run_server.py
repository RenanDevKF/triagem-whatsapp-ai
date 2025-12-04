"""
Script para rodar o servidor FastAPI com configurações adequadas.

Rode: python scripts/run_server.py
"""

import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

import uvicorn
from src.core.config import get_settings

settings = get_settings()


def main():
    """Inicia o servidor"""
    
    print("=" * 60)
    print(f"🚀 INICIANDO {settings.app_name}")
    print("=" * 60)
    print(f"\n📍 Ambiente: {settings.environment}")
    print(f"🌐 URL: http://{settings.api_host}:{settings.api_port}")
    print(f"📚 Docs: http://{settings.api_host}:{settings.api_port}/docs")
    print(f"❤️  Health: http://{settings.api_host}:{settings.api_port}/health")
    print("\n" + "=" * 60)
    print("⚡ Pressione CTRL+C para parar o servidor")
    print("=" * 60 + "\n")
    
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    main()
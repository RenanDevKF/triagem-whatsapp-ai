"""
Script para inicializar o banco de dados.
Cria todas as tabelas necessárias.

Rode: python scripts/init_database.py
"""

import asyncio
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.infrastructure.database.session import init_db, check_db_connection
from src.core.config import get_settings

settings = get_settings()


async def main():
    """Inicializa o banco de dados"""
    
    print("=" * 60)
    print("🗄️  INICIALIZANDO BANCO DE DADOS")
    print("=" * 60)
    print(f"\n📍 Database: {settings.database_url}\n")
    
    try:
        # 1. Verifica conexão
        print("1️⃣  Verificando conexão...")
        is_connected = await check_db_connection()
        
        if not is_connected:
            logger.error("❌ Falha na conexão com o banco de dados")
            return False
        
        print("   ✅ Conexão OK\n")
        
        # 2. Cria tabelas
        print("2️⃣  Criando tabelas...")
        await init_db()
        print("   ✅ Tabelas criadas com sucesso\n")
        
        # 3. Verifica se arquivo SQLite foi criado
        if settings.database_url.startswith("sqlite"):
            db_file = settings.database_url.split("///")[1]
            if Path(db_file).exists():
                size = Path(db_file).stat().st_size
                print(f"   📁 Arquivo criado: {db_file} ({size} bytes)\n")
        
        print("=" * 60)
        print("✅ BANCO DE DADOS INICIALIZADO COM SUCESSO!")
        print("=" * 60)
        print("\n🚀 Próximo passo: python scripts/run_server.py\n")
        
        return True
        
    except Exception as e:
        logger.exception(f"❌ Erro ao inicializar banco: {e}")
        print("\n" + "=" * 60)
        print("❌ FALHA NA INICIALIZAÇÃO")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
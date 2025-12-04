"""
Configuração e gerenciamento de sessões do banco de dados.
Usa SQLAlchemy 2.0 com suporte assíncrono.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.pool import NullPool, QueuePool
from loguru import logger

from src.core.config import get_settings
from src.infrastructure.database.models import Base

settings = get_settings()

# ========================================
# ENGINE
# ========================================

def create_engine() -> AsyncEngine:
    """
    Cria engine assíncrona do SQLAlchemy.
    Configuração otimizada para produção e desenvolvimento.
    """
    
    # Configurações baseadas no ambiente
    engine_kwargs = {
        "echo": settings.db_echo,  # Log de SQL queries
        "future": True  # SQLAlchemy 2.0 mode
    }
    
    # SQLite: sem pool (não suporta async pool)
    if settings.database_url.startswith("sqlite"):
        engine_kwargs["poolclass"] = NullPool
        logger.info("Using SQLite with NullPool")
    
    # PostgreSQL: com pool de conexões
    else:
        engine_kwargs.update({
            "poolclass": QueuePool,
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_pre_ping": True,  # Valida conexões antes de usar
            "pool_recycle": 3600,  # Recicla conexões a cada 1h
        })
        logger.info(
            f"Using PostgreSQL with QueuePool "
            f"(size={settings.db_pool_size}, max_overflow={settings.db_max_overflow})"
        )
    
    engine = create_async_engine(
        settings.database_url,
        **engine_kwargs
    )
    
    return engine


# Instância global do engine
engine: AsyncEngine = create_engine()


# ========================================
# SESSION FACTORY
# ========================================

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Permite usar objetos após commit
    autocommit=False,
    autoflush=False
)


# ========================================
# DEPENDENCY INJECTION (FastAPI)
# ========================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency para injetar sessão de banco de dados nas rotas do FastAPI.
    
    Uso:
        @app.get("/leads")
        async def list_leads(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ========================================
# CONTEXT MANAGER (uso manual)
# ========================================

@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager para usar fora do FastAPI.
    
    Uso:
        async with get_db_context() as db:
            result = await db.execute(select(Lead))
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ========================================
# INICIALIZAÇÃO DO BANCO
# ========================================

async def init_db() -> None:
    """
    Cria todas as tabelas no banco de dados.
    ⚠️ Atenção: NÃO usar em produção com dados existentes!
    Para produção, use Alembic migrations.
    """
    logger.info("Initializing database...")
    
    try:
        async with engine.begin() as conn:
            # DROP ALL (apenas dev!)
            if settings.is_development:
                logger.warning("DROPPING all tables (development mode)")
                await conn.run_sync(Base.metadata.drop_all)
            
            # CREATE ALL
            await conn.run_sync(Base.metadata.create_all)
            logger.success("Database tables created successfully")
    
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def check_db_connection() -> bool:
    """
    Verifica se a conexão com o banco está funcionando.
    Útil para health checks.
    """
    try:
        async with engine.connect() as conn:
            # Importa text do sqlalchemy
            from sqlalchemy import text
            # Usa text() para envolver a string SQL
            await conn.execute(text("SELECT 1"))
        logger.debug("Database connection OK")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


async def close_db() -> None:
    """
    Fecha todas as conexões do pool.
    Deve ser chamado ao desligar a aplicação.
    """
    logger.info("Closing database connections...")
    await engine.dispose()
    logger.success("Database connections closed")


# ========================================
# HELPERS
# ========================================

async def execute_raw_sql(sql: str) -> None:
    """
    Executa SQL raw (use com cuidado!).
    Útil para seeds, migrations manuais, etc.
    """
    async with engine.begin() as conn:
        from sqlalchemy import text
        await conn.execute(text(sql))
        logger.info(f"Executed raw SQL: {sql[:100]}...")


# ========================================
# STARTUP/SHUTDOWN (integração FastAPI)
# ========================================

@asynccontextmanager
async def lifespan_db():
    """
    Context manager para lifecycle do banco no FastAPI.
    
    Uso no main.py:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with lifespan_db():
                yield
    """
    # Startup
    logger.info("Starting database...")
    
    # Verifica conexão
    if not await check_db_connection():
        logger.error("Failed to connect to database on startup")
        raise RuntimeError("Database connection failed")
    
    # Em desenvolvimento, recria tabelas
    if settings.is_development and settings.debug:
        await init_db()
    
    yield
    
    # Shutdown
    logger.info("Shutting down database...")
    await close_db()
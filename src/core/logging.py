"""
Sistema de logging centralizado usando Loguru.
Configuração de logs estruturados, rotação e integração com Sentry.
"""

import sys
import logging
from pathlib import Path
from typing import Optional
from loguru import logger

from src.core.config import get_settings

settings = get_settings()


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_json: bool = False
) -> None:
    """
    Configura o sistema de logging da aplicação.
    
    Args:
        log_level: Nível de log (DEBUG, INFO, WARNING, ERROR)
        log_file: Caminho para arquivo de log (opcional)
        enable_json: Se True, usa formato JSON estruturado
    """
    
    # Remove handler padrão do loguru
    logger.remove()
    
    # Define nível de log
    level = log_level or settings.log_level
    
    # ========================================
    # CONSOLE (stdout)
    # ========================================
    if enable_json or settings.is_production:
        # Formato JSON para produção (facilita parsing)
        log_format = (
            "{{"
            '"time": "{time:YYYY-MM-DD HH:mm:ss.SSS}", '
            '"level": "{level}", '
            '"module": "{name}", '
            '"function": "{function}", '
            '"line": {line}, '
            '"message": "{message}"'
            "}}"
        )
    else:
        # Formato legível para desenvolvimento
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )
    
    logger.add(
        sys.stdout,
        format=log_format,
        level=level,
        colorize=not enable_json,
        backtrace=True,
        diagnose=settings.is_development
    )
    
    # ========================================
    # ARQUIVO (se especificado)
    # ========================================
    if log_file or settings.is_production:
        log_path = log_file or "logs/app.log"
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        
        logger.add(
            log_path,
            format=log_format,
            level=level,
            rotation="100 MB",
            retention="30 days",
            compression="zip",
            enqueue=True,
            backtrace=True,
            diagnose=False
        )
    
    # ========================================
    # INTEGRAÇÃO COM LOGGING PADRÃO
    # ========================================
    class InterceptHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno
            
            frame, depth = logging.currentframe(), 2
            while frame and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1
            
            logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )
    
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    for logger_name in ["uvicorn", "uvicorn.access", "sqlalchemy", "httpx"]:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.propagate = False
    
    # ========================================
    # SENTRY (se configurado)
    # ========================================
    if settings.sentry_dsn and settings.is_production:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.logging import LoggingIntegration
            
            sentry_logging = LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR
            )
            
            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                environment=settings.environment,
                release=settings.app_version,
                traces_sample_rate=settings.sentry_traces_sample_rate,
                integrations=[sentry_logging],
                send_default_pii=False
            )
            
            logger.info("Sentry error tracking enabled")
        except ImportError:
            logger.warning("Sentry SDK not installed, skipping error tracking")
    
    logger.info(
        f"Logging configured: level={level}, environment={settings.environment}"
    )


def log_request(method: str, path: str, status_code: int, duration_ms: float) -> None:
    """Loga requisição HTTP de forma estruturada."""
    log_data = {
        "method": method,
        "path": path,
        "status": status_code,
        "duration_ms": round(duration_ms, 2)
    }
    
    if status_code < 400:
        logger.bind(**log_data).info(f"{method} {path} - {status_code}")
    elif status_code < 500:
        logger.bind(**log_data).warning(f"{method} {path} - {status_code}")
    else:
        logger.bind(**log_data).error(f"{method} {path} - {status_code}")


def log_ai_call(
    model: str,
    tokens_used: int,
    duration_ms: float,
    success: bool,
    error: Optional[str] = None
) -> None:
    """Loga chamada para IA de forma estruturada."""
    log_data = {
        "model": model,
        "tokens": tokens_used,
        "duration_ms": round(duration_ms, 2),
        "success": success
    }
    
    if success:
        logger.bind(**log_data).info(
            f"AI call successful: {model} ({tokens_used} tokens, {duration_ms:.0f}ms)"
        )
    else:
        log_data["error"] = error
        logger.bind(**log_data).error(f"AI call failed: {model} - {error}")


def log_whatsapp_event(
    event_type: str,
    phone_number: str,
    success: bool,
    details: Optional[dict] = None
) -> None:
    """Loga eventos do WhatsApp (mensagem recebida, enviada, etc)."""
    masked_phone = f"***{phone_number[-4:]}" if len(phone_number) > 4 else "***"
    
    log_data = {
        "event": event_type,
        "phone": masked_phone,
        "success": success
    }
    
    if details:
        log_data.update(details)
    
    level = "info" if success else "error"
    logger.bind(**log_data).log(
        level.upper(),
        f"WhatsApp {event_type}: {masked_phone}"
    )


# Configuração automática ao importar
if settings.is_development:
    setup_logging(enable_json=False)
else:
    setup_logging(enable_json=True, log_file="logs/app.log")
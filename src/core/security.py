"""
Módulo de segurança e validação.
Inclui validação de assinaturas de webhooks, API keys, etc.
"""

import hmac
import hashlib
from fastapi import Request, Header, HTTPException
from typing import Optional

from src.core.config import get_settings
from src.core.exceptions import InvalidWebhookSignatureError, InvalidAPIKeyError

settings = get_settings()


# ========================================
# VALIDAÇÃO DE WEBHOOK DO WHATSAPP
# ========================================

async def verify_whatsapp_signature(
    request: Request,
    app_secret: str
) -> bool:
    """
    Valida a assinatura HMAC-SHA256 do webhook do WhatsApp.
    
    O WhatsApp envia um header X-Hub-Signature-256 com o HMAC do corpo da requisição.
    Precisamos recalcular e comparar para garantir autenticidade.
    
    Args:
        request: Request do FastAPI
        app_secret: App Secret do WhatsApp
        
    Returns:
        True se válido
        
    Raises:
        InvalidWebhookSignatureError: Se assinatura inválida
    """
    
    # Pega assinatura do header
    signature_header = request.headers.get("X-Hub-Signature-256")
    
    if not signature_header:
        raise InvalidWebhookSignatureError()
    
    # Remove o prefixo "sha256="
    try:
        provided_signature = signature_header.split("sha256=")[1]
    except IndexError:
        raise InvalidWebhookSignatureError()
    
    # Pega o corpo bruto da requisição (já foi lido antes, usa request.state)
    # Precisamos do corpo bruto para calcular o HMAC corretamente
    body = await request.body()
    
    # Calcula HMAC-SHA256
    expected_signature = hmac.new(
        key=app_secret.encode('utf-8'),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    # Comparação timing-safe (previne timing attacks)
    if not hmac.compare_digest(provided_signature, expected_signature):
        raise InvalidWebhookSignatureError()
    
    return True


# ========================================
# VALIDAÇÃO DE API KEY (para endpoints admin)
# ========================================

async def verify_api_key(
    x_api_key: Optional[str] = Header(None)
) -> str:
    """
    Valida API Key para endpoints administrativos.
    
    Usage:
        @app.get("/admin/stats")
        async def get_stats(api_key: str = Depends(verify_api_key)):
            ...
    """
    
    if not x_api_key:
        raise InvalidAPIKeyError()
    
    if x_api_key != settings.admin_api_key:
        raise InvalidAPIKeyError()
    
    return x_api_key


# ========================================
# SANITIZAÇÃO DE INPUTS
# ========================================

def sanitize_phone_number(phone: str) -> str:
    """
    Sanitiza número de telefone removendo caracteres não-numéricos.
    
    Args:
        phone: Número bruto (pode conter +, -, espaços, etc)
        
    Returns:
        Número apenas com dígitos
    """
    return "".join(filter(str.isdigit, phone))


def mask_phone_number(phone: str, show_last_digits: int = 4) -> str:
    """
    Mascara número de telefone para logs (LGPD compliance).
    
    Args:
        phone: Número completo
        show_last_digits: Quantos dígitos finais mostrar
        
    Returns:
        Número mascarado (ex: "***1234")
    """
    if len(phone) <= show_last_digits:
        return "*" * len(phone)
    
    return "*" * (len(phone) - show_last_digits) + phone[-show_last_digits:]


def sanitize_user_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitiza input do usuário para prevenir injection attacks.
    
    Args:
        text: Texto do usuário
        max_length: Comprimento máximo permitido
        
    Returns:
        Texto sanitizado
    """
    # Remove caracteres nulos
    text = text.replace("\x00", "")
    
    # Limita comprimento
    text = text[:max_length]
    
    # Remove espaços extras
    text = " ".join(text.split())
    
    return text.strip()


# ========================================
# RATE LIMITING (helper)
# ========================================

class RateLimiter:
    """
    Rate limiter simples baseado em memória.
    Para produção com múltiplos workers, usar Redis.
    """
    
    def __init__(self):
        self.requests: dict[str, list[float]] = {}
    
    def is_allowed(
        self,
        identifier: str,
        max_requests: int,
        window_seconds: int
    ) -> bool:
        """
        Verifica se o identificador pode fazer mais uma requisição.
        
        Args:
            identifier: ID único (IP, phone, user_id, etc)
            max_requests: Máximo de requisições permitidas
            window_seconds: Janela de tempo em segundos
            
        Returns:
            True se permitido, False se excedeu limite
        """
        import time
        
        current_time = time.time()
        
        # Limpa requisições antigas
        if identifier in self.requests:
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier]
                if current_time - req_time < window_seconds
            ]
        else:
            self.requests[identifier] = []
        
        # Verifica limite
        if len(self.requests[identifier]) >= max_requests:
            return False
        
        # Adiciona requisição atual
        self.requests[identifier].append(current_time)
        return True


# Instância global (para simplicidade)
# Em produção, usar Redis ou similar
rate_limiter = RateLimiter()
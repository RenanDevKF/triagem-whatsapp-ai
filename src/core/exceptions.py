"""
Exceções customizadas do sistema.
Facilita tratamento de erros e respostas HTTP adequadas.
"""

from typing import Optional, Any


class BaseAppException(Exception):
    """Exceção base da aplicação"""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


# ========================================
# EXCEÇÕES DE VALIDAÇÃO
# ========================================

class ValidationError(BaseAppException):
    """Erro de validação de dados"""
    
    def __init__(self, message: str, field: Optional[str] = None, **kwargs: Any):
        details = {"field": field} if field else {}
        details.update(kwargs)
        super().__init__(message, status_code=422, details=details)


class InvalidPhoneNumberError(ValidationError):
    """Número de telefone inválido"""
    
    def __init__(self, phone: str):
        super().__init__(
            message=f"Número de telefone inválido: {phone}",
            field="phone_number"
        )


class UnsupportedCityError(ValidationError):
    """Cidade não atendida"""
    
    def __init__(self, city: str):
        super().__init__(
            message=f"Cidade não atendida: {city}",
            field="city"
        )


# ========================================
# EXCEÇÕES DE WHATSAPP
# ========================================

class WhatsAppError(BaseAppException):
    """Erro relacionado ao WhatsApp"""
    
    def __init__(self, message: str, **kwargs: Any):
        super().__init__(message, status_code=502, details=kwargs)


class InvalidWebhookSignatureError(WhatsAppError):
    """Assinatura de webhook inválida"""
    
    def __init__(self):
        super().__init__(
            message="Invalid webhook signature",
            status_code=401
        )


class MessageSendError(WhatsAppError):
    """Erro ao enviar mensagem"""
    
    def __init__(self, phone: str, reason: str):
        super().__init__(
            message=f"Failed to send message to {phone}: {reason}",
            phone=phone,
            reason=reason
        )


class WebhookValidationError(WhatsAppError):
    """Erro na validação do webhook"""
    
    def __init__(self, reason: str):
        super().__init__(
            message=f"Webhook validation failed: {reason}",
            status_code=400,
            reason=reason
        )


# ========================================
# EXCEÇÕES DE IA
# ========================================

class AIError(BaseAppException):
    """Erro relacionado ao processamento de IA"""
    
    def __init__(self, message: str, model: Optional[str] = None, **kwargs: Any):
        details = {"model": model} if model else {}
        details.update(kwargs)
        super().__init__(message, status_code=503, details=details)


class AITimeoutError(AIError):
    """Timeout na chamada da IA"""
    
    def __init__(self, model: str, timeout: int):
        super().__init__(
            message=f"AI request timeout after {timeout}s",
            model=model,
            timeout=timeout
        )


class AIResponseParseError(AIError):
    """Erro ao fazer parse da resposta da IA"""
    
    def __init__(self, model: str, raw_response: str):
        super().__init__(
            message="Failed to parse AI response as JSON",
            model=model,
            raw_response=raw_response[:200]  # Limita tamanho
        )


class AIQuotaExceededError(AIError):
    """Cota de API da IA excedida"""
    
    def __init__(self, model: str):
        super().__init__(
            message=f"API quota exceeded for {model}",
            model=model,
            status_code=429
        )


# ========================================
# EXCEÇÕES DE BANCO DE DADOS
# ========================================

class DatabaseError(BaseAppException):
    """Erro relacionado ao banco de dados"""
    
    def __init__(self, message: str, **kwargs: Any):
        super().__init__(message, status_code=500, details=kwargs)


class LeadNotFoundError(DatabaseError):
    """Lead não encontrado"""
    
    def __init__(self, identifier: str):
        super().__init__(
            message=f"Lead not found: {identifier}",
            status_code=404,
            identifier=identifier
        )


class ConversationNotFoundError(DatabaseError):
    """Conversa não encontrada"""
    
    def __init__(self, conversation_id: str):
        super().__init__(
            message=f"Conversation not found: {conversation_id}",
            status_code=404,
            conversation_id=conversation_id
        )


class DuplicateLeadError(DatabaseError):
    """Lead duplicado (phone já existe)"""
    
    def __init__(self, phone: str):
        super().__init__(
            message=f"Lead already exists with phone: {phone}",
            status_code=409,
            phone=phone
        )


# ========================================
# EXCEÇÕES DE AUTENTICAÇÃO
# ========================================

class AuthenticationError(BaseAppException):
    """Erro de autenticação"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class InvalidAPIKeyError(AuthenticationError):
    """API Key inválida"""
    
    def __init__(self):
        super().__init__(message="Invalid or missing API key")


# ========================================
# EXCEÇÕES DE NEGÓCIO
# ========================================

class BusinessRuleError(BaseAppException):
    """Erro de regra de negócio"""
    
    def __init__(self, message: str, **kwargs: Any):
        super().__init__(message, status_code=400, details=kwargs)


class SessionExpiredError(BusinessRuleError):
    """Sessão de conversa expirada"""
    
    def __init__(self, phone: str):
        super().__init__(
            message=f"Conversation session expired for {phone}",
            phone=phone
        )


class MaxMessagesExceededError(BusinessRuleError):
    """Limite de mensagens atingido"""
    
    def __init__(self, phone: str, limit: int):
        super().__init__(
            message=f"Max messages ({limit}) exceeded for {phone}",
            phone=phone,
            limit=limit
        )


# ========================================
# EXCEÇÕES DE RATE LIMITING
# ========================================

class RateLimitExceededError(BaseAppException):
    """Rate limit excedido"""
    
    def __init__(self, identifier: str, limit: int, window: str):
        super().__init__(
            message=f"Rate limit exceeded: {limit} requests per {window}",
            status_code=429,
            details={
                "identifier": identifier,
                "limit": limit,
                "window": window
            }
        )
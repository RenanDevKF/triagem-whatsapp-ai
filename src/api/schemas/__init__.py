"""
Schemas da API - Importações centralizadas.
Facilita importar schemas de qualquer lugar do código.

Uso:
    from src.api.schemas import LeadResponse, MessageResponse
"""

# Webhook
from src.api.schemas.webhook import (
    WhatsAppWebhookPayload,
    WhatsAppMessage,
    WebhookVerification
)

# Lead
from src.api.schemas.lead import (
    LeadCreate,
    LeadUpdate,
    LeadResponse,
    LeadListResponse,
    LeadStats,
    LeadStatusEnum,
    LeadClassificationEnum
)

# Message
from src.api.schemas.message import (
    MessageCreate,
    MessageResponse,
    MessageDirectionEnum,
    MessageTypeEnum
)

# Conversation
from src.api.schemas.conversation import (
    ConversationResponse,
    ConversationStats
)

# AI
from src.api.schemas.ai import (
    AIResponse,
    AIExtractedData
)

# Responses genéricas
from src.api.schemas.responses import (
    SuccessResponse,
    ErrorResponse,
    HealthCheckResponse,
    DailyStats
)

__all__ = [
    # Webhook
    "WhatsAppWebhookPayload",
    "WhatsAppMessage",
    "WebhookVerification",
    # Lead
    "LeadCreate",
    "LeadUpdate",
    "LeadResponse",
    "LeadListResponse",
    "LeadStats",
    "LeadStatusEnum",
    "LeadClassificationEnum",
    # Message
    "MessageCreate",
    "MessageResponse",
    "MessageDirectionEnum",
    "MessageTypeEnum",
    # Conversation
    "ConversationResponse",
    "ConversationStats",
    # AI
    "AIResponse",
    "AIExtractedData",
    # Generic
    "SuccessResponse",
    "ErrorResponse",
    "HealthCheckResponse",
    "DailyStats",
]
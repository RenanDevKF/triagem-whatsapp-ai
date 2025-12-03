"""
Schemas para Message (mensagens da conversa).
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


# ========================================
# ENUMS
# ========================================

class MessageDirectionEnum(str, Enum):
    INBOUND = "entrada"
    OUTBOUND = "saida"


class MessageTypeEnum(str, Enum):
    TEXT = "texto"
    IMAGE = "imagem"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "documento"
    BUTTON_REPLY = "resposta_botao"


# ========================================
# SCHEMAS
# ========================================

class MessageBase(BaseModel):
    """Base para mensagem"""
    content: str = Field(..., min_length=1)
    message_type: MessageTypeEnum = MessageTypeEnum.TEXT
    media_url: Optional[str] = None


class MessageCreate(MessageBase):
    """Schema para criação de mensagem"""
    conversation_id: str
    direction: MessageDirectionEnum


class MessageResponse(MessageBase):
    """Schema de resposta de mensagem"""
    id: str
    conversation_id: str
    direction: MessageDirectionEnum
    whatsapp_message_id: Optional[str] = None
    ai_model: Optional[str] = None
    ai_tokens_used: Optional[int] = None
    ai_processing_time_ms: Optional[int] = None
    extracted_data: Optional[Dict[str, Any]] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
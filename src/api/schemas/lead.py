"""
Schemas para webhooks do WhatsApp.
Validação de payloads recebidos da Meta API.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

# ========================================
# ENUMS (espelhando os do banco)
# ========================================

class LeadStatusEnum(str, Enum):
    NEW = "novo"
    IN_CONVERSATION = "em_conversa"
    QUALIFIED = "qualificado"
    DISQUALIFIED = "desqualificado"
    TRANSFERRED = "transferido"
    ARCHIVED = "arquivado"


class LeadClassificationEnum(str, Enum):
    HOT = "quente"
    WARM = "morno"
    COLD = "frio"
    UNQUALIFIED = "nao_qualificado"


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
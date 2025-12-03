"""
Schemas para webhooks do WhatsApp.
Estruturas de dados enviadas pelo WhatsApp Cloud API.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class WhatsAppProfile(BaseModel):
    """Perfil do usuário no WhatsApp"""
    name: str


class WhatsAppContact(BaseModel):
    """Contato do WhatsApp"""
    profile: WhatsAppProfile
    wa_id: str  # WhatsApp ID (número)


class WhatsAppTextMessage(BaseModel):
    """Mensagem de texto"""
    body: str


class WhatsAppButtonReply(BaseModel):
    """Resposta de botão"""
    id: str
    title: str


class WhatsAppInteractive(BaseModel):
    """Mensagem interativa (botões/lista)"""
    type: str
    button_reply: Optional[WhatsAppButtonReply] = None


class WhatsAppMessage(BaseModel):
    """Estrutura de mensagem do webhook"""
    from_: str = Field(..., alias="from")
    id: str
    timestamp: str
    type: str
    text: Optional[WhatsAppTextMessage] = None
    interactive: Optional[WhatsAppInteractive] = None
    
    model_config = ConfigDict(populate_by_name=True)


class WhatsAppChange(BaseModel):
    """Mudança no webhook"""
    value: Dict[str, Any]
    field: str


class WhatsAppEntry(BaseModel):
    """Entry do webhook"""
    id: str
    changes: List[WhatsAppChange]


class WhatsAppWebhookPayload(BaseModel):
    """Payload completo do webhook do WhatsApp"""
    object: str
    entry: List[WhatsAppEntry]


class WebhookVerification(BaseModel):
    """Schema para verificação do webhook (GET)"""
    mode: str = Field(..., alias="hub.mode")
    token: str = Field(..., alias="hub.verify_token")
    challenge: str = Field(..., alias="hub.challenge")
    
    model_config = ConfigDict(populate_by_name=True)
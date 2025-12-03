"""
Schemas para Conversation (conversas).
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

from src.api.schemas.message import MessageResponse


class ConversationResponse(BaseModel):
    """Schema de resposta de conversa"""
    id: str
    lead_id: str
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    total_messages: int
    ai_messages: int
    user_messages: int
    data_collected_complete: bool
    transferred_to_human: bool
    
    # Incluir mensagens opcionalmente
    messages: Optional[List[MessageResponse]] = None
    
    model_config = ConfigDict(from_attributes=True)


class ConversationStats(BaseModel):
    """Estatísticas de conversas"""
    total: int
    active: int
    completed: int
    transferred: int
    avg_messages: float
    avg_duration_minutes: float
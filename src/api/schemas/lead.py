"""
Schemas para Lead (CRUD e listagem).
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum


# ========================================
# ENUMS
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


# ========================================
# BASE SCHEMAS
# ========================================

class LeadBase(BaseModel):
    """Campos comuns de Lead"""
    phone_number: str = Field(..., min_length=10, max_length=20)
    name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=2)
    prosthesis_type: Optional[str] = None
    urgency_level: Optional[str] = None
    budget_range: Optional[str] = None
    has_insurance: Optional[bool] = None
    source: Optional[str] = None
    campaign_id: Optional[str] = None
    
    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Remove caracteres não numéricos do telefone"""
        cleaned = "".join(filter(str.isdigit, v))
        if len(cleaned) < 10:
            raise ValueError("Phone number too short")
        return cleaned
    
    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Validação básica de email"""
        if v and "@" not in v:
            raise ValueError("Invalid email format")
        return v


class LeadCreate(LeadBase):
    """Schema para criação de lead"""
    pass


class LeadUpdate(BaseModel):
    """Schema para atualização de lead (todos campos opcionais)"""
    name: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    prosthesis_type: Optional[str] = None
    urgency_level: Optional[str] = None
    budget_range: Optional[str] = None
    has_insurance: Optional[bool] = None
    classification: Optional[LeadClassificationEnum] = None
    status: Optional[LeadStatusEnum] = None
    routed_to: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


class LeadResponse(LeadBase):
    """Schema de resposta de lead"""
    id: str
    classification: Optional[LeadClassificationEnum] = None
    score: int
    status: LeadStatusEnum
    routed_to: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    first_contact_at: Optional[datetime] = None
    qualified_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class LeadListResponse(BaseModel):
    """Lista paginada de leads"""
    leads: List[LeadResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ========================================
# ESTATÍSTICAS
# ========================================

class LeadStats(BaseModel):
    """Estatísticas de leads"""
    total: int
    new: int
    in_conversation: int
    qualified: int
    disqualified: int
    hot: int
    warm: int
    cold: int
    avg_score: float
    conversion_rate: float
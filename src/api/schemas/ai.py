"""
Schemas para respostas da IA.
Estrutura de dados extraídos e resposta do modelo.
"""

from typing import Optional
from pydantic import BaseModel, Field


class AIExtractedData(BaseModel):
    """Dados extraídos pela IA da mensagem do usuário"""
    nome: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    tipo_protese: Optional[str] = None
    urgencia: Optional[str] = Field(None, pattern="^(baixa|media|alta|emergencia)$")
    possui_convenio: Optional[bool] = None
    orcamento_mencionado: Optional[bool] = None


class AIResponse(BaseModel):
    """Resposta estruturada da IA"""
    response_text: str = Field(..., min_length=1)
    extracted_data: AIExtractedData
    intent: str = Field(
        ...,
        pattern="^(informacao|orcamento|agendamento|urgencia|desistencia)$"
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    should_transfer_to_human: bool = False
    transfer_reason: Optional[str] = None
    next_question: Optional[str] = None
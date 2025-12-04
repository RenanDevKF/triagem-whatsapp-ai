"""
Schemas genéricos de resposta da API.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel


class SuccessResponse(BaseModel):
    """Resposta de sucesso genérica"""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Resposta de erro genérica"""
    success: bool = False
    error: str
    details: Optional[Dict[str, Any]] = None


class HealthCheckResponse(BaseModel):
    """Resposta do health check"""
    status: str = "healthy"
    version: str
    database: bool
    ai_service: bool
    whatsapp: bool
    timestamp: datetime


class DailyStats(BaseModel):
    """Estatísticas diárias"""
    date: datetime
    new_leads: int
    qualified_leads: int
    total_messages: int
    avg_response_time_seconds: float
"""
Rotas de gerenciamento de leads.
CRUD e listagem com filtros.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from loguru import logger

from src.api.schemas.lead import (
    LeadResponse, LeadListResponse, LeadUpdate, LeadStats
)
from src.infrastructure.database.models import Lead, LeadStatus, LeadClassification
from src.infrastructure.database.session import get_db
from src.core.security import verify_api_key

router = APIRouter()


@router.get("", response_model=LeadListResponse)
async def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    classification: Optional[str] = None,
    city: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Lista leads com paginação e filtros.
    
    Filtros disponíveis:
    - status: novo, em_conversa, qualificado, desqualificado
    - classification: quente, morno, frio, nao_qualificado
    - city: nome da cidade
    """
    
    # Base query
    query = select(Lead)
    
    # Aplicar filtros
    if status:
        query = query.where(Lead.status == status)
    
    if classification:
        query = query.where(Lead.classification == classification)
    
    if city:
        query = query.where(Lead.city.ilike(f"%{city}%"))
    
    # Total de registros (para paginação)
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Ordenar por criação (mais recentes primeiro)
    query = query.order_by(desc(Lead.created_at))
    
    # Paginação
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    # Executar
    result = await db.execute(query)
    leads = result.scalars().all()
    
    # Calcular total de páginas
    total_pages = (total + page_size - 1) // page_size
    
    return LeadListResponse(
        leads=[LeadResponse.model_validate(lead) for lead in leads],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/stats", response_model=LeadStats)
async def get_lead_stats(
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Retorna estatísticas agregadas de leads.
    """
    
    # Total de leads
    total_result = await db.execute(select(func.count(Lead.id)))
    total = total_result.scalar()
    
    # Por status
    status_counts = {}
    for status in LeadStatus:
        result = await db.execute(
            select(func.count(Lead.id)).where(Lead.status == status)
        )
        status_counts[status.value] = result.scalar()
    
    # Por classificação
    classification_counts = {}
    for classification in LeadClassification:
        result = await db.execute(
            select(func.count(Lead.id)).where(Lead.classification == classification)
        )
        classification_counts[classification.value] = result.scalar()
    
    # Score médio
    avg_score_result = await db.execute(select(func.avg(Lead.score)))
    avg_score = avg_score_result.scalar() or 0
    
    # Taxa de conversão (qualificados / total)
    qualified = status_counts.get("qualificado", 0)
    conversion_rate = (qualified / total * 100) if total > 0 else 0
    
    return LeadStats(
        total=total,
        new=status_counts.get("novo", 0),
        in_conversation=status_counts.get("em_conversa", 0),
        qualified=qualified,
        disqualified=status_counts.get("desqualificado", 0),
        hot=classification_counts.get("quente", 0),
        warm=classification_counts.get("morno", 0),
        cold=classification_counts.get("frio", 0),
        avg_score=round(avg_score, 2),
        conversion_rate=round(conversion_rate, 2)
    )


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Busca lead por ID.
    """
    
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id)
    )
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return LeadResponse.model_validate(lead)


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: str,
    update_data: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Atualiza informações de um lead.
    """
    
    # Busca lead
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id)
    )
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Atualiza campos fornecidos
    update_dict = update_data.model_dump(exclude_unset=True)
    
    for field, value in update_dict.items():
        setattr(lead, field, value)
    
    await db.commit()
    await db.refresh(lead)
    
    logger.info(f"Lead {lead_id} updated: {update_dict}")
    
    return LeadResponse.model_validate(lead)


@router.delete("/{lead_id}")
async def delete_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Deleta um lead (soft delete - muda status para arquivado).
    """
    
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id)
    )
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Soft delete
    lead.status = LeadStatus.ARCHIVED
    await db.commit()
    
    logger.info(f"Lead {lead_id} archived")
    
    return {"success": True, "message": "Lead archived successfully"}
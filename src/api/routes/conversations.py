"""
Rotas para visualização de conversas e mensagens.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.schemas.conversation import ConversationResponse
from src.api.schemas.message import MessageResponse
from src.infrastructure.database.models import Conversation, Message, Lead
from src.infrastructure.database.session import get_db
from src.core.security import verify_api_key

router = APIRouter()


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    include_messages: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Busca conversa por ID, opcionalmente com todas as mensagens.
    """
    
    query = select(Conversation).where(Conversation.id == conversation_id)
    
    if include_messages:
        query = query.options(selectinload(Conversation.messages))
    
    result = await db.execute(query)
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return ConversationResponse.model_validate(conversation)


@router.get("/lead/{lead_id}", response_model=List[ConversationResponse])
async def get_lead_conversations(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Lista todas as conversas de um lead específico.
    """
    
    result = await db.execute(
        select(Conversation)
        .where(Conversation.lead_id == lead_id)
        .order_by(Conversation.started_at.desc())
    )
    conversations = result.scalars().all()
    
    return [ConversationResponse.model_validate(conv) for conv in conversations]


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Lista mensagens de uma conversa específica.
    """
    
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    messages = result.scalars().all()
    
    return [MessageResponse.model_validate(msg) for msg in messages]
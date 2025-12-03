"""
Rotas para webhooks do WhatsApp.
Recebe notificações de mensagens recebidas, enviadas, entregues, etc.
"""

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, BackgroundTasks
from fastapi.responses import PlainTextResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.webhook import WhatsAppWebhookPayload, WebhookVerification
from src.core.config import get_settings
from src.core.security import verify_whatsapp_signature
from src.core.exceptions import InvalidWebhookSignatureError, WebhookValidationError
from src.infrastructure.database.session import get_db
from src.domain.services.message_processor import MessageProcessor

settings = get_settings()
router = APIRouter()


# ========================================
# WEBHOOK VERIFICATION (GET)
# ========================================

@router.get("/whatsapp")
async def verify_webhook(
    mode: str = Query(..., alias="hub.mode"),
    token: str = Query(..., alias="hub.verify_token"),
    challenge: str = Query(..., alias="hub.challenge")
) -> PlainTextResponse:
    """
    Endpoint de verificação do webhook do WhatsApp.
    O Meta/Facebook chama este endpoint com um challenge que deve ser retornado.
    
    Documentação: https://developers.facebook.com/docs/graph-api/webhooks/getting-started
    """
    
    logger.info(f"Webhook verification request: mode={mode}, token={token[:10]}...")
    
    # Valida mode
    if mode != "subscribe":
        logger.error(f"Invalid mode: {mode}")
        raise WebhookValidationError(f"Invalid mode: {mode}")
    
    # Valida token
    if token != settings.whatsapp_verify_token:
        logger.error("Invalid verify token")
        raise InvalidWebhookSignatureError()
    
    # Retorna challenge
    logger.success("Webhook verified successfully")
    return PlainTextResponse(content=challenge, status_code=200)


# ========================================
# WEBHOOK RECEIVER (POST)
# ========================================

@router.post("/whatsapp")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> Response:
    """
    Recebe notificações de eventos do WhatsApp.
    
    Eventos possíveis:
    - messages: mensagem recebida
    - message_status: status de mensagem enviada (sent, delivered, read, failed)
    
    IMPORTANTE: Este endpoint DEVE retornar 200 OK em < 5 segundos,
    caso contrário o WhatsApp considera como falha e para de enviar webhooks.
    """
    
    # ========== 1. VALIDAÇÃO DE ASSINATURA ==========
    try:
        await verify_whatsapp_signature(request, settings.whatsapp_app_secret)
    except InvalidWebhookSignatureError:
        logger.error("Invalid webhook signature - possible security issue!")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # ========== 2. PARSE PAYLOAD ==========
    try:
        body = await request.json()
        payload = WhatsAppWebhookPayload(**body)
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        # Retorna 200 mesmo assim para não perder o webhook
        return Response(status_code=200)
    
    # ========== 3. PROCESSA CADA ENTRY ==========
    for entry in payload.entry:
        for change in entry.changes:
            
            # Apenas processa mudanças no campo 'messages'
            if change.field != "messages":
                logger.debug(f"Ignoring change field: {change.field}")
                continue
            
            value = change.value
            
            # ========== 3.1 MENSAGENS RECEBIDAS ==========
            if "messages" in value:
                for message_data in value["messages"]:
                    
                    # Extrai dados essenciais
                    phone_number = message_data.get("from")
                    message_id = message_data.get("id")
                    message_type = message_data.get("type")
                    timestamp = message_data.get("timestamp")
                    
                    # Extrai conteúdo baseado no tipo
                    content = None
                    if message_type == "text":
                        content = message_data.get("text", {}).get("body")
                    elif message_type == "button":
                        content = message_data.get("button", {}).get("text")
                    elif message_type == "interactive":
                        interactive = message_data.get("interactive", {})
                        if "button_reply" in interactive:
                            content = interactive["button_reply"].get("title")
                        elif "list_reply" in interactive:
                            content = interactive["list_reply"].get("title")
                    
                    if not content:
                        logger.warning(f"Message without content: {message_type}")
                        continue
                    
                    logger.info(
                        f"📨 Received message from {phone_number}: "
                        f"{content[:50]}{'...' if len(content) > 50 else ''}"
                    )
                    
                    # ========== PROCESSA EM BACKGROUND ==========
                    # Não bloqueia o webhook (deve retornar 200 rápido!)
                    background_tasks.add_task(
                        process_incoming_message,
                        db=db,
                        phone_number=phone_number,
                        message_id=message_id,
                        content=content,
                        message_type=message_type,
                        timestamp=timestamp
                    )
            
            # ========== 3.2 STATUS DE MENSAGENS ENVIADAS ==========
            if "statuses" in value:
                for status_data in value["statuses"]:
                    message_id = status_data.get("id")
                    status = status_data.get("status")
                    timestamp = status_data.get("timestamp")
                    
                    logger.debug(f"Message {message_id} status: {status}")
                    
                    # Atualiza status no banco em background
                    background_tasks.add_task(
                        update_message_status,
                        db=db,
                        message_id=message_id,
                        status=status,
                        timestamp=timestamp
                    )
    
    # ========== 4. RETORNA 200 OK IMEDIATAMENTE ==========
    # CRÍTICO: WhatsApp espera resposta rápida
    return Response(status_code=200)


# ========================================
# BACKGROUND TASKS
# ========================================

async def process_incoming_message(
    db: AsyncSession,
    phone_number: str,
    message_id: str,
    content: str,
    message_type: str,
    timestamp: str
) -> None:
    """
    Processa mensagem recebida em background (após retornar 200 ao WhatsApp).
    
    Fluxo:
    1. Busca ou cria Lead
    2. Busca ou cria Conversation
    3. Salva Message no banco
    4. Envia para IA processar
    5. Gera resposta
    6. Envia resposta
    """
    try:
        processor = MessageProcessor(db)
        
        await processor.process_inbound_message(
            phone_number=phone_number,
            whatsapp_message_id=message_id,
            content=content,
            message_type=message_type,
            timestamp=timestamp
        )
        
        logger.success(f"✅ Message processed successfully: {message_id}")
        
    except Exception as e:
        logger.exception(f"❌ Error processing message {message_id}: {e}")
        # TODO: Implementar retry logic ou dead letter queue


async def update_message_status(
    db: AsyncSession,
    message_id: str,
    status: str,
    timestamp: str
) -> None:
    """
    Atualiza status de mensagem enviada (delivered, read, failed, etc).
    """
    try:
        from src.infrastructure.database.repositories.message_repository import MessageRepository
        from datetime import datetime
        
        repo = MessageRepository(db)
        message = await repo.get_by_whatsapp_id(message_id)
        
        if not message:
            logger.warning(f"Message not found for status update: {message_id}")
            return
        
        # Atualiza timestamps baseado no status
        updates = {}
        ts = datetime.fromtimestamp(int(timestamp))
        
        if status == "sent":
            updates["sent_at"] = ts
        elif status == "delivered":
            updates["delivered_at"] = ts
        elif status == "read":
            updates["read_at"] = ts
        elif status == "failed":
            updates["failed_at"] = ts
        
        if updates:
            await repo.update(message.id, **updates)
            logger.debug(f"Message {message_id} status updated: {status}")
        
    except Exception as e:
        logger.error(f"Error updating message status: {e}")
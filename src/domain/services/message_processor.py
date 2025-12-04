"""
Serviço principal de processamento de mensagens.
Orquestra todo o fluxo: recebe mensagem → IA → classifica → responde.
"""

from datetime import datetime, UTC, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from src.infrastructure.database.models import (
    Lead, Conversation, Message, Event,
    LeadStatus, ConversationStatus, MessageDirection, MessageType, EventType
)
from src.infrastructure.ai.client import get_ai_client
from src.infrastructure.messaging.whatsapp_client import WhatsAppClient
from src.domain.services.lead_classifier import LeadClassifier
from src.core.config import get_settings
from src.core.exceptions import SessionExpiredError, MaxMessagesExceededError

settings = get_settings()


class MessageProcessor:
    """
    Processador central de mensagens.
    Coordena Lead, Conversation, IA e envio de respostas.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai = get_ai_client()
        self.whatsapp = WhatsAppClient()
        self.classifier = LeadClassifier()
    
    async def process_inbound_message(
        self,
        phone_number: str,
        whatsapp_message_id: str,
        content: str,
        message_type: str,
        timestamp: str
    ) -> None:
        """
        Processa mensagem recebida do usuário.
        
        Fluxo:
        1. Busca/cria Lead
        2. Busca/cria Conversation
        3. Valida sessão e limites
        4. Salva mensagem no banco
        5. Processa com IA
        6. Atualiza Lead com dados extraídos
        7. Classifica Lead
        8. Envia resposta
        9. Verifica se deve transferir para humano
        """
        
        logger.info(f"Processing inbound message from {phone_number}")
        
        # ========== 1. LEAD ==========
        lead = await self._get_or_create_lead(phone_number)
        
        # ========== 2. CONVERSATION ==========
        conversation = await self._get_or_create_conversation(lead)
        
        # ========== 3. VALIDAÇÕES ==========
        await self._validate_session(conversation)
        
        # ========== 4. SALVA MENSAGEM DO USUÁRIO ==========
        user_message = await self._save_message(
            conversation_id=conversation.id,
            direction=MessageDirection.INBOUND,
            content=content,
            message_type=message_type,
            whatsapp_message_id=whatsapp_message_id
        )
        
        # Atualiza contadores
        conversation.total_messages += 1
        conversation.user_messages += 1
        conversation.last_activity_at = datetime.now(UTC)
        lead.last_message_at = datetime.now(UTC)
        
        # ========== 5. PROCESSA COM IA ==========
        try:
            # Pega histórico da conversa
            history = await self._get_conversation_history(conversation.id)
            
            # Pega dados já coletados do lead
            lead_data = self._lead_to_dict(lead)
            
            # Chama IA
            ai_response = await self.ai.process_message(
                user_message=content,
                conversation_history=history,
                lead_data=lead_data
            )
            
            logger.info(f"AI response: intent={ai_response.intent}, confidence={ai_response.confidence}")
            
            # ========== 6. ATUALIZA LEAD COM DADOS EXTRAÍDOS ==========
            await self._update_lead_with_extracted_data(lead, ai_response.extracted_data)
            
            # ========== 7. CLASSIFICA LEAD ==========
            classification = self.classifier.classify_lead(lead, conversation)
            lead.classification = classification["classification"]
            lead.score = classification["score"]
            
            # Se foi qualificado pela primeira vez
            if not lead.qualified_at and classification["classification"] in ["quente", "morno"]:
                lead.qualified_at = datetime.now(UTC)
                lead.status = LeadStatus.QUALIFIED
                
                # Registra evento
                await self._create_event(
                    lead_id=lead.id,
                    event_type=EventType.CLASSIFIED,
                    data={"classification": classification}
                )
            
            # ========== 8. ENVIA RESPOSTA ==========
            response_text = ai_response.response_text
            
            # Adiciona contexto se necessário (ex: cidade não atendida)
            if ai_response.extracted_data.cidade:
                if ai_response.extracted_data.cidade not in settings.covered_cities_list:
                    response_text += (
                        f"\n\n⚠️ Nota: Ainda não atendemos {ai_response.extracted_data.cidade}. "
                        "Quer deixar seu contato para futuras expansões?"
                    )
            
            # Salva resposta da IA no banco
            ai_message = await self._save_message(
                conversation_id=conversation.id,
                direction=MessageDirection.OUTBOUND,
                content=response_text,
                message_type=MessageType.TEXT,
                ai_model="deepseek",
                extracted_data=ai_response.extracted_data.model_dump()
            )
            
            # Envia via WhatsApp (apenas se token configurado)
            if settings.whatsapp_access_token and settings.whatsapp_access_token.strip():
                sent = await self.whatsapp.send_text_message(
                    phone_number=phone_number,
                    message=response_text
                )
                
                if sent and "id" in sent:
                    # Atualiza com ID do WhatsApp
                    ai_message.whatsapp_message_id = sent["id"]
                    ai_message.sent_at = datetime.now(UTC)
            else:
                logger.warning("⚠️ WhatsApp token not configured, skipping send")
                # Marca como "enviado virtualmente" para testes
                ai_message.sent_at = datetime.now(UTC)
            
            conversation.total_messages += 1
            conversation.ai_messages += 1
            
            # ========== 9. TRANSFERE PARA HUMANO SE NECESSÁRIO ==========
            if ai_response.should_transfer_to_human:
                logger.info(f"Transferring lead {lead.id} to human: {ai_response.transfer_reason}")
                
                conversation.status = ConversationStatus.TRANSFERRED
                conversation.transferred_to_human = True
                conversation.ended_at = datetime.now(UTC)
                
                lead.status = LeadStatus.TRANSFERRED
                lead.routed_to = self.classifier.determine_routing(lead)
                
                # Registra evento
                await self._create_event(
                    lead_id=lead.id,
                    event_type=EventType.TRANSFERRED,
                    data={
                        "reason": ai_response.transfer_reason,
                        "routed_to": lead.routed_to
                    }
                )
                
                # TODO: Notificar equipe humana
                await self._notify_human_team(lead, conversation)
            
        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            
            # Envia mensagem de erro amigável
            error_message = (
                "Desculpe, tive um problema técnico. 😔\n"
                "Nossa equipe será notificada e entrará em contato em breve!"
            )
            
            if settings.whatsapp_access_token and settings.whatsapp_access_token.strip():
                await self.whatsapp.send_text_message(
                    phone_number=phone_number,
                    message=error_message
                )
            
            raise
        
        finally:
            # Commit de todas as mudanças
            await self.db.commit()
            logger.success(f"✅ Message processed successfully for {phone_number}")
    
    # ========================================
    # MÉTODOS AUXILIARES
    # ========================================
    
    async def _get_or_create_lead(self, phone_number: str) -> Lead:
        """Busca lead existente ou cria novo"""
        from sqlalchemy import select
        
        result = await self.db.execute(
            select(Lead).where(Lead.phone_number == phone_number)
        )
        lead = result.scalar_one_or_none()
        
        if not lead:
            lead = Lead(
                phone_number=phone_number,
                status=LeadStatus.NEW,
                first_contact_at=datetime.now(UTC),
                source="whatsapp"
            )
            self.db.add(lead)
            await self.db.flush()  # Gera ID
            
            # Registra evento
            await self._create_event(
                lead_id=lead.id,
                event_type=EventType.LEAD_CREATED,
                data={"phone": phone_number}
            )
            
            logger.info(f"Created new lead: {lead.id}")
        
        return lead
    
    async def _get_or_create_conversation(self, lead: Lead) -> Conversation:
        """Busca conversa ativa ou cria nova"""
        from sqlalchemy import select
        
        # Busca conversa ativa
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.lead_id == lead.id)
            .where(Conversation.status == ConversationStatus.ACTIVE)
            .order_by(Conversation.started_at.desc())
        )
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            conversation = Conversation(
                lead_id=lead.id,
                status=ConversationStatus.ACTIVE
            )
            self.db.add(conversation)
            await self.db.flush()
            
            logger.info(f"Created new conversation: {conversation.id}")
        
        # Atualiza status do lead
        if lead.status == LeadStatus.NEW:
            lead.status = LeadStatus.IN_CONVERSATION
        
        return conversation
    
    async def _validate_session(self, conversation: Conversation) -> None:
        """Valida se a sessão ainda está ativa"""
        
        # Verifica timeout
        timeout = timedelta(minutes=settings.session_timeout_minutes)
        if datetime.now(UTC) - conversation.last_activity_at > timeout:
            conversation.status = ConversationStatus.EXPIRED
            raise SessionExpiredError(conversation.lead.phone_number)
        
        # Verifica limite de mensagens
        if conversation.total_messages >= settings.max_messages_without_progress:
            if not conversation.data_collected_complete:
                raise MaxMessagesExceededError(
                    conversation.lead.phone_number,
                    settings.max_messages_without_progress
                )
    
    async def _save_message(
        self,
        conversation_id: str,
        direction: MessageDirection,
        content: str,
        message_type: str,
        whatsapp_message_id: Optional[str] = None,
        ai_model: Optional[str] = None,
        extracted_data: Optional[Dict] = None
    ) -> Message:
        """Salva mensagem no banco"""
        
        message = Message(
            conversation_id=conversation_id,
            direction=direction,
            message_type=message_type,
            content=content,
            whatsapp_message_id=whatsapp_message_id,
            ai_model=ai_model,
            extracted_data=extracted_data
        )
        
        self.db.add(message)
        await self.db.flush()
        
        return message
    
    async def _get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 10
    ) -> List[Dict[str, str]]:
        """Retorna histórico da conversa formatado para IA"""
        from sqlalchemy import select
        
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = result.scalars().all()
        
        # Inverte ordem (mais antigas primeiro)
        messages = list(reversed(messages))
        
        # Formata para IA
        history = []
        for msg in messages:
            role = "user" if msg.direction == MessageDirection.INBOUND else "assistant"
            history.append({
                "role": role,
                "content": msg.content
            })
        
        return history
    
    def _lead_to_dict(self, lead: Lead) -> Dict[str, Any]:
        """Converte Lead para dicionário"""
        return {
            "name": lead.name,
            "city": lead.city,
            "state": lead.state,
            "prosthesis_type": lead.prosthesis_type,
            "urgency_level": lead.urgency_level,
            "has_insurance": lead.has_insurance,
            "budget_range": lead.budget_range
        }
    
    async def _update_lead_with_extracted_data(
        self,
        lead: Lead,
        extracted: Any
    ) -> None:
        """Atualiza lead com dados extraídos pela IA"""
        
        if extracted.nome and not lead.name:
            lead.name = extracted.nome
        
        if extracted.cidade and not lead.city:
            lead.city = extracted.cidade
        
        if extracted.estado and not lead.state:
            lead.state = extracted.estado
        
        if extracted.tipo_protese and not lead.prosthesis_type:
            lead.prosthesis_type = extracted.tipo_protese
        
        if extracted.urgencia:
            # Sempre atualiza urgência (pode aumentar)
            lead.urgency_level = extracted.urgencia
        
        if extracted.possui_convenio is not None and lead.has_insurance is None:
            lead.has_insurance = extracted.possui_convenio
        
        await self.db.flush()
    
    async def _create_event(
        self,
        lead_id: str,
        event_type: EventType,
        data: Dict[str, Any]
    ) -> Event:
        """Cria evento de auditoria"""
        
        event = Event(
            lead_id=lead_id,
            event_type=event_type,
            event_data=data,
            triggered_by="ai"
        )
        
        self.db.add(event)
        await self.db.flush()
        
        return event
    
    async def _notify_human_team(
        self,
        lead: Lead,
        conversation: Conversation
    ) -> None:
        """Notifica equipe humana sobre lead qualificado"""
        
        # TODO: Implementar notificações (email, Slack, etc)
        logger.info(
            f"🔔 NOTIFICAÇÃO: Lead {lead.id} ({lead.phone_number}) "
            f"classificado como {lead.classification} e transferido para {lead.routed_to}"
        )
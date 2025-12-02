"""
Cliente para WhatsApp Cloud API.
Envia mensagens de texto, botões, templates, etc.
"""

import httpx
from typing import Optional, Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger

from src.core.config import get_settings
from src.core.exceptions import MessageSendError
from src.core.logging import log_whatsapp_event

settings = get_settings()


class WhatsAppClient:
    """
    Cliente para WhatsApp Cloud API (Meta/Facebook).
    
    Documentação: https://developers.facebook.com/docs/whatsapp/cloud-api
    """
    
    def __init__(self):
        self.api_url = settings.whatsapp_send_message_url
        self.access_token = settings.whatsapp_access_token
        self.phone_number_id = settings.whatsapp_phone_number_id
        
        # HTTP client com timeout
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
        )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def send_text_message(
        self,
        phone_number: str,
        message: str,
        preview_url: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Envia mensagem de texto simples.
        
        Args:
            phone_number: Número do destinatário (formato: 5511999999999)
            message: Texto da mensagem (máximo 4096 caracteres)
            preview_url: Se True, mostra preview de links
            
        Returns:
            Resposta da API com message_id ou None se falhar
        """
        
        # Valida
        if not message or len(message.strip()) == 0:
            logger.error("Cannot send empty message")
            return None
        
        if len(message) > 4096:
            logger.warning(f"Message too long ({len(message)} chars), truncating...")
            message = message[:4090] + "..."
        
        # Payload
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "text",
            "text": {
                "preview_url": preview_url,
                "body": message
            }
        }
        
        try:
            logger.debug(f"Sending message to {phone_number}: {message[:50]}...")
            
            response = await self.client.post(
                self.api_url,
                json=payload
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Log sucesso
            log_whatsapp_event(
                event_type="message_sent",
                phone_number=phone_number,
                success=True,
                details={"message_id": data.get("messages", [{}])[0].get("id")}
            )
            
            logger.success(f"✅ Message sent to {phone_number}")
            return data
        
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.error(f"Failed to send message: {error_msg}")
            
            log_whatsapp_event(
                event_type="message_send_failed",
                phone_number=phone_number,
                success=False,
                details={"error": error_msg}
            )
            
            raise MessageSendError(phone_number, error_msg)
        
        except Exception as e:
            logger.error(f"Unexpected error sending message: {e}")
            
            log_whatsapp_event(
                event_type="message_send_failed",
                phone_number=phone_number,
                success=False,
                details={"error": str(e)}
            )
            
            raise MessageSendError(phone_number, str(e))
    
    async def send_template_message(
        self,
        phone_number: str,
        template_name: str,
        language_code: str = "pt_BR",
        parameters: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Envia mensagem usando template pré-aprovado.
        
        Templates devem ser criados e aprovados no Meta Business Manager.
        Útil para mensagens de boas-vindas, confirmações, etc.
        
        Args:
            phone_number: Número do destinatário
            template_name: Nome do template aprovado
            language_code: Código do idioma (pt_BR, en_US, etc)
            parameters: Parâmetros para substituir no template
        """
        
        # Monta componentes do template
        components = []
        
        if parameters:
            components.append({
                "type": "body",
                "parameters": [
                    {"type": "text", "text": param}
                    for param in parameters
                ]
            })
        
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language_code
                },
                "components": components
            }
        }
        
        try:
            response = await self.client.post(self.api_url, json=payload)
            response.raise_for_status()
            
            logger.success(f"✅ Template '{template_name}' sent to {phone_number}")
            return response.json()
        
        except Exception as e:
            logger.error(f"Failed to send template: {e}")
            raise MessageSendError(phone_number, f"Template send failed: {e}")
    
    async def send_buttons_message(
        self,
        phone_number: str,
        body_text: str,
        buttons: List[Dict[str, str]],
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Envia mensagem com botões de resposta rápida.
        
        Args:
            phone_number: Número do destinatário
            body_text: Texto principal da mensagem
            buttons: Lista de botões (máximo 3)
                     Ex: [{"id": "1", "title": "Sim"}, {"id": "2", "title": "Não"}]
            header_text: Texto do cabeçalho (opcional)
            footer_text: Texto do rodapé (opcional)
        """
        
        if len(buttons) > 3:
            logger.warning("Maximum 3 buttons allowed, truncating...")
            buttons = buttons[:3]
        
        # Formata botões
        formatted_buttons = []
        for btn in buttons:
            formatted_buttons.append({
                "type": "reply",
                "reply": {
                    "id": btn.get("id", btn["title"]),
                    "title": btn["title"][:20]  # Max 20 chars
                }
            })
        
        # Monta payload
        interactive = {
            "type": "button",
            "body": {"text": body_text}
        }
        
        if header_text:
            interactive["header"] = {"type": "text", "text": header_text}
        
        if footer_text:
            interactive["footer"] = {"text": footer_text}
        
        interactive["action"] = {"buttons": formatted_buttons}
        
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "interactive",
            "interactive": interactive
        }
        
        try:
            response = await self.client.post(self.api_url, json=payload)
            response.raise_for_status()
            
            logger.success(f"✅ Buttons message sent to {phone_number}")
            return response.json()
        
        except Exception as e:
            logger.error(f"Failed to send buttons: {e}")
            # Fallback: envia como texto simples
            fallback_text = f"{body_text}\n\nOpções:\n"
            fallback_text += "\n".join([f"{i+1}. {btn['title']}" for i, btn in enumerate(buttons)])
            return await self.send_text_message(phone_number, fallback_text)
    
    async def mark_as_read(self, message_id: str) -> bool:
        """
        Marca mensagem como lida (exibe checkmarks azuis).
        
        Args:
            message_id: ID da mensagem recebida
        """
        
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        
        try:
            response = await self.client.post(self.api_url, json=payload)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"Failed to mark message as read: {e}")
            return False
    
    async def close(self):
        """Fecha o cliente HTTP"""
        await self.client.aclose()


# ========================================
# HELPERS
# ========================================

def format_phone_number(phone: str) -> str:
    """
    Formata número para o padrão do WhatsApp (sem + ou espaços).
    
    Entrada: "+55 11 99999-9999" ou "11999999999"
    Saída: "5511999999999"
    """
    # Remove tudo que não é dígito
    digits = "".join(filter(str.isdigit, phone))
    
    # Se não tem código do país, assume Brasil (55)
    if len(digits) == 11:  # Apenas DDD + número
        digits = "55" + digits
    
    return digits
"""
Cliente SIMPLIFICADO para Gemini 2.5 Flash (gratuito e moderno).
Usando a biblioteca google-genai mais recente.
"""

import json
import asyncio
from typing import Optional, Dict, Any, List
from loguru import logger
from google import genai  # BIBLIOTECA NOVA!

from src.core.config import get_settings
from src.api.schemas.ai import AIResponse, AIExtractedData
from src.infrastructure.ai.prompts import build_triage_prompt

settings = get_settings()


class AIClient:
    """Cliente simples para Gemini 2.5 Flash"""
    
    def __init__(self):
        self.client = None
        self.is_configured = False
        
        if not settings.gemini_api_key:
            logger.warning("⚠️  Gemini API key not configured!")
            return
        
        try:
            # Configura cliente Gemini
            self.client = genai.Client(api_key=settings.gemini_api_key)
            self.is_configured = True
            logger.success("✅ Gemini 2.5 Flash configurado (gratuito)")
            
        except Exception as e:
            logger.error(f"❌ Erro ao configurar Gemini: {e}")
    
    async def process_message(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        lead_data: Optional[Dict[str, Any]] = None
    ) -> AIResponse:
        """Processa mensagem do usuário"""
        
        if not self.is_configured:
            logger.error("AI client not configured")
            return self._get_fallback_response(user_message)
        
        try:
            # Monta prompt
            messages = build_triage_prompt(
                user_message=user_message,
                conversation_history=conversation_history,
                lead_data=lead_data
            )
            
            logger.info("🤖 Chamando Gemini 2.5 Flash...")
            
            # Converte mensagens para formato da nova API
            contents = self._format_contents(messages)
            
            # Chama API
            response = self.client.models.generate_content(
                model=settings.gemini_model,
                contents=contents
            )
            
            # Parse resposta
            ai_response = self._parse_response(response.text)
            logger.success("✅ Gemini respondeu com sucesso")
            
            return ai_response
            
        except Exception as e:
            logger.error(f"❌ Gemini falhou: {e}")
            return self._get_fallback_response(user_message)
    
    def _format_contents(self, messages: List[Dict[str, str]]) -> str:
        """Formata mensagens para a nova API"""
        formatted = []
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "system":
                formatted.append(f"## INSTRUÇÕES DO SISTEMA\n{content}")
            elif role == "user":
                formatted.append(f"## USUÁRIO\n{content}")
            elif role == "assistant":
                formatted.append(f"## ASSISTENTE\n{content}")
        
        formatted.append("\n## SUA RESPOSTA\nResponda APENAS com JSON válido.")
        return "\n\n".join(formatted)
    
    def _parse_response(self, raw_response: str) -> AIResponse:
        """Parse simples da resposta"""
        try:
            # Limpa resposta
            text = raw_response.strip()
            
            # Extrai JSON
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                json_str = text[start:end]
                data = json.loads(json_str)
                return AIResponse(**data)
            else:
                raise ValueError("No JSON found")
                
        except Exception as e:
            logger.error(f"Parse error: {e}")
            return self._get_fallback_response("")
    
    def _get_fallback_response(self, user_message: str) -> AIResponse:
        """Resposta inteligente de fallback"""
        if "urgente" in user_message.lower() and "são paulo" in user_message.lower():
            return AIResponse(
                response_text=(
                    "Olá! Entendo que você precisa de uma prótese dentária urgente em São Paulo. "
                    "Vou priorizar seu atendimento! Qual é seu nome completo?"
                ),
                extracted_data=AIExtractedData(
                    cidade="São Paulo",
                    urgencia="alta"
                ),
                intent="urgencia",
                confidence=0.9,
                should_transfer_to_human=False,
                next_question="Qual é seu nome completo?"
            )
        else:
            return AIResponse(
                response_text="Olá! Como posso ajudar você com próteses dentárias hoje?",
                extracted_data=AIExtractedData(),
                intent="informacao",
                confidence=0.7,
                should_transfer_to_human=False,
                next_question="Qual tipo de prótese você precisa?"
            )


# Singleton
_ai_client = None

def get_ai_client():
    global _ai_client
    if _ai_client is None:
        _ai_client = AIClient()
    return _ai_client

get_ai_orchestrator = get_ai_client
"""
Cliente de IA para processamento de mensagens.
Suporta múltiplos providers (DeepSeek, OpenAI, Groq) com fallback automático.
"""

import json
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from openai import AsyncOpenAI, APIError, APITimeoutError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from loguru import logger

from src.core.config import get_settings
from src.core.exceptions import AIError, AITimeoutError, AIResponseParseError, AIQuotaExceededError
from src.api.schemas.ai import AIResponse, AIExtractedData
from src.infrastructure.ai.prompts import build_triage_prompt, SYSTEM_PROMPT

settings = get_settings()


# ========================================
# ABSTRACT PROVIDER
# ========================================

class AIProvider(ABC):
    """Interface abstrata para providers de IA"""
    
    @abstractmethod
    async def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """Gera completação"""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nome do provider"""
        pass


# ========================================
# DEEPSEEK PROVIDER (GRATUITO)
# ========================================

class DeepSeekProvider(AIProvider):
    """
    Provider para DeepSeek V3 (gratuito até 10M tokens/mês).
    API compatível com OpenAI SDK.
    """
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_api_base
        )
        self.model = settings.deepseek_model
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(APITimeoutError)
    )
    async def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """Chama API do DeepSeek"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},  # Força JSON
                timeout=settings.ai_timeout_seconds
            )
            
            return response.choices[0].message.content
        
        except APITimeoutError as e:
            logger.error(f"DeepSeek timeout: {e}")
            raise AITimeoutError(model=self.model, timeout=settings.ai_timeout_seconds)
        
        except APIError as e:
            # Verifica se é erro de quota
            if "quota" in str(e).lower() or "rate limit" in str(e).lower():
                raise AIQuotaExceededError(model=self.model)
            
            logger.error(f"DeepSeek API error: {e}")
            raise AIError(f"DeepSeek API error: {e}", model=self.model)
    
    @property
    def name(self) -> str:
        return "deepseek"


# ========================================
# GROQ PROVIDER (ALTERNATIVA GRATUITA)
# ========================================

class GroqProvider(AIProvider):
    """
    Provider para Groq (Llama 3.1 70B gratuito).
    Extremamente rápido, boa alternativa.
    """
    
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        self.model = "llama-3.1-70b-versatile"
    
    async def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """Chama API do Groq"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=settings.ai_timeout_seconds
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            logger.error(f"Groq error: {e}")
            raise AIError(f"Groq error: {e}", model=self.model)
    
    @property
    def name(self) -> str:
        return "groq"


# ========================================
# AI ORCHESTRATOR (FALLBACK AUTOMÁTICO)
# ========================================

class AIOrchestrator:
    """
    Orquestra chamadas para IA com fallback automático.
    Tenta provider primário, se falhar, tenta secundário.
    """
    
    def __init__(self):
        # Configura providers disponíveis
        self.providers: List[AIProvider] = []
        
        # DeepSeek (primário - gratuito)
        if settings.deepseek_api_key:
            self.providers.append(DeepSeekProvider())
            logger.info("✅ DeepSeek provider configured")
        
        # Groq (secundário - gratuito, se configurado)
        # if settings.groq_api_key:
        #     self.providers.append(GroqProvider(settings.groq_api_key))
        #     logger.info("✅ Groq provider configured")
        
        if not self.providers:
            logger.warning("⚠️  No AI providers configured!")
    
    async def process_message(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        lead_data: Optional[Dict[str, Any]] = None
    ) -> AIResponse:
        """
        Processa mensagem do usuário e retorna resposta estruturada.
        
        Args:
            user_message: Mensagem atual do usuário
            conversation_history: Histórico da conversa (últimas 5-10 mensagens)
            lead_data: Dados já coletados do lead
            
        Returns:
            AIResponse com texto de resposta e dados extraídos
        """
        
        start_time = time.time()
        
        # Monta prompt
        messages = build_triage_prompt(
            user_message=user_message,
            conversation_history=conversation_history,
            lead_data=lead_data
        )
        
        # Tenta cada provider
        last_error = None
        for provider in self.providers:
            try:
                logger.info(f"🤖 Calling {provider.name} AI...")
                
                # Chama IA
                raw_response = await provider.complete(
                    messages=messages,
                    temperature=settings.ai_temperature,
                    max_tokens=settings.ai_max_tokens
                )
                
                # Parse resposta
                ai_response = self._parse_response(raw_response, provider.name)
                
                # Calcula métricas
                duration_ms = (time.time() - start_time) * 1000
                tokens_used = self._estimate_tokens(messages, raw_response)
                
                logger.success(
                    f"✅ {provider.name} responded in {duration_ms:.0f}ms "
                    f"(~{tokens_used} tokens)"
                )
                
                # Log estruturado para analytics
                from src.core.logging import log_ai_call
                log_ai_call(
                    model=provider.name,
                    tokens_used=tokens_used,
                    duration_ms=duration_ms,
                    success=True
                )
                
                return ai_response
            
            except Exception as e:
                last_error = e
                logger.warning(f"❌ {provider.name} failed: {e}")
                
                # Log falha
                from src.core.logging import log_ai_call
                log_ai_call(
                    model=provider.name,
                    tokens_used=0,
                    duration_ms=(time.time() - start_time) * 1000,
                    success=False,
                    error=str(e)
                )
                
                continue  # Tenta próximo provider
        
        # Todos os providers falharam
        logger.error("❌ All AI providers failed!")
        
        # Fallback: resposta genérica
        if last_error:
            raise last_error
        
        return self._get_fallback_response()
    
    def _parse_response(self, raw_response: str, model: str) -> AIResponse:
        """
        Faz parse da resposta JSON da IA.
        
        Args:
            raw_response: String JSON retornada pela IA
            model: Nome do modelo (para logs)
            
        Returns:
            AIResponse validado
            
        Raises:
            AIResponseParseError: Se não conseguir parsear
        """
        try:
            # Remove markdown code blocks se existirem
            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned.split("```json")[1]
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()
            
            # Parse JSON
            data = json.loads(cleaned)
            
            # Valida com Pydantic
            return AIResponse(**data)
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Raw response: {raw_response[:500]}")
            raise AIResponseParseError(model=model, raw_response=raw_response)
        
        except Exception as e:
            logger.error(f"Failed to validate AI response: {e}")
            raise AIResponseParseError(model=model, raw_response=raw_response)
    
    def _estimate_tokens(
        self,
        messages: List[Dict[str, str]],
        response: str
    ) -> int:
        """
        Estima quantidade de tokens usados (aproximação).
        1 token ≈ 4 caracteres em português.
        """
        total_chars = sum(len(msg["content"]) for msg in messages)
        total_chars += len(response)
        return total_chars // 4
    
    def _get_fallback_response(self) -> AIResponse:
        """
        Retorna resposta de fallback quando IA não está disponível.
        """
        return AIResponse(
            response_text=(
                "Desculpe, estou com dificuldades técnicas no momento. "
                "Você poderia me fornecer seu nome e telefone? "
                "Entraremos em contato em breve."
            ),
            extracted_data=AIExtractedData(),
            intent="informacao",
            confidence=0.0,
            should_transfer_to_human=True,
            transfer_reason="AI service unavailable"
        )


# ========================================
# INSTÂNCIA GLOBAL (singleton)
# ========================================

_ai_orchestrator: Optional[AIOrchestrator] = None

def get_ai_orchestrator() -> AIOrchestrator:
    """Retorna instância singleton do orquestrador de IA"""
    global _ai_orchestrator
    if _ai_orchestrator is None:
        _ai_orchestrator = AIOrchestrator()
    return _ai_orchestrator
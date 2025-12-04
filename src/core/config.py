"""
Configurações centralizadas do sistema usando Pydantic Settings.
Todas as variáveis de ambiente são carregadas e validadas aqui.
"""

from functools import lru_cache
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações globais da aplicação"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # ========================================
    # APLICAÇÃO
    # ========================================
    app_name: str = Field(default="Prothesis Triage Bot")
    app_version: str = Field(default="0.1.0")
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    
    # ========================================
    # API/SERVER
    # ========================================
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_reload: bool = Field(default=True)
    allowed_origins: str = Field(default="*")
    
    secret_key: str = Field(
        default="change-me-in-production-min-32-characters",
        min_length=32
    )
    admin_api_key: str = Field(default="admin-key-change-me")
    
    # ========================================
    # BANCO DE DADOS
    # ========================================
    database_url: str = Field(
        default="sqlite+aiosqlite:///./dental_triage.db"
    )
    db_pool_size: int = Field(default=5)
    db_max_overflow: int = Field(default=10)
    db_echo: bool = Field(default=False)
    
    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Valida e ajusta URL do banco"""
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v
    
    # ========================================
    # WHATSAPP
    # ========================================
    whatsapp_api_version: str = Field(default="v18.0")
    whatsapp_phone_number_id: str = Field(default="")
    whatsapp_business_account_id: str = Field(default="")
    whatsapp_access_token: str = Field(default="")
    whatsapp_app_secret: str = Field(default="")
    whatsapp_verify_token: str = Field(default="my-verify-token-12345")
    whatsapp_webhook_path: str = Field(default="/webhooks/whatsapp")
    
    @property
    def whatsapp_api_url(self) -> str:
        """URL base da API do WhatsApp"""
        return f"https://graph.facebook.com/{self.whatsapp_api_version}"
    
    @property
    def whatsapp_send_message_url(self) -> str:
        """Endpoint para enviar mensagens"""
        return f"{self.whatsapp_api_url}/{self.whatsapp_phone_number_id}/messages"
    
    # ========================================
    # IA (GEMINI - ÚNICO PROVEDOR)
    # ========================================
    gemini_api_key: str = Field(default="")
    gemini_model: str = Field(default="gemini-1.5-flash")
    
    # ========================================
    # IA (GEMINI - NOVO)
    # ========================================
    gemini_api_key: str = Field(default="")
    gemini_model: str = Field(default="gemini-1.5-flash")
    
    # ========================================
    # CONFIGURAÇÕES GERAIS DE IA
    # ========================================
    ai_max_tokens: int = Field(default=500)
    ai_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    ai_timeout_seconds: int = Field(default=15)
    ai_max_retries: int = Field(default=3)
    
    # ========================================
    # LÓGICA DE NEGÓCIO
    # ========================================
    covered_cities: str = Field(
        default="Juiz de Fora, Rio de Janeiro, São Paulo"
    )
    
    @property
    def covered_cities_list(self) -> List[str]:
        """Lista de cidades atendidas"""
        return [city.strip() for city in self.covered_cities.split(",")]
    
    score_threshold_hot: int = Field(default=70, ge=0, le=100)
    score_threshold_warm: int = Field(default=40, ge=0, le=100)
    
    session_timeout_minutes: int = Field(default=30)
    max_messages_without_progress: int = Field(default=10)
    
    # ========================================
    # NOTIFICAÇÕES
    # ========================================
    smtp_host: Optional[str] = Field(default=None)
    smtp_port: int = Field(default=587)
    smtp_user: Optional[str] = Field(default=None)
    smtp_password: Optional[str] = Field(default=None)
    smtp_from: Optional[str] = Field(default=None)
    
    notify_on_qualified_lead: bool = Field(default=False)
    notification_email: Optional[str] = Field(default=None)
    
    # ========================================
    # MONITORAMENTO
    # ========================================
    sentry_dsn: Optional[str] = Field(default=None)
    sentry_traces_sample_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    
    # ========================================
    # RATE LIMITING
    # ========================================
    rate_limit_per_minute: int = Field(default=60)
    rate_limit_per_hour: int = Field(default=1000)
    
    # ========================================
    # FEATURES
    # ========================================
    enable_admin_dashboard: bool = Field(default=True)
    enable_analytics: bool = Field(default=True)
    enable_crm_sync: bool = Field(default=False)
    
    # ========================================
    # MÉTODOS AUXILIARES
    # ========================================
    
    @property
    def is_development(self) -> bool:
        """Verifica se está em modo desenvolvimento"""
        return self.environment.lower() in ("development", "dev", "local")
    
    @property
    def is_production(self) -> bool:
        """Verifica se está em modo produção"""
        return self.environment.lower() in ("production", "prod")
    
    # ========================================
    # PROPRIEDADES DE IA (SIMPLIFICADAS)
    # ========================================

    @property
    def ai_api_key(self) -> str:
        """Retorna a chave da IA"""
        return self.gemini_api_key

    @property
    def ai_provider(self) -> str:
        """Retorna o provedor de IA"""
        return "gemini" if self.gemini_api_key else ""

    @property
    def is_ai_configured(self) -> bool:
        """Verifica se a IA está configurada"""
        return bool(self.gemini_api_key)

    @property
    def ai_model(self) -> str:
        """Retorna o modelo da IA"""
        return self.gemini_model

    def get_cors_origins(self) -> List[str]:
        """Retorna lista de origens permitidas para CORS"""
        if self.allowed_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    def model_dump_safe(self) -> dict:
        """Retorna configurações sem dados sensíveis"""
        data = self.model_dump()
        sensitive_keys = [
            "secret_key", "admin_api_key", "whatsapp_access_token",
            "whatsapp_app_secret", "gemini_api_key", 
            "smtp_password", "sentry_dsn", "database_url"
        ]
        for key in sensitive_keys:
            if key in data and data[key]:
                data[key] = "***HIDDEN***"
        return data


@lru_cache
def get_settings() -> Settings:
    """
    Retorna instância única de Settings (Singleton).
    Usa LRU cache para evitar recarregar .env múltiplas vezes.
    """
    return Settings()


# Instância global (opcional, para conveniência)
settings = get_settings()


# Validação ao importar (fail-fast)
if __name__ == "__main__":
    print("🔧 Validando configurações...")
    s = get_settings()
    print(f"✅ App: {s.app_name} v{s.app_version}")
    print(f"✅ Environment: {s.environment}")
    print(f"✅ Database: {s.database_url.split('@')[0]}...")
    print(f"✅ WhatsApp configurado: {bool(s.whatsapp_access_token)}")
    print(f"✅ IA configurada: {s.is_ai_configured}")
    print(f"✅ Provedor de IA: {s.ai_provider}")
    print(f"✅ Modelo: {s.ai_model}")
    print(f"✅ Cidades atendidas: {len(s.covered_cities_list)}")
    print("\n📋 Configurações completas (sem secrets):")
    import json
    print(json.dumps(s.model_dump_safe(), indent=2, ensure_ascii=False))
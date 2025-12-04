"""
Modelos de banco de dados usando SQLAlchemy 2.0.
Define todas as tabelas e relacionamentos do sistema.
"""

from datetime import datetime, UTC
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    String, Integer, Boolean, Text, JSON, DateTime, Interval,
    ForeignKey, Index, UniqueConstraint, Enum as SQLEnum
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from enum import Enum


# ========================================
# BASE
# ========================================

class Base(DeclarativeBase):
    """Classe base para todos os modelos"""
    
    # Usa JSONB no PostgreSQL, JSON no SQLite
    type_annotation_map = {
        dict: JSONB
    }


# ========================================
# ENUMS
# ========================================

class LeadStatus(str, Enum):
    """Status do lead no funil"""
    NEW = "novo"
    IN_CONVERSATION = "em_conversa"
    QUALIFIED = "qualificado"
    DISQUALIFIED = "desqualificado"
    TRANSFERRED = "transferido"
    ARCHIVED = "arquivado"


class LeadClassification(str, Enum):
    """Classificação de temperatura do lead"""
    HOT = "quente"
    WARM = "morno"
    COLD = "frio"
    UNQUALIFIED = "nao_qualificado"


class ConversationStatus(str, Enum):
    """Status da conversa"""
    ACTIVE = "ativa"
    COMPLETED = "concluida"
    TRANSFERRED = "transferida"
    EXPIRED = "expirada"


class MessageDirection(str, Enum):
    """Direção da mensagem"""
    INBOUND = "entrada"
    OUTBOUND = "saida"


class MessageType(str, Enum):
    """Tipo de mensagem do WhatsApp"""
    TEXT = "text"
    IMAGE = "image" 
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    BUTTON_REPLY = "button"
    LIST_REPLY = "interactive"


class EventType(str, Enum):
    """Tipos de eventos do sistema"""
    LEAD_CREATED = "lead_criado"
    MESSAGE_RECEIVED = "mensagem_recebida"
    MESSAGE_SENT = "mensagem_enviada"
    CLASSIFIED = "classificado"
    ROUTED = "roteado"
    TRANSFERRED = "transferido"
    SESSION_EXPIRED = "sessao_expirada"


# ========================================
# MODELOS
# ========================================

class Lead(Base):
    """
    Lead/Contato principal.
    Representa uma pessoa que entrou em contato via WhatsApp.
    """
    __tablename__ = "leads"
    
    # Primary Key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4())
    )
    
    # Identificação
    phone_number: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True
    )
    name: Mapped[Optional[str]] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Localização
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(2))
    
    # Dados específicos da clínica
    prosthesis_type: Mapped[Optional[str]] = mapped_column(String(50))
    urgency_level: Mapped[Optional[str]] = mapped_column(String(20))
    budget_range: Mapped[Optional[str]] = mapped_column(String(50))
    has_insurance: Mapped[Optional[bool]] = mapped_column(Boolean)
    
    # Classificação e roteamento
    classification: Mapped[Optional[str]] = mapped_column(
        SQLEnum(LeadClassification, native_enum=False),
        index=True
    )
    score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        SQLEnum(LeadStatus, native_enum=False),
        default=LeadStatus.NEW,
        index=True
    )
    routed_to: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Metadados de origem
    source: Mapped[Optional[str]] = mapped_column(String(50))
    campaign_id: Mapped[Optional[str]] = mapped_column(String(100))
    utm_source: Mapped[Optional[str]] = mapped_column(String(100))
    utm_medium: Mapped[Optional[str]] = mapped_column(String(100))
    utm_campaign: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Dados extras (flexível)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC)
    )
    first_contact_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    qualified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relacionamentos
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan"
    )
    events: Mapped[list["Event"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan"
    )
    
    # Índices compostos
    __table_args__ = (
        Index('idx_lead_classification_status', 'classification', 'status'),
        Index('idx_lead_created_at_status', 'created_at', 'status'),
    )
    
    def __repr__(self) -> str:
        return f"<Lead {self.phone_number} - {self.status}>"


class Conversation(Base):
    """
    Conversa completa com um lead.
    Agrupa múltiplas mensagens de uma sessão.
    """
    __tablename__ = "conversations"
    
    # Primary Key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4())
    )
    
    # Foreign Key
    lead_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Status
    status: Mapped[str] = mapped_column(
        SQLEnum(ConversationStatus, native_enum=False),
        default=ConversationStatus.ACTIVE,
        index=True
    )
    
    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC)
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC)
    )
    
    # Métricas
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    ai_messages: Mapped[int] = mapped_column(Integer, default=0)
    user_messages: Mapped[int] = mapped_column(Integer, default=0)
    average_response_time: Mapped[Optional[int]] = mapped_column(Integer)  # em segundos
    
    # Flags
    data_collected_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    transferred_to_human: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relacionamentos
    lead: Mapped["Lead"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at"
    )
    
    __table_args__ = (
        Index('idx_conv_lead_status', 'lead_id', 'status'),
    )
    
    def __repr__(self) -> str:
        return f"<Conversation {self.id} - {self.status}>"


class Message(Base):
    """
    Mensagem individual (entrada ou saída).
    """
    __tablename__ = "messages"
    
    # Primary Key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4())
    )
    
    # Foreign Key
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # WhatsApp IDs
    whatsapp_message_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        index=True
    )
    
    # Conteúdo
    direction: Mapped[str] = mapped_column(
        SQLEnum(MessageDirection, native_enum=False),
        nullable=False
    )
    message_type: Mapped[str] = mapped_column(
        SQLEnum(MessageType, native_enum=False),
        default=MessageType.TEXT
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_url: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Metadados de IA (quando aplicável)
    ai_model: Mapped[Optional[str]] = mapped_column(String(50))
    ai_tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    ai_processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    ai_confidence: Mapped[Optional[float]] = mapped_column(String(10))  # 0.0-1.0
    extracted_data: Mapped[Optional[dict]] = mapped_column(JSON)
    
    # Status de entrega (para mensagens enviadas)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True
    )
    
    # Relacionamento
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    
    __table_args__ = (
        Index('idx_msg_conversation_created', 'conversation_id', 'created_at'),
        Index('idx_msg_direction_created', 'direction', 'created_at'),
    )
    
    def __repr__(self) -> str:
        preview = self.content[:30] + "..." if len(self.content) > 30 else self.content
        return f"<Message {self.direction} - {preview}>"


class Event(Base):
    """
    Eventos do sistema para auditoria e analytics.
    """
    __tablename__ = "events"
    
    # Primary Key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4())
    )
    
    # Foreign Key (opcional)
    lead_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("leads.id", ondelete="CASCADE"),
        index=True
    )
    
    # Tipo de evento
    event_type: Mapped[str] = mapped_column(
        SQLEnum(EventType, native_enum=False),
        nullable=False,
        index=True
    )
    
    # Dados do evento
    event_data: Mapped[Optional[dict]] = mapped_column(JSON)
    
    # Origem do evento
    triggered_by: Mapped[Optional[str]] = mapped_column(String(50))  # 'ai', 'webhook', 'admin'
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True
    )
    
    # Relacionamento
    lead: Mapped[Optional["Lead"]] = relationship(back_populates="events")
    
    __table_args__ = (
        Index('idx_event_type_created', 'event_type', 'created_at'),
        Index('idx_event_lead_type', 'lead_id', 'event_type'),
    )
    
    def __repr__(self) -> str:
        return f"<Event {self.event_type} - {self.created_at}>"
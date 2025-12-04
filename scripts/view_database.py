"""
Script para visualizar dados do banco de forma amigável.

Rode: python scripts/view_database.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from src.infrastructure.database.session import get_db_context
from src.infrastructure.database.models import Lead, Conversation, Message


async def show_leads():
    """Mostra todos os leads"""
    
    print("\n" + "=" * 60)
    print("👥 LEADS CADASTRADOS")
    print("=" * 60 + "\n")
    
    async with get_db_context() as db:
        result = await db.execute(select(Lead).order_by(Lead.created_at.desc()))
        leads = result.scalars().all()
        
        if not leads:
            print("📭 Nenhum lead encontrado ainda.\n")
            return
        
        for i, lead in enumerate(leads, 1):
            print(f"{i}. 📱 {lead.phone_number}")
            if lead.name:
                print(f"   👤 Nome: {lead.name}")
            if lead.city:
                print(f"   📍 Cidade: {lead.city}")
            if lead.prosthesis_type:
                print(f"   🦷 Tipo: {lead.prosthesis_type}")
            print(f"   🎯 Classificação: {lead.classification or 'Não classificado'}")
            print(f"   📊 Score: {lead.score}")
            print(f"   📅 Status: {lead.status}")
            if lead.urgency_level:
                print(f"   ⚠️  Urgência: {lead.urgency_level}")
            print()


async def show_conversations():
    """Mostra conversas com mensagens"""
    
    print("\n" + "=" * 60)
    print("💬 CONVERSAS")
    print("=" * 60 + "\n")
    
    async with get_db_context() as db:
        result = await db.execute(
            select(Conversation)
            .order_by(Conversation.started_at.desc())
            .limit(5)
        )
        conversations = result.scalars().all()
        
        if not conversations:
            print("📭 Nenhuma conversa encontrada ainda.\n")
            return
        
        for i, conv in enumerate(conversations, 1):
            # Busca lead
            lead_result = await db.execute(
                select(Lead).where(Lead.id == conv.lead_id)
            )
            lead = lead_result.scalar_one()
            
            print(f"\n{i}. Conversa com {lead.phone_number}")
            print(f"   📅 Iniciada: {conv.started_at.strftime('%d/%m/%Y %H:%M')}")
            print(f"   📊 Status: {conv.status}")
            print(f"   💬 Mensagens: {conv.total_messages} (👤 {conv.user_messages} | 🤖 {conv.ai_messages})")
            
            # Busca mensagens
            msg_result = await db.execute(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.created_at)
                .limit(10)
            )
            messages = msg_result.scalars().all()
            
            if messages:
                print(f"\n   Últimas mensagens:")
                for msg in messages[-5:]:  # Últimas 5
                    icon = "👤" if msg.direction.value == "entrada" else "🤖"
                    preview = msg.content[:60] + "..." if len(msg.content) > 60 else msg.content
                    print(f"   {icon} {preview}")


async def show_stats():
    """Mostra estatísticas gerais"""
    
    print("\n" + "=" * 60)
    print("📊 ESTATÍSTICAS")
    print("=" * 60 + "\n")
    
    async with get_db_context() as db:
        # Total de leads
        total_leads = await db.execute(select(Lead))
        total = len(total_leads.scalars().all())
        
        # Por classificação
        for classification in ["quente", "morno", "frio"]:
            result = await db.execute(
                select(Lead).where(Lead.classification == classification)
            )
            count = len(result.scalars().all())
            if count > 0:
                emoji = "🔥" if classification == "quente" else "☀️" if classification == "morno" else "❄️"
                print(f"{emoji} {classification.capitalize()}: {count}")
        
        # Total de conversas
        total_conv = await db.execute(select(Conversation))
        conv_count = len(total_conv.scalars().all())
        
        # Total de mensagens
        total_msg = await db.execute(select(Message))
        msg_count = len(total_msg.scalars().all())
        
        print(f"\n📈 Totais:")
        print(f"   👥 Leads: {total}")
        print(f"   💬 Conversas: {conv_count}")
        print(f"   📝 Mensagens: {msg_count}")
        print()


async def main():
    """Menu principal"""
    
    while True:
        print("\n╔" + "=" * 58 + "╗")
        print("║" + " " * 18 + "VISUALIZAR DADOS" + " " * 24 + "║")
        print("╚" + "=" * 58 + "╝\n")
        print("  1. 👥 Ver Leads")
        print("  2. 💬 Ver Conversas")
        print("  3. 📊 Ver Estatísticas")
        print("  4. 🔄 Ver Tudo")
        print("  5. ❌ Sair\n")
        
        choice = input("Escolha uma opção (1-5): ").strip()
        
        if choice == "1":
            await show_leads()
        elif choice == "2":
            await show_conversations()
        elif choice == "3":
            await show_stats()
        elif choice == "4":
            await show_stats()
            await show_leads()
            await show_conversations()
        elif choice == "5":
            print("\n👋 Até logo!\n")
            break
        else:
            print("\n⚠️  Opção inválida!\n")
        
        input("\nPressione ENTER para continuar...")


if __name__ == "__main__":
    asyncio.run(main())
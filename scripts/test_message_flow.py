"""
Script de teste para simular uma conversa completa.
Testa todo o fluxo: receber mensagem → IA → classificação → resposta.

Rode: python scripts/test_message_flow.py
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.infrastructure.database.session import get_db_context
from src.domain.services.message_processor import MessageProcessor


async def simulate_conversation():
    """Simula uma conversa completa com múltiplas mensagens"""
    
    print("\n" + "=" * 60)
    print("🧪 TESTE DE FLUXO COMPLETO")
    print("=" * 60 + "\n")
    
    # Número de telefone fictício
    test_phone = "5511999887766"
    
    # Sequência de mensagens do usuário
    messages = [
        "Oi, queria saber sobre prótese dentária",
        "Meu nome é João Silva",
        "Moro em São Paulo capital",
        "Preciso de uma prótese total",
        "É bem urgente, tenho um casamento semana que vem"
    ]
    
    print(f"📱 Simulando conversa com: {test_phone}\n")
    
    async with get_db_context() as db:
        processor = MessageProcessor(db)
        
        for i, user_message in enumerate(messages, 1):
            print(f"\n{'─' * 60}")
            print(f"💬 Mensagem {i}/{len(messages)}")
            print(f"{'─' * 60}")
            print(f"\n👤 USUÁRIO: {user_message}\n")
            
            try:
                # Processa mensagem (simula webhook)
                message_id = f"test_msg_{i}_{datetime.now().timestamp()}"
                
                await processor.process_inbound_message(
                    phone_number=test_phone,
                    whatsapp_message_id=message_id,
                    content=user_message,
                    message_type="text",
                    timestamp=str(int(datetime.now().timestamp()))
                )
                
                print("✅ Mensagem processada com sucesso!")
                
                # Aguarda um pouco antes da próxima mensagem
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.exception(f"❌ Erro ao processar mensagem {i}: {e}")
                print(f"\n❌ ERRO: {e}\n")
                break
    
    print("\n" + "=" * 60)
    print("✅ TESTE CONCLUÍDO!")
    print("=" * 60)
    print("\n📊 Para ver os resultados:")
    print("   1. Acesse: http://localhost:8000/docs")
    print("   2. Teste o endpoint: GET /api/leads")
    print("   3. Você verá o lead criado com os dados extraídos\n")
    print("📝 NOTA: Como não tem WhatsApp configurado, as respostas")
    print("   não serão enviadas, mas você verá nos logs!\n")


async def test_ai_only():
    """Testa apenas a IA sem salvar no banco"""
    
    print("\n" + "=" * 60)
    print("🤖 TESTE RÁPIDO - APENAS IA")
    print("=" * 60 + "\n")
    
    from src.infrastructure.ai.client import get_ai_orchestrator
    
    ai = get_ai_orchestrator()
    
    test_message = "Olá, preciso de uma prótese dentária urgente em São Paulo"
    
    print(f"💬 Mensagem de teste: {test_message}\n")
    print("⏳ Processando com IA...\n")
    
    try:
        response = await ai.process_message(
            user_message=test_message,
            conversation_history=[],
            lead_data={}
        )
        
        print("✅ RESPOSTA DA IA:")
        print(f"\n📝 Texto: {response.response_text}\n")
        print(f"🎯 Intenção: {response.intent}")
        print(f"📊 Confiança: {response.confidence}")
        print(f"\n📋 Dados extraídos:")
        print(f"   Nome: {response.extracted_data.nome}")
        print(f"   Cidade: {response.extracted_data.cidade}")
        print(f"   Tipo: {response.extracted_data.tipo_protese}")
        print(f"   Urgência: {response.extracted_data.urgencia}")
        
        if response.should_transfer_to_human:
            print(f"\n🔄 Deve transferir para humano: {response.transfer_reason}")
        
        print("\n" + "=" * 60)
        print("✅ TESTE DE IA CONCLUÍDO!")
        print("=" * 60 + "\n")
        
    except Exception as e:
        logger.exception(f"❌ Erro no teste de IA: {e}")
        print(f"\n❌ ERRO: {e}\n")
        print("⚠️  Verifique se a DEEPSEEK_API_KEY está correta no .env\n")


async def main():
    """Menu de testes"""
    
    print("\n╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "MENU DE TESTES" + " " * 29 + "║")
    print("╚" + "=" * 58 + "╝\n")
    print("  1. 🤖 Teste rápido (apenas IA)")
    print("  2. 🔄 Teste completo (conversa simulada)")
    print("  3. ❌ Sair\n")
    
    choice = input("Escolha uma opção (1-3): ").strip()
    
    if choice == "1":
        await test_ai_only()
    elif choice == "2":
        await simulate_conversation()
    elif choice == "3":
        print("\n👋 Até logo!\n")
        return
    else:
        print("\n⚠️  Opção inválida!\n")


if __name__ == "__main__":
    asyncio.run(main())
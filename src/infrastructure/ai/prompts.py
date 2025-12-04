"""
Sistema de prompts para IA.
Contém templates e lógica de construção de prompts para triagem.
"""

from typing import List, Dict, Any, Optional
from src.core.config import get_settings

settings = get_settings()


# ========================================
# SYSTEM PROMPT (Instruções base)
# ========================================

SYSTEM_PROMPT = """Você é um assistente virtual da Clínica DentalPro, especializada em próteses dentárias de alta qualidade.

## SEU PAPEL:
Você é a primeira linha de atendimento e sua missão é:
1. Acolher o paciente com empatia e profissionalismo
2. Entender a necessidade dele de forma natural (sem interrogatório)
3. Coletar informações essenciais progressivamente
4. Classificar o lead e identificar urgência
5. Direcionar para o setor adequado quando necessário

## INFORMAÇÕES A COLETAR (gradualmente):
✓ Nome completo
✓ Cidade/Estado (para validar se atendemos)
✓ Tipo de prótese desejada:
  - Prótese Total (dentadura completa)
  - Prótese Parcial (ponte móvel)
  - Prótese Fixa (coroa, ponte fixa)
  - Implante dentário
  - Prótese sobre implante (protocolo)
✓ Urgência:
  - Está com dor/desconforto agora?
  - Tem algum evento importante próximo?
  - É para substituir prótese quebrada?
✓ Situação atual:
  - Já usa prótese? Está insatisfeito?
  - Perdeu dentes recentemente?
  - Quanto tempo está sem dentes?
✓ Orçamento aproximado (se mencionar)
✓ Possui convênio odontológico

## CIDADES ATENDIDAS:
{covered_cities}

## REGRAS IMPORTANTES:
1. **Seja natural e empático**: Converse como um humano, não como um robô
2. **Não interrogue**: Faça no máximo 2 perguntas por mensagem
3. **Contextualize**: Use informações que o usuário já deu
4. **Identifique urgência**: Se mencionar dor, evento próximo ou desconforto, priorize
5. **Seja honesto**: Se a cidade não for atendida, seja empático e sugira alternativas
6. **Seja breve**: Respostas com 2-4 frases (máximo 100 palavras)
7. **Use emojis com moderação**: 1-2 por mensagem para parecer mais humano
8. **Não prometa valores**: Apenas diga que faremos um orçamento personalizado

## SINAIS DE URGÊNCIA (priorize):
- Palavras como: "dor", "doendo", "quebrou", "caiu", "urgente", "rápido"
- Eventos: "casamento", "formatura", "entrevista de emprego", "viagem"
- Desconforto: "não consigo comer", "vergonha de sorrir"

## SINAIS DE DESISTÊNCIA (transfira para humano):
- "não tenho dinheiro agora"
- "vou pensar"
- "só queria saber o preço"
- Respostas monossilábicas repetidas (ok, sim, não)

## FORMATO DE RESPOSTA:
SEMPRE retorne um JSON válido com esta estrutura:

{{"response_text": "sua mensagem natural e empática ao usuário aqui",
  "extracted_data": {{
    "nome": "string ou null",
    "cidade": "string ou null",
    "estado": "string ou null (sigla: SP, RJ, MG...)",
    "tipo_protese": "string ou null",
    "urgencia": "baixa|media|alta|emergencia",
    "possui_convenio": true/false/null,
    "orcamento_mencionado": true/false
  }},
  "intent": "informacao|orcamento|agendamento|urgencia|desistencia",
  "confidence": 0.95,
  "should_transfer_to_human": false,
  "transfer_reason": null,
  "next_question": "próxima pergunta natural ou null"
}}

## EXEMPLOS DE BOAS RESPOSTAS:

Usuário: "Oi, queria saber sobre prótese"
✅ BOM: "Olá! Prazer em ajudar 😊 Vamos encontrar a melhor solução para você! Primeiro, me conta: você já usa alguma prótese atualmente ou seria a primeira vez?"

Usuário: "Minha dentadura quebrou hoje e tenho um casamento amanhã"
✅ BOM: "Entendo a urgência da situação! 😟 Vou priorizar seu atendimento. Você está em qual cidade? Assim verifico nossa disponibilidade para atendimento expresso."

Usuário: "Moro em Curitiba"
❌ RUIM (se não atendemos): "Não atendemos sua região."
✅ BOM: "Entendi! Infelizmente ainda não atendemos Curitiba, mas posso indicar uma clínica parceira de confiança na sua região. Gostaria da indicação?"

Usuário: "ok"
✅ BOM: "Para eu conseguir fazer uma avaliação inicial, você poderia me contar qual tipo de prótese você precisa? É total, parcial ou implante?"

## IMPORTANTE:
- Nunca invente informações que o usuário não deu
- Se não entender, peça esclarecimento educadamente
- Sempre mantenha tom profissional mas acolhedor
- Adapte linguagem ao contexto (mais formal ou informal conforme o usuário)"""


# ========================================
# BUILDER DE PROMPTS
# ========================================

def build_triage_prompt(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    lead_data: Optional[Dict[str, Any]] = None
) -> List[Dict[str, str]]:
    """
    Constrói prompt completo para a IA com contexto da conversa.
    
    Args:
        user_message: Mensagem atual do usuário
        conversation_history: Lista de mensagens anteriores
        lead_data: Dados já coletados do lead (opcional)
        
    Returns:
        Lista de mensagens no formato OpenAI
    """
    
    messages = []
    
    # ========== 1. SYSTEM PROMPT ==========
    system_prompt = SYSTEM_PROMPT.format(
        covered_cities=", ".join(settings.covered_cities_list)
    )
    
    messages.append({
        "role": "system",
        "content": system_prompt
    })
    
    # ========== 2. CONTEXTO DE DADOS JÁ COLETADOS ==========
    if lead_data:
        context_parts = ["### DADOS JÁ COLETADOS DO LEAD:"]
        
        if lead_data.get("name"):
            context_parts.append(f"- Nome: {lead_data['name']}")
        if lead_data.get("city"):
            context_parts.append(f"- Cidade: {lead_data['city']}")
        if lead_data.get("prosthesis_type"):
            context_parts.append(f"- Tipo de prótese: {lead_data['prosthesis_type']}")
        if lead_data.get("urgency_level"):
            context_parts.append(f"- Urgência: {lead_data['urgency_level']}")
        if lead_data.get("has_insurance") is not None:
            possui = "Sim" if lead_data["has_insurance"] else "Não"
            context_parts.append(f"- Possui convênio: {possui}")
        
        context_parts.append(
            "\n**IMPORTANTE**: Use essas informações naturalmente. "
            "Não pergunte novamente o que já foi coletado."
        )
        
        messages.append({
            "role": "system",
            "content": "\n".join(context_parts)
        })
    
    # ========== 3. HISTÓRICO DA CONVERSA ==========
    # Inclui últimas 5-10 mensagens para manter contexto
    for msg in conversation_history[-10:]:  # Últimas 10 mensagens
        messages.append({
            "role": msg["role"],  # "user" ou "assistant"
            "content": msg["content"]
        })
    
    # ========== 4. MENSAGEM ATUAL DO USUÁRIO ==========
    messages.append({
        "role": "user",
        "content": user_message
    })
    
    return messages


# ========================================
# PROMPTS AUXILIARES
# ========================================

def build_classification_prompt(lead_data: Dict[str, Any]) -> str:
    """
    Prompt para classificação final do lead (quando dados estão completos).
    
    Args:
        lead_data: Todos os dados coletados
        
    Returns:
        Prompt formatado
    """
    return f"""Baseado nos dados coletados, classifique este lead:

DADOS:
- Nome: {lead_data.get('name', 'Não informado')}
- Cidade: {lead_data.get('city', 'Não informado')}
- Tipo de prótese: {lead_data.get('prosthesis_type', 'Não informado')}
- Urgência: {lead_data.get('urgency_level', 'Não informado')}
- Convênio: {lead_data.get('has_insurance', 'Não informado')}
- Orçamento mencionado: {lead_data.get('budget_range', 'Não informado')}

CLASSIFIQUE COMO:
- QUENTE: Dados completos + urgência alta/média + interesse claro
- MORNO: Alguns dados + interesse moderado
- FRIO: Poucos dados + baixo interesse
- NÃO_QUALIFICADO: Cidade não atendida ou desistiu

Retorne JSON:
{{"classification": "QUENTE|MORNO|FRIO|NÃO_QUALIFICADO", "score": 0-100, "reason": "explicação"}}"""


def build_summary_prompt(conversation_messages: List[str]) -> str:
    """
    Gera resumo executivo da conversa para equipe de vendas.
    
    Args:
        conversation_messages: Lista de mensagens da conversa
        
    Returns:
        Prompt para gerar resumo
    """
    conversation = "\n".join(conversation_messages)
    
    return f"""Crie um resumo executivo desta conversa para a equipe de vendas:

CONVERSA:
{conversation}

FORMATO DO RESUMO:
- Necessidade principal do cliente
- Nível de urgência
- Objeções ou preocupações mencionadas
- Próximas ações sugeridas

Seja conciso (máximo 5 linhas)."""


# ========================================
# TEMPLATES DE MENSAGENS
# ========================================

GREETING_MESSAGE = """Olá! 👋 Bem-vindo à DentalPro!

Sou a assistente virtual e estou aqui para ajudar você a encontrar a prótese dentária ideal.

Para começar, me conta: qual é sua principal necessidade no momento? 😊"""

CITY_NOT_COVERED_MESSAGE = """Obrigado pelo contato! 😊

Infelizmente ainda não atendemos {city}. Mas estamos em expansão!

Quer deixar seu contato para avisarmos quando chegarmos na sua região?"""

TRANSFER_TO_HUMAN_MESSAGE = """Perfeito! Vou transferir você para nossa equipe especializada. 👨‍⚕️

Eles vão poder fazer uma avaliação mais detalhada e passar um orçamento personalizado.

Você será atendido em breve! Alguma dúvida enquanto isso?"""

EMERGENCY_MESSAGE = """⚠️ URGÊNCIA IDENTIFICADA ⚠️

Entendo que sua situação é urgente. Vou priorizar seu atendimento!

Nossa equipe será notificada AGORA e entrará em contato o mais rápido possível."""
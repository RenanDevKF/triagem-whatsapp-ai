"""
Serviço de classificação e pontuação de leads.
Define regras de negócio para identificar leads quentes/mornos/frios.
"""

from typing import Dict, Any
from loguru import logger

from src.infrastructure.database.models import Lead, Conversation, LeadClassification
from src.core.config import get_settings

settings = get_settings()


class LeadClassifier:
    """
    Classifica leads baseado em dados coletados e comportamento.
    """
    
    def classify_lead(
        self,
        lead: Lead,
        conversation: Conversation
    ) -> Dict[str, Any]:
        """
        Classifica lead e calcula score.
        
        Retorna:
            {
                "classification": "quente|morno|frio|nao_qualificado",
                "score": 0-100,
                "reasons": ["motivo1", "motivo2"]
            }
        """
        
        score = 0
        reasons = []
        
        # ========================================
        # CRITÉRIOS DE PONTUAÇÃO
        # ========================================
        
        # 1. DADOS COLETADOS (máximo 40 pontos)
        if lead.name:
            score += 10
            reasons.append("Nome informado (+10)")
        
        if lead.city:
            if lead.city in settings.covered_cities_list:
                score += 15
                reasons.append(f"Cidade atendida: {lead.city} (+15)")
            else:
                score -= 30
                reasons.append(f"Cidade NÃO atendida: {lead.city} (-30)")
        
        if lead.prosthesis_type:
            score += 15
            reasons.append(f"Tipo de prótese definido: {lead.prosthesis_type} (+15)")
        
        # 2. URGÊNCIA (máximo 30 pontos)
        urgency_scores = {
            "emergencia": 30,
            "alta": 25,
            "media": 15,
            "baixa": 5
        }
        
        if lead.urgency_level:
            urgency_score = urgency_scores.get(lead.urgency_level, 0)
            score += urgency_score
            reasons.append(f"Urgência {lead.urgency_level} (+{urgency_score})")
        
        # 3. SITUAÇÃO FINANCEIRA (máximo 20 pontos)
        if lead.has_insurance:
            score += 15
            reasons.append("Possui convênio (+15)")
        
        if lead.budget_range:
            score += 10
            reasons.append("Orçamento mencionado (+10)")
        
        # 4. ENGAJAMENTO (máximo 10 pontos)
        if conversation.user_messages >= 3:
            score += 10
            reasons.append(f"Engajado ({conversation.user_messages} mensagens) (+10)")
        elif conversation.user_messages >= 2:
            score += 5
            reasons.append("Engajamento moderado (+5)")
        
        # 5. TEMPO DE RESPOSTA (bônus)
        if conversation.average_response_time and conversation.average_response_time < 120:  # < 2min
            score += 5
            reasons.append("Respostas rápidas (+5)")
        
        # ========================================
        # PENALIZAÇÕES
        # ========================================
        
        # Lead com muitas mensagens mas sem progresso
        if conversation.total_messages > 10 and not conversation.data_collected_complete:
            score -= 15
            reasons.append("Muitas mensagens sem progresso (-15)")
        
        # Conversa muito longa (possível perda de interesse)
        if conversation.total_messages > 20:
            score -= 10
            reasons.append("Conversa muito longa (-10)")
        
        # ========================================
        # CLASSIFICAÇÃO FINAL
        # ========================================
        
        # Limita score entre 0-100
        score = max(0, min(100, score))
        
        # Define classificação baseada em thresholds
        if score >= settings.score_threshold_hot:
            classification = LeadClassification.HOT
        elif score >= settings.score_threshold_warm:
            classification = LeadClassification.WARM
        elif score > 0:
            classification = LeadClassification.COLD
        else:
            classification = LeadClassification.UNQUALIFIED
        
        # Log classificação
        logger.info(
            f"Lead {lead.id} classified: {classification} (score={score})"
        )
        logger.debug(f"Classification reasons: {reasons}")
        
        return {
            "classification": classification.value,
            "score": score,
            "reasons": reasons
        }
    
    def determine_routing(self, lead: Lead) -> str:
        """
        Determina para qual setor o lead deve ser roteado.
        
        Retorna:
            Nome do setor/equipe destino
        """
        
        # EMERGÊNCIA → Atendimento urgente
        if lead.urgency_level == "emergencia":
            return "ATENDIMENTO_URGENTE"
        
        # QUENTE → Vendas prioritárias
        if lead.classification == LeadClassification.HOT:
            if lead.urgency_level in ["alta", "media"]:
                return "VENDAS_PRIORIDADE"
            return "VENDAS"
        
        # MORNO → Agendamento
        if lead.classification == LeadClassification.WARM:
            return "AGENDAMENTO"
        
        # FRIO → Nutrição de leads
        if lead.classification == LeadClassification.COLD:
            return "NUTRICAO"
        
        # NÃO QUALIFICADO → Descarte
        return "DESCARTE"
    
    def should_transfer_to_human(
        self,
        lead: Lead,
        conversation: Conversation,
        ai_confidence: float
    ) -> bool:
        """
        Decide se deve transferir para atendimento humano.
        
        Critérios:
        - Urgência alta/emergência
        - Lead quente com dados completos
        - Baixa confiança da IA
        - Muitas mensagens sem progresso
        """
        
        # Emergência → sempre transfere
        if lead.urgency_level == "emergencia":
            return True
        
        # Lead quente → transfere
        if lead.classification == LeadClassification.HOT:
            return True
        
        # Dados completos + interesse → transfere
        if self._is_data_complete(lead) and conversation.user_messages >= 3:
            return True
        
        # IA com baixa confiança → transfere
        if ai_confidence < 0.5:
            return True
        
        # Travou na conversa → transfere
        if conversation.total_messages > 15 and not conversation.data_collected_complete:
            return True
        
        return False
    
    def _is_data_complete(self, lead: Lead) -> bool:
        """Verifica se dados essenciais foram coletados"""
        
        required_fields = [
            lead.name,
            lead.city,
            lead.prosthesis_type
        ]
        
        return all(field is not None for field in required_fields)
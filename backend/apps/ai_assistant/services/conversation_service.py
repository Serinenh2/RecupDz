"""
Conversation Service — business logic for conversations.

Responsibilities:
    - System prompt selection based on context and language
    - History building with sliding window + summarization logic
    - Message formatting for LLM consumption

Does NOT call Ollama or access Django ORM directly.
Uses ConversationHistoryRepository for data access.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_HISTORY = 10

SUMMARIZE_SYSTEM = (
    "Tu es un assistant de résumé. Résume la conversation suivante en 3-5 phrases "
    "claires et concises. Conserve les informations importantes : questions posées, "
    "réponses données, décisions prises, et contexte technique. Ne donne que le "
    "résumé, sans introduction ni conclusion."
)


# ---------------------------------------------------------------------------
# System prompts per context
# ---------------------------------------------------------------------------

SYSTEM_PROMPTS: Dict[str, str] = {
    "default": (
        "Tu es l'assistant réglementaire de RECUP-DZ, une entreprise de gestion des "
        "déchets en Algérie. Tu connais parfaitement la loi 01-19, le décret 06-104, "
        "les BSD (Bordereaux de Suivi des Déchets), les nomenclatures de déchets, "
        "et toute la réglementation algérienne liée aux déchets dangereux et non "
        "dangereux. Tu réponds toujours en français, de manière claire et concise. "
        "Si tu ne connais pas une réponse, dis-le honnêtement."
    ),
    "ar": (
        "أنت المساعد التنظيمي لشركة RECUP-DZ المتخصصة في إدارة النفايات في الجزائر. "
        "تعرف تماماً القانون 01-19 والمرسوم 06-104 وبوليصات متابعة النفايات "
        "والتصنيفات التنظيمية. تجيب دائماً بالعربية بشكل واضح ومختصر."
    ),
    "bsd": (
        "Tu es l'assistant réglementaire de RECUP-DZ spécialisé dans les BSD "
        "(Bordereaux de Suivi des Déchets). Tu connais les statuts des BSD : "
        "BROUILLON, EMIS, EN_COURS, REALISE, ARCHIVE, ANNULE. Tu peux analyser "
        "les retards, les données incomplètes, et la conformité réglementaire."
    ),
    "agrement": (
        "Tu es l'assistant réglementaire de RECUP-DZ spécialisé dans les agréments "
        "des récupérateurs. Tu connais les types d'agrément (A, B, C), les conditions "
        "d'obtention, les durées de validité, et les raisons de rejet ou de suspension."
    ),
    "nomenclature": (
        "Tu es l'assistant réglementaire de RECUP-DZ spécialisé dans la nomenclature "
        "des déchets. Tu connais les codes 15.01, 16.01, 20.01, etc., les familles "
        "de déchets, les niveaux de dangerosité, et les filières de traitement."
    ),
    "stock": (
        "Tu es l'assistant réglementaire de RECUP-DZ spécialisé dans l'analyse des "
        "stocks de déchets. Tu peux détecter les dépassements de seuils, les risques "
        "d'incendie, les problèmes de traçabilité, et recommander des actions."
    ),
    "recuperateur": (
        "Tu es l'assistant réglementaire de RECUP-DZ spécialisé dans les récupérateurs. "
        "Tu connais les catégories (A, B, C), les agréments, les capacités de traitement, "
        "et la situation réglementaire de chaque récupérateur."
    ),
}

SYSTEM_PROMPTS["fr"] = SYSTEM_PROMPTS["default"]


# ---------------------------------------------------------------------------
# Conversation Service
# ---------------------------------------------------------------------------

class ConversationService:
    """
    Pure business logic for conversation processing.

    Handles:
        - System prompt selection (context + language)
        - History building (sliding window with summarization)
        - Message formatting for LLM

    Does NOT call Ollama or access Django ORM.
    """

    def __init__(self, history_repo=None) -> None:
        self._history_repo = history_repo

    @property
    def repository(self):
        if self._history_repo is None:
            from apps.ai_assistant.repositories.conversation_history_repository import (
                ConversationHistoryRepository,
            )
            self._history_repo = ConversationHistoryRepository()
        return self._history_repo

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    def build_system_prompt(self, conversation: Any) -> str:
        """
        Select the appropriate system prompt for the conversation context.

        Detects language from the last user message and selects the matching
        prompt. Falls back to French default.
        """
        ctx = getattr(conversation, "contexte", None) or "default"

        langue = self._detect_language(conversation.pk)

        if langue == "ar":
            return SYSTEM_PROMPTS.get("ar", SYSTEM_PROMPTS["default"])

        return SYSTEM_PROMPTS.get(ctx, SYSTEM_PROMPTS["default"])

    def _detect_language(self, conversation_id: int) -> str:
        """Detect language from the last user message."""
        last_user = self.repository.get_last_user_message(conversation_id)
        if last_user:
            from apps.ai_assistant.glossaire_data import detecter_langue
            return detecter_langue(last_user.get("message", ""))
        return "fr"

    # ------------------------------------------------------------------
    # History building
    # ------------------------------------------------------------------

    def build_history(self, conversation: Any) -> List[Dict[str, str]]:
        """
        Build the conversation history for LLM consumption.

        - Loads ALL messages from repository
        - If total ≤ MAX_HISTORY → return all as-is
        - If total > MAX_HISTORY → summarize older, keep last MAX_HISTORY
        - Summarization is a pure logic step (caller provides the summarizer)
        """
        converted = self.repository.get_messages_for_prompt(conversation.pk)

        if not converted:
            return []

        if len(converted) <= MAX_HISTORY:
            return converted

        older = converted[:-MAX_HISTORY]
        recent = converted[-MAX_HISTORY:]

        return older, recent

    def format_history_with_summary(
        self,
        older: List[Dict[str, str]],
        recent: List[Dict[str, str]],
        summary: Optional[str],
    ) -> List[Dict[str, str]]:
        """
        Format history after summarization.

        If summary succeeded → prepend summary as system message + recent.
        If summary failed → just return recent messages.
        """
        if summary:
            logger.info(
                "Summarized %d older messages into %d chars",
                len(older),
                len(summary),
            )
            return [
                {"role": "system", "content": f"Résumé de la conversation précédente :\n{summary}"}
            ] + recent

        return recent

    # ------------------------------------------------------------------
    # Summarization text
    # ------------------------------------------------------------------

    def build_summarization_text(self, messages: List[Dict[str, str]]) -> str:
        """Build the conversation text for summarization."""
        return "\n".join(
            f"{'Utilisateur' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in messages
        )

    # ------------------------------------------------------------------
    # Prompt assembly
    # ------------------------------------------------------------------

    def assemble_prompt(
        self,
        system_prompt: str,
        history: List[Dict[str, str]],
        message: str,
    ) -> Dict[str, Any]:
        """
        Assemble the full prompt structure for LLM.

        Returns a dict with system_prompt, history, and message.
        """
        return {
            "system_prompt": system_prompt,
            "history": history,
            "message": message,
        }

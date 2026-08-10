"""
Intent Router — classifies user messages and extracts entities.

Responsibilities:
    - Intent detection (11 supported intents)
    - Entity extraction (waste codes, dates, names, etc.)
    - Confidence scoring
    - Tool routing
    - Fallback to UNKNOWN

Returns:
    {
        "intent": "nomenclature",
        "confidence": 0.92,
        "entities": [{"type": "waste_code", "value": "15.01.01"}],
        "tool": "nomenclature_tool"
    }
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Entity:
    """An extracted entity from the user message."""
    type: str
    value: str
    start: int = 0
    end: int = 0

    def to_dict(self) -> Dict[str, str]:
        return {"type": self.type, "value": self.value}


@dataclass
class RoutingDecision:
    """The output of the intent router."""
    intent: str
    confidence: float
    entities: List[Entity]
    tool: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "confidence": round(self.confidence, 2),
            "entities": [e.to_dict() for e in self.entities],
            "tool": self.tool,
        }


# ---------------------------------------------------------------------------
# Intent definitions
# ---------------------------------------------------------------------------

_INTENTS: Dict[str, Dict[str, Any]] = {
    "greeting": {
        "keywords_fr": [
            "bonjour", "salut", "hello", "coucou", "bonsoir", "bsr",
            "hey", "yo", "salam", "مرحبا", "سلام", "السلام", "أهلا", "هاي",
            "hi", "greetings", "good morning", "good evening",
        ],
        "patterns_fr": [r"\b(bonjour|salut|hey|hello|coucou|hi|greetings)\b"],
        "patterns_ar": ["مرحبا", "سلام", "السلام", "أهلا", "هاي"],
        "tool": "",
    },
    "question": {
        "keywords_fr": [
            "qu'est-ce", "quel", "quelle", "quels", "quelles", "comment",
            "pourquoi", "où", "quand", "combien", "est-ce que", "c'est quoi",
            "ما هو", "ما هي", "كيف", "لماذا", "أين", "متى", "كم",
            "what", "which", "how", "why", "where", "when", "how many",
            "can you", "do you", "is it", "are there",
        ],
        "patterns_fr": [
            r"\b(quel|quelle|quels|quelles|comment|pourquoi|où|quand|combien)\b",
            r"\b(what|which|how|why|where|when)\b",
        ],
        "tool": "",
    },
    "waste_search": {
        "keywords_fr": [
            "rechercher", "trouver", "chercher", "recherche",
            "famille", "catégorie",
            "نفايات", "بحث", "تصنيف",
            "search", "find", "look up", "waste",
        ],
        "patterns_fr": [
            r"\b(déchet|déchets|waste)\b.*\b(recherch|cherch|trouv|find|search)\b",
            r"\b(recherch|cherch|find|search)\b.*\b(déchet|déchets|waste)\b",
        ],
        "tool": "waste_tool",
    },
    "nomenclature": {
        "keywords_fr": [
            "nomenclature", "code", "codification", "classification", "famille",
            "15.01", "16.01", "20.01", "20.03", "17.01",
            "تصنيف", "ترقيم", "شفرة",
        ],
        "patterns_fr": [
            r"\b\d{1,2}\.\d{2}\.\d{2}\b",
            r"\b(code|nomenclature|codification)\b",
        ],
        "tool": "nomenclature_tool",
    },
    "declaration": {
        "keywords_fr": [
            "déclaration", "déclarer", "declaration", "déclaratif",
            "BSD", "bordereau", "bordereaux", "suivi", "tracking",
            "émission", "réception", "transport",
            "retard", "en retard", "conformité", "conformite",
            "بوليصة", "_statement", "تتبع",
            "declare", "declaration", "manifest", "shipment",
        ],
        "patterns_fr": [
            r"\b(BSD|bordereau|bordereaux)\b",
            r"\b(déclar|declar|declare)\b",
            r"\bBSD[- ]?\d{4,}\b",
        ],
        "tool": "declaration_tool",
    },
    "company": {
        "keywords_fr": [
            "entreprise", "société", "societe", "compagnie", "organisme",
            "établissement", "etablissement", "usine", "site",
            "شركة", "مؤسسة", "مصنع",
            "company", "companies", "business", "facility", "plant",
        ],
        "patterns_fr": [
            r"\b(entreprise|société|societe|compagnie|organisme)\b",
            r"\b(établissement|etablissement|usine|site)\b",
            r"\b(company|companies|business|facility|plant)\b",
        ],
        "tool": "entreprise_tool",
    },
    "partner": {
        "keywords_fr": [
            "partenaire", "récupérateur", "recuperateur", "transporteur",
            "collecteur", "traitant", "partenaire",
            "شريك", "منقّب", "ناقل", "处理",
            "partner", "transporter", "recycler", "handler",
        ],
        "patterns_fr": [
            r"\b(partenaire|récupérateur|recuperateur|transporteur|collecteur)\b",
            r"\b(partner|transporter|recycler|handler)\b",
        ],
        "tool": "partner_tool",
    },
    "report": {
        "keywords_fr": [
            "rapport", "rapports", "report", "bilan", "synthèse", "synthese",
            "compte-rendu", "pdf", "export", "générer", "generer",
            "تقرير", "تقرير",
            "reports", "summary", "generate", "export",
        ],
        "patterns_fr": [
            r"\b(rapport|rapports|report|bilan|synthèse|synthese)\b",
            r"\b(générer|generer|generate)\b.*\b(rapport|report)\b",
        ],
        "tool": "rapport_tool",
    },
    "statistics": {
        "keywords_fr": [
            "statistique", "statistiques", "stats", "chiffre", "chiffres",
            "données", "donnees", "métrique", "metrique", "indicateur",
            "graphique", "courbe", "tendance",
            "إحصائيات", "أرقام",
            "statistics", "metrics", "data", "figures", "numbers",
        ],
        "patterns_fr": [
            r"\b(statistiques?|stats?|chiffres?|données|donnees)\b",
            r"\b(statistics?|metrics?|figures?)\b",
        ],
        "tool": "statistiques_tool",
    },
    "regulation": {
        "keywords_fr": [
            "loi", "lois", "décret", "decret", "réglementation", "reglementation",
            "juridique", "juridiction", "légal", "legal", "norme",
            "conformité", "conformite", "réglementaire", "reglementaire",
            "loi 01-19", "décret 06-104", "décret 11-194",
            "قانون", "مرسوم", "تنظيم", "تشريع",
            "law", "decree", "regulation", "legal", "compliance", "norm",
        ],
        "patterns_fr": [
            r"\b(loi|lois|décret|decret|réglementation|reglementation)\b",
            r"\b(01-19|06-104|11-194)\b",
            r"\b(law|decree|regulation|compliance)\b",
        ],
        "tool": "reglementation_tool",
    },
}


# ---------------------------------------------------------------------------
# Entity extractors
# ---------------------------------------------------------------------------

_ENTITY_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("waste_code", re.compile(r"\b(\d{1,2}\.\d{2}\.\d{2})\b")),
    ("bsd_number", re.compile(r"\b(BSD[- ]?\d{4,})\b", re.IGNORECASE)),
    ("agrement_number", re.compile(r"\b(agré?ment[- ]?\d{3,})\b", re.IGNORECASE)),
    ("year", re.compile(r"\b(20[0-9]{2})\b")),
    ("percentage", re.compile(r"\b(\d+(?:[.,]\d+)?\s*%)\b")),
    ("quantity", re.compile(r"\b(\d+(?:[.,]\d+)?\s*(?:tonnes?|kg|tons?|kilos?))\b", re.IGNORECASE)),
    ("email", re.compile(r"\b([\w.+-]+@[\w-]+\.[\w.-]+)\b")),
    ("phone", re.compile(r"\b(\+?\d{10,13})\b")),
]


# ---------------------------------------------------------------------------
# Intent Router
# ---------------------------------------------------------------------------

class IntentRouter:
    """
    Rule-based intent router with entity extraction.

    Usage:
        router = IntentRouter()
        decision = router.route("Quel est le code nomenclature pour les huiles usagées ?")
        print(decision.to_dict())
        # {
        #     "intent": "nomenclature",
        #     "confidence": 0.95,
        #     "entities": [{"type": "waste_code", "value": "13.01.01"}],
        #     "tool": "nomenclature_tool"
        # }
    """

    def route(self, message: str) -> RoutingDecision:
        """
        Analyze a user message and return a routing decision.

        Args:
            message: The raw user message text.

        Returns:
            RoutingDecision with intent, confidence, entities, and tool.
        """
        if not message or not message.strip():
            return RoutingDecision(
                intent="unknown",
                confidence=1.0,
                entities=[],
                tool="",
            )

        msg_lower = message.lower().strip()
        entities = self._extract_entities(message)

        # Score each intent
        scores: List[Tuple[str, float]] = []
        for intent_name, intent_def in _INTENTS.items():
            score = self._score_intent(msg_lower, intent_def)
            if score > 0:
                scores.append((intent_name, score))

        # Pick the best match
        if not scores:
            return RoutingDecision(
                intent="unknown",
                confidence=0.5,
                entities=entities,
                tool="",
            )

        scores.sort(key=lambda x: x[1], reverse=True)
        best_intent, best_score = scores[0]

        # Normalize confidence to [0, 1]
        confidence = min(best_score, 1.0)

        tool = _INTENTS[best_intent].get("tool", "")

        return RoutingDecision(
            intent=best_intent,
            confidence=confidence,
            entities=entities,
            tool=tool,
        )

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_intent(self, msg_lower: str, intent_def: Dict[str, Any]) -> float:
        """Score how well the message matches an intent definition."""
        score = 0.0

        # Pattern matching — highest weight (specific matches)
        patterns_fr = intent_def.get("patterns_fr", [])
        for pattern in patterns_fr:
            if re.search(pattern, msg_lower):
                score += 0.5

        # Pattern matching (Arabic)
        patterns_ar = intent_def.get("patterns_ar", [])
        for pattern in patterns_ar:
            if pattern in msg_lower:
                score += 0.5

        # Keyword matching — lower weight (generic matches)
        keywords = intent_def.get("keywords_fr", [])
        keyword_hits = sum(1 for kw in keywords if kw in msg_lower)
        if keyword_hits:
            score += min(keyword_hits * 0.2, 0.6)

        return score

    # ------------------------------------------------------------------
    # Entity extraction
    # ------------------------------------------------------------------

    def _extract_entities(self, message: str) -> List[Entity]:
        """Extract all recognizable entities from the message."""
        entities: List[Entity] = []
        seen = set()

        for entity_type, pattern in _ENTITY_PATTERNS:
            for match in pattern.finditer(message):
                value = match.group(1)
                key = (entity_type, value)
                if key not in seen:
                    seen.add(key)
                    entities.append(Entity(
                        type=entity_type,
                        value=value,
                        start=match.start(),
                        end=match.end(),
                    ))

        return entities


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_router: Optional[IntentRouter] = None


def route_message(message: str) -> Dict[str, Any]:
    """
    Quick routing function.

    Returns:
        {"intent": "...", "confidence": 0.0, "entities": [...], "tool": "..."}
    """
    global _router
    if _router is None:
        _router = IntentRouter()
    return _router.route(message).to_dict()

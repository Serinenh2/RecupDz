"""
Prompt template engine.

Templates are plain-text files with `{variable}` placeholders.
The PromptRegistry manages named templates and renders them safely.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------

_TEMPLATE_VAR_RE = re.compile(r"\{(\w+)\}")


@dataclass
class PromptTemplate:
    """A named, versioned prompt template with typed variables."""
    name: str
    template: str
    description: str = ""
    required_vars: List[str] = field(default_factory=list)
    optional_vars: List[str] = field(default_factory=list)
    version: int = 1

    def __post_init__(self) -> None:
        if not self.required_vars:
            self.required_vars = sorted(set(_TEMPLATE_VAR_RE.findall(self.template)))
        return

    def render(self, **kwargs: Any) -> str:
        """Render the template, raising on missing required variables."""
        missing = [v for v in self.required_vars if v not in kwargs and v not in self.optional_vars]
        if missing:
            raise ValueError(f"Template '{self.name}' missing required vars: {missing}")
        rendered = self.template
        for key, value in kwargs.items():
            rendered = rendered.replace(f"{{{key}}}", str(value))
        return rendered

    def extract_vars(self) -> List[str]:
        """Return all variable names found in the template."""
        return sorted(set(_TEMPLATE_VAR_RE.findall(self.template)))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class PromptRegistry:
    """Thread-safe registry of named prompt templates."""

    def __init__(self) -> None:
        self._templates: Dict[str, PromptTemplate] = {}
        self._register_builtins()

    # -- public API --

    def register(self, template: PromptTemplate) -> None:
        self._templates[template.name] = template
        logger.debug("Registered prompt template: %s v%d", template.name, template.version)

    def get(self, name: str) -> PromptTemplate:
        try:
            return self._templates[name]
        except KeyError:
            raise KeyError(f"Prompt template '{name}' not found. Available: {list(self._templates.keys())}")

    def render(self, name: str, **kwargs: Any) -> str:
        template = self.get(name)
        return template.render(**kwargs)

    def list_templates(self) -> List[str]:
        return sorted(self._templates.keys())

    def has(self, name: str) -> bool:
        return name in self._templates

    # -- built-in templates --

    def _register_builtins(self) -> None:
        for tpl in _BUILTIN_TEMPLATES:
            self.register(tpl)


# ---------------------------------------------------------------------------
# Built-in Templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = PromptTemplate(
    name="system_prompt",
    description="Base system prompt for the LLM.",
    template=(
        "Tu es un assistant IA intelligent et serviable. "
        "Tu réponds toujours dans la langue de l'utilisateur. "
        "Tu es précis, concis et professionnel. "
        "Si tu ne connais pas la réponse, dis-le honnêtement.\n\n"
        "{custom_instructions}"
    ),
    optional_vars=["custom_instructions"],
)

INTENT_CLASSIFICATION = PromptTemplate(
    name="intent_classification",
    description="Classify user intent from a message.",
    template=(
        "Classifie l'intention de l'utilisateur dans le message suivant.\n\n"
        "Intentions possibles: greeting, question, command, clarification, chitchat, "
        "entity_lookup, analysis, recommendation\n\n"
        "Message: {user_message}\n\n"
        "Réponds UNIQUEMENT avec un JSON:\n"
        '{{"intent": "<intention>", "confidence": <0.0-1.0>, '
        '"entities": {{}}, "tool_hint": "<tool_name_or_null>"}}'
    ),
    required_vars=["user_message"],
)

PLANNING_PROMPT = PromptTemplate(
    name="planning",
    description="Create an execution plan from user message + context.",
    template=(
        "Tu es un planificateur de tâches. Décompose la demande en étapes exécutables.\n\n"
        "OUTILS DISPONIBLES:\n{available_tools}\n\n"
        "CONTEXTE:\n{context}\n\n"
        "DEMANDE UTILISATEUR:\n{user_message}\n\n"
        "Réponds UNIQUEMENT avec un JSON:\n"
        '{{"steps": [{{"id": "step_1", "tool_name": "<tool>", "description": "<desc>", '
        '"parameters": {{}}}}], "reasoning": "<explication>"}}'
    ),
    required_vars=["available_tools", "context", "user_message"],
)

REASONING_PROMPT = PromptTemplate(
    name="reasoning",
    description="Chain-of-thought reasoning about a plan.",
    template=(
        "Analyse le plan d'exécution suivant et vérifie sa cohérence.\n\n"
        "PLAN:\n{plan}\n\n"
        "CONTEXTE:\n{context}\n\n"
        "Raisonne étape par étape:\n"
        "1. Le plan est-il adapté à la demande ?\n"
        "2. Y a-t-il des étapes manquantes ?\n"
        "3. L'ordre est-il correct ?\n"
        "4. Des ajustements sont-ils nécessaires ?\n\n"
        "Réponds UNIQUEMENT avec un JSON:\n"
        '{{"chain_of_thought": ["<étape1>", "<étape2>"], '
        '"conclusion": "<résumé>", "confidence": <0.0-1.0>, '
        '"adjustments": {{"steps_to_add": [], "steps_to_remove": [], "steps_to_modify": {{}}}}}}'
    ),
    required_vars=["plan", "context"],
)

RESPONSE_FORMATTING = PromptTemplate(
    name="response_formatting",
    description="Format raw results into a user-friendly response.",
    template=(
        "Formate les résultats suivants en une réponse claire et utile.\n\n"
        "RÉSULTATS:\n{results}\n\n"
        "DEMANDE ORIGINALE:\n{user_message}\n\n"
        "LANGUE: {language}\n\n"
        "Consignes:\n"
        "- Réponds dans la langue spécifiée\n"
        "- Sois concis mais complet\n"
        "- Utilise un ton professionnel\n"
        "- Structure ta réponse avec desparagraphes si nécessaire\n"
    ),
    required_vars=["results", "user_message", "language"],
)

CLARIFICATION_PROMPT = PromptTemplate(
    name="clarification",
    description="Generate a clarification question when intent is unclear.",
    template=(
        "L'intention de l'utilisateur n'est pas claire.\n\n"
        "Message: {user_message}\n\n"
        "Génère une question de clarification polie en {language} "
        "pour mieux comprendre le besoin."
    ),
    required_vars=["user_message", "language"],
)

ERROR_RESPONSE = PromptTemplate(
    name="error_response",
    description="Generate a user-friendly error message.",
    template=(
        "Une erreur s'est produite lors du traitement de la demande.\n\n"
        "Erreur: {error_message}\n\n"
        "Génère un message d'erreur poli et utile en {language}."
    ),
    required_vars=["error_message", "language"],
)

HEALTH_CHECK_PROMPT = PromptTemplate(
    name="health_check",
    description="Simple prompt to verify LLM availability.",
    template="Réponds simplement avec 'pong'.",
)

_SUMMARY_TEMPLATE = PromptTemplate(
    name="conversation_summary",
    description="Summarise a conversation for long-term memory.",
    template=(
        "Résume cette conversation en 2-3 phrases clés:\n\n"
        "{conversation}\n\n"
        "Résumé:"
    ),
    required_vars=["conversation"],
)

_BUILTIN_TEMPLATES: List[PromptTemplate] = [
    _SYSTEM_PROMPT,
    INTENT_CLASSIFICATION,
    PLANNING_PROMPT,
    REASONING_PROMPT,
    RESPONSE_FORMATTING,
    CLARIFICATION_PROMPT,
    ERROR_RESPONSE,
    HEALTH_CHECK_PROMPT,
    _SUMMARY_TEMPLATE,
]

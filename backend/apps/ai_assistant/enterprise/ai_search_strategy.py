"""
AI Search Strategy — automatic multi-source search for short queries.

When the user sends only a word, code, number, or short expression,
searches automatically across all knowledge sources in priority order:

    1. Glossary        — terminology, definitions, abbreviations
    2. Nomenclature    — waste classification codes
    3. Regulations     — laws, decrees, referentiels
    4. Procedures      — operational procedures
    5. Traceability    — waste recovery operations
    6. Reports         — operational report generation

Returns the best match. If multiple close matches exist,
generates a clarification question so the user can pick.

Integration:
    Orchestrator → AISearchStrategy.is_short_query() → .search()
                 → SearchResult (best match or clarification)

Design:
    - Zero LLM calls — fully deterministic scoring
    - Each source returns a SearchSourceResult with score
    - Best match wins if score >= threshold and gap >= margin
    - Clarification generated if top-2 results are too close
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SearchSourceResult:
    """Result from a single knowledge source search."""

    source: str          # "glossary" | "nomenclature" | "regulation" | "procedure" | "traceability" | "report"
    tool: str            # tool name to execute
    action: str          # tool action
    parameters: Dict[str, Any] = field(default_factory=dict)
    matches: List[Dict[str, Any]] = field(default_factory=list)
    score: float = 0.0   # 0.0 - 1.0
    label: str = ""      # human-readable label

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "tool": self.tool,
            "action": self.action,
            "parameters": self.parameters,
            "match_count": len(self.matches),
            "score": round(self.score, 3),
            "label": self.label,
        }


@dataclass(frozen=True)
class SearchResult:
    """Complete search result across all sources."""

    query: str
    is_short: bool
    best_match: Optional[SearchSourceResult] = None
    all_matches: List[SearchSourceResult] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    clarification_options: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def has_result(self) -> bool:
        return self.best_match is not None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "is_short": self.is_short,
            "has_result": self.has_result,
            "best_match": self.best_match.to_dict() if self.best_match else None,
            "all_matches": [m.to_dict() for m in self.all_matches],
            "needs_clarification": self.needs_clarification,
            "clarification_question": self.clarification_question,
            "clarification_options": self.clarification_options,
        }


# ---------------------------------------------------------------------------
# Short Query Detection
# ---------------------------------------------------------------------------

# Patterns that indicate a code/reference query
_CODE_PATTERNS = [
    re.compile(r"^\d{1,2}\.\d{2}\.\d{2}$"),              # 15.01.06
    re.compile(r"^\d{1,2}\.\d{2}$"),                       # 15.01
    re.compile(r"^\d{1,3}\.\d{1,3}(\.\d{1,3})?$"),        # 1.3.1, 10.2
    re.compile(r"^[A-Z]{2,5}[- ]?\d{4,}", re.IGNORECASE), # BSD-2024-001
    re.compile(r"^[A-Z]{2,5}/\d+", re.IGNORECASE),        # ART/2024/001
]

# Stop words that indicate a natural language query (not a search)
_STOP_WORDS = {
    "bonjour", "salut", "hello", "merci", "aujourd'hui",
    "comment", "pourquoi", "quest-ce", "quel", "quelle",
    "quels", "quelles", "peux", "pouvez", "fais", "fait",
    "aide", "aidez", "expliquer", "dire", "lire", "ecrire",
    "oui", "non", "ok", "daccord", "bien", "mal",
    "le", "la", "les", "un", "une", "des", "du", "de", "d",
    "ce", "cette", "ces", "mon", "ma", "mes", "ton", "ta", "tes",
    "son", "sa", "ses", "notre", "votre", "leur",
    "je", "tu", "il", "elle", "nous", "vous", "ils", "elles",
    "me", "te", "se", "lui", "leur", "y", "en",
    "est", "sont", "ete", "avoir", "etre", "faire",
    "dans", "sur", "sous", "avec", "pour", "par", "sans",
    "ou", "et", "mais", "donc", "car", "ni",
    "aussi", "tres", "trop", "peu", "bien", "mieux",
}


def is_short_query(message: str) -> bool:
    """Detect if a message is a short search query.

    Returns True for:
        - Single word: "BSD", "dechets", "nomenclature"
        - Code pattern: "15.01.06", "BSD-2024-001"
        - Number: "2024", "100"
        - Short expression (<= 4 words, no sentence structure)

    Returns False for:
        - Full sentences with verb/subject
        - Questions (contains "?"  with > 3 words)
        - Long text (> 4 words)
        - Greetings and conversation starters
    """
    if not message or not isinstance(message, str):
        return False

    text = message.strip()

    # Empty or too short
    if len(text) < 1:
        return False

    # Check if it's a code pattern (highest priority)
    for pattern in _CODE_PATTERNS:
        if pattern.match(text):
            return True

    # Pure number
    if text.replace(".", "").replace(",", "").replace(" ", "").isdigit():
        return True

    words = text.split()

    # Single word — always a search query (unless stop word)
    if len(words) == 1:
        word_lower = words[0].lower().strip("?.!,;:")
        return word_lower not in _STOP_WORDS

    # 2-4 words — check if it looks like a natural language query
    if len(words) <= 4:
        # If it ends with "?" and has > 2 words, likely a question
        if text.rstrip().endswith("?") and len(words) > 2:
            return False

        # If all words are stop words, it's conversation
        if all(w.lower().strip("?.!,;:") in _STOP_WORDS for w in words):
            return False

        # Otherwise treat as short search expression
        return True

    # 5+ words — not a short query
    return False


# ---------------------------------------------------------------------------
# Source Search Functions
# ---------------------------------------------------------------------------

def _search_glossary(
    query: str,
    glossary_repo: Any,
) -> SearchSourceResult:
    """Search glossary for terminology and definitions."""
    matches = []
    score = 0.0

    try:
        # 1. Try exact definition first (highest score)
        definition = glossary_repo.get_definition(query)
        if definition:
            matches.append(definition)
            score = 1.0

        # 2. Try scored search
        search_results = glossary_repo.search(query, limit=5)
        for r in search_results:
            if not any(m.get("terme_fr") == r.get("terme_fr") for m in matches):
                matches.append(r)
                if score == 0.0:
                    score = max(0.7, 1.0 - len(matches) * 0.1)

        # 3. Try similar terms
        if not matches:
            similar = glossary_repo.search_similar(query, limit=3)
            matches.extend(similar)
            if similar:
                score = 0.4

    except Exception as exc:
        logger.debug("Glossary search failed: %s", exc)

    return SearchSourceResult(
        source="glossary",
        tool="glossaire_tool",
        action="search" if len(matches) != 1 else "get_definition",
        parameters={"query": query} if len(matches) != 1 else {"term": query},
        matches=matches,
        score=min(score, 1.0),
        label="Glossaire" if matches else "",
    )


def _search_nomenclature(
    query: str,
    nomenclature_repo: Any,
) -> SearchSourceResult:
    """Search nomenclature for waste classification codes."""
    matches = []
    score = 0.0

    try:
        # 1. Try exact code match
        if re.match(r"^\d{1,2}\.\d{2}(\.\d{2})?$", query.replace(" ", ".")):
            exact = nomenclature_repo.get_by_code(query.replace(" ", "."))
            if exact:
                matches.append(exact)
                score = 1.0

        # 2. Try search by code/designation
        if not matches:
            search_results = nomenclature_repo.search(query, limit=5)
            matches.extend(search_results)
            if search_results:
                # Exact code match in results gets higher score
                for i, r in enumerate(search_results):
                    if r.get("code", "").replace(".", "") == query.replace(".", "").replace(" ", ""):
                        score = max(score, 0.95)
                    elif i == 0:
                        score = max(score, 0.7)

        # 3. Try similar codes
        if not matches:
            similar = nomenclature_repo.search_similar(query, limit=3)
            matches.extend(similar)
            if similar:
                score = 0.4

    except Exception as exc:
        logger.debug("Nomenclature search failed: %s", exc)

    return SearchSourceResult(
        source="nomenclature",
        tool="nomenclature_tool",
        action="search_by_code" if score >= 0.9 else "search",
        parameters={"code": query} if score >= 0.9 else {"term": query},
        matches=matches,
        score=min(score, 1.0),
        label="Nomenclature" if matches else "",
    )


def _search_regulation(
    query: str,
    knowledge_repo: Any,
) -> SearchSourceResult:
    """Search regulatory knowledge base (laws, decrees, referentiels)."""
    matches = []
    score = 0.0

    try:
        # 1. Try exact reference match
        if re.match(r"^[A-Z]", query) and len(query) <= 20:
            exact = knowledge_repo.get_by_reference(query)
            if exact:
                matches.append(exact)
                score = 1.0

        # 2. Try search across LOI, DECRET, REFERENTIEL categories
        if not matches:
            search_results = knowledge_repo.search(query, limit=5)
            # Filter to regulatory categories
            regulatory = [
                r for r in search_results
                if r.get("categorie") in ("LOI", "DECRET", "REFERENTIEL", None, "")
            ]
            matches.extend(regulatory[:5])
            if regulatory:
                score = 0.6

        # 3. Try category-specific search
        if not matches:
            for cat in ("LOI", "DECRET", "REFERENTIEL"):
                cat_results = knowledge_repo.filter_by_category(cat, limit=3)
                for r in cat_results:
                    content = (r.get("contenu", "") + " " + r.get("titre", "")).lower()
                    if query.lower() in content:
                        matches.append(r)
                        if score == 0.0:
                            score = 0.5

    except Exception as exc:
        logger.debug("Regulation search failed: %s", exc)

    return SearchSourceResult(
        source="regulation",
        tool="reglementation_tool",
        action="by_reference" if score >= 0.9 else "search",
        parameters={"reference": query} if score >= 0.9 else {"query": query},
        matches=matches,
        score=min(score, 1.0),
        label="Réglementation" if matches else "",
    )


def _search_procedure(
    query: str,
    knowledge_repo: Any,
) -> SearchSourceResult:
    """Search operational procedures."""
    matches = []
    score = 0.0

    try:
        # Search in PROCEDURE category
        procedures = knowledge_repo.filter_by_category("PROCEDURE", limit=10)
        for p in procedures:
            content = (p.get("contenu", "") + " " + p.get("titre", "")).lower()
            if query.lower() in content:
                matches.append(p)
                if score == 0.0:
                    score = 0.6

        # Also search GUIDE category
        if not matches:
            guides = knowledge_repo.filter_by_category("GUIDE", limit=10)
            for g in guides:
                content = (g.get("contenu", "") + " " + g.get("titre", "")).lower()
                if query.lower() in content:
                    matches.append(g)
                    if score == 0.0:
                        score = 0.5

    except Exception as exc:
        logger.debug("Procedure search failed: %s", exc)

    return SearchSourceResult(
        source="procedure",
        tool="reglementation_tool",
        action="by_category",
        parameters={"categorie": "PROCEDURE", "query": query},
        matches=matches,
        score=min(score, 1.0),
        label="Procédures" if matches else "",
    )


def _search_traceability(
    query: str,
    traceability_repo: Any,
) -> SearchSourceResult:
    """Search waste recovery operations."""
    matches = []
    score = 0.0

    try:
        # 1. Try exact numero match
        if re.match(r"^[A-Z]{0,3}[- ]?\d{4,}", query, re.IGNORECASE):
            exact = traceability_repo.get_by_numero(query)
            if exact:
                matches.append(exact)
                score = 1.0

        # 2. Try search
        if not matches:
            search_results = traceability_repo.search(query, limit=5)
            matches.extend(search_results)
            if search_results:
                score = 0.5

    except Exception as exc:
        logger.debug("Traceability search failed: %s", exc)

    return SearchSourceResult(
        source="traceability",
        tool="traceability_tool",
        action="get_by_numero" if score >= 0.9 else "search",
        parameters={"numero": query} if score >= 0.9 else {"query": query},
        matches=matches,
        score=min(score, 1.0),
        label="Traçabilité" if matches else "",
    )


def _search_report(
    query: str,
    traceability_repo: Any,
    nomenclature_repo: Any,
) -> SearchSourceResult:
    """Search for report-related data."""
    matches = []
    score = 0.0

    try:
        # Check if query looks like a report request
        report_keywords = {
            "rapport", "report", "statistiques", "stats", "bilan",
            "resumé", "resume", "synthese", "synthèse", "somme",
            "total", "quantité", "quantite", "tonnage",
        }
        query_lower = query.lower()

        is_report_query = any(kw in query_lower for kw in report_keywords)
        if not is_report_query:
            return SearchSourceResult(
                source="report",
                tool="rapport_tool",
                action="waste_report",
                parameters={},
                matches=[],
                score=0.0,
                label="",
            )

        # Try waste report
        dangerous = nomenclature_repo.filter_dangerous(limit=5)
        if dangerous:
            matches.extend(dangerous)
            score = 0.5

        # Try traceability summary
        total = traceability_repo.sum_quantities()
        if total > 0:
            matches.append({"total_quantity": total, "type": "summary"})
            score = max(score, 0.4)

    except Exception as exc:
        logger.debug("Report search failed: %s", exc)

    return SearchSourceResult(
        source="report",
        tool="rapport_tool",
        action="waste_report",
        parameters={"classe": query} if score > 0 else {},
        matches=matches,
        score=min(score, 1.0),
        label="Rapports" if matches else "",
    )


# ---------------------------------------------------------------------------
# Search Strategy
# ---------------------------------------------------------------------------

# Minimum score to consider a match as "best"
BEST_MATCH_THRESHOLD: float = 0.5

# Minimum gap between top-2 to avoid clarification
CLARIFICATION_GAP: float = 0.15


class AISearchStrategy:
    """Automatic multi-source search for short queries.

    Search order:
        1. Glossary        — terminology, definitions, abbreviations
        2. Nomenclature    — waste classification codes
        3. Regulations     — laws, decrees, referentiels
        4. Procedures      — operational procedures
        5. Traceability    — waste recovery operations
        6. Reports         — operational report generation

    Features:
        - Zero LLM calls — fully deterministic scoring
        - Each source returns a SearchSourceResult with score
        - Best match wins if score >= threshold and gap >= margin
        - Clarification generated if top-2 results are too close
    """

    def __init__(self, container: Any = None) -> None:
        self._container = container

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(self, message: str) -> SearchResult:
        """Search all knowledge sources for a short query.

        Returns SearchResult with best_match (if clear winner)
        or clarification_question (if ambiguous).
        """
        query = message.strip()

        if not self.is_short_query(query):
            return SearchResult(
                query=query,
                is_short=False,
                best_match=None,
                all_matches=[],
                needs_clarification=False,
            )

        # Execute searches in priority order
        all_results = self._search_all_sources(query)

        # Filter to results with matches
        valid_results = [r for r in all_results if r.matches]

        if not valid_results:
            return SearchResult(
                query=query,
                is_short=True,
                best_match=None,
                all_matches=[],
                needs_clarification=False,
            )

        # Determine best match
        best, needs_clarification, question, options = self._rank_results(
            query, valid_results,
        )

        return SearchResult(
            query=query,
            is_short=True,
            best_match=best,
            all_matches=valid_results,
            needs_clarification=needs_clarification,
            clarification_question=question,
            clarification_options=options,
        )

    @staticmethod
    def is_short_query(message: str) -> bool:
        """Detect if a message is a short search query."""
        return is_short_query(message)

    # ------------------------------------------------------------------
    # Internal: Search All Sources
    # ------------------------------------------------------------------

    def _search_all_sources(self, query: str) -> List[SearchSourceResult]:
        """Execute searches across all 6 sources in priority order."""
        results: List[SearchSourceResult] = []

        # Lazy-load repositories (no Django imports until needed)
        glossary_repo = self._get_glossary_repo()
        nomenclature_repo = self._get_nomenclature_repo()
        knowledge_repo = self._get_knowledge_repo()
        traceability_repo = self._get_traceability_repo()

        # 1. Glossary (highest priority for terminology)
        r = _search_glossary(query, glossary_repo)
        results.append(r)

        # 2. Nomenclature (code classification)
        r = _search_nomenclature(query, nomenclature_repo)
        results.append(r)

        # 3. Regulations (laws, decrees)
        r = _search_regulation(query, knowledge_repo)
        results.append(r)

        # 4. Procedures (operational guides)
        r = _search_procedure(query, knowledge_repo)
        results.append(r)

        # 5. Traceability (operations tracking)
        r = _search_traceability(query, traceability_repo)
        results.append(r)

        # 6. Reports (report generation)
        r = _search_report(query, traceability_repo, nomenclature_repo)
        results.append(r)

        return results

    # ------------------------------------------------------------------
    # Internal: Ranking & Clarification
    # ------------------------------------------------------------------

    def _rank_results(
        self,
        query: str,
        results: List[SearchSourceResult],
    ) -> Tuple[Optional[SearchSourceResult], bool, Optional[str], List[Dict[str, Any]]]:
        """Rank results and determine if clarification is needed.

        Returns: (best_match, needs_clarification, question, options)
        """
        if not results:
            return None, False, None, []

        # Sort by score descending, then by priority (source order)
        source_priority = {
            "glossary": 0,
            "nomenclature": 1,
            "regulation": 2,
            "procedure": 3,
            "traceability": 4,
            "report": 5,
        }
        sorted_results = sorted(
            results,
            key=lambda r: (-r.score, source_priority.get(r.source, 99)),
        )

        best = sorted_results[0]

        # No match above threshold
        if best.score < BEST_MATCH_THRESHOLD:
            return best, False, None, []

        # Single match — clear winner
        if len(sorted_results) < 2:
            return best, False, None, []

        second = sorted_results[1]
        gap = best.score - second.score

        # Clear winner (gap >= threshold)
        if gap >= CLARIFICATION_GAP:
            return best, False, None, []

        # Close match — clarification needed
        options = self._build_clarification_options(sorted_results[:3])
        question = self._format_clarification_question(query, options)
        return best, True, question, [o.to_dict() for o in options]

    def _build_clarification_options(
        self,
        results: List[SearchSourceResult],
    ) -> List[ClarificationOption]:
        """Build clarification options from top search results."""
        options = []
        for r in results:
            label = r.label or r.source
            if r.matches:
                # Add first match name as context
                first_match = r.matches[0]
                name = (
                    first_match.get("terme_fr")
                    or first_match.get("designation_fr")
                    or first_match.get("titre")
                    or first_match.get("numero")
                    or ""
                )
                if name:
                    label = f"{label} — {name[:50]}"

            options.append(ClarificationOption(
                label=label,
                tool=r.tool,
                action=r.action,
                parameters=r.parameters,
                confidence=r.score,
            ))
        return options

    @staticmethod
    def _format_clarification_question(
        query: str,
        options: List[ClarificationOption],
    ) -> str:
        """Format a French clarification question."""
        numbered = "\n".join(
            f"  {i}. {opt.label}" for i, opt in enumerate(options, 1)
        )
        return (
            f"J'ai trouvé plusieurs interprétations possibles pour « {query} ».\n"
            f"Est-ce :\n{numbered}\n\n"
            f"Répondez avec le numéro de votre choix ou décrivez ce que vous recherchez."
        )

    # ------------------------------------------------------------------
    # Internal: Repository Access (lazy, no Django imports at module level)
    # ------------------------------------------------------------------

    def _get_glossary_repo(self) -> Any:
        from apps.ai_assistant.repositories.glossary_repository import GlossaryRepository
        return GlossaryRepository()

    def _get_nomenclature_repo(self) -> Any:
        from apps.ai_assistant.repositories.nomenclature_repository import NomenclatureRepository
        return NomenclatureRepository()

    def _get_knowledge_repo(self) -> Any:
        from apps.ai_assistant.repositories.knowledge_repository import KnowledgeBaseRepository
        return KnowledgeBaseRepository()

    def _get_traceability_repo(self) -> Any:
        from apps.ai_assistant.repositories.traceability_repository import TraceabilityRepository
        return TraceabilityRepository()


# ---------------------------------------------------------------------------
# Convenience function (matches pattern used by reference_classifier)
# ---------------------------------------------------------------------------

def search_short_query(
    message: str,
    container: Any = None,
) -> SearchResult:
    """Search all knowledge sources for a short query.

    Module-level convenience function matching the pattern
    established by reference_classifier.classify_reference().
    """
    strategy = AISearchStrategy(container=container)
    return strategy.search(message)


# Re-export ClarificationOption for type checking
from apps.ai_assistant.enterprise.clarification_manager import ClarificationOption  # noqa: E402

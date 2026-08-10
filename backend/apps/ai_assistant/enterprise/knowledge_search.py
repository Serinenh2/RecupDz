"""
Knowledge Search Engine — ranked multi-source knowledge retrieval.

Responsibilities:
    - Search across 7 knowledge sources in priority order.
    - Keyword search (TF-IDF-like scoring).
    - Semantic search (vector cosine similarity).
    - Hybrid search (weighted blend of keyword + semantic).
    - Confidence scoring per result.
    - Ranked SearchResults with source attribution.

Architecture:
    KnowledgeSearchEngine accepts **repository interfaces** as injected
    callables.  It NEVER imports or queries business modules directly.

    Repository interface protocol:
        Each source is a callable: (query: str, limit: int) -> List[Dict]

    Search priority (descending):
        1. Glossary
        2. Nomenclature
        3. Regulations
        4. Procedures
        5. Internal Documents
        6. Reports
        7. General LLM knowledge (fallback)

Design rules:
    - Zero Django imports.
    - Zero repository imports.
    - Zero business logic — only search, scoring, ranking.
    - All repositories injected as callables.
"""

from __future__ import annotations

import logging
import math
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════

_DEFAULT_LIMIT: int = 10
_DEFAULT_MAX_RESULTS: int = 20
_CONFIDENCE_HIGH: float = 0.80
_CONFIDENCE_MEDIUM: float = 0.50
_CONFIDENCE_LOW: float = 0.20
_KEYWORD_WEIGHT: float = 0.6
_SEMANTIC_WEIGHT: float = 0.4
_MIN_SCORE: float = 0.01

# ── Source priorities (lower number = higher priority) ────────────────

PRIORITY_GLOSSARY: int = 1
PRIORITY_NOMENCLATURE: int = 2
PRIORITY_REGULATIONS: int = 3
PRIORITY_PROCEDURES: int = 4
PRIORITY_INTERNAL_DOCS: int = 5
PRIORITY_REPORTS: int = 6
PRIORITY_LLM_KNOWLEDGE: int = 7

_SOURCE_PRIORITIES: Dict[str, int] = {
    "glossary": PRIORITY_GLOSSARY,
    "nomenclature": PRIORITY_NOMENCLATURE,
    "regulation": PRIORITY_REGULATIONS,
    "regulations": PRIORITY_REGULATIONS,
    "procedure": PRIORITY_PROCEDURES,
    "procedures": PRIORITY_PROCEDURES,
    "internal_document": PRIORITY_INTERNAL_DOCS,
    "internal_documents": PRIORITY_INTERNAL_DOCS,
    "report": PRIORITY_REPORTS,
    "reports": PRIORITY_REPORTS,
    "llm_knowledge": PRIORITY_LLM_KNOWLEDGE,
    "general": PRIORITY_LLM_KNOWLEDGE,
}

_SOURCE_LABELS: Dict[str, str] = {
    "glossary": "Glossaire",
    "nomenclature": "Nomenclature",
    "regulation": "Réglementation",
    "regulations": "Réglementation",
    "procedure": "Procédures",
    "procedures": "Procédures",
    "internal_document": "Documents internes",
    "internal_documents": "Documents internes",
    "report": "Rapports",
    "reports": "Rapports",
    "llm_knowledge": "Connaissances générales",
    "general": "Connaissances générales",
}

# ── Scoring weights ──────────────────────────────────────────────────

_WEIGHT_EXACT_MATCH: float = 1.0
_WEIGHT_PREFIX_MATCH: float = 0.85
_WEIGHT_CONTAINS_MATCH: float = 0.65
_WEIGHT_PARTIAL_MATCH: float = 0.40
_WEIGHT_FUZZY_MATCH: float = 0.25

# ── Common French/English stop words for keyword extraction ───────────

_STOP_WORDS: Tuple[str, ...] = (
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "ou",
    "est", "sont", "a", "ai", "as", "avons", "avez", "ont",
    "que", "qui", "quoi", "quel", "quelle", "quels", "quelles",
    "comment", "pourquoi", "combien", "quand", "où",
    "je", "tu", "il", "elle", "nous", "vous", "ils", "elles",
    "me", "te", "se", "lui", "leur", "leurs",
    "dans", "sur", "sous", "avec", "sans", "pour", "par",
    "pas", "ne", "plus", "moins", "très", "bien",
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did",
    "what", "which", "who", "whom", "where", "when", "why", "how",
    "i", "you", "he", "she", "it", "we", "they",
    "my", "your", "his", "her", "its", "our", "their",
    "this", "that", "these", "those",
    "in", "on", "at", "to", "for", "of", "with", "by", "from",
)

_STOP_WORDS_SET: frozenset = frozenset(_STOP_WORDS)


# ══════════════════════════════════════════════════════════════════════
# Enums
# ══════════════════════════════════════════════════════════════════════


class SearchMode(str, Enum):
    """Search strategy selection."""

    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


# ══════════════════════════════════════════════════════════════════════
# Data Contracts
# ══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class KnowledgeHit:
    """
    A single search hit from one knowledge source.

    Attributes:
        source: Source identifier (glossary, nomenclature, etc.).
        title: Document or entry title.
        content: Matching text excerpt.
        score: Relevance score (0.0 – 1.0).
        confidence: Confidence in the score (0.0 – 1.0).
        match_type: How the match was found (exact, prefix, contains, etc.).
        metadata: Additional source-specific data.
        reference: Optional reference code or identifier.
        category: Optional category or classification.
    """

    source: str
    title: str
    content: str = ""
    score: float = 0.0
    confidence: float = 0.0
    match_type: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    reference: str = ""
    category: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "source": self.source,
            "title": self.title,
            "score": round(self.score, 4),
            "confidence": round(self.confidence, 4),
        }
        if self.content:
            d["content"] = self.content[:500]
        if self.match_type:
            d["match_type"] = self.match_type
        if self.reference:
            d["reference"] = self.reference
        if self.category:
            d["category"] = self.category
        if self.metadata:
            d["metadata"] = self.metadata
        return d


@dataclass(frozen=True)
class SourceResult:
    """
    Aggregated results from a single knowledge source.

    Groups all KnowledgeHits from one source with an aggregate score.
    """

    source: str
    label: str
    priority: int
    hits: List[KnowledgeHit] = field(default_factory=list)
    aggregate_score: float = 0.0
    elapsed_ms: float = 0.0

    @property
    def hit_count(self) -> int:
        return len(self.hits)

    @property
    def has_results(self) -> bool:
        return len(self.hits) > 0

    @property
    def best_hit(self) -> Optional[KnowledgeHit]:
        if not self.hits:
            return None
        return max(self.hits, key=lambda h: h.score)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "source": self.source,
            "label": self.label,
            "priority": self.priority,
            "hit_count": self.hit_count,
            "aggregate_score": round(self.aggregate_score, 4),
            "elapsed_ms": round(self.elapsed_ms, 2),
        }
        if self.hits:
            d["hits"] = [h.to_dict() for h in self.hits[:5]]
        return d


@dataclass(frozen=True)
class SearchResults:
    """
    Complete search results across all knowledge sources.

    Ranked by aggregate score.  Contains per-source breakdowns
    and the overall best matches.
    """

    query: str
    mode: str = "hybrid"
    sources: List[SourceResult] = field(default_factory=list)
    total_hits: int = 0
    total_elapsed_ms: float = 0.0
    searched_sources: List[str] = field(default_factory=list)

    @property
    def has_results(self) -> bool:
        return self.total_hits > 0

    @property
    def best_source(self) -> Optional[SourceResult]:
        """Highest-priority source with results."""
        with_results = [s for s in self.sources if s.has_results]
        if not with_results:
            return None
        return min(with_results, key=lambda s: s.priority)

    @property
    def best_hit(self) -> Optional[KnowledgeHit]:
        """Single best hit across all sources."""
        best = self.best_source
        if best is None:
            return None
        return best.best_hit

    @property
    def confidence(self) -> float:
        """Overall confidence based on best hit score and source priority."""
        bh = self.best_hit
        if bh is None:
            return 0.0
        priority_bonus = max(0.0, (7 - bh.score * 7) * 0.02)
        return min(1.0, bh.score + priority_bonus)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "query": self.query,
            "mode": self.mode,
            "total_hits": self.total_hits,
            "total_elapsed_ms": round(self.total_elapsed_ms, 2),
            "confidence": round(self.confidence, 4),
            "searched_sources": self.searched_sources,
        }
        if self.sources:
            d["sources"] = [s.to_dict() for s in self.sources if s.has_results]
        if self.best_hit:
            d["best_hit"] = self.best_hit.to_dict()
        return d

    def to_context_string(self) -> str:
        """
        Render as a block suitable for LLM system prompt injection.

        Returns a formatted string with the most relevant hits,
        ordered by priority.
        """
        parts: List[str] = []
        for source in self.sources:
            if not source.has_results:
                continue
            parts.append(f"=== {source.label} ===")
            for hit in source.hits[:3]:
                title = hit.title
                content = hit.content[:200] if hit.content else ""
                ref = f" [{hit.reference}]" if hit.reference else ""
                if content:
                    parts.append(f"- {title}{ref}: {content}")
                else:
                    parts.append(f"- {title}{ref}")
        return "\n".join(parts) if parts else ""


# ══════════════════════════════════════════════════════════════════════
# Repository Protocol (type hint only — no enforcement)
# ══════════════════════════════════════════════════════════════════════

# A source repository is any callable with signature:
#   (query: str, limit: int) -> List[Dict[str, Any]]
#
# Each returned dict should contain at minimum:
#   {"title": str, "content": str}
#
# Optional keys: "reference", "category", "metadata", "score"

SourceRepository = Callable[[str, int], List[Dict[str, Any]]]


# ══════════════════════════════════════════════════════════════════════
# Knowledge Search Engine
# ══════════════════════════════════════════════════════════════════════


class KnowledgeSearchEngine:
    """
    Ranked multi-source knowledge search engine.

    Searches across 7 knowledge sources in priority order using
    keyword, semantic, or hybrid strategies.  All repositories are
    injected as callables — no direct business module access.

    Usage:
        engine = KnowledgeSearchEngine(
            glossary_repo=lambda q, lim: glossary.search(q, limit=lim),
            nomenclature_repo=lambda q, lim: nomenclature.search(q, limit=lim),
        )
        results = engine.search("que signifie BSD ?")
        ctx = results.to_context_string()
    """

    def __init__(
        self,
        *,
        glossary_repo: Optional[SourceRepository] = None,
        nomenclature_repo: Optional[SourceRepository] = None,
        regulations_repo: Optional[SourceRepository] = None,
        procedures_repo: Optional[SourceRepository] = None,
        internal_docs_repo: Optional[SourceRepository] = None,
        reports_repo: Optional[SourceRepository] = None,
        max_results: int = _DEFAULT_MAX_RESULTS,
        default_limit: int = _DEFAULT_LIMIT,
        keyword_weight: float = _KEYWORD_WEIGHT,
        semantic_weight: float = _SEMANTIC_WEIGHT,
    ) -> None:
        self._repos: Dict[str, Optional[SourceRepository]] = {
            "glossary": glossary_repo,
            "nomenclature": nomenclature_repo,
            "regulation": regulations_repo,
            "procedure": procedures_repo,
            "internal_document": internal_docs_repo,
            "report": reports_repo,
        }
        self._max_results = max_results
        self._default_limit = default_limit
        self._keyword_weight = keyword_weight
        self._semantic_weight = semantic_weight

    # ════════════════════════════════════════════════════════════════
    # Public API
    # ════════════════════════════════════════════════════════════════

    def search(
        self,
        query: str,
        *,
        mode: SearchMode = SearchMode.HYBRID,
        limit: int = 0,
        sources: Optional[List[str]] = None,
    ) -> SearchResults:
        """
        Search across all configured knowledge sources.

        Args:
            query: Search query string.
            mode: Search strategy (KEYWORD, SEMANTIC, HYBRID).
            limit: Max results per source (0 = default_limit).
            sources: Optional subset of sources to search.

        Returns:
            Ranked SearchResults with hits from all sources.
        """
        if not query or not query.strip():
            return SearchResults(query=query, mode=mode.value)

        t0 = time.monotonic()
        effective_limit = limit if limit > 0 else self._default_limit
        tokens = self._tokenize(query)

        source_order = self._get_source_order(sources)
        source_results: List[SourceResult] = []
        searched: List[str] = []

        for source_key in source_order:
            repo = self._repos.get(source_key)
            if repo is None:
                continue

            sr = self._search_source(
                source_key, repo, query, tokens, effective_limit, mode,
            )
            source_results.append(sr)
            if sr.has_results:
                searched.append(source_key)

        total_hits = sum(sr.hit_count for sr in source_results)
        total_elapsed = (time.monotonic() - t0) * 1000

        results = SearchResults(
            query=query,
            mode=mode.value,
            sources=source_results,
            total_hits=total_hits,
            total_elapsed_ms=total_elapsed,
            searched_sources=searched,
        )

        logger.info(
            "KnowledgeSearch[%s]: %d hits from %d sources in %.1fms",
            mode.value, total_hits, len(searched), total_elapsed,
        )
        return results

    def search_keyword(
        self,
        query: str,
        *,
        limit: int = 0,
        sources: Optional[List[str]] = None,
    ) -> SearchResults:
        """Shortcut for keyword-only search."""
        return self.search(query, mode=SearchMode.KEYWORD, limit=limit, sources=sources)

    def search_semantic(
        self,
        query: str,
        *,
        limit: int = 0,
        sources: Optional[List[str]] = None,
    ) -> SearchResults:
        """Shortcut for semantic-only search."""
        return self.search(query, mode=SearchMode.SEMANTIC, limit=limit, sources=sources)

    def search_hybrid(
        self,
        query: str,
        *,
        limit: int = 0,
        sources: Optional[List[str]] = None,
    ) -> SearchResults:
        """Shortcut for hybrid search."""
        return self.search(query, mode=SearchMode.HYBRID, limit=limit, sources=sources)

    def get_definition(self, term: str) -> Optional[KnowledgeHit]:
        """
        Look up an exact definition in the glossary.

        Args:
            term: Term to look up.

        Returns:
            KnowledgeHit if found, None otherwise.
        """
        repo = self._repos.get("glossary")
        if repo is None:
            return None
        try:
            results = repo(term, 1)
        except Exception as exc:
            logger.warning("Glossary lookup failed for '%s': %s", term, exc)
            return None
        if not results:
            return None
        item = results[0]
        score = self._score_exact_match(term.lower(), item.get("title", "").lower())
        return KnowledgeHit(
            source="glossary",
            title=item.get("title", term),
            content=item.get("content", ""),
            score=score,
            confidence=self._compute_confidence(score, "glossary"),
            match_type="exact" if score >= 0.9 else "prefix",
            reference=item.get("reference", ""),
            category=item.get("category", ""),
        )

    def search_by_source(
        self,
        source: str,
        query: str,
        *,
        limit: int = 0,
        mode: SearchMode = SearchMode.KEYWORD,
    ) -> SourceResult:
        """
        Search a single source.

        Args:
            source: Source key (glossary, nomenclature, etc.).
            query: Search query.
            limit: Max results.
            mode: Search mode.

        Returns:
            SourceResult for the requested source.
        """
        repo = self._repos.get(source)
        if repo is None:
            return SourceResult(
                source=source,
                label=_SOURCE_LABELS.get(source, source),
                priority=_SOURCE_PRIORITIES.get(source, 99),
            )
        effective_limit = limit if limit > 0 else self._default_limit
        tokens = self._tokenize(query)
        return self._search_source(source, repo, query, tokens, effective_limit, mode)

    # ════════════════════════════════════════════════════════════════
    # Internal — Source Search
    # ════════════════════════════════════════════════════════════════

    def _search_source(
        self,
        source_key: str,
        repo: SourceRepository,
        query: str,
        tokens: List[str],
        limit: int,
        mode: SearchMode,
    ) -> SourceResult:
        """Search a single source and return scored results."""
        t0 = time.monotonic()
        priority = _SOURCE_PRIORITIES.get(source_key, 99)
        label = _SOURCE_LABELS.get(source_key, source_key)

        try:
            raw_results = repo(query, limit * 2)  # fetch extra for ranking
        except Exception as exc:
            logger.warning("Search failed for source '%s': %s", source_key, exc)
            return SourceResult(
                source=source_key, label=label, priority=priority,
            )

        hits: List[KnowledgeHit] = []
        for item in raw_results:
            hit = self._score_item(source_key, item, query, tokens, mode)
            if hit.score >= _MIN_SCORE:
                hits.append(hit)

        hits.sort(key=lambda h: h.score, reverse=True)
        hits = hits[:limit]

        agg = self._aggregate_score(hits)
        elapsed = (time.monotonic() - t0) * 1000

        return SourceResult(
            source=source_key,
            label=label,
            priority=priority,
            hits=hits,
            aggregate_score=agg,
            elapsed_ms=elapsed,
        )

    # ════════════════════════════════════════════════════════════════
    # Internal — Scoring
    # ════════════════════════════════════════════════════════════════

    def _score_item(
        self,
        source_key: str,
        item: Dict[str, Any],
        query: str,
        tokens: List[str],
        mode: SearchMode,
    ) -> KnowledgeHit:
        """Score a single item against the query."""
        title = item.get("title", "")
        content = item.get("content", "")
        reference = item.get("reference", "")
        category = item.get("category", "")
        metadata = item.get("metadata", {})

        title_lower = title.lower()
        content_lower = content.lower()
        query_lower = query.lower()

        # Keyword score
        kw_score, match_type = self._keyword_score(
            query_lower, title_lower, content_lower, tokens,
        )

        # Semantic score (cosine-like similarity on token overlap)
        sem_score = self._semantic_score(query_lower, title_lower, content_lower)

        # Blend based on mode
        if mode == SearchMode.KEYWORD:
            score = kw_score
        elif mode == SearchMode.SEMANTIC:
            score = sem_score
        else:
            score = (
                self._keyword_weight * kw_score
                + self._semantic_weight * sem_score
            )

        # Boost for reference/code matches
        if reference and query_lower in reference.lower():
            score = min(1.0, score + 0.15)

        confidence = self._compute_confidence(score, source_key)

        return KnowledgeHit(
            source=source_key,
            title=title,
            content=content[:1000],
            score=round(score, 4),
            confidence=round(confidence, 4),
            match_type=match_type,
            metadata=metadata if metadata else {},
            reference=reference,
            category=category,
        )

    def _keyword_score(
        self,
        query_lower: str,
        title_lower: str,
        content_lower: str,
        tokens: List[str],
    ) -> Tuple[float, str]:
        """
        Compute keyword relevance score.

        Returns:
            (score, match_type) tuple.
        """
        # Exact full match in title
        if query_lower == title_lower:
            return _WEIGHT_EXACT_MATCH, "exact"

        # Title starts with query
        if title_lower.startswith(query_lower):
            return _WEIGHT_PREFIX_MATCH, "prefix"

        # Query entirely contained in title
        if query_lower in title_lower:
            return _WEIGHT_CONTAINS_MATCH, "contains"

        # All tokens found in title
        if tokens and all(t in title_lower for t in tokens):
            return 0.75, "title_tokens"

        # Query contained in content
        if query_lower in content_lower:
            return 0.55, "content_contains"

        # Some tokens in title
        if tokens:
            title_hits = sum(1 for t in tokens if t in title_lower)
            title_ratio = title_hits / len(tokens)
            if title_ratio >= 0.5:
                return 0.45, "partial_title"

        # Token overlap with content
        if tokens:
            content_hits = sum(1 for t in tokens if t in content_lower)
            content_ratio = content_hits / len(tokens)
            if content_ratio >= 0.3:
                return 0.30, "partial_content"

        # Fuzzy: any token substring match
        if tokens:
            fuzzy_hits = sum(
                1 for t in tokens
                if any(t in w for w in title_lower.split())
            )
            if fuzzy_hits > 0:
                return _WEIGHT_FUZZY_MATCH * (fuzzy_hits / len(tokens)), "fuzzy"

        return 0.0, ""

    def _semantic_score(
        self,
        query_lower: str,
        title_lower: str,
        content_lower: str,
    ) -> float:
        """
        Compute semantic similarity via token overlap (Jaccard-like).

        No external model — pure token-based similarity.
        """
        query_tokens = set(query_lower.split())
        # Remove stop words
        query_tokens -= _STOP_WORDS_SET

        if not query_tokens:
            return 0.0

        title_tokens = set(title_lower.split())
        content_tokens = set(content_lower.split())

        # Title overlap (weighted higher)
        title_overlap = len(query_tokens & title_tokens)
        title_score = title_overlap / len(query_tokens) if query_tokens else 0.0

        # Content overlap
        content_overlap = len(query_tokens & content_tokens)
        content_score = content_overlap / len(query_tokens) if query_tokens else 0.0

        # Weighted combination: title matches count more
        return min(1.0, 0.7 * title_score + 0.3 * content_score)

    def _score_exact_match(self, query_lower: str, title_lower: str) -> float:
        """Score for exact term lookup."""
        if query_lower == title_lower:
            return 1.0
        if title_lower.startswith(query_lower):
            return 0.9
        if query_lower in title_lower:
            return 0.7
        return 0.3

    def _compute_confidence(self, score: float, source_key: str) -> float:
        """
        Compute confidence in a score based on score magnitude
        and source priority.
        """
        if score >= _CONFIDENCE_HIGH:
            base = 0.95
        elif score >= _CONFIDENCE_MEDIUM:
            base = 0.75
        elif score >= _CONFIDENCE_LOW:
            base = 0.50
        else:
            base = 0.25

        # Higher-priority sources get a small confidence boost
        priority = _SOURCE_PRIORITIES.get(source_key, 7)
        priority_bonus = max(0.0, (7 - priority) * 0.02)

        return min(1.0, base + priority_bonus)

    def _aggregate_score(self, hits: List[KnowledgeHit]) -> float:
        """Compute aggregate score for a source from its hits."""
        if not hits:
            return 0.0
        scores = [h.score for h in hits]
        # Weighted average: top hit gets more weight
        scores.sort(reverse=True)
        weights = [1.0 / (i + 1) for i in range(len(scores))]
        total_weight = sum(weights)
        return sum(s * w for s, w in zip(scores, weights)) / total_weight

    # ════════════════════════════════════════════════════════════════
    # Internal — Helpers
    # ════════════════════════════════════════════════════════════════

    def _tokenize(self, text: str) -> List[str]:
        """Extract meaningful tokens from a query."""
        text_lower = text.lower()
        # Split on non-alphanumeric (keep code-like tokens: 20.01.01)
        tokens = re.findall(r'[a-zà-ÿ0-9]+(?:\.[a-zà-ÿ0-9]+)*', text_lower)
        # Remove stop words and very short tokens
        tokens = [
            t for t in tokens
            if t not in _STOP_WORDS and len(t) > 1
        ]
        return tokens

    def _get_source_order(
        self,
        sources: Optional[List[str]] = None,
    ) -> List[str]:
        """Return source keys in priority order."""
        all_sources = list(_SOURCE_PRIORITIES.keys())
        # Deduplicate while preserving priority order
        seen: set = set()
        ordered: List[str] = []
        for s in all_sources:
            canonical = self._canonical_source(s)
            if canonical not in seen:
                seen.add(canonical)
                ordered.append(s)

        if sources:
            requested = set()
            for s in sources:
                requested.add(self._canonical_source(s))
            ordered = [s for s in ordered if self._canonical_source(s) in requested]

        return ordered

    @staticmethod
    def _canonical_source(source: str) -> str:
        """Map source name to canonical key."""
        mapping = {
            "glossary": "glossary",
            "glossaire": "glossary",
            "nomenclature": "nomenclature",
            "regulation": "regulation",
            "regulations": "regulation",
            "réglementation": "regulation",
            "procedure": "procedure",
            "procedures": "procedure",
            "procédure": "procedure",
            "internal_document": "internal_document",
            "internal_documents": "internal_document",
            "documents_internes": "internal_document",
            "report": "report",
            "reports": "report",
            "rapports": "report",
        }
        return mapping.get(source.lower(), source.lower())

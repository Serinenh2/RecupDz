"""
Embedding Service — TF-IDF + numpy vectorization.

No neural networks. No GPU. No external model downloads.
Fast, deterministic, production-ready.

Uses TF-IDF (Term Frequency - Inverse Document Frequency) for
vector representation and cosine similarity for comparison.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Text preprocessing
# ---------------------------------------------------------------------------

_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED]")
_PUNCTUATION = re.compile(r"[^\w\s\u00C0-\u024F\u0600-\u06FF\u0660-\u0669\u06F0-\u06F9]")
_FRENCH_STOP_WORDS = frozenset({
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "au", "aux",
    "et", "ou", "est", "sont", "a", "ai", "as", "avons", "avez", "ont",
    "que", "qui", "quoi", "quel", "quelle", "quels", "quelles",
    "ce", "cette", "ces", "mon", "ma", "mes", "ton", "ta", "tes",
    "son", "sa", "ses", "notre", "votre", "leur", "leurs",
    "pas", "ne", "n", "se", "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
    "dans", "par", "pour", "sur", "sous", "avec", "sans", "entre", "vers",
    "plus", "moins", "très", "tout", "tous", "toute", "toutes",
    "mais", "donc", "car", "si", "alors", "aussi", "bien", "encore",
    "être", "avoir", "faire", "dire", "aller", "voir", "pouvoir", "vouloir",
    "cette", "ces", "cet", "lorsqu", "lorsque", "comme",
})
_ENGLISH_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "must",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them",
    "my", "your", "his", "its", "our", "their", "mine", "yours", "hers", "ours", "theirs",
    "this", "that", "these", "those", "what", "which", "who", "whom", "whose",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as", "into",
    "not", "no", "nor", "but", "or", "and", "if", "then", "so", "than",
    "very", "just", "also", "too", "more", "most", "other", "some", "any",
    "all", "each", "every", "both", "few", "many", "much", "such",
})
_ARABIC_STOP_WORDS = frozenset({
    "في", "من", "على", "إلى", "عن", "مع", "بين", "حوالي", "منذ",
    "هذا", "هذه", "ذلك", "تلك", "الذي", "التي", "الذين", "اللذين", "اللتين",
    "أن", "إن", "لا", "ما", "هل", "كيف", "لماذا", "أين", "متى",
    "كان", "يكون", "ليس", "ليست", "قد", "لم", "لن", "حتى",
    "و", "ف", "ب", "ل", "ك", "ال", "ها", "هم", "هن",
})
_ALL_STOP_WORDS = _FRENCH_STOP_WORDS | _ENGLISH_STOP_WORDS | _ARABIC_STOP_WORDS


def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase words, removing stop words and short tokens."""
    text = text.lower()
    text = _ARABIC_DIACRITICS.sub("", text)
    text = _PUNCTUATION.sub(" ", text)
    words = re.findall(r"[a-z0-9\u00C0-\u024F\u0600-\u06FF]{2,}", text)
    return [w for w in words if w not in _ALL_STOP_WORDS]


# ---------------------------------------------------------------------------
# Embedding Service
# ---------------------------------------------------------------------------

class EmbeddingService:
    """
    TF-IDF based embedding service.

    Converts text to sparse vectors and computes cosine similarity.
    No neural networks required.

    Usage:
        emb = EmbeddingService()
        vectors = emb.encode_documents(["text1", "text2"])
        query_vec = emb.encode_query("search term")
        similarities = emb.similarity(query_vec, vectors)
    """

    def __init__(self) -> None:
        self._vocab: Dict[str, int] = {}
        self._idf: Optional[np.ndarray] = None
        self._fitted = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, documents: List[str]) -> None:
        """
        Build the vocabulary and IDF weights from a corpus.

        Args:
            documents: List of document texts to build vocabulary from.
        """
        if not documents:
            logger.warning("Empty corpus for fitting")
            return

        # Tokenize all documents
        tokenized = [tokenize(doc) for doc in documents]

        # Build vocabulary
        doc_freq: Counter[str] = Counter()
        all_words: set = set()
        for tokens in tokenized:
            unique = set(tokens)
            for word in unique:
                doc_freq[word] += 1
            all_words.update(unique)

        # Sort for deterministic ordering
        sorted_words = sorted(all_words)
        self._vocab = {word: idx for idx, word in enumerate(sorted_words)}

        # Compute IDF: log(N / df) where N = total docs, df = docs containing word
        n_docs = len(documents)
        vocab_size = len(self._vocab)
        self._idf = np.zeros(vocab_size, dtype=np.float64)

        for word, idx in self._vocab.items():
            df = doc_freq.get(word, 0)
            self._idf[idx] = math.log((n_docs + 1) / (df + 1)) + 1  # smoothed IDF

        self._fitted = True
        logger.info("EmbeddingService fitted: %d docs, %d vocab terms", n_docs, vocab_size)

    def encode_documents(self, documents: List[str]) -> np.ndarray:
        """
        Encode a list of documents into TF-IDF vectors.

        Returns:
            2D numpy array of shape (n_documents, vocab_size)
        """
        if not self._fitted:
            self.fit(documents)

        vectors = []
        for doc in documents:
            vec = self._tfidf_vector(doc)
            vectors.append(vec)

        return np.array(vectors, dtype=np.float64)

    def encode_query(self, query: str) -> np.ndarray:
        """Encode a query string into a TF-IDF vector."""
        if not self._fitted:
            self.fit([query])

        return self._tfidf_vector(query)

    def similarity(self, query_vec: np.ndarray, doc_vectors: np.ndarray) -> np.ndarray:
        """
        Compute cosine similarity between a query vector and document vectors.

        Returns:
            1D numpy array of similarity scores.
        """
        if doc_vectors.shape[0] == 0:
            return np.array([])

        # Cosine similarity: dot(a, b) / (||a|| * ||b||)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return np.zeros(doc_vectors.shape[0], dtype=np.float64)

        doc_norms = np.linalg.norm(doc_vectors, axis=1)
        doc_norms[doc_norms == 0] = 1.0  # avoid division by zero

        similarities = np.dot(doc_vectors, query_vec) / (doc_norms * query_norm)
        return similarities

    def save(self, path: str) -> None:
        """Save the fitted model to disk."""
        data = {
            "vocab": self._vocab,
            "idf": self._idf.tolist() if self._idf is not None else None,
            "fitted": self._fitted,
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f)
        logger.info("EmbeddingService saved to %s", path)

    def load(self, path: str) -> None:
        """Load a fitted model from disk."""
        with open(path) as f:
            data = json.load(f)
        self._vocab = data["vocab"]
        self._idf = np.array(data["idf"]) if data["idf"] is not None else None
        self._fitted = data["fitted"]
        logger.info("EmbeddingService loaded from %s", path)

    @property
    def vocab_size(self) -> int:
        return len(self._vocab)

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _tfidf_vector(self, text: str) -> np.ndarray:
        """Convert text to a TF-IDF vector."""
        tokens = tokenize(text)
        if not tokens:
            return np.zeros(len(self._vocab), dtype=np.float64)

        # Term frequency
        tf = Counter(tokens)
        total = len(tokens)

        # TF-IDF vector
        vector = np.zeros(len(self._vocab), dtype=np.float64)
        for word, count in tf.items():
            if word in self._vocab:
                idx = self._vocab[word]
                tf_val = count / total
                idf_val = self._idf[idx] if self._idf is not None else 1.0
                vector[idx] = tf_val * idf_val

        # Normalize
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector

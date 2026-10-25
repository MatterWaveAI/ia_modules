"""Basic retrieval safety rails for RAG pipelines."""
from typing import Any, Dict, Optional, List
import re
from ..base import BaseGuardrail
from ..models import RailResult, RailAction, RailType


class SourceValidationRail(BaseGuardrail):
    """
    Validate retrieved document sources.

    Ensures documents come from trusted sources and have required metadata.
    """

    def __init__(self, config, allowed_sources: Optional[List[str]] = None,
                 require_metadata: Optional[List[str]] = None):
        """
        Initialize source validation rail.

        Args:
            config: Rail configuration
            allowed_sources: List of allowed source domains/patterns (e.g., ["wikipedia.org", "*.gov"])
            require_metadata: Required metadata fields (e.g., ["author", "date", "url"])
        """
        super().__init__(config)
        self.allowed_sources = allowed_sources or []
        self.require_metadata = require_metadata or []

    async def check(self, content: Any, context: Optional[Dict[str, Any]] = None) -> RailResult:
        """Validate document source."""
        context = context or {}

        # Extract document metadata
        doc_metadata = context.get("metadata", {})
        source = doc_metadata.get("source", "")

        # Check allowed sources
        if self.allowed_sources:
            source_valid = any(
                self._match_source(source, allowed)
                for allowed in self.allowed_sources
            )

            if not source_valid:
                return RailResult(
                    rail_id=self.config.id,
                    rail_type=RailType.RETRIEVAL,
                    action=RailAction.BLOCK,
                    original_content=content,
                    triggered=True,
                    reason=f"Source '{source}' not in allowed list",
                    confidence=1.0,
                    metadata={
                        "source": source,
                        "allowed_sources": self.allowed_sources
                    }
                )

        # Check required metadata
        missing_fields = [
            field for field in self.require_metadata
            if field not in doc_metadata or not doc_metadata[field]
        ]

        if missing_fields:
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.RETRIEVAL,
                action=RailAction.WARN,
                original_content=content,
                triggered=True,
                reason=f"Missing required metadata: {', '.join(missing_fields)}",
                confidence=0.8,
                metadata={
                    "missing_fields": missing_fields,
                    "available_metadata": list(doc_metadata.keys())
                }
            )

        return RailResult(
            rail_id=self.config.id,
            rail_type=RailType.RETRIEVAL,
            action=RailAction.ALLOW,
            original_content=content,
            triggered=False,
            metadata={"source": source}
        )

    def _match_source(self, source: str, pattern: str) -> bool:
        """Check if source matches pattern (supports wildcards)."""
        if "*" in pattern:
            regex_pattern = pattern.replace(".", r"\.").replace("*", ".*")
            return bool(re.match(regex_pattern, source))
        return pattern in source


class RelevanceFilterRail(BaseGuardrail):
    """
    Filter documents by relevance score.

    Ensures retrieved documents meet minimum relevance threshold.
    """

    def __init__(self, config, min_score: float = 0.5,
                 max_documents: Optional[int] = None):
        """
        Initialize relevance filter rail.

        Args:
            config: Rail configuration
            min_score: Minimum relevance score (0.0 to 1.0)
            max_documents: Maximum number of documents to allow
        """
        super().__init__(config)
        self.min_score = min_score
        self.max_documents = max_documents

    async def check(self, content: Any, context: Optional[Dict[str, Any]] = None) -> RailResult:
        """Filter by relevance score."""
        context = context or {}

        # Handle both single document and list of documents
        is_list = isinstance(content, list)
        documents = content if is_list else [content]

        # Extract relevance scores
        filtered_docs = []
        low_relevance_count = 0

        for doc in documents:
            if isinstance(doc, dict):
                score = doc.get("score", doc.get("relevance_score", 1.0))
            else:
                # Check context for score
                score = context.get("score", context.get("relevance_score", 1.0))

            if score >= self.min_score:
                filtered_docs.append(doc)
            else:
                low_relevance_count += 1

        # Check max documents
        if self.max_documents and len(filtered_docs) > self.max_documents:
            filtered_docs = filtered_docs[:self.max_documents]

        # Determine action
        if not filtered_docs:
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.RETRIEVAL,
                action=RailAction.BLOCK,
                original_content=content,
                triggered=True,
                reason="No documents met minimum relevance threshold",
                confidence=1.0,
                metadata={
                    "min_score": self.min_score,
                    "filtered_count": low_relevance_count
                }
            )

        if low_relevance_count > 0 or (self.max_documents and len(documents) > self.max_documents):
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.RETRIEVAL,
                action=RailAction.MODIFY,
                original_content=content,
                modified_content=filtered_docs if is_list else filtered_docs[0],
                triggered=True,
                reason=f"Filtered {low_relevance_count} low-relevance documents",
                confidence=0.9,
                metadata={
                    "original_count": len(documents),
                    "filtered_count": len(filtered_docs),
                    "min_score": self.min_score
                }
            )

        return RailResult(
            rail_id=self.config.id,
            rail_type=RailType.RETRIEVAL,
            action=RailAction.ALLOW,
            original_content=content,
            triggered=False,
            metadata={"document_count": len(filtered_docs)}
        )


class RetrievedContentFilterRail(BaseGuardrail):
    """
    Filter harmful or inappropriate content in retrieved documents.

    Prevents toxic or harmful retrieved content from being used in RAG.
    """

    HARMFUL_PATTERNS = [
        r"\b(violence|violent|kill|murder|attack)\b",
        r"\b(hate|racist|sexist|discrimination)\b",
        r"\b(explicit|nsfw|pornographic)\b",
        r"\b(illegal|crime|criminal)\b"
    ]

    def __init__(self, config, block_harmful: bool = True,
                 custom_patterns: Optional[List[str]] = None):
        """
        Initialize retrieved content filter.

        Args:
            config: Rail configuration
            block_harmful: If True, BLOCK harmful content; if False, WARN only
            custom_patterns: Additional regex patterns to detect
        """
        super().__init__(config)
        self.block_harmful = block_harmful
        self.patterns = self.HARMFUL_PATTERNS + (custom_patterns or [])

    async def check(self, content: Any, context: Optional[Dict[str, Any]] = None) -> RailResult:
        """Check retrieved content for harmful material."""
        if not isinstance(content, str):
            # Handle document objects
            if isinstance(content, dict):
                content = content.get("content", content.get("text", str(content)))
            else:
                content = str(content)

        content_lower = content.lower()

        # Check for harmful patterns
        matched_patterns = []
        for pattern in self.patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                matched_patterns.append(pattern)

        if matched_patterns:
            action = RailAction.BLOCK if self.block_harmful else RailAction.WARN
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.RETRIEVAL,
                action=action,
                original_content=content,
                triggered=True,
                reason=f"Retrieved content contains harmful patterns: {len(matched_patterns)} matches",
                confidence=0.7,
                metadata={
                    "matched_patterns": matched_patterns[:3],  # First 3 matches
                    "match_count": len(matched_patterns)
                }
            )

        return RailResult(
            rail_id=self.config.id,
            rail_type=RailType.RETRIEVAL,
            action=RailAction.ALLOW,
            original_content=content,
            triggered=False
        )

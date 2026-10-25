"""
Evidence Collector

Automatically extracts evidence from tool results, agent outputs, and state changes.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging

# Import Evidence from decision_trail to avoid duplication
from ia_modules.reliability.decision_trail import Evidence


class EvidenceCollector:
    """
    Automatically collect evidence from various sources.

    Extracts evidence from:
    - Tool executions (verified)
    - Database reads (verified)
    - API responses (verified)
    - User inputs (verified)
    - Agent outputs (claimed)

    Example:
        >>> collector = EvidenceCollector()
        >>>
        >>> # Collect from tool result
        >>> evidence = collector.from_tool_result(
        ...     tool_name="search_api",
        ...     result={"results": [...]}
        ... )
        >>>
        >>> # Collect from agent output
        >>> evidence = collector.from_agent_output(
        ...     agent_name="planner",
        ...     output={"plan": ["step1", "step2"]}
        ... )
        >>>
        >>> # Get all evidence
        >>> all_evidence = collector.get_evidence()
    """

    def __init__(self):
        """Initialize evidence collector."""
        self.evidence: List[Evidence] = []
        self.logger = logging.getLogger("EvidenceCollector")

    def from_tool_result(
        self,
        tool_name: str,
        result: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Evidence:
        """
        Extract evidence from tool execution result.

        Args:
            tool_name: Name of the tool
            result: Tool execution result
            metadata: Optional metadata

        Returns:
            Evidence with "verified" confidence
        """
        evidence = Evidence(
            type="tool_result",
            source=tool_name,
            content=result,
            timestamp=datetime.now(timezone.utc).isoformat(),
            confidence="verified",
            metadata=metadata or {}
        )

        self.evidence.append(evidence)
        self.logger.debug(f"Collected tool evidence from {tool_name}")

        return evidence

    def from_database_read(
        self,
        query: str,
        results: Any,
        database: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Evidence:
        """
        Extract evidence from database read.

        Args:
            query: SQL query or query description
            results: Query results
            database: Database name (optional)
            metadata: Optional metadata

        Returns:
            Evidence with "verified" confidence
        """
        meta = metadata or {}
        if database:
            meta["database"] = database
        meta["query"] = query

        evidence = Evidence(
            type="database_read",
            source=database or "database",
            content=results,
            timestamp=datetime.now(timezone.utc).isoformat(),
            confidence="verified",
            metadata=meta
        )

        self.evidence.append(evidence)
        self.logger.debug(f"Collected database evidence from {database or 'database'}")

        return evidence

    def from_api_response(
        self,
        endpoint: str,
        response: Any,
        status_code: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Evidence:
        """
        Extract evidence from API response.

        Args:
            endpoint: API endpoint
            response: API response data
            status_code: HTTP status code (optional)
            metadata: Optional metadata

        Returns:
            Evidence with "verified" confidence
        """
        meta = metadata or {}
        if status_code:
            meta["status_code"] = status_code

        evidence = Evidence(
            type="api_response",
            source=endpoint,
            content=response,
            timestamp=datetime.now(timezone.utc).isoformat(),
            confidence="verified",
            metadata=meta
        )

        self.evidence.append(evidence)
        self.logger.debug(f"Collected API evidence from {endpoint}")

        return evidence

    def from_user_input(
        self,
        user_id: str,
        input_data: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Evidence:
        """
        Extract evidence from user input.

        Args:
            user_id: User identifier
            input_data: User input data
            metadata: Optional metadata

        Returns:
            Evidence with "verified" confidence
        """
        meta = metadata or {}
        meta["user_id"] = user_id

        evidence = Evidence(
            type="user_input",
            source=f"user:{user_id}",
            content=input_data,
            timestamp=datetime.now(timezone.utc).isoformat(),
            confidence="verified",
            metadata=meta
        )

        self.evidence.append(evidence)
        self.logger.debug(f"Collected user input evidence from {user_id}")

        return evidence

    def from_agent_output(
        self,
        agent_name: str,
        output: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Evidence:
        """
        Extract evidence from agent output.

        Args:
            agent_name: Name of the agent
            output: Agent output (plan, analysis, etc.)
            metadata: Optional metadata

        Returns:
            Evidence with "claimed" confidence
        """
        evidence = Evidence(
            type="agent_claim",
            source=agent_name,
            content=output,
            timestamp=datetime.now(timezone.utc).isoformat(),
            confidence="claimed",
            metadata=metadata or {}
        )

        self.evidence.append(evidence)
        self.logger.debug(f"Collected agent claim from {agent_name}")

        return evidence

    def from_inference(
        self,
        source: str,
        conclusion: Any,
        based_on: List[Evidence],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Evidence:
        """
        Extract evidence from inference/reasoning.

        Args:
            source: Source of the inference (agent name, process, etc.)
            conclusion: The inferred conclusion
            based_on: List of evidence used to make inference
            metadata: Optional metadata

        Returns:
            Evidence with "inferred" confidence
        """
        meta = metadata or {}
        meta["based_on_count"] = len(based_on)
        meta["source_types"] = [e.type for e in based_on]

        evidence = Evidence(
            type="agent_claim",  # Inferences are still agent claims
            source=source,
            content=conclusion,
            timestamp=datetime.now(timezone.utc).isoformat(),
            confidence="inferred",
            metadata=meta
        )

        self.evidence.append(evidence)
        self.logger.debug(f"Collected inferred evidence from {source}")

        return evidence

    def get_evidence(
        self,
        confidence: Optional[str] = None,
        source: Optional[str] = None,
        evidence_type: Optional[str] = None
    ) -> List[Evidence]:
        """
        Get collected evidence with optional filtering.

        Args:
            confidence: Filter by confidence level ("verified", "claimed", "inferred")
            source: Filter by source
            evidence_type: Filter by type

        Returns:
            List of evidence matching filters
        """
        results = self.evidence

        if confidence:
            results = [e for e in results if e.confidence == confidence]

        if source:
            results = [e for e in results if e.source == source]

        if evidence_type:
            results = [e for e in results if e.type == evidence_type]

        return results

    def get_verified_evidence(self) -> List[Evidence]:
        """
        Get only verified evidence.

        Returns:
            List of verified evidence
        """
        return self.get_evidence(confidence="verified")

    def get_claimed_evidence(self) -> List[Evidence]:
        """
        Get only claimed evidence.

        Returns:
            List of claimed evidence
        """
        return self.get_evidence(confidence="claimed")

    def get_inferred_evidence(self) -> List[Evidence]:
        """
        Get only inferred evidence.

        Returns:
            List of inferred evidence
        """
        return self.get_evidence(confidence="inferred")

    def clear(self):
        """Clear all collected evidence."""
        self.evidence.clear()
        self.logger.debug("Cleared all evidence")

    def get_count(self, confidence: Optional[str] = None) -> int:
        """
        Get count of evidence.

        Args:
            confidence: Filter by confidence level (optional)

        Returns:
            Number of evidence items
        """
        if confidence:
            return len(self.get_evidence(confidence=confidence))
        return len(self.evidence)

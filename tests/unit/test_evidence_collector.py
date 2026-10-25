"""
Unit tests for evidence collector.

Tests EvidenceCollector for automatic evidence extraction.
"""

from ia_modules.reliability.evidence_collector import EvidenceCollector


class TestEvidenceCollector:
    """Test EvidenceCollector class."""

    def test_collector_creation(self):
        """EvidenceCollector can be created."""
        collector = EvidenceCollector()

        assert collector.evidence == []

    def test_from_tool_result(self):
        """Can collect evidence from tool result."""
        collector = EvidenceCollector()

        evidence = collector.from_tool_result(
            tool_name="search_api",
            result={"results": ["result1", "result2"]}
        )

        assert evidence.type == "tool_result"
        assert evidence.source == "search_api"
        assert evidence.confidence == "verified"
        assert len(collector.evidence) == 1

    def test_from_database_read(self):
        """Can collect evidence from database read."""
        collector = EvidenceCollector()

        evidence = collector.from_database_read(
            query="SELECT * FROM users",
            results=[{"id": 1, "name": "Alice"}],
            database="main_db"
        )

        assert evidence.type == "database_read"
        assert evidence.source == "main_db"
        assert evidence.confidence == "verified"
        assert evidence.metadata["query"] == "SELECT * FROM users"

    def test_from_api_response(self):
        """Can collect evidence from API response."""
        collector = EvidenceCollector()

        evidence = collector.from_api_response(
            endpoint="/api/users",
            response={"users": []},
            status_code=200
        )

        assert evidence.type == "api_response"
        assert evidence.source == "/api/users"
        assert evidence.confidence == "verified"
        assert evidence.metadata["status_code"] == 200

    def test_from_user_input(self):
        """Can collect evidence from user input."""
        collector = EvidenceCollector()

        evidence = collector.from_user_input(
            user_id="user-123",
            input_data={"query": "What is the weather?"}
        )

        assert evidence.type == "user_input"
        assert evidence.source == "user:user-123"
        assert evidence.confidence == "verified"
        assert evidence.metadata["user_id"] == "user-123"

    def test_from_agent_output(self):
        """Can collect evidence from agent output."""
        collector = EvidenceCollector()

        evidence = collector.from_agent_output(
            agent_name="planner",
            output={"plan": ["step1", "step2"]}
        )

        assert evidence.type == "agent_claim"
        assert evidence.source == "planner"
        assert evidence.confidence == "claimed"

    def test_from_inference(self):
        """Can collect evidence from inference."""
        collector = EvidenceCollector()

        # Create some base evidence
        base_evidence = [
            collector.from_tool_result("search", {"result": "data"}),
            collector.from_database_read("SELECT *", {"data": "value"})
        ]

        # Create inference based on them
        evidence = collector.from_inference(
            source="reasoner",
            conclusion={"conclusion": "Based on data, likely true"},
            based_on=base_evidence
        )

        assert evidence.confidence == "inferred"
        assert evidence.metadata["based_on_count"] == 2

    def test_get_evidence_all(self):
        """Can get all evidence."""
        collector = EvidenceCollector()

        collector.from_tool_result("tool1", "result1")
        collector.from_tool_result("tool2", "result2")

        all_evidence = collector.get_evidence()
        assert len(all_evidence) == 2

    def test_get_evidence_by_confidence(self):
        """Can filter evidence by confidence."""
        collector = EvidenceCollector()

        collector.from_tool_result("tool", "result")  # verified
        collector.from_agent_output("agent", "output")  # claimed

        verified = collector.get_evidence(confidence="verified")
        claimed = collector.get_evidence(confidence="claimed")

        assert len(verified) == 1
        assert len(claimed) == 1

    def test_get_evidence_by_source(self):
        """Can filter evidence by source."""
        collector = EvidenceCollector()

        collector.from_tool_result("tool1", "result1")
        collector.from_tool_result("tool2", "result2")

        tool1_evidence = collector.get_evidence(source="tool1")

        assert len(tool1_evidence) == 1
        assert tool1_evidence[0].source == "tool1"

    def test_get_evidence_by_type(self):
        """Can filter evidence by type."""
        collector = EvidenceCollector()

        collector.from_tool_result("tool", "result")
        collector.from_database_read("query", "data")

        tool_evidence = collector.get_evidence(evidence_type="tool_result")
        db_evidence = collector.get_evidence(evidence_type="database_read")

        assert len(tool_evidence) == 1
        assert len(db_evidence) == 1

    def test_get_verified_evidence(self):
        """Can get only verified evidence."""
        collector = EvidenceCollector()

        collector.from_tool_result("tool", "result")
        collector.from_agent_output("agent", "output")

        verified = collector.get_verified_evidence()

        assert len(verified) == 1
        assert verified[0].confidence == "verified"

    def test_get_claimed_evidence(self):
        """Can get only claimed evidence."""
        collector = EvidenceCollector()

        collector.from_tool_result("tool", "result")
        collector.from_agent_output("agent", "output")

        claimed = collector.get_claimed_evidence()

        assert len(claimed) == 1
        assert claimed[0].confidence == "claimed"

    def test_get_inferred_evidence(self):
        """Can get only inferred evidence."""
        collector = EvidenceCollector()

        base = [collector.from_tool_result("tool", "result")]
        collector.from_inference("reasoner", "conclusion", base)

        inferred = collector.get_inferred_evidence()

        assert len(inferred) == 1
        assert inferred[0].confidence == "inferred"

    def test_clear(self):
        """Can clear all evidence."""
        collector = EvidenceCollector()

        collector.from_tool_result("tool", "result")
        collector.from_agent_output("agent", "output")

        collector.clear()

        assert len(collector.evidence) == 0

    def test_get_count(self):
        """Can get count of evidence."""
        collector = EvidenceCollector()

        collector.from_tool_result("tool", "result")
        collector.from_agent_output("agent", "output")

        assert collector.get_count() == 2
        assert collector.get_count(confidence="verified") == 1
        assert collector.get_count(confidence="claimed") == 1

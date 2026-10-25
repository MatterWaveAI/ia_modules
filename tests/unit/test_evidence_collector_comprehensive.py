"""Comprehensive tests for reliability.evidence_collector module"""

from ia_modules.reliability.evidence_collector import EvidenceCollector
from ia_modules.reliability.decision_trail import Evidence


class TestEvidenceCollector:
    """Test EvidenceCollector class"""

    def test_init(self):
        """Test collector initialization"""
        collector = EvidenceCollector()
        assert isinstance(collector.evidence, list)
        assert len(collector.evidence) == 0

    def test_from_tool_result(self):
        """Test collecting tool result evidence"""
        collector = EvidenceCollector()
        result = {"data": "test", "count": 5}

        evidence = collector.from_tool_result("search_api", result)

        assert evidence.type == "tool_result"
        assert evidence.source == "search_api"
        assert evidence.content == result
        assert evidence.confidence == "verified"
        assert len(collector.evidence) == 1

    def test_from_tool_result_with_metadata(self):
        """Test tool result with metadata"""
        collector = EvidenceCollector()
        metadata = {"version": "1.0", "duration_ms": 500}

        evidence = collector.from_tool_result("api", {"result": "ok"}, metadata)

        assert evidence.metadata == metadata

    def test_from_database_read(self):
        """Test collecting database read evidence"""
        collector = EvidenceCollector()
        results = [{"id": 1, "name": "test"}]

        evidence = collector.from_database_read("SELECT * FROM users", results, "prod_db")

        assert evidence.type == "database_read"
        assert evidence.source == "prod_db"
        assert evidence.content == results
        assert evidence.confidence == "verified"
        assert evidence.metadata["query"] == "SELECT * FROM users"
        assert evidence.metadata["database"] == "prod_db"

    def test_from_database_read_no_db_name(self):
        """Test database read without database name"""
        collector = EvidenceCollector()

        evidence = collector.from_database_read("SELECT 1", [{"result": 1}])

        assert evidence.source == "database"
        assert "query" in evidence.metadata

    def test_from_api_response(self):
        """Test collecting API response evidence"""
        collector = EvidenceCollector()
        response = {"status": "success", "data": {}}

        evidence = collector.from_api_response("/api/users", response, 200)

        assert evidence.type == "api_response"
        assert evidence.source == "/api/users"
        assert evidence.content == response
        assert evidence.confidence == "verified"
        assert evidence.metadata["status_code"] == 200

    def test_from_api_response_no_status(self):
        """Test API response without status code"""
        collector = EvidenceCollector()

        evidence = collector.from_api_response("/api/test", {"data": "test"})

        assert "status_code" not in evidence.metadata

    def test_from_user_input(self):
        """Test collecting user input evidence"""
        collector = EvidenceCollector()
        input_data = {"query": "search term", "filters": {}}

        evidence = collector.from_user_input("user-123", input_data)

        assert evidence.type == "user_input"
        assert evidence.source == "user:user-123"
        assert evidence.content == input_data
        assert evidence.confidence == "verified"
        assert evidence.metadata["user_id"] == "user-123"

    def test_from_agent_output(self):
        """Test collecting agent output evidence"""
        collector = EvidenceCollector()
        output = {"plan": ["step1", "step2", "step3"]}

        evidence = collector.from_agent_output("planner_agent", output)

        assert evidence.type == "agent_claim"
        assert evidence.source == "planner_agent"
        assert evidence.content == output
        assert evidence.confidence == "claimed"

    def test_from_inference(self):
        """Test collecting inferred evidence"""
        collector = EvidenceCollector()

        # Create base evidence
        base1 = Evidence("tool_result", "api", {"value": 5}, "2024-01-01", "verified")
        base2 = Evidence("database_read", "db", {"value": 10}, "2024-01-01", "verified")

        evidence = collector.from_inference(
            "reasoning_agent",
            {"conclusion": "sum is 15"},
            [base1, base2]
        )

        assert evidence.confidence == "inferred"
        assert evidence.source == "reasoning_agent"
        assert evidence.metadata["based_on_count"] == 2
        assert evidence.metadata["source_types"] == ["tool_result", "database_read"]

    def test_get_evidence_all(self):
        """Test getting all evidence"""
        collector = EvidenceCollector()

        collector.from_tool_result("tool1", {"data": 1})
        collector.from_agent_output("agent1", {"output": 2})
        collector.from_user_input("user1", {"input": 3})

        all_evidence = collector.get_evidence()
        assert len(all_evidence) == 3

    def test_get_evidence_by_confidence(self):
        """Test filtering evidence by confidence"""
        collector = EvidenceCollector()

        collector.from_tool_result("tool", {})  # verified
        collector.from_agent_output("agent", {})  # claimed
        collector.from_database_read("query", [])  # verified

        verified = collector.get_evidence(confidence="verified")
        claimed = collector.get_evidence(confidence="claimed")

        assert len(verified) == 2
        assert len(claimed) == 1

    def test_get_evidence_by_source(self):
        """Test filtering evidence by source"""
        collector = EvidenceCollector()

        collector.from_tool_result("search_api", {})
        collector.from_tool_result("search_api", {})
        collector.from_tool_result("other_tool", {})

        search_evidence = collector.get_evidence(source="search_api")
        assert len(search_evidence) == 2

    def test_get_evidence_by_type(self):
        """Test filtering evidence by type"""
        collector = EvidenceCollector()

        collector.from_tool_result("tool", {})
        collector.from_database_read("query", [])
        collector.from_api_response("/api", {})

        tool_evidence = collector.get_evidence(evidence_type="tool_result")
        db_evidence = collector.get_evidence(evidence_type="database_read")

        assert len(tool_evidence) == 1
        assert len(db_evidence) == 1

    def test_get_evidence_multiple_filters(self):
        """Test filtering with multiple criteria"""
        collector = EvidenceCollector()

        collector.from_tool_result("search_api", {"data": 1})
        collector.from_tool_result("search_api", {"data": 2})
        collector.from_tool_result("other_api", {"data": 3})
        collector.from_agent_output("search_api", {"claim": "test"})

        results = collector.get_evidence(
            confidence="verified",
            source="search_api",
            evidence_type="tool_result"
        )

        assert len(results) == 2

    def test_get_verified_evidence(self):
        """Test get_verified_evidence shortcut"""
        collector = EvidenceCollector()

        collector.from_tool_result("tool", {})
        collector.from_agent_output("agent", {})
        collector.from_database_read("query", [])

        verified = collector.get_verified_evidence()
        assert len(verified) == 2
        assert all(e.confidence == "verified" for e in verified)

    def test_get_claimed_evidence(self):
        """Test get_claimed_evidence shortcut"""
        collector = EvidenceCollector()

        collector.from_agent_output("agent1", {})
        collector.from_agent_output("agent2", {})
        collector.from_tool_result("tool", {})

        claimed = collector.get_claimed_evidence()
        assert len(claimed) == 2
        assert all(e.confidence == "claimed" for e in claimed)

    def test_get_inferred_evidence(self):
        """Test get_inferred_evidence shortcut"""
        collector = EvidenceCollector()

        base = Evidence("tool_result", "tool", {}, "2024-01-01", "verified")
        collector.from_inference("reasoner", {"conclusion": "test"}, [base])
        collector.from_agent_output("agent", {})

        inferred = collector.get_inferred_evidence()
        assert len(inferred) == 1
        assert inferred[0].confidence == "inferred"

    def test_clear(self):
        """Test clearing evidence"""
        collector = EvidenceCollector()

        collector.from_tool_result("tool", {})
        collector.from_agent_output("agent", {})
        assert len(collector.evidence) == 2

        collector.clear()
        assert len(collector.evidence) == 0

    def test_get_count(self):
        """Test getting evidence count"""
        collector = EvidenceCollector()

        collector.from_tool_result("tool", {})
        collector.from_agent_output("agent", {})
        collector.from_database_read("query", [])

        assert collector.get_count() == 3

    def test_get_count_by_confidence(self):
        """Test getting count by confidence"""
        collector = EvidenceCollector()

        collector.from_tool_result("tool", {})
        collector.from_agent_output("agent1", {})
        collector.from_agent_output("agent2", {})

        assert collector.get_count(confidence="verified") == 1
        assert collector.get_count(confidence="claimed") == 2

    def test_multiple_collections(self):
        """Test collecting evidence from multiple sources"""
        collector = EvidenceCollector()

        # Simulate a workflow
        collector.from_user_input("user-1", {"request": "search for AI"})
        collector.from_agent_output("planner", {"plan": ["search", "summarize"]})
        collector.from_tool_result("search_api", {"results": ["result1"]})
        collector.from_database_read("SELECT * FROM cache", [{"cached": "data"}])
        collector.from_agent_output("summarizer", {"summary": "AI info"})

        assert collector.get_count() == 5
        assert collector.get_count(confidence="verified") == 3
        assert collector.get_count(confidence="claimed") == 2

    def test_evidence_timestamps(self):
        """Test that timestamps are created"""
        collector = EvidenceCollector()

        evidence = collector.from_tool_result("tool", {})

        assert evidence.timestamp is not None
        assert isinstance(evidence.timestamp, str)
        assert "T" in evidence.timestamp  # ISO format

    def test_empty_metadata_defaults(self):
        """Test that metadata defaults to empty dict"""
        collector = EvidenceCollector()

        evidence = collector.from_tool_result("tool", {"data": "test"})

        assert evidence.metadata == {}

    def test_inference_metadata_structure(self):
        """Test inference metadata structure"""
        collector = EvidenceCollector()

        base_evidence = [
            Evidence("tool", "t1", {}, "2024", "verified"),
            Evidence("api", "a1", {}, "2024", "verified"),
            Evidence("db", "d1", {}, "2024", "verified")
        ]

        evidence = collector.from_inference("reasoner", {"result": "x"}, base_evidence)

        assert evidence.metadata["based_on_count"] == 3
        assert evidence.metadata["source_types"] == ["tool", "api", "db"]

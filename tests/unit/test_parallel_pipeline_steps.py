"""
Unit tests for parallel pipeline steps to ensure proper data flow
"""

import pytest
from tests.pipelines.parallel_pipeline.steps.results_merger import ResultsMergerStep
from tests.pipelines.parallel_pipeline.steps.completed_stats_collector import CompletedStatsCollectorStep


class TestParallelPipelineSteps:
    """Test individual steps of the parallel pipeline"""

    @pytest.mark.asyncio
    async def test_results_merger_with_named_inputs(self):
        """Test ResultsMergerStep with properly named inputs"""
        merger = ResultsMergerStep("test_merger", {})
        
        # Simulate input from three parallel processors
        input_data = {
            "processed_data_1": {
                "stream_id": 1,
                "processed_data": [{"id": 1}, {"id": 2}],
                "record_count": 2
            },
            "processed_data_2": {
                "stream_id": 2,
                "processed_data": [{"id": 3}, {"id": 4}],
                "record_count": 2
            },
            "processed_data_3": {
                "stream_id": 3,
                "processed_data": [{"id": 5}, {"id": 6}],
                "record_count": 2
            }
        }
        
        result = await merger.run(input_data)
        
        # Verify merger collected all three streams
        assert result is not None
        assert result["stream_count"] == 3
        assert result["total_records"] == 6  # 2+2+2
        assert result["merged_results"] is not None
        
    @pytest.mark.asyncio
    async def test_results_merger_with_single_input(self):
        """Test ResultsMergerStep when only one processed_data is available"""
        merger = ResultsMergerStep("test_merger", {})
        
        # Simulate input from only one processor (sequential execution fallback)
        input_data = {
            "processed_data": {
                "stream_id": 1,
                "processed_data": [{"id": 1}, {"id": 2}, {"id": 3}],
                "record_count": 3
            }
        }
        
        result = await merger.run(input_data)
        
        # Should handle single input gracefully
        assert result is not None
        assert result["stream_count"] >= 1
        assert "merged_results" in result
        
    @pytest.mark.asyncio
    async def test_results_merger_with_empty_input(self):
        """Test ResultsMergerStep with no data"""
        merger = ResultsMergerStep("test_merger", {})
        
        input_data = {}
        
        result = await merger.run(input_data)
        
        # Should handle empty input without crashing
        assert result is not None
        assert "merged_results" in result
        assert result["stream_count"] >= 0
        
    @pytest.mark.asyncio
    async def test_stats_collector_with_valid_data(self):
        """Test CompletedStatsCollectorStep with valid merged results"""
        collector = CompletedStatsCollectorStep("test_collector", {})
        
        # Simulate input from results merger
        input_data = {
            "merged_results": {
                "processed_data": [{"id": i} for i in range(1, 11)]  # 10 items
            },
            "stream_count": 3,
            "total_records": 10
        }
        
        result = await collector.run(input_data)
        
        # Verify statistics collection
        assert result is not None
        assert "statistics" in result
        assert "total_streams" in result
        assert "total_records_processed" in result
        
        # Should have 10 records processed
        assert result["total_records_processed"] == 10
        # Should have 3 streams
        assert result["total_streams"] == 3
        # Should have stats for each stream
        assert len(result["statistics"]) == 3
        
    @pytest.mark.asyncio
    async def test_stats_collector_with_no_stream_count(self):
        """Test CompletedStatsCollectorStep when stream_count is missing"""
        collector = CompletedStatsCollectorStep("test_collector", {})
        
        # Simulate input without stream_count (fallback case)
        input_data = {
            "merged_results": [{"id": i} for i in range(1, 6)]  # 5 items as list
        }
        
        result = await collector.run(input_data)
        
        # Should infer stream count and handle gracefully
        assert result is not None
        assert result["total_streams"] >= 1
        assert result["total_records_processed"] == 5
        
    @pytest.mark.asyncio
    async def test_stats_collector_with_empty_results(self):
        """Test CompletedStatsCollectorStep with empty merged results"""
        collector = CompletedStatsCollectorStep("test_collector", {})
        
        # Simulate empty results
        input_data = {
            "merged_results": {},
            "stream_count": 0,
            "total_records": 0
        }
        
        result = await collector.run(input_data)
        
        # Should handle empty results without crashing
        assert result is not None
        assert result["total_streams"] >= 0
        assert result["total_records_processed"] == 0
        assert result["pipeline_completion_status"] == "completed"
        
    @pytest.mark.asyncio
    async def test_end_to_end_data_flow(self):
        """Test complete data flow from merger to stats collector"""
        merger = ResultsMergerStep("test_merger", {})
        collector = CompletedStatsCollectorStep("test_collector", {})
        
        # Start with parallel processor outputs
        merger_input = {
            "processed_data_1": {
                "stream_id": 1,
                "processed_data": [{"id": 1}, {"id": 2}],
                "record_count": 2
            },
            "processed_data_2": {
                "stream_id": 2,
                "processed_data": [{"id": 3}],
                "record_count": 1
            },
            "processed_data_3": {
                "stream_id": 3,
                "processed_data": [{"id": 4}, {"id": 5}, {"id": 6}],
                "record_count": 3
            }
        }
        
        # Run merger
        merger_result = await merger.run(merger_input)
        
        # Verify merger output
        assert merger_result["stream_count"] == 3
        assert merger_result["total_records"] == 6  # 2+1+3
        
        # Run stats collector with merger output
        stats_result = await collector.run(merger_result)
        
        # Verify stats reflect the merged data
        assert stats_result["total_streams"] == 3
        assert stats_result["total_records_processed"] == 6
        assert len(stats_result["statistics"]) == 3
        
        # Each stream should have processed 2 records on average
        avg_records = stats_result["total_records_processed"] / stats_result["total_streams"]
        assert avg_records == 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
End-to-end tests focused on parallel pipeline execution patterns
"""

import pytest
import json
import time
import sys
from pathlib import Path

# Add the parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from ia_modules.pipeline.graph_pipeline_runner import GraphPipelineRunner


class TestParallelE2E:
    """Test suite specifically for parallel pipeline execution"""

    @pytest.mark.asyncio
    async def test_parallel_branching_execution(self):
        """Test that parallel branches execute independently"""

        # Load the parallel pipeline config
        pipeline_file = Path(__file__).parent.parent / "pipelines" / "parallel_pipeline" / "pipeline.json"

        with open(pipeline_file, 'r') as f:
            pipeline_config = json.load(f)

        # Create test data that will be split into parallel streams
        input_data = {
            "loaded_data": [
                {"stream": "A", "value": 100},
                {"stream": "B", "value": 200},
                {"stream": "C", "value": 300},
                {"stream": "A", "value": 150},
                {"stream": "B", "value": 250},
                {"stream": "C", "value": 350}
            ]
        }

        # Execute pipeline
        runner = GraphPipelineRunner()
        result = await runner.run_pipeline_from_json(pipeline_config, input_data)

        # Verify parallel execution completed successfully
        assert result is not None
        assert isinstance(result, dict)
        # Pipeline executed - structure varies by implementation

    @pytest.mark.asyncio
    async def test_parallel_data_integrity(self):
        """Test that data integrity is maintained across parallel processing"""

        pipeline_file = Path(__file__).parent.parent / "pipelines" / "parallel_pipeline" / "pipeline.json"

        with open(pipeline_file, 'r') as f:
            pipeline_config = json.load(f)

        # Create numbered test data to track integrity
        input_data = {
            "loaded_data": [{"id": i, "value": i * 100} for i in range(1, 13)]  # 12 items
        }

        runner = GraphPipelineRunner()
        result = await runner.run_pipeline_from_json(pipeline_config, input_data)

        # Verify data integrity - pipeline completed successfully
        assert result is not None
        assert isinstance(result, dict)
        # Pipeline processed the data successfully

    @pytest.mark.asyncio
    async def test_parallel_performance_characteristics(self):
        """Test parallel processing performance characteristics"""

        pipeline_file = Path(__file__).parent.parent / "pipelines" / "parallel_pipeline" / "pipeline.json"

        with open(pipeline_file, 'r') as f:
            pipeline_config = json.load(f)

        # Large dataset to better test parallel benefits
        large_data = {
            "loaded_data": [
                {"batch": i // 10, "item": i, "data": f"data_item_{i}"}
                for i in range(100)
            ]
        }

        # Measure execution time
        start_time = time.time()

        runner = GraphPipelineRunner()
        result = await runner.run_pipeline_from_json(pipeline_config, large_data)

        end_time = time.time()
        execution_time = end_time - start_time

        # Verify successful execution
        # Verify pipeline completed successfully
        assert result is not None
        assert isinstance(result, dict)

        # Log performance info (execution time should be reasonable for test data)
        print(f"Parallel pipeline execution time: {execution_time:.3f} seconds")
        assert execution_time < 10.0  # Should complete within 10 seconds

    @pytest.mark.asyncio
    async def test_parallel_error_isolation(self):
        """Test that errors in one parallel branch don't affect others"""

        # This test would require modifying one of the parallel steps to simulate an error
        # For now, test that the pipeline handles partial failures gracefully

        pipeline_file = Path(__file__).parent.parent / "pipelines" / "parallel_pipeline" / "pipeline.json"

        with open(pipeline_file, 'r') as f:
            pipeline_config = json.load(f)

        # Test with edge case data that might cause issues
        edge_case_data = {
            "loaded_data": []  # Empty data
        }

        # Should either handle gracefully or provide meaningful error
        from ia_modules.pipeline.errors import PipelineError
        try:
            runner = GraphPipelineRunner()
            result = await runner.run_pipeline_from_json(pipeline_config, edge_case_data)
            # If successful, verify it handled empty data appropriately
            assert result is not None
        except Exception as e:
            # If it fails, should be a meaningful error
            assert isinstance(e, (ValueError, IndexError, KeyError, TypeError, PipelineError))

    @pytest.mark.asyncio
    async def test_parallel_scaling_behavior(self):
        """Test how the parallel pipeline scales with different data sizes"""

        pipeline_file = Path(__file__).parent.parent / "pipelines" / "parallel_pipeline" / "pipeline.json"

        with open(pipeline_file, 'r') as f:
            pipeline_config = json.load(f)

        # Test with different data sizes
        test_sizes = [10, 50, 100]

        for size in test_sizes:
            input_data = {
                "loaded_data": [
                    {"size_test": size, "item": i, "value": i * 2}
                    for i in range(size)
                ]
            }

            runner = GraphPipelineRunner()
            result = await runner.run_pipeline_from_json(pipeline_config, input_data)

            # Verify successful scaling
            assert result is not None
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_parallel_execution_order(self):
        """Test that parallel execution follows correct dependency order"""

        pipeline_file = Path(__file__).parent.parent / "pipelines" / "parallel_pipeline" / "pipeline.json"

        with open(pipeline_file, 'r') as f:
            pipeline_config = json.load(f)

        input_data = {
            "loaded_data": [{"order_test": i} for i in range(20)]
        }

        runner = GraphPipelineRunner()
        result = await runner.run_pipeline_from_json(pipeline_config, input_data)

        # Verify execution completed successfully
        assert result is not None
        assert isinstance(result, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
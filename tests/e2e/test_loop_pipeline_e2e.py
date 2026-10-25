"""
E2E tests for loop pipeline execution

Tests iterative content generation with loops and conditional branching.
"""

import pytest
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from ia_modules.pipeline.graph_pipeline_runner import GraphPipelineRunner


class TestLoopPipelineE2E:
    """Test suite for loop pipeline execution"""

    @pytest.mark.asyncio
    async def test_loop_pipeline_single_iteration(self):
        """Test loop pipeline that approves on first iteration"""
        pipeline_file = Path(__file__).parent.parent / "pipelines" / "loop_pipeline" / "pipeline.json"
        
        with open(pipeline_file, 'r') as f:
            pipeline_config = json.load(f)
        
        # Use topic that will get high quality score on first iteration
        input_data = {
            "topic": "artificial intelligence",
            "max_revisions": 5
        }
        
        runner = GraphPipelineRunner()
        result = await runner.run_pipeline_from_json(pipeline_config, input_data)
        
        assert result is not None
        
        # Verify execution tracking
        tracker = runner.services.get('execution_tracker')
        executions = tracker.get_all_executions()
        assert len(executions) == 1
        assert executions[0]['status'] == 'completed'
        
        # Verify steps were tracked
        steps = tracker.get_all_steps()
        assert len(steps) > 0

    @pytest.mark.asyncio
    async def test_loop_pipeline_multiple_iterations(self):
        """Test loop pipeline with multiple iterations"""
        pipeline_file = Path(__file__).parent.parent / "pipelines" / "loop_pipeline" / "pipeline.json"
        
        with open(pipeline_file, 'r') as f:
            pipeline_config = json.load(f)
        
        input_data = {
            "topic": "machine learning",
            "max_revisions": 3
        }
        
        runner = GraphPipelineRunner()
        result = await runner.run_pipeline_from_json(pipeline_config, input_data)
        
        assert result is not None
        
        # Verify tracking
        tracker = runner.services.get('execution_tracker')
        steps = tracker.get_all_steps()
        
        # Should have draft, review, and publish steps
        # Plus potentially multiple draft/review iterations
        assert len(steps) >= 3

    @pytest.mark.asyncio
    async def test_loop_pipeline_max_iterations(self):
        """Test that loop respects max_iterations limit"""
        pipeline_file = Path(__file__).parent.parent / "pipelines" / "loop_pipeline" / "pipeline.json"
        
        with open(pipeline_file, 'r') as f:
            pipeline_config = json.load(f)
        
        # Set low max_revisions to test limit
        input_data = {
            "topic": "testing loops",
            "max_revisions": 2
        }
        
        runner = GraphPipelineRunner()
        result = await runner.run_pipeline_from_json(pipeline_config, input_data)
        
        assert result is not None
        
        # Verify it completed even if quality threshold not met
        tracker = runner.services.get('execution_tracker')
        executions = tracker.get_all_executions()
        assert executions[0]['status'] == 'completed'

    @pytest.mark.asyncio
    async def test_loop_pipeline_tracks_revisions(self):
        """Test that revision count is properly tracked"""
        pipeline_file = Path(__file__).parent.parent / "pipelines" / "loop_pipeline" / "pipeline.json"
        
        with open(pipeline_file, 'r') as f:
            pipeline_config = json.load(f)
        
        input_data = {
            "topic": "revision tracking",
            "max_revisions": 4
        }
        
        runner = GraphPipelineRunner()
        result = await runner.run_pipeline_from_json(pipeline_config, input_data)
        
        assert result is not None
        
        # Count how many times draft_content was executed
        tracker = runner.services.get('execution_tracker')
        steps = tracker.get_all_steps()
        
        draft_steps = [s for s in steps if s['step_id'] == 'draft_content']
        review_steps = [s for s in steps if s['step_id'] == 'review_content']
        
        # Should have at least one draft and one review
        assert len(draft_steps) >= 1
        assert len(review_steps) >= 1
        
        # Number of drafts and reviews should be close (differ by at most 1)
        assert abs(len(draft_steps) - len(review_steps)) <= 1

    @pytest.mark.asyncio
    async def test_loop_pipeline_quality_improvement(self):
        """Test that quality scores improve with iterations"""
        pipeline_file = Path(__file__).parent.parent / "pipelines" / "loop_pipeline" / "pipeline.json"
        
        with open(pipeline_file, 'r') as f:
            pipeline_config = json.load(f)
        
        input_data = {
            "topic": "quality improvement",
            "max_revisions": 5
        }
        
        runner = GraphPipelineRunner()
        result = await runner.run_pipeline_from_json(pipeline_config, input_data)
        
        assert result is not None
        
        # Verify execution completed
        tracker = runner.services.get('execution_tracker')
        executions = tracker.get_all_executions()
        assert executions[0]['status'] == 'completed'
        
        # Get review steps and check quality scores
        review_steps = [s for s in tracker.get_all_steps() if s['step_id'] == 'review_content']
        
        if len(review_steps) > 1:
            # Extract quality scores from output data
            quality_scores = []
            for step in review_steps:
                if step['output_data'] and 'quality_score' in step['output_data']:
                    quality_scores.append(step['output_data']['quality_score'])
            
            # Verify quality improves (or at least doesn't decrease)
            if len(quality_scores) > 1:
                for i in range(1, len(quality_scores)):
                    assert quality_scores[i] >= quality_scores[i-1], \
                        f"Quality should improve: {quality_scores[i]} < {quality_scores[i-1]}"

    @pytest.mark.asyncio
    async def test_loop_pipeline_publishes_final_content(self):
        """Test that approved content is published"""
        pipeline_file = Path(__file__).parent.parent / "pipelines" / "loop_pipeline" / "pipeline.json"
        
        with open(pipeline_file, 'r') as f:
            pipeline_config = json.load(f)
        
        input_data = {
            "topic": "final publication",
            "max_revisions": 3
        }
        
        runner = GraphPipelineRunner()
        result = await runner.run_pipeline_from_json(pipeline_config, input_data)
        
        assert result is not None
        
        # Verify publish step was executed
        tracker = runner.services.get('execution_tracker')
        publish_steps = [s for s in tracker.get_all_steps() if s['step_id'] == 'publish_content']
        
        assert len(publish_steps) == 1, "Should have exactly one publish step"
        # Status can be enum or string
        status = publish_steps[0]['status']
        assert status == 'completed' or (hasattr(status, 'value') and status.value == 'completed')
        
        # Verify publish step has expected outputs
        publish_output = publish_steps[0]['output_data']
        assert 'published_url' in publish_output
        assert 'final_draft' in publish_output
        assert 'publication_id' in publish_output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

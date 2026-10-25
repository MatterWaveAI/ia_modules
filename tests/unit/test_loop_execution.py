"""
Tests for cyclic graph execution (loop detection and execution).
"""
import pytest
import asyncio
from datetime import datetime

from ia_modules.pipeline.loop_detector import LoopDetector
from ia_modules.pipeline.loop_executor import LoopExecutionContext, LoopAwareExecutor


class TestLoopDetector:
    """Tests for loop detection algorithm."""

    def test_detect_simple_loop(self):
        """Test detection of simple A -> B -> A loop."""
        flow = {
            'start_at': 'step_a',
            'paths': [
                {'from': 'step_a', 'to': 'step_b'},
                {
                    'from': 'step_b',
                    'to': 'step_a',
                    'condition': {'type': 'expression', 'config': {}}
                }
            ]
        }

        detector = LoopDetector(flow)
        loops = detector.detect_loops()

        assert len(loops) == 1
        assert set(loops[0].steps) == {'step_a', 'step_b'}

    def test_detect_no_loops(self):
        """Test that DAG has no loops."""
        flow = {
            'start_at': 'step_a',
            'paths': [
                {'from': 'step_a', 'to': 'step_b'},
                {'from': 'step_b', 'to': 'step_c'}
            ]
        }

        detector = LoopDetector(flow)
        loops = detector.detect_loops()

        assert len(loops) == 0

    def test_detect_multi_step_loop(self):
        """Test detection of longer loop A -> B -> C -> A."""
        flow = {
            'start_at': 'step_a',
            'paths': [
                {'from': 'step_a', 'to': 'step_b'},
                {'from': 'step_b', 'to': 'step_c'},
                {
                    'from': 'step_c',
                    'to': 'step_a',
                    'condition': {'type': 'expression'}
                }
            ]
        }

        detector = LoopDetector(flow)
        loops = detector.detect_loops()

        assert len(loops) == 1
        assert set(loops[0].steps) == {'step_a', 'step_b', 'step_c'}

    def test_detect_multiple_loops(self):
        """Test detection of multiple independent loops."""
        flow = {
            'start_at': 'step_a',
            'paths': [
                # Loop 1: a -> b -> a
                {'from': 'step_a', 'to': 'step_b'},
                {'from': 'step_b', 'to': 'step_a', 'condition': {'type': 'expression'}},

                # Loop 2: c -> d -> c
                {'from': 'step_c', 'to': 'step_d'},
                {'from': 'step_d', 'to': 'step_c', 'condition': {'type': 'expression'}},
            ]
        }

        detector = LoopDetector(flow)
        loops = detector.detect_loops()

        assert len(loops) == 2

    def test_find_exit_conditions(self):
        """Test that exit conditions are correctly identified."""
        flow = {
            'start_at': 'draft',
            'paths': [
                {'from': 'draft', 'to': 'review'},
                {
                    'from': 'review',
                    'to': 'draft',  # Loop back
                    'condition': {
                        'type': 'expression',
                        'config': {'source': 'review.approved', 'operator': 'equals', 'value': False}
                    }
                },
                {
                    'from': 'review',
                    'to': 'publish',  # Exit loop
                    'condition': {
                        'type': 'expression',
                        'config': {'source': 'review.approved', 'operator': 'equals', 'value': True}
                    }
                }
            ]
        }

        detector = LoopDetector(flow)
        loops = detector.detect_loops()

        assert len(loops) == 1
        assert len(loops[0].exit_conditions) == 1
        assert loops[0].exit_conditions[0]['to'] == 'publish'

    def test_validate_loop_without_exit(self):
        """Test validation catches loops without exit conditions."""
        flow = {
            'start_at': 'step_a',
            'paths': [
                {'from': 'step_a', 'to': 'step_b'},
                {
                    'from': 'step_b',
                    'to': 'step_a',
                    'condition': {'type': 'always'}  # Always loops, no exit!
                }
            ]
        }

        detector = LoopDetector(flow)
        errors = detector.validate_loops()

        assert len(errors) > 0
        assert any('infinite loop' in error.lower() for error in errors)

    def test_validate_loop_with_exit(self):
        """Test validation passes for loop with proper exit."""
        flow = {
            'start_at': 'draft',
            'paths': [
                {'from': 'draft', 'to': 'review'},
                {
                    'from': 'review',
                    'to': 'draft',
                    'condition': {
                        'type': 'expression',
                        'config': {'source': 'approved', 'operator': 'equals', 'value': False}
                    }
                },
                {
                    'from': 'review',
                    'to': 'publish',
                    'condition': {
                        'type': 'expression',
                        'config': {'source': 'approved', 'operator': 'equals', 'value': True}
                    }
                }
            ]
        }

        detector = LoopDetector(flow)
        errors = detector.validate_loops()

        # Should have no errors (or only warnings, not critical errors)
        critical_errors = [e for e in errors if 'infinite loop' in e.lower()]
        assert len(critical_errors) == 0

    def test_get_loop_for_step(self):
        """Test finding which loop a step belongs to."""
        flow = {
            'start_at': 'step_a',
            'paths': [
                {'from': 'step_a', 'to': 'step_b'},
                {'from': 'step_b', 'to': 'step_a', 'condition': {'type': 'expression'}}
            ]
        }

        detector = LoopDetector(flow)
        loop = detector.get_loop_for_step('step_a')

        assert loop is not None
        assert 'step_a' in loop.steps
        assert 'step_b' in loop.steps

    def test_is_in_loop(self):
        """Test checking if step is in any loop."""
        flow = {
            'start_at': 'step_a',
            'paths': [
                {'from': 'step_a', 'to': 'step_b'},
                {'from': 'step_b', 'to': 'step_c'},
                {'from': 'step_c', 'to': 'step_a', 'condition': {'type': 'expression'}},
                {'from': 'step_c', 'to': 'step_d'}  # step_d not in loop
            ]
        }

        detector = LoopDetector(flow)

        assert detector.is_in_loop('step_a') is True
        assert detector.is_in_loop('step_b') is True
        assert detector.is_in_loop('step_c') is True
        assert detector.is_in_loop('step_d') is False

    def test_visualize_loops(self):
        """Test loop visualization output."""
        flow = {
            'start_at': 'step_a',
            'paths': [
                {'from': 'step_a', 'to': 'step_b'},
                {'from': 'step_b', 'to': 'step_a', 'condition': {'type': 'expression'}}
            ]
        }

        detector = LoopDetector(flow)
        visualization = detector.visualize_loops()

        assert 'Loop' in visualization
        assert 'step_a' in visualization
        assert 'step_b' in visualization


class TestLoopExecutionContext:
    """Tests for loop execution context and safety limits."""

    def test_increment_iteration(self):
        """Test iteration counting."""
        context = LoopExecutionContext()

        assert context.get_iteration('step_a') == 0

        iteration = context.increment_iteration('step_a')
        assert iteration == 1
        assert context.get_iteration('step_a') == 1

        iteration = context.increment_iteration('step_a')
        assert iteration == 2

    def test_max_iterations_safety(self):
        """Test that loops stop at max iterations."""
        context = LoopExecutionContext({'max_iterations': 3})

        # First 3 iterations should be allowed
        for i in range(3):
            context.increment_iteration('step_a')
            should_stop, reason = context.should_stop_loop('loop1', 'step_a')

            if i < 2:  # Iterations 0, 1
                assert not should_stop, f"Iteration {i} stopped too early"
            else:  # Iteration 2 (3rd iteration, at limit)
                assert should_stop, f"Iteration {i} should have stopped"
                assert 'max iterations' in reason.lower()

    @pytest.mark.asyncio
    async def test_timeout_safety(self):
        """Test that loops stop after timeout."""
        context = LoopExecutionContext({'max_loop_time_seconds': 1})

        context.start_loop('loop1')

        # Should not stop immediately
        should_stop, _ = context.should_stop_loop('loop1', 'step_a')
        assert not should_stop

        # Sleep past timeout
        await asyncio.sleep(1.2)

        # Should stop now
        should_stop, reason = context.should_stop_loop('loop1', 'step_a')
        assert should_stop
        assert 'time' in reason.lower() or 'exceeded' in reason.lower()

    def test_record_step(self):
        """Test step execution recording."""
        context = LoopExecutionContext()

        context.record_step('step_a', 1)
        context.record_step('step_b', 1)
        context.record_step('step_a', 2)  # Loop back to a

        assert len(context.loop_history) == 3
        assert context.loop_history[0]['step'] == 'step_a'
        assert context.loop_history[0]['iteration'] == 1
        assert context.loop_history[2]['iteration'] == 2

    @pytest.mark.asyncio
    async def test_iteration_delay(self):
        """Test delay between iterations."""
        context = LoopExecutionContext({'iteration_delay_seconds': 0.1})

        start = datetime.now()
        await context.delay_if_needed()
        elapsed = (datetime.now() - start).total_seconds()

        assert elapsed >= 0.1

    def test_get_execution_summary(self):
        """Test execution summary generation."""
        context = LoopExecutionContext()

        context.increment_iteration('step_a')
        context.increment_iteration('step_b')
        context.increment_iteration('step_a')

        summary = context.get_execution_summary()

        assert summary['total_iterations'] == 3
        assert summary['steps_executed'] == 2
        assert summary['iteration_breakdown']['step_a'] == 2
        assert summary['iteration_breakdown']['step_b'] == 1

    def test_get_loop_duration(self):
        """Test loop duration tracking."""
        context = LoopExecutionContext()

        context.start_loop('loop1')

        # Duration should be very small (just started)
        duration = context.get_loop_duration('loop1')
        assert duration is not None
        assert duration >= 0
        assert duration < 1  # Should be under 1 second


class TestLoopAwareExecutor:
    """Tests for loop-aware pipeline executor."""

    def test_has_loops_detection(self):
        """Test detection of loops in pipeline."""
        flow_with_loop = {
            'start_at': 'step_a',
            'paths': [
                {'from': 'step_a', 'to': 'step_b'},
                {'from': 'step_b', 'to': 'step_a', 'condition': {'type': 'expression'}}
            ]
        }

        executor = LoopAwareExecutor(flow_with_loop)
        assert executor.has_loops() is True

        flow_without_loop = {
            'start_at': 'step_a',
            'paths': [
                {'from': 'step_a', 'to': 'step_b'},
                {'from': 'step_b', 'to': 'step_c'}
            ]
        }

        executor = LoopAwareExecutor(flow_without_loop)
        assert executor.has_loops() is False

    def test_is_step_in_loop(self):
        """Test checking if step is in loop."""
        flow = {
            'start_at': 'step_a',
            'paths': [
                {'from': 'step_a', 'to': 'step_b'},
                {'from': 'step_b', 'to': 'step_a', 'condition': {'type': 'expression'}},
                {'from': 'step_b', 'to': 'step_c'}  # step_c not in loop
            ]
        }

        executor = LoopAwareExecutor(flow)

        assert executor.is_step_in_loop('step_a') is True
        assert executor.is_step_in_loop('step_b') is True
        assert executor.is_step_in_loop('step_c') is False

    @pytest.mark.asyncio
    async def test_check_loop_safety(self):
        """Test loop safety checking."""
        flow = {
            'start_at': 'step_a',
            'paths': [
                {'from': 'step_a', 'to': 'step_b'},
                {'from': 'step_b', 'to': 'step_a', 'condition': {'type': 'expression'}}
            ]
        }

        executor = LoopAwareExecutor(flow, {'max_iterations': 2})

        # First iteration should be safe
        is_safe, _ = await executor.check_loop_safety('step_a', 'loop_step_a')
        assert is_safe

        # Record iterations
        executor.loop_context.increment_iteration('step_a')
        executor.loop_context.increment_iteration('step_a')

        # Should hit limit
        is_safe, reason = await executor.check_loop_safety('step_a', 'loop_step_a')
        assert not is_safe
        assert 'max iterations' in reason.lower()

    def test_record_step_execution(self):
        """Test recording step execution."""
        flow = {
            'start_at': 'step_a',
            'paths': [
                {'from': 'step_a', 'to': 'step_b'}
            ]
        }

        executor = LoopAwareExecutor(flow)

        executor.record_step_execution('step_a', 1, None)

        assert len(executor.loop_context.loop_history) == 1

    def test_get_execution_metadata(self):
        """Test execution metadata generation."""
        flow = {
            'start_at': 'step_a',
            'paths': [
                {'from': 'step_a', 'to': 'step_b'},
                {'from': 'step_b', 'to': 'step_a', 'condition': {'type': 'expression'}}
            ]
        }

        executor = LoopAwareExecutor(flow)

        metadata = executor.get_execution_metadata()

        assert metadata['has_loops'] is True
        assert metadata['loop_count'] == 1
        assert 'execution_summary' in metadata
        assert 'loops' in metadata
        assert len(metadata['loops']) == 1

    def test_format_execution_report(self):
        """Test execution report formatting."""
        flow = {
            'start_at': 'step_a',
            'paths': [
                {'from': 'step_a', 'to': 'step_b'},
                {'from': 'step_b', 'to': 'step_a', 'condition': {'type': 'expression'}}
            ]
        }

        executor = LoopAwareExecutor(flow)

        # Simulate some execution
        executor.loop_context.increment_iteration('step_a')
        executor.loop_context.increment_iteration('step_b')

        report = executor.format_execution_report()

        assert 'Loop Execution Report' in report
        assert 'Total iterations' in report
        assert 'step_a' in report

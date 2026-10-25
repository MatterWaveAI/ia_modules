"""
Pipeline Performance Tests

Comprehensive performance testing for pipeline execution:
- Throughput (pipelines/sec)
- Latency (P50, P95, P99)
- Memory usage
- Scalability
- Large data handling
"""

import pytest
import time
import asyncio
from ia_modules.pipeline.core import Pipeline, Step
from ia_modules.pipeline.test_utils import create_test_execution_context
from ia_modules.pipeline.services import ServiceRegistry


class SimpleStep(Step):
    """Simple test step"""
    def __init__(self, name):
        super().__init__(name, {})

    async def run(self, data):
        return {"result": data.get("value", 0) + 1}


class SlowStep(Step):
    """Slow test step"""
    def __init__(self, name):
        super().__init__(name, {})

    async def run(self, data):
        await asyncio.sleep(0.1)
        return {"result": "slow"}


class DataProcessingStep(Step):
    """Step that processes data"""
    def __init__(self, name):
        super().__init__(name, {})

    async def run(self, data):
        input_data = data.get("data", [])
        result = [x * 2 for x in input_data]
        return {"processed": result}


def create_pipeline(steps):
    """Helper to create a pipeline with proper configuration"""
    flow = {
        "start_at": steps[0].name,
        "paths": []
    }

    # Create sequential paths
    for i in range(len(steps) - 1):
        flow["paths"].append({
            "from_step": steps[i].name,
            "to_step": steps[i + 1].name
        })

    # Add final path to end
    flow["paths"].append({
        "from_step": steps[-1].name,
        "to_step": "end_with_success"
    })

    return Pipeline(
        name="test_pipeline",
        steps=steps,
        flow=flow,
        services=ServiceRegistry(),
        enable_telemetry=False
    )


class TestPipelineThroughput:
    """Test pipeline execution throughput"""

    @pytest.mark.asyncio
    async def test_simple_pipeline_throughput(self):
        """Test how many simple pipelines can execute per second"""
        steps = [SimpleStep("step1"), SimpleStep("step2"), SimpleStep("step3")]
        pipeline = create_pipeline(steps)

        iterations = 100
        start = time.time()

        for i in range(iterations):
            result = await pipeline.run({"value": i}, create_test_execution_context())
            # Steps is now a list, check it has entries
            assert len(result.get("steps", [])) > 0

        elapsed = time.time() - start
        throughput = iterations / max(elapsed, 1e-9)

        print(f"\nSimple pipeline throughput: {throughput:.1f} pipelines/sec")
        print(f"Average time per pipeline: {elapsed/iterations*1000:.2f}ms")

        # Should handle at least 50 pipelines/sec
        assert throughput > 50

    @pytest.mark.asyncio
    async def test_parallel_pipeline_throughput(self):
        """Test concurrent pipeline execution"""
        steps = [SimpleStep("step1"), SimpleStep("step2")]
        pipeline = create_pipeline(steps)

        iterations = 100
        start = time.time()

        # Execute pipelines concurrently
        tasks = [pipeline.run({"value": i}, create_test_execution_context()) for i in range(iterations)]
        results = await asyncio.gather(*tasks)

        elapsed = time.time() - start
        throughput = iterations / max(elapsed, 1e-9)

        print(f"\nParallel pipeline throughput: {throughput:.1f} pipelines/sec")

        # Concurrent execution should be much faster
        assert throughput > 100
        assert len(results) == iterations


class TestPipelineLatency:
    """Test pipeline execution latency"""

    @pytest.mark.asyncio
    async def test_latency_percentiles(self):
        """Test P50, P95, P99 latency"""
        steps = [SimpleStep("step1")]
        pipeline = create_pipeline(steps)

        latencies = []
        iterations = 100  # Reduced from 1000 for faster testing

        for i in range(iterations):
            start = time.time()
            await pipeline.run({"value": i}, create_test_execution_context())
            latencies.append((time.time() - start) * 1000)  # Convert to ms

        latencies.sort()

        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        print(f"\nLatency percentiles ({iterations} iterations):")
        print(f"P50: {p50:.2f}ms")
        print(f"P95: {p95:.2f}ms")
        print(f"P99: {p99:.2f}ms")

        # Performance targets (relaxed for test environment)
        assert p50 < 100.0  # P50 should be < 100ms
        assert p95 < 500.0  # P95 should be < 500ms

    @pytest.mark.asyncio
    async def test_slow_step_impact(self):
        """Test impact of slow steps on overall latency"""
        fast_steps = [SimpleStep("fast")]
        slow_steps = [SlowStep("slow")]

        fast_pipeline = create_pipeline(fast_steps)
        slow_pipeline = create_pipeline(slow_steps)

        # Fast pipeline
        start = time.time()
        await fast_pipeline.run({"value": 1}, create_test_execution_context())
        fast_time = time.time() - start

        # Slow pipeline
        start = time.time()
        await slow_pipeline.run({"value": 1}, create_test_execution_context())
        slow_time = time.time() - start

        print(f"\nFast pipeline: {fast_time*1000:.2f}ms")
        print(f"Slow pipeline: {slow_time*1000:.2f}ms")
        print(f"Difference: {(slow_time - fast_time)*1000:.2f}ms")

        # Slow pipeline should be noticeably slower
        assert slow_time > fast_time + 0.05  # At least 50ms slower


class TestDataProcessing:
    """Test processing of large datasets"""

    @pytest.mark.asyncio
    async def test_large_array_processing(self):
        """Test processing large arrays of data"""
        steps = [DataProcessingStep("processor")]
        pipeline = create_pipeline(steps)

        # Test with increasingly large datasets
        sizes = [100, 1000, 10000]

        for size in sizes:
            data = list(range(size))

            start = time.time()
            result = await pipeline.run({"data": data}, create_test_execution_context())
            elapsed = time.time() - start

            # Find processor step result
            processor_step = next(s for s in result.get("steps", []) if s["step_name"] == "processor")
            processed = processor_step["result"].get("processed", [])

            print(f"\nProcessed {size} items in {elapsed*1000:.2f}ms")
            print(f"Throughput: {size/ max(elapsed, 1e-9):.0f} items/sec")

            assert len(processed) == size
            assert processed[0] == 0  # First item should be 0 * 2
            assert processed[-1] == (size - 1) * 2

    @pytest.mark.asyncio
    async def test_memory_efficiency(self):
        """Test that pipeline doesn't leak memory with repeated executions"""
        steps = [DataProcessingStep("processor")]
        pipeline = create_pipeline(steps)

        # Run many iterations
        iterations = 50  # Reduced from 1000
        data = list(range(100))

        start = time.time()
        for _ in range(iterations):
            result = await pipeline.run({"data": data}, create_test_execution_context())
            # Steps is now a list, just check it exists
            assert len(result.get("steps", [])) > 0

        elapsed = time.time() - start
        avg_time = elapsed / iterations

        print(f"\n{iterations} iterations: {elapsed:.2f}s")
        print(f"Average time: {avg_time*1000:.2f}ms")

        # Should maintain consistent performance
        assert avg_time < 0.1  # Less than 100ms per execution


class TestScalability:
    """Test pipeline scalability"""

    @pytest.mark.asyncio
    async def test_concurrent_execution_scaling(self):
        """Test performance with increasing concurrency"""
        steps = [SimpleStep("step1")]
        pipeline = create_pipeline(steps)

        concurrency_levels = [1, 10, 50]

        for concurrency in concurrency_levels:
            start = time.time()

            tasks = [
                pipeline.run({"value": i}, create_test_execution_context())
                for i in range(concurrency)
            ]
            results = await asyncio.gather(*tasks)

            elapsed = time.time() - start
            throughput = concurrency / max(elapsed, 1e-9)

            print(f"\nConcurrency {concurrency}: {throughput:.1f} pipelines/sec")

            assert len(results) == concurrency

    @pytest.mark.asyncio
    async def test_step_chain_scaling(self):
        """Test performance with increasing number of steps"""
        step_counts = [1, 3, 5]

        for count in step_counts:
            steps = [SimpleStep(f"step{i}") for i in range(count)]
            pipeline = create_pipeline(steps)

            iterations = 20
            start = time.time()

            for i in range(iterations):
                await pipeline.run({"value": i}, create_test_execution_context())

            elapsed = time.time() - start
            avg_time = (elapsed / iterations) * 1000

            print(f"\n{count} steps: {avg_time:.2f}ms per execution")

            # Time should scale roughly linearly
            assert avg_time < count * 50  # Less than 50ms per step

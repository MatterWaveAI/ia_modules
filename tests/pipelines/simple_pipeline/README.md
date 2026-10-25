# Simple Three-Step Pipeline

A basic example demonstrating sequential data flow and transformation in IA Modules.

## What It Does

This pipeline takes a topic string and transforms it through three sequential steps:

```
Input: "artificial intelligence"
  ↓
Step 1: Uppercase + "PROCESSED_" prefix
  → "PROCESSED_ARTIFICIAL INTELLIGENCE"
  ↓
Step 2: Lowercase + "_enriched" suffix
  → "processed_artificial intelligence_enriched"
  ↓
Step 3: Reverse + "FINAL_" prefix
  → "FINAL_dehcirne_ecnegilletni laicifitra_dessecorp"
```

## File Structure

```
simple_pipeline/
├── README.md          # This file
├── pipeline.json      # Pipeline configuration
└── steps/
    ├── step1.py       # Data Preparation step
    ├── step2.py       # Data Enrichment step
    └── step3.py       # Data Finalization step
```

## Pipeline Configuration (`pipeline.json`)

### Parameters
- **topic** (string, required) - The input topic to process

### Steps Configuration

Each step follows the same pattern:

```json
{
  "id": "step1",
  "name": "Data Preparation",
  "step_class": "Step1",
  "module": "tests.pipelines.simple_pipeline.steps.step1",
  "inputs": [
    {
      "name": "topic",
      "source": "{parameters.topic}",  // or {steps.previous_step.output.topic}
      "schema": {"type": "string"},
      "required": true
    }
  ],
  "outputs": [
    {
      "name": "topic",
      "schema": {"type": "string"},
      "required": true
    }
  ]
}
```

### Flow Control

The pipeline uses **unconditional sequential flow**:

```json
{
  "flow": {
    "start_at": "step1",
    "paths": [
      {"from_step": "step1", "to_step": "step2", "condition": {"type": "always"}},
      {"from_step": "step2", "to_step": "step3", "condition": {"type": "always"}}
    ]
  }
}
```

## How to Run

### Using the Showcase App

1. Navigate to the **Pipelines** page
2. Find "Simple Three-Step Pipeline"
3. Click **Execute**
4. Enter a topic (e.g., "machine learning")
5. Click **Execute Pipeline**
6. View the execution progress and results

### Using Python Code

Run from the repository root so the `tests.pipelines...` step modules are importable:

```python
import asyncio, json
from ia_modules.pipeline.graph_pipeline_runner import GraphPipelineRunner
from ia_modules.pipeline.core import ExecutionContext

async def main():
    with open("tests/pipelines/simple_pipeline/pipeline.json") as f:
        config = json.load(f)

    runner = GraphPipelineRunner()
    result = await runner.run_pipeline_from_json(
        config,
        input_data={"topic": "artificial intelligence"},
        execution_context=ExecutionContext(execution_id="simple-1", pipeline_id="simple_pipeline"),
    )

    # Get final output
    print(result["output"]["topic"])
    # Output: "FINAL_dehcirne_ecnegilletni laicifitra_dessecorp"

asyncio.run(main())
```

### Using the CLI

```bash
echo '{"topic": "artificial intelligence"}' > input.json
ia-modules run tests/pipelines/simple_pipeline/pipeline.json --input input.json --working-dir .
```

## Using CLI (if available)

```bash
ia-modules execute tests/pipelines/simple_pipeline/pipeline.json \
  --input '{"topic": "artificial intelligence"}'
```

## Key Concepts Demonstrated

### 1. **Data Flow**
- Each step receives its input from the previous step's output
- Data flows sequentially through the pipeline
- The framework handles data passing automatically

### 2. **Input/Output Binding**
```python
# Step 1 gets from pipeline parameters
"source": "{parameters.topic}"

# Step 2 gets from Step 1's output
"source": "{steps.step1.output.topic}"

# Step 3 gets from Step 2's output
"source": "{steps.step2.output.topic}"
```

### 3. **Step Implementation**
Each step:
- Inherits from `ia_modules.pipeline.core.Step`
- Implements async `run()` method
- Receives resolved inputs as dict
- Returns outputs as dict

```python
class Step1(Step):
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        topic = input.get("topic", "unknown")
        transformed_topic = f"PROCESSED_{topic.upper()}"
        return {"topic": transformed_topic}
```

### 4. **Always Conditions**
- Each transition uses `"condition": {"type": "always"}`
- This means the next step always executes
- More complex pipelines can use conditional logic

## Testing

This pipeline is used in integration tests to verify:
- ✅ Sequential step execution
- ✅ Data passing between steps
- ✅ Input parameter resolution
- ✅ Output collection
- ✅ Pipeline completion

## Extending This Pipeline

You can modify this pipeline to learn more:

1. **Add a fourth step** - Add validation or formatting
2. **Add conditional logic** - Execute step 3 only if step 2 output meets criteria
3. **Add parallel steps** - Split processing after step 1
4. **Add error handling** - Handle invalid input gracefully
5. **Add retry logic** - Retry failed transformations

## Related Examples

- **Conditional Pipeline** - Shows branching logic
- **Parallel Pipeline** - Demonstrates concurrent execution
- **Error Handling Pipeline** - Shows retry and compensation
- **Human-in-the-Loop Pipeline** - Demonstrates async approval

## Troubleshooting

**Issue: Pipeline doesn't execute**
- Check that all step modules are importable
- Verify the pipeline.json syntax is valid
- Ensure required input parameters are provided

**Issue: Data not passing between steps**
- Verify output names match input sources
- Check that each step returns the expected output format
- Review the step execution logs

**Issue: Transformation not working as expected**
- Add logging to each step's `run()` method
- Print input/output at each stage
- Verify data types match schema definitions

## Learn More

- [Getting Started](../../../docs/GETTING_STARTED.md)
- [Pipeline Architecture](../../../docs/PIPELINE_ARCHITECTURE.md)
- [Execution Architecture](../../../docs/EXECUTION_ARCHITECTURE.md)
- [IA Modules Documentation](../../../README.md)

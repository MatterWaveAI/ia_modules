# AI Patterns LLM Integration Testing

This guide explains how to run integration tests for AI patterns (Chain-of-Thought, Self-Consistency, ReAct, Tree of Thoughts) with real LLM providers.

> **Note:** `tests/integration/test_patterns_llm_integration.py`, which every command below runs, has been removed
> from the repository, so these commands currently fail with "file not found". The guide is kept for reference.

## Quick Start

### 1. Set API Keys

You need at least one LLM provider API key. Set them as environment variables:

**PowerShell (Windows):**
```powershell
$env:OPENAI_API_KEY="sk-..."
$env:ANTHROPIC_API_KEY="sk-ant-..."
$env:GOOGLE_API_KEY="AIza..."  # or GEMINI_API_KEY
```

**Bash (Linux/Mac):**
```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="AIza..."
```

**Or create a .env file in the tests directory:**
```bash
# tests/.env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
```

### 2. Run the Tests

**Run all integration tests:**
```bash
# from the repository root
python -m pytest tests/integration/test_patterns_llm_integration.py -v
```

**Run tests for specific provider:**
```bash
# OpenAI only
pytest tests/integration/test_patterns_llm_integration.py -v -k openai

# Anthropic only
pytest tests/integration/test_patterns_llm_integration.py -v -k anthropic

# Google only
pytest tests/integration/test_patterns_llm_integration.py -v -k google
```

**Run tests for specific pattern:**
```bash
# Chain-of-Thought tests only
pytest tests/integration/test_patterns_llm_integration.py -v -k cot

# Self-Consistency tests only
pytest tests/integration/test_patterns_llm_integration.py -v -k self_consistency

# ReAct Agent tests only
pytest tests/integration/test_patterns_llm_integration.py -v -k react

# Tree of Thoughts tests only
pytest tests/integration/test_patterns_llm_integration.py -v -k tot
```

**Run comparison tests (tests all available providers):**
```bash
pytest tests/integration/test_patterns_llm_integration.py -v -k comparison
```

**Run performance tests (slower, measures latency):**
```bash
pytest tests/integration/test_patterns_llm_integration.py -v -k performance
```

## What Gets Tested

### Chain-of-Thought (CoT)
- ✅ Math reasoning problems
- ✅ Logic problems
- ✅ Word problems
- ✅ Multi-step reasoning
- ✅ Numbered and bullet formats

### Self-Consistency
- ✅ Factual questions with majority voting
- ✅ Calculations with confidence scoring
- ✅ Threshold-based consensus
- ✅ Multiple sampling strategies
- ✅ Parallel vs sequential execution

### ReAct Agent
- ✅ Tool usage (calculator, search, wikipedia)
- ✅ Multi-step reasoning with actions
- ✅ Trajectory tracking
- ✅ Error handling
- ✅ Max iteration limits

### Tree of Thoughts (ToT)
- ✅ Problem solving with exploration
- ✅ Creative tasks
- ✅ Pruning strategies (best-first, threshold, beam search)
- ✅ Node evaluation and scoring
- ✅ Branch exploration

### Cross-Provider Comparison
- ✅ Consistency across providers
- ✅ Answer correctness comparison
- ✅ Confidence scoring comparison

### Performance Metrics
- ✅ Latency measurements
- ✅ Parallel vs sequential speed
- ✅ Token usage tracking

## Expected Output

When tests run successfully, you'll see output like:

```
✓ OpenAI CoT Result:
  Reasoning: Step 1: The train travels 60 miles in 1 hour...
  Answer: 150 miles

✓ Anthropic Self-Consistency Result:
  Answer: Paris
  Confidence: 100.00%
  Samples: 5

✓ Google ReAct Result:
  Answer: The final price is $40
  Steps: 3

✓ Cross-Provider CoT Comparison:
  openai       - Answer: 56                         - Correct: True
  anthropic    - Answer: 56                         - Correct: True
  google       - Answer: 56                         - Correct: True
```

## API Key Locations

Get your API keys from:

- **OpenAI**: https://platform.openai.com/api-keys
- **Anthropic**: https://console.anthropic.com/account/keys
- **Google AI**: https://makersuite.google.com/app/apikey

## Models Used

The tests use the following models by default:

- **OpenAI**: `gpt-3.5-turbo` (fast and cost-effective)
- **Anthropic**: `claude-3-haiku-20240307` (fast and efficient)
- **Google**: `gemini-2.0-flash-exp` (latest experimental model)

You can modify these in the test file if needed.

## Costs

These integration tests make real API calls, so they will incur small costs:

- **OpenAI GPT-3.5-turbo**: ~$0.001 per test
- **Anthropic Haiku**: ~$0.001 per test
- **Google Gemini**: Free tier available, then ~$0.001 per test

Total cost to run all tests: **~$0.05 - $0.20** depending on which providers you test.

## Troubleshooting

### Tests are skipped
```
SKIPPED [1] test_patterns_llm_integration.py:52: OPENAI_API_KEY not set
```
**Solution**: Set the API key environment variable for that provider.

### Authentication errors
```
Exception: Invalid API key
```
**Solution**: Check that your API key is correct and has not expired.

### Rate limit errors
```
Exception: Rate limit exceeded
```
**Solution**: Wait a few seconds and try again, or reduce the number of tests running in parallel.

### Import errors
```
ModuleNotFoundError: No module named 'ia_modules'
```
**Solution**: Make sure you're in the correct directory and the package is installed:
```bash
# from the repository root
pip install -e .
```

### Tests fail with wrong answers
This is normal for some creative/open-ended prompts. The tests focus on:
- Response structure (not empty, has required fields)
- Factual correctness (for factual questions)
- Proper tool usage (for ReAct)
- Exploration behavior (for ToT)

## Running Specific Test Classes

```bash
# Only Chain-of-Thought tests
pytest tests/integration/test_patterns_llm_integration.py::TestChainOfThoughtLLMIntegration -v

# Only Self-Consistency tests
pytest tests/integration/test_patterns_llm_integration.py::TestSelfConsistencyLLMIntegration -v

# Only ReAct tests
pytest tests/integration/test_patterns_llm_integration.py::TestReActAgentLLMIntegration -v

# Only Tree of Thoughts tests
pytest tests/integration/test_patterns_llm_integration.py::TestTreeOfThoughtsLLMIntegration -v

# Only cross-provider comparison
pytest tests/integration/test_patterns_llm_integration.py::TestCrossProviderComparison -v

# Only performance tests
pytest tests/integration/test_patterns_llm_integration.py::TestPatternPerformance -v
```

## Running a Single Test

```bash
pytest tests/integration/test_patterns_llm_integration.py::TestChainOfThoughtLLMIntegration::test_cot_openai_math_problem -v
```

## CI/CD Integration

To run these tests in CI/CD, add API keys as secrets and conditionally run:

```yaml
- name: Run Pattern LLM Integration Tests
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
  run: |
    pytest tests/integration/test_patterns_llm_integration.py -v
```

Tests will automatically skip providers without API keys.

## Test Statistics

- **Total Tests**: 19 integration tests
- **Patterns Tested**: 4 (CoT, Self-Consistency, ReAct, ToT)
- **Providers Supported**: 3 (OpenAI, Anthropic, Google)
- **Test Coverage**:
  - Chain-of-Thought: 3 provider tests
  - Self-Consistency: 3 provider tests
  - ReAct Agent: 3 provider tests
  - Tree of Thoughts: 3 provider tests
  - Cross-provider: 2 comparison tests
  - Performance: 2 performance tests

## Next Steps

After running these tests:

1. ✅ Verify all patterns work with your API keys
2. ✅ Check cross-provider consistency
3. ✅ Review performance metrics
4. ✅ Integrate patterns into your pipelines
5. ✅ Monitor token usage and costs

## Support

If you encounter issues:
1. Check the test output for specific error messages
2. Verify API keys are set correctly
3. Ensure you have the latest version: `pip install -e . --upgrade`
4. Review the test file for detailed implementation

Happy testing! 🚀

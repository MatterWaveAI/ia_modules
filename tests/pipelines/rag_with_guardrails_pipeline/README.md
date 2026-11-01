# RAG Pipeline with Guardrails

Retrieval-augmented generation with the library's guardrails at each boundary: the
question is checked on the way in, the retrieved documents are checked before they
reach the model, and the answer is checked on the way out.

```
query
   ↓
input_guardrails        InputGuardrailStep      jailbreaks blocked, personal data redacted
   ↓
load_documents          DocumentLoaderStep      reads sample_docs/ (.txt, .md, .json, .rst)
   ↓
retrieve                SimpleRetrieverStep     keyword scoring, top_k 2
   ↓
retrieval_guardrails    RetrievalGuardrailStep  checks the documents (max_doc_length 5000)
   ↓
build_context           ContextBuilderStep      concatenates the documents, max_length 3000
   ↓
rag_llm                 RAGLLMStep              answers the query from the context
   ↓
output_guardrails       OutputGuardrailStep     toxic answers blocked, max_length 1000
   ↓
answer
```

The guardrail steps come from `ia_modules.guardrails.pipeline_steps`; the retrieval
steps are in `steps/` and work on the files in `sample_docs/`. `steps/sql_retriever.py`
is an alternative retriever backed by a database (`setup_test_db.py` loads the sample
documents into one); it is not wired into `pipeline.json`.

## Run it

```bash
echo '{"query": "How do I define a function in Python?"}' > input.json
ia-modules run tests/pipelines/rag_with_guardrails_pipeline/pipeline.json --working-dir . --input input.json
```

`query` (string) is required.

## With and without an agent

`rag_llm` is an `LLMStep`. With a registered agent executor (the showcase backend has
one) the model answers from the context. Without one, under pytest or the bare CLI, the
step answers with an excerpt of the retrieved context, so every guardrail still runs
against real data.

## Output

`answer`, plus `input_guardrails_result` and `output_guardrails_result` (each with its
`action`), `retrieved_docs`, `num_retrieved`, and the `context` the answer was built from.

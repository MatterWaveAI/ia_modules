# Vector RAG Pipeline with ChromaDB

RAG pipeline using vector embeddings and ChromaDB for semantic search.

## Features

- ✅ Vector embeddings using OpenAI text-embedding-3-small
- ✅ ChromaDB for vector storage and similarity search
- ✅ Semantic search (not just keyword matching)
- ✅ Persistent vector database
- ✅ Input/Output/Retrieval guardrails
- ✅ LLM answer generation with context

## Setup

```bash
# Install dependencies
pip install chromadb openai

# Ensure .env has OPENAI_API_KEY
```

## Usage

### Step 1: Index Documents

First, index your documents into the vector database:

From the repository root:

```bash
ia-modules run tests/pipelines/vector_rag_pipeline/index_pipeline.json --working-dir .
```

This will:
- Load documents from `rag_with_guardrails_pipeline/sample_docs/`
- Generate embeddings for each document
- Store in ChromaDB at `vector_rag_pipeline/chroma_db/`

### Step 2: Query with Semantic Search

Then query using natural language:

```bash
echo '{"query": "What is attention mechanism?"}' > input.json
ia-modules run tests/pipelines/vector_rag_pipeline/query_pipeline.json --input input.json --working-dir .
```

This will:
- Generate embedding for your query
- Find semantically similar documents using cosine similarity
- Build context from top results
- Generate answer using LLM

## How Vector Search Works

**Traditional keyword search:**
- Query: "neural network learning"
- Matches: Documents containing those exact words

**Vector semantic search:**
- Query: "neural network learning"
- Matches: Documents about:
  - Deep learning
  - Backpropagation
  - Training algorithms
  - Model optimization

Even if they don't use the exact words!

## Architecture

### Indexing Pipeline:
```
Load Docs → Generate Embeddings → Store in ChromaDB
```

### Query Pipeline:
```
Input Guards → Embed Query → Vector Search → Retrieval Guards
            ↓
Context Builder → LLM Answer → Output Guards
```

## Vector Database

**ChromaDB** stores:
- Document text
- 1536-dimensional embeddings (text-embedding-3-small)
- Metadata (filename, type, size)
- Uses cosine similarity for search

**Persistence:**
- Database saved to `chroma_db/` directory
- Survives between runs
- Can be version controlled or deployed

## Example Queries

Semantic search finds related content even with different wording:

```bash
# These all find transformer/attention documents:
"explain attention mechanisms"
"how do transformers work"
"self-attention in neural networks"
"what makes GPT different from RNNs"
```

## Benefits vs Keyword Search

- ✅ Understands meaning, not just words
- ✅ Finds synonyms and related concepts
- ✅ Works across languages (with multilingual models)
- ✅ Handles typos and variations better
- ✅ More relevant results

## Customization

Edit `index_pipeline.json` or `query_pipeline.json`:

```json
{
  "config": {
    "embedding_model": "text-embedding-3-large",  // More accurate, larger
    "top_k": 5,                                   // Return more results
    "collection_name": "my_docs"                  // Different collection
  }
}
```

## Output

Results saved to `runs/run_YYYYMMDD_HHMMSS/` with:
- Retrieved documents with similarity scores
- Generated answer
- LLM metadata (tokens, model, etc.)

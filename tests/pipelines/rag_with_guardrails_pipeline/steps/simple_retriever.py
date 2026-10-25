"""Simple keyword-based retriever for RAG pipeline."""
from typing import Dict, Any
from ia_modules.pipeline.core import Step


class SimpleRetrieverStep(Step):
    """Simple keyword-based document retriever."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.query_field = config.get("query_field", "query")
        self.docs_field = config.get("docs_field", "documents")
        self.top_k = config.get("top_k", 3)

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve relevant documents based on query."""
        query = data.get(self.query_field, "")
        documents = data.get(self.docs_field, [])

        if not query:
            self.logger.warning("No query provided")
            data["retrieved_docs"] = []
            return data

        if not documents:
            self.logger.warning("No documents available")
            data["retrieved_docs"] = []
            return data

        # Simple keyword matching
        query_lower = query.lower()
        query_words = set(query_lower.split())

        # Score each document
        scored_docs = []
        for doc in documents:
            content_lower = doc["content"].lower()

            # Count keyword matches
            score = sum(1 for word in query_words if word in content_lower)

            # Boost for exact phrase match
            if query_lower in content_lower:
                score += 10

            scored_docs.append({
                "doc": doc,
                "score": score
            })

        # Sort by score and take top k
        scored_docs.sort(key=lambda x: x["score"], reverse=True)
        top_docs = [item["doc"] for item in scored_docs[:self.top_k] if item["score"] > 0]

        self.logger.info(f"Retrieved {len(top_docs)} relevant documents")

        data["retrieved_docs"] = top_docs
        data["num_retrieved"] = len(top_docs)

        return data

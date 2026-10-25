"""Context builder for RAG pipeline."""
from typing import Dict, Any
from ia_modules.pipeline.core import Step


class ContextBuilderStep(Step):
    """Build context from retrieved documents."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.docs_field = config.get("docs_field", "retrieved_docs")
        self.max_length = config.get("max_length", 2000)

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build context string from retrieved documents."""
        retrieved_docs = data.get(self.docs_field, [])

        if not retrieved_docs:
            self.logger.warning("No retrieved documents to build context from")
            data["context"] = ""
            return data

        # Build context from documents
        context_parts = []
        total_length = 0

        for i, doc in enumerate(retrieved_docs, 1):
            # Create section for this document
            section = f"[Document {i}: {doc['filename']}]\n{doc['content']}\n"

            # Check if adding this would exceed max length
            if total_length + len(section) > self.max_length:
                # Truncate this section
                remaining = self.max_length - total_length
                if remaining > 100:  # Only add if we have reasonable space left
                    section = section[:remaining] + "...\n"
                    context_parts.append(section)
                break

            context_parts.append(section)
            total_length += len(section)

        context = "\n".join(context_parts)

        self.logger.info(f"Built context from {len(retrieved_docs)} documents ({len(context)} chars)")

        data["context"] = context
        data["context_length"] = len(context)

        return data

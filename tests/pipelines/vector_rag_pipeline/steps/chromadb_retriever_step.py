"""Retrieve documents from ChromaDB using vector similarity."""
from typing import Dict, Any
from pathlib import Path
from ia_modules.pipeline.core import Step


class ChromaDBRetrieverStep(Step):
    """Retrieve documents from ChromaDB using vector similarity."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.collection_name = config.get("collection_name", "documents")
        self.persist_directory = config.get("persist_directory", "./chroma_db")
        self.top_k = config.get("top_k", 3)
        self.query_field = config.get("query_field", "query")
        self.embedding_field = config.get("embedding_field", "embedding")

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve documents using vector similarity."""
        try:
            import chromadb
        except ImportError:
            raise RuntimeError("ChromaDB not installed. Install with: pip install chromadb")

        query_embedding = data.get(self.embedding_field)
        if not query_embedding:
            self.logger.warning("No query embedding provided")
            data["retrieved_docs"] = []
            data["num_retrieved"] = 0
            return data

        # Get absolute path
        pipeline_dir = Path(__file__).parent.parent
        persist_path = pipeline_dir / self.persist_directory

        if not persist_path.exists():
            self.logger.warning(f"ChromaDB not found at {persist_path}")
            data["retrieved_docs"] = []
            data["num_retrieved"] = 0
            return data

        # Create client and get collection
        client = chromadb.PersistentClient(path=str(persist_path))
        collection = client.get_collection(name=self.collection_name)

        # Query collection
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=self.top_k
        )

        # Format results
        retrieved_docs = []
        if results['documents'] and len(results['documents']) > 0:
            for i, doc_text in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                distance = results['distances'][0][i] if results['distances'] else 0.0

                retrieved_docs.append({
                    "content": doc_text,
                    "filename": metadata.get("filename", "unknown"),
                    "type": metadata.get("type", "unknown"),
                    "similarity_score": 1.0 - distance,  # Convert distance to similarity
                    "distance": distance
                })

        self.logger.info(f"Retrieved {len(retrieved_docs)} documents from ChromaDB")

        data["retrieved_docs"] = retrieved_docs
        data["num_retrieved"] = len(retrieved_docs)

        return data

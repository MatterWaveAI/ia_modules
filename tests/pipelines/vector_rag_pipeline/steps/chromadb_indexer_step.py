"""Index documents into ChromaDB vector database."""
from typing import Dict, Any, List
from pathlib import Path
from ia_modules.pipeline.core import Step


class ChromaDBIndexerStep(Step):
    """Index documents into ChromaDB."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.collection_name = config.get("collection_name", "documents")
        self.persist_directory = config.get("persist_directory", "./chroma_db")
        self.docs_field = config.get("docs_field", "documents")
        self.embedding_model = config.get("embedding_model", "text-embedding-3-small")

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Index documents into ChromaDB."""
        try:
            import chromadb
        except ImportError:
            raise RuntimeError("ChromaDB not installed. Install with: pip install chromadb")

        documents = data.get(self.docs_field, [])
        if not documents:
            self.logger.warning("No documents to index")
            data["indexed_count"] = 0
            return data

        # Get LLM service for embeddings
        llm_service = self.services.get('llm_provider')
        if not llm_service:
            raise RuntimeError("LLM service not registered")

        # Get absolute path for persist directory
        pipeline_dir = Path(__file__).parent.parent
        persist_path = pipeline_dir / self.persist_directory

        # Create ChromaDB client
        client = chromadb.PersistentClient(path=str(persist_path))

        # Get or create collection
        collection = client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

        # Prepare documents for indexing
        texts = []
        metadatas = []
        ids = []

        for i, doc in enumerate(documents):
            texts.append(doc.get("content", ""))
            metadatas.append({
                "filename": doc.get("filename", f"doc_{i}"),
                "type": doc.get("type", "unknown"),
                "size": doc.get("size", 0)
            })
            ids.append(f"doc_{i}")

        # Generate embeddings
        self.logger.info(f"Generating embeddings for {len(texts)} documents...")
        embeddings = await self._generate_embeddings(llm_service, texts)

        # Add to collection
        collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )

        self.logger.info(f"Indexed {len(texts)} documents into ChromaDB")

        data["indexed_count"] = len(texts)
        data["collection_name"] = self.collection_name
        data["vector_db_path"] = str(persist_path)

        return data

    async def _generate_embeddings(self, llm_service, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        import openai

        # Get OpenAI provider config
        providers = llm_service.list_providers()
        openai_provider = next((p for p in providers if p['provider'] == 'openai'), None)

        if not openai_provider:
            raise RuntimeError("OpenAI provider not configured")

        client = openai.AsyncOpenAI(api_key=openai_provider['api_key'])

        # Generate embeddings in batch
        response = await client.embeddings.create(
            model=self.embedding_model,
            input=texts
        )

        return [item.embedding for item in response.data]

"""Generate embeddings for text using LLM or embedding models."""
from typing import Dict, Any, List
from ia_modules.pipeline.core import Step


class VectorEmbeddingStep(Step):
    """Generate vector embeddings for text."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.embedding_model = config.get("embedding_model", "text-embedding-3-small")
        self.text_field = config.get("text_field", "query")
        self.output_field = config.get("output_field", "embedding")

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate embedding for input text."""
        llm_service = self.services.get('llm_provider')
        if not llm_service:
            raise RuntimeError("LLM service not registered")

        text = data.get(self.text_field, "")
        if not text:
            self.logger.warning("No text to embed")
            data[self.output_field] = []
            return data

        # Generate embedding using OpenAI
        embedding = await self._generate_embedding(llm_service, text)

        self.logger.info(f"Generated {len(embedding)}-dimensional embedding")

        data[self.output_field] = embedding
        data["embedding_model"] = self.embedding_model

        return data

    async def _generate_embedding(self, llm_service, text: str) -> List[float]:
        """Generate embedding using OpenAI API."""
        try:
            import openai

            # Get OpenAI provider config
            providers = llm_service.list_providers()
            openai_provider = next((p for p in providers if p['provider'] == 'openai'), None)

            if not openai_provider:
                raise RuntimeError("OpenAI provider not configured for embeddings")

            # Create OpenAI client
            client = openai.AsyncOpenAI(api_key=openai_provider['api_key'])

            # Generate embedding
            response = await client.embeddings.create(
                model=self.embedding_model,
                input=text
            )

            return response.data[0].embedding

        except ImportError:
            raise RuntimeError("OpenAI package not installed. Install with: pip install openai")

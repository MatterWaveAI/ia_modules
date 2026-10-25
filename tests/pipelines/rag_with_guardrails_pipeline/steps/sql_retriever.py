"""SQL-based retriever for RAG pipeline."""
from typing import Dict, Any
from ia_modules.pipeline.core import Step


class SQLRetrieverStep(Step):
    """Retrieve documents from SQL database."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.query_field = config.get("query_field", "query")
        self.table = config.get("table", "documents")
        self.content_column = config.get("content_column", "content")
        self.title_column = config.get("title_column", "title")
        self.id_column = config.get("id_column", "id")
        self.search_column = config.get("search_column", self.content_column)
        self.top_k = config.get("top_k", 3)
        self.search_type = config.get("search_type", "keyword")  # keyword, full_text, or vector

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve relevant documents from database."""
        # Get database from services
        db_manager = self.services.get('database')
        if not db_manager:
            raise RuntimeError("Database not registered in services")

        query = data.get(self.query_field, "")
        if not query:
            self.logger.warning("No query provided")
            data["retrieved_docs"] = []
            return data

        # Build SQL query based on search type
        if self.search_type == "full_text":
            # Full-text search (PostgreSQL or MySQL with FULLTEXT index)
            sql = self._build_fulltext_query(query)
        elif self.search_type == "vector":
            # Vector similarity search (requires embedding column)
            sql = self._build_vector_query(query)
        else:
            # Simple keyword search
            sql = self._build_keyword_query(query)

        self.logger.info(f"Executing SQL query: {sql[:100]}...")

        # Execute query
        async with db_manager.get_session() as session:
            result = await session.execute(sql)
            rows = result.fetchall()

        # Convert rows to documents
        retrieved_docs = []
        for row in rows:
            doc = {
                "id": getattr(row, self.id_column, None),
                "title": getattr(row, self.title_column, "Untitled"),
                "content": getattr(row, self.content_column, ""),
                "type": "database",
                "source": f"{self.table}:{getattr(row, self.id_column, 'unknown')}"
            }

            # Add score if available
            if hasattr(row, 'score'):
                doc["score"] = row.score

            retrieved_docs.append(doc)

        self.logger.info(f"Retrieved {len(retrieved_docs)} documents from database")

        data["retrieved_docs"] = retrieved_docs
        data["num_retrieved"] = len(retrieved_docs)

        return data

    def _build_keyword_query(self, query: str):
        """Build simple keyword search query."""
        from sqlalchemy import text

        # Simple LIKE-based search
        sql = text(f"""
            SELECT
                {self.id_column},
                {self.title_column},
                {self.content_column}
            FROM {self.table}
            WHERE {self.search_column} LIKE :query
            LIMIT :limit
        """)

        return sql.bindparams(query=f"%{query}%", limit=self.top_k)

    def _build_fulltext_query(self, query: str):
        """Build full-text search query."""
        from sqlalchemy import text

        # PostgreSQL full-text search
        sql = text(f"""
            SELECT
                {self.id_column},
                {self.title_column},
                {self.content_column},
                ts_rank(to_tsvector('english', {self.search_column}),
                        plainto_tsquery('english', :query)) as score
            FROM {self.table}
            WHERE to_tsvector('english', {self.search_column}) @@
                  plainto_tsquery('english', :query)
            ORDER BY score DESC
            LIMIT :limit
        """)

        return sql.bindparams(query=query, limit=self.top_k)

    def _build_vector_query(self, query: str):
        """Build vector similarity search query."""

        # This requires an embedding column and pgvector extension
        # For now, return a placeholder - user needs to implement embedding logic
        raise NotImplementedError(
            "Vector search requires embedding generation. "
            "Use 'keyword' or 'full_text' search type, or implement custom embedding logic."
        )

"""RAG answer step: the LLM answers the query from the retrieved context."""
from typing import Any, Dict

from ia_modules.pipeline.llm_config import get_agent_config, get_llm_config
from ia_modules.pipeline.llm_step import LLMStep

_SYSTEM_PROMPT = (
    "Answer the user's question using only the provided context. If the context "
    "does not contain the answer, say so. Be concise."
)


class RAGLLMStep(LLMStep):
    """Answer `query_field` from `context_field`, into `output_field`.

    Config: query_field (default "query"), context_field ("context"),
    output_field ("answer"), plus temperature and max_tokens for the agent.
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        self.query_field = config.get("query_field", "query")
        self.context_field = config.get("context_field", "context")
        self.output_field = config.get("output_field", "answer")
        env_config = get_llm_config()
        agent_cfg = get_agent_config()
        merged = {
            **config,
            "system_prompt": _SYSTEM_PROMPT,
            "cwd": agent_cfg["cwd"],
            "logs_dir": agent_cfg["logs_dir"],
            "timeout_seconds": agent_cfg["timeout_seconds"],
            **env_config,
        }
        super().__init__(name, merged)

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        query = str(data.get(self.query_field, ""))
        context = str(data.get(self.context_field, ""))
        if not self.agent_available:
            return self._without_agent(query, context)

        llm_input: Dict[str, Any] = {"prompt": f"Context:\n{context}\n\nQuestion: {query}"}
        if "_execution_id" in data:
            llm_input["_execution_id"] = data["_execution_id"]
        llm_result = await super().run(llm_input)
        return {
            self.output_field: llm_result.get("text", ""),
            "agent_job_id": llm_result.get("agent_job_id"),
            "event_count": llm_result.get("event_count", 0),
        }

    # Without a registered agent executor the answer is the opening of the retrieved
    # context, so the retrieval and output guardrails around this step still run.
    def _without_agent(self, query: str, context: str) -> Dict[str, Any]:
        excerpt = " ".join(context.split())[:400]
        answer = (
            f"From the retrieved documents: {excerpt}" if excerpt
            else "The retrieved documents do not cover this question."
        )
        return {self.output_field: answer, "agent_job_id": None, "event_count": 0}

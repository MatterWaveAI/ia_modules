"""A2AExecutor — dispatches agent execution to an A2A server via JSON-RPC.

Optional executor for distributed setups where agents run on a separate
machine or container. Requires an A2A-compatible server running.

The A2A server handles subprocess spawning, NDJSON normalization, and
log persistence. This executor sends the request and yields a submitted
event — the caller is responsible for receiving callback events.
"""

import logging
import os
from typing import AsyncIterator, Optional

import httpx

from .executor import AgentConfig, AgentEvent, EventType

logger = logging.getLogger(__name__)


class A2AExecutor:
    """Dispatches agent execution to an A2A server.

    Sends JSON-RPC message/send to the server. Events arrive via
    callback URL (server POSTs to your endpoint).

    Args:
        a2a_url: URL of the A2A server (default: http://localhost:3008)
        callback_url: URL where the A2A server should POST events.
    """

    def __init__(
        self,
        a2a_url: Optional[str] = None,
        callback_url: Optional[str] = None,
        auth_token: Optional[str] = None,
    ):
        self.a2a_url = a2a_url or os.getenv("A2A_SERVER_URL", "http://localhost:3008")
        self.callback_url = callback_url
        self.auth_token = auth_token

    async def execute(self, config: AgentConfig) -> AsyncIterator[AgentEvent]:
        """Send agent execution to A2A server and yield events."""
        payload = self._build_payload(config)
        url = f"{self.a2a_url}/api/a2a/jsonrpc"
        label = f"a2a-{config.job_id[:8]}"
        logger.info("[%s] POST %s mode=%s cli=%s", label, url,
                    config.mode.value, config.cli_type.value)

        try:
            headers = {}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
        except Exception as e:
            logger.error("[%s] A2A request failed: %s", label, e)
            yield AgentEvent(
                type=EventType.RESULT, subtype="error",
                error=f"A2A server error: {e}",
                job_id=config.job_id, seq=1,
            )
            yield AgentEvent(
                type=EventType.SYSTEM, subtype="stream_end",
                job_id=config.job_id, seq=2,
            )
            return

        # Task submitted — caller receives events via callback endpoint
        yield AgentEvent(
            type=EventType.SYSTEM, subtype="submitted",
            job_id=config.job_id, seq=1,
            metadata={"a2a_url": self.a2a_url, "task_id": config.job_id},
        )

    def _build_payload(self, config: AgentConfig) -> dict:
        """Build JSON-RPC payload for A2A message/send."""
        prompt = config.task
        if config.chat_history:
            parts = []
            for msg in config.chat_history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user":
                    parts.append(f"User: {content}")
                elif role == "assistant":
                    parts.append(f"Assistant: {content}")
            if parts:
                prompt = (
                    "Previous conversation:\n"
                    + "\n\n".join(parts)
                    + "\n\nCurrent request:\n"
                    + config.task
                )

        return {
            "jsonrpc": "2.0",
            "id": config.job_id,
            "method": "message/send",
            "params": {
                "message": {
                    "taskId": config.job_id,
                    "contextId": config.metadata.get("context_id", ""),
                    "parts": [{"kind": "text", "text": prompt}],
                    "metadata": {
                        "agent_id": config.agent_id,
                        "job_id": config.job_id,
                        "system_prompt": config.system_prompt,
                        "tools": config.tools,
                        "cwd": config.cwd,
                        "mode": config.mode.value,
                        "cli_type": config.cli_type.value,
                        "model": config.model,
                        "provider": config.provider,
                        "api_key": config.api_key,
                        "callback_url": self.callback_url,
                    },
                }
            },
        }

    async def cancel(self, job_id: str) -> bool:
        """Cancel a running task on the A2A server."""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": job_id,
                "method": "tasks/cancel",
                "params": {"id": job_id},
            }
            headers = {}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                resp = await client.post(
                    f"{self.a2a_url}/api/a2a/jsonrpc", json=payload, headers=headers
                )
                return resp.is_success
        except Exception as e:
            logger.error("A2A cancel failed: %s", e)
            return False

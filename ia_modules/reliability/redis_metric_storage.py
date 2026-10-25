"""
Redis-backed metric storage for production reliability metrics.

Uses Redis sorted sets for time-series data and hashes for structured records.
Optimized for high-throughput, low-latency metric storage and retrieval.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import json
import logging

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from .metrics import MetricStorage


class RedisMetricStorage(MetricStorage):
    """
    Redis-backed metric storage using sorted sets and hashes.

    Features:
    - Time-series data using sorted sets (ZADD with timestamp scores)
    - Structured records using hashes
    - Atomic operations for consistency
    - TTL support for automatic cleanup
    - Efficient time-range queries

    Data Model:
    - Steps: Sorted set `reliability:steps:{agent}` with hash `reliability:step:{id}`
    - Workflows: Sorted set `reliability:workflows` with hash `reliability:workflow:{id}`
    - SLO Measurements: Sorted set `reliability:slo:{type}` with hash `reliability:slo:{id}`

    Example:
        >>> storage = RedisMetricStorage(redis_url="redis://localhost:6379")
                >>> await storage.record_step({
        ...     "agent": "researcher",
        ...     "success": True,
        ...     "timestamp": datetime.now(timezone.utc)
        ... })
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        key_prefix: str = "reliability",
        ttl_days: Optional[int] = 90
    ):
        """
        Initialize Redis storage.

        Args:
            redis_url: Redis connection URL
            key_prefix: Prefix for all Redis keys
            ttl_days: Days to retain data (None = forever)
        """
        if not REDIS_AVAILABLE:
            raise ImportError("redis package required for RedisMetricStorage. Install with: pip install redis")

        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.ttl_seconds = ttl_days * 86400 if ttl_days else None
        self.logger = logging.getLogger("RedisMetricStorage")
        self._step_counter = 0
        self._workflow_counter = 0
        self._slo_counter = 0

        # Create Redis client (lazy connection on first use)
        self.client = redis.Redis.from_url(self.redis_url, decode_responses=True)

    async def close(self):
        """Close Redis connection."""
        if self.client:
            await self.client.aclose()
            self.logger.info("Closed Redis connection")

    def _get_key(self, *parts: str) -> str:
        """Generate namespaced Redis key."""
        return ":".join([self.key_prefix] + list(parts))

    async def record_step(self, record: Dict[str, Any]):
        """
        Record a step-level metric.

        Args:
            record: Step record with agent, success, timestamp, etc.
        """

        agent = record["agent"]
        timestamp = record.get("timestamp", datetime.now(timezone.utc))

        # Generate unique step ID
        self._step_counter += 1
        step_id = f"{agent}:{int(timestamp.timestamp() * 1000)}:{self._step_counter}"

        # Store step data in hash
        step_key = self._get_key("step", step_id)
        step_data = {
            "agent": agent,
            "success": str(record["success"]),
            "required_compensation": str(record.get("required_compensation", False)),
            "required_human": str(record.get("required_human", False)),
            "mode": record.get("mode", ""),
            "declared_mode": record.get("declared_mode", ""),
            "mode_violation": str(record.get("mode_violation", False)),
            "timestamp": timestamp.isoformat()
        }

        # Use pipeline for atomic operations
        async with self.client.pipeline() as pipe:
            # Store hash
            await pipe.hset(step_key, mapping=step_data)

            # Add to global sorted set
            await pipe.zadd(
                self._get_key("steps", agent),
                {step_id: timestamp.timestamp()}
            )

            # Set TTL if configured
            if self.ttl_seconds:
                await pipe.expire(step_key, self.ttl_seconds)

            await pipe.execute()

        self.logger.debug(f"Recorded step for agent {agent}")

    async def record_workflow(self, record: Dict[str, Any]):
        """
        Record a workflow-level metric.

        Args:
            record: Workflow record with workflow_id, steps, retries, etc.
        """

        workflow_id = record["workflow_id"]
        timestamp = record.get("timestamp", datetime.now(timezone.utc))

        # Store workflow data in hash
        workflow_key = self._get_key("workflow", workflow_id)
        workflow_data = {
            "workflow_id": workflow_id,
            "total_steps": str(record["total_steps"]),
            "total_retries": str(record["total_retries"]),
            "required_compensation": str(record.get("required_compensation", False)),
            "required_human": str(record.get("required_human", False)),
            "agents_involved": json.dumps(record.get("agents_involved", [])),
            "timestamp": timestamp.isoformat()
        }

        # Use pipeline for atomic operations
        async with self.client.pipeline() as pipe:
            # Store hash
            await pipe.hset(workflow_key, mapping=workflow_data)

            # Add to global sorted set
            await pipe.zadd(
                self._get_key("workflows"),
                {workflow_id: timestamp.timestamp()}
            )

            # Set TTL if configured
            if self.ttl_seconds:
                await pipe.expire(workflow_key, self.ttl_seconds)

            await pipe.execute()

        self.logger.debug(f"Recorded workflow {workflow_id}")

    async def get_steps(
        self,
        agent: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve step records.

        Args:
            agent: Filter by agent name (None = all agents)
            since: Start time filter
            until: End time filter

        Returns:
            List of step records
        """

        # Determine time range
        min_score = since.timestamp() if since else "-inf"
        max_score = until.timestamp() if until else "+inf"

        steps = []

        if agent:
            # Query specific agent
            step_ids = await self.client.zrangebyscore(
                self._get_key("steps", agent),
                min_score,
                max_score
            )

            for step_id in step_ids:
                step_data = await self.client.hgetall(self._get_key("step", step_id))
                if step_data:
                    steps.append(self._parse_step(step_data))
        else:
            # Query all agents (expensive - use with caution)
            # Get all step keys matching pattern
            pattern = self._get_key("steps", "*")
            agent_keys = []
            async for key in self.client.scan_iter(match=pattern):
                agent_keys.append(key)

            for agent_key in agent_keys:
                step_ids = await self.client.zrangebyscore(
                    agent_key,
                    min_score,
                    max_score
                )

                for step_id in step_ids:
                    step_data = await self.client.hgetall(self._get_key("step", step_id))
                    if step_data:
                        steps.append(self._parse_step(step_data))

        return steps

    async def get_workflows(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve workflow records.

        Args:
            since: Start time filter
            until: End time filter

        Returns:
            List of workflow records
        """

        # Determine time range
        min_score = since.timestamp() if since else "-inf"
        max_score = until.timestamp() if until else "+inf"

        # Query sorted set
        workflow_ids = await self.client.zrangebyscore(
            self._get_key("workflows"),
            min_score,
            max_score
        )

        workflows = []
        for workflow_id in workflow_ids:
            workflow_data = await self.client.hgetall(self._get_key("workflow", workflow_id))
            if workflow_data:
                workflows.append(self._parse_workflow(workflow_data))

        return workflows

    async def record_slo_measurement(
        self,
        measurement_type: str,
        thread_id: str,
        checkpoint_id: str,
        value: float,
        success: bool,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record an SLO measurement (MTTE or RSR).

        Args:
            measurement_type: "mtte" or "rsr"
            thread_id: Thread identifier
            checkpoint_id: Checkpoint identifier
            value: Measurement value (duration_ms for MTTE, 1.0/0.0 for RSR)
            success: Whether measurement was successful
            metadata: Additional metadata
        """

        timestamp = datetime.now(timezone.utc)

        # Generate unique measurement ID
        self._slo_counter += 1
        measurement_id = f"{measurement_type}:{thread_id}:{checkpoint_id}:{self._slo_counter}"

        # Store measurement data in hash
        measurement_key = self._get_key("slo", measurement_id)
        measurement_data = {
            "measurement_type": measurement_type,
            "thread_id": thread_id,
            "checkpoint_id": checkpoint_id,
            "value": str(value),
            "success": str(success),
            "metadata": json.dumps(metadata or {}),
            "timestamp": timestamp.isoformat()
        }

        # Use pipeline for atomic operations
        async with self.client.pipeline() as pipe:
            # Store hash
            await pipe.hset(measurement_key, mapping=measurement_data)

            # Add to type-specific sorted set
            await pipe.zadd(
                self._get_key("slo", measurement_type),
                {measurement_id: timestamp.timestamp()}
            )

            # Set TTL if configured
            if self.ttl_seconds:
                await pipe.expire(measurement_key, self.ttl_seconds)

            await pipe.execute()

        self.logger.debug(f"Recorded {measurement_type} measurement: {value}")

    async def get_slo_measurements(
        self,
        measurement_type: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve SLO measurements.

        Args:
            measurement_type: "mtte" or "rsr"
            since: Start time filter
            until: End time filter

        Returns:
            List of SLO measurement records
        """

        # Determine time range
        min_score = since.timestamp() if since else "-inf"
        max_score = until.timestamp() if until else "+inf"

        # Query sorted set
        measurement_ids = await self.client.zrangebyscore(
            self._get_key("slo", measurement_type),
            min_score,
            max_score
        )

        measurements = []
        for measurement_id in measurement_ids:
            measurement_data = await self.client.hgetall(self._get_key("slo", measurement_id))
            if measurement_data:
                measurements.append(self._parse_slo_measurement(measurement_data))

        return measurements

    def _parse_step(self, data: Dict[str, str]) -> Dict[str, Any]:
        """Parse step data from Redis hash."""
        return {
            "agent": data["agent"],
            "success": data["success"] == "True",
            "required_compensation": data.get("required_compensation", "False") == "True",
            "required_human": data.get("required_human", "False") == "True",
            "mode": data.get("mode", ""),
            "declared_mode": data.get("declared_mode", ""),
            "mode_violation": data.get("mode_violation", "False") == "True",
            "timestamp": datetime.fromisoformat(data["timestamp"])
        }

    def _parse_workflow(self, data: Dict[str, str]) -> Dict[str, Any]:
        """Parse workflow data from Redis hash."""
        return {
            "workflow_id": data["workflow_id"],
            "total_steps": int(data["total_steps"]),
            "total_retries": int(data["total_retries"]),
            "required_compensation": data.get("required_compensation", "False") == "True",
            "required_human": data.get("required_human", "False") == "True",
            "agents_involved": json.loads(data.get("agents_involved", "[]")),
            "timestamp": datetime.fromisoformat(data["timestamp"])
        }

    def _parse_slo_measurement(self, data: Dict[str, str]) -> Dict[str, Any]:
        """Parse SLO measurement data from Redis hash."""
        return {
            "measurement_type": data["measurement_type"],
            "thread_id": data["thread_id"],
            "checkpoint_id": data["checkpoint_id"],
            "value": float(data["value"]),
            "success": data["success"] == "True",
            "metadata": json.loads(data.get("metadata", "{}")),
            "timestamp": datetime.fromisoformat(data["timestamp"])
        }

"""
Human-in-the-Loop (HITL) Manager

Manages paused pipeline executions waiting for human input.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from nexusql import DatabaseManager


@dataclass
class HITLInteraction:
    """Represents a human interaction request"""
    interaction_id: str
    execution_id: str
    pipeline_id: str
    step_id: str
    step_name: str
    status: str
    ui_schema: Dict[str, Any]
    prompt: str
    context_data: Dict[str, Any]
    human_input: Optional[Dict[str, Any]]
    responded_by: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]
    completed_at: Optional[datetime]


class HITLManager:
    """Manages human-in-the-loop interactions"""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def create_interaction(
        self,
        execution_id: str,
        pipeline_id: str,
        step_id: str,
        step_name: str,
        prompt: str,
        context_data: Dict[str, Any],
        ui_schema: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 3600,
        channels: Optional[List[str]] = None,
        assigned_users: Optional[List[str]] = None
    ) -> str:
        """
        Create a new HITL interaction and pause pipeline execution.

        Args:
            execution_id: ID of the pipeline execution
            pipeline_id: ID of the pipeline
            step_id: ID of the step requesting input
            step_name: Name of the step
            prompt: Human-readable prompt for the interaction
            context_data: Data context for the interaction
            ui_schema: Schema for rendering the UI form
            timeout_seconds: How long to wait before expiring (default 1 hour)

        Returns:
            interaction_id: Unique ID for this interaction
        """
        interaction_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=timeout_seconds) if timeout_seconds > 0 else None

        # Default UI schema if not provided
        if ui_schema is None:
            ui_schema = {
                "type": "form",
                "fields": [
                    {
                        "name": "response",
                        "type": "textarea",
                        "label": "Your Response",
                        "required": True
                    }
                ]
            }

        query = """
        INSERT INTO hitl_interactions
        (interaction_id, execution_id, pipeline_id, step_id, step_name,
         status, ui_schema, prompt, context_data, created_at, expires_at)
        VALUES (:interaction_id, :execution_id, :pipeline_id, :step_id, :step_name,
                :status, :ui_schema, :prompt, :context_data, :created_at, :expires_at)
        """

        self.db.execute(query, {
            'interaction_id': interaction_id,
            'execution_id': execution_id,
            'pipeline_id': pipeline_id,
            'step_id': step_id,
            'step_name': step_name,
            'status': 'pending',
            'ui_schema': json.dumps(ui_schema),
            'prompt': prompt,
            'context_data': json.dumps(context_data),
            'created_at': now,
            'expires_at': expires_at
        })

        # Create user assignments if specified
        if assigned_users:
            assignment_query = """
            INSERT INTO hitl_assignments
            (interaction_id, user_id, role, assigned_at)
            VALUES (:interaction_id, :user_id, :role, :assigned_at)
            """
            for user_id in assigned_users:
                self.db.execute(assignment_query, {
                    'interaction_id': interaction_id,
                    'user_id': user_id,
                    'role': 'reviewer',
                    'assigned_at': now
                })

        # Notify assigned users via channels
        if channels and assigned_users:
            # Try to get WebSocket manager for real-time notifications
            ws_manager = None
            try:
                # Import here to avoid circular dependency
                import sys
                if 'ia_modules.showcase_app.backend.api.websocket' in sys.modules:
                    from ia_modules.showcase_app.backend.api.websocket import get_ws_manager
                    ws_manager = get_ws_manager()
            except Exception:
                pass  # WebSocket not available (e.g., in tests or standalone usage)

            await self.notify_channels(interaction_id, channels, prompt, ui_schema, assigned_users, ws_manager)

        return interaction_id

    async def get_interaction(self, interaction_id: str) -> Optional[HITLInteraction]:
        """Get a specific interaction by ID"""
        query = """
        SELECT * FROM hitl_interactions
        WHERE interaction_id = :interaction_id
        """

        result = self.db.fetch_one(query, {'interaction_id': interaction_id})

        if not result:
            return None

        return self._row_to_interaction(result)

    async def get_pending_interactions(
        self,
        execution_id: Optional[str] = None,
        pipeline_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> List[HITLInteraction]:
        """
        Get all pending interactions, optionally filtered by execution, pipeline, or user.

        Args:
            execution_id: Filter by specific execution
            pipeline_id: Filter by specific pipeline
            user_id: Filter by assigned user

        Returns:
            List of pending HITL interactions
        """
        conditions = ["hi.status = 'pending'"]
        params = {}

        if execution_id:
            conditions.append("hi.execution_id = :execution_id")
            params['execution_id'] = execution_id

        if pipeline_id:
            conditions.append("hi.pipeline_id = :pipeline_id")
            params['pipeline_id'] = pipeline_id

        # Build query - join with assignments if filtering by user
        if user_id:
            query = f"""
            SELECT DISTINCT hi.* FROM hitl_interactions hi
            JOIN hitl_assignments ha ON hi.interaction_id = ha.interaction_id
            WHERE {' AND '.join(conditions)} AND ha.user_id = :user_id
            ORDER BY hi.created_at
            """
            params['user_id'] = user_id
        else:
            query = f"""
            SELECT * FROM hitl_interactions hi
            WHERE {' AND '.join(conditions)}
            ORDER BY hi.created_at
            """

        results = self.db.execute(query, params)
        return [self._row_to_interaction(row) for row in results]

    async def respond_to_interaction(
        self,
        interaction_id: str,
        human_input: Dict[str, Any],
        responded_by: Optional[str] = None
    ) -> bool:
        """
        Submit human response to an interaction.

        Args:
            interaction_id: ID of the interaction
            human_input: The human's response data
            responded_by: Optional user ID who responded

        Returns:
            bool: True if response was accepted, False if interaction not found/expired
        """
        # Check if interaction exists and is pending
        interaction = await self.get_interaction(interaction_id)

        if not interaction:
            return False

        if interaction.status != 'pending':
            return False

        # Check if expired (make sure both datetimes are timezone-aware)
        if interaction.expires_at:
            now = datetime.now(timezone.utc)
            expires = interaction.expires_at if interaction.expires_at.tzinfo else interaction.expires_at.replace(tzinfo=timezone.utc)
            if now > expires:
                self._expire_interaction(interaction_id)
                return False

        # Update interaction with response
        query = """
        UPDATE hitl_interactions
        SET status = 'completed',
            human_input = :human_input,
            responded_by = :responded_by,
            completed_at = :completed_at
        WHERE interaction_id = :interaction_id
        """

        self.db.execute(query, {
            'interaction_id': interaction_id,
            'human_input': json.dumps(human_input),
            'responded_by': responded_by,
            'completed_at': datetime.now(timezone.utc)
        })

        return True

    async def cancel_interaction(self, interaction_id: str) -> bool:
        """Cancel a pending interaction"""
        query = """
        UPDATE hitl_interactions
        SET status = 'cancelled',
            completed_at = :completed_at
        WHERE interaction_id = :interaction_id AND status = 'pending'
        """

        # Execute returns empty list for UPDATE, we need to check if interaction exists first
        interaction = await self.get_interaction(interaction_id)
        if not interaction or interaction.status != 'pending':
            return False

        self.db.execute(query, {
            'interaction_id': interaction_id,
            'completed_at': datetime.now(timezone.utc)
        })

        return True

    async def cleanup_expired_interactions(self) -> int:
        """
        Mark expired interactions as expired.

        Returns:
            Number of interactions expired
        """
        query = """
        UPDATE hitl_interactions
        SET status = 'expired'
        WHERE status = 'pending'
          AND expires_at IS NOT NULL
          AND expires_at < :now
        """

        result = self.db.execute(query, {
            'now': datetime.now(timezone.utc)
        })

        return result

    def _expire_interaction(self, interaction_id: str):
        """Mark a specific interaction as expired"""
        query = """
        UPDATE hitl_interactions
        SET status = 'expired'
        WHERE interaction_id = :interaction_id
        """

        self.db.execute(query, {'interaction_id': interaction_id})

    def _row_to_interaction(self, row: Dict[str, Any]) -> HITLInteraction:
        """Convert database row to HITLInteraction object"""
        # Parse datetime strings if needed
        def parse_datetime(dt):
            if dt is None:
                return None
            if isinstance(dt, str):
                from dateutil import parser  # type: ignore[import-untyped]
                return parser.isoparse(dt).replace(tzinfo=timezone.utc)
            return dt

        return HITLInteraction(
            interaction_id=row['interaction_id'],
            execution_id=row['execution_id'],
            pipeline_id=row['pipeline_id'],
            step_id=row['step_id'],
            step_name=row['step_name'],
            status=row['status'],
            ui_schema=json.loads(row['ui_schema']) if row['ui_schema'] else {},
            prompt=row['prompt'],
            context_data=json.loads(row['context_data']) if row['context_data'] else {},
            human_input=json.loads(row['human_input']) if row['human_input'] else None,
            responded_by=row['responded_by'],
            created_at=parse_datetime(row['created_at']),
            expires_at=parse_datetime(row['expires_at']),
            completed_at=parse_datetime(row['completed_at'])
        )

    async def save_execution_state(
        self,
        interaction_id: str,
        execution_state: Dict[str, Any]
    ):
        """
        [DEPRECATED - Not needed anymore]

        Save the pipeline execution state for later resumption.

        NOTE: This method is no longer called because we now pass the full
        execution state as context_data when creating the interaction.
        Kept for backward compatibility.

        Args:
            interaction_id: The HITL interaction ID
            execution_state: Full execution state including:
                - pipeline_name
                - pipeline_config
                - current_step
                - step_index
                - current_data
                - input_data
                - completed_steps
                - execution_context
        """
        query = """
        UPDATE hitl_interactions
        SET context_data = :execution_state
        WHERE interaction_id = :interaction_id
        """

        self.db.execute(query, {
            'interaction_id': interaction_id,
            'execution_state': json.dumps(execution_state)
        })

    async def get_execution_state(self, interaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve the saved execution state for resumption.

        Args:
            interaction_id: The HITL interaction ID

        Returns:
            Execution state dictionary or None if not found
        """
        query = """
        SELECT context_data
        FROM hitl_interactions
        WHERE interaction_id = :interaction_id
        """

        result = self.db.fetch_one(query, {'interaction_id': interaction_id})
        if result and result['context_data']:
            return json.loads(result['context_data'])
        return None

    async def notify_channels(
        self,
        interaction_id: str,
        channels: List[str],
        prompt: str,
        ui_schema: Dict[str, Any],
        assigned_users: List[str],
        ws_manager=None
    ):
        """
        Send notifications to specified channels (email, Discord, Slack, etc).

        Args:
            interaction_id: The HITL interaction ID
            channels: List of channel names (e.g., ['web', 'email', 'discord'])
            prompt: The prompt to display
            ui_schema: The UI schema for the interaction
            assigned_users: List of user IDs/emails to notify
            ws_manager: Optional WebSocket manager for real-time notifications

        Sends notifications via configured channels.
        """
        import logging
        logger = logging.getLogger(__name__)

        # WebSocket notification for 'web' channel
        if 'web' in channels and ws_manager and assigned_users:
            try:
                await ws_manager.broadcast_hitl_notification(
                    user_ids=assigned_users,
                    message={
                        "type": "hitl_notification",
                        "interaction_id": interaction_id,
                        "prompt": prompt,
                        "ui_schema": ui_schema,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                )
                logger.info(f"Sent WebSocket notification to {len(assigned_users)} users")
            except Exception as e:
                logger.error(f"Failed to send WebSocket notification: {e}")

        # Future channel notifiers:
        for channel in channels:
            if channel == 'email':
                logger.info(f"Would send email to {assigned_users}")
                # await EmailNotifier().send(assigned_users, interaction_id, prompt, ui_schema)
            elif channel == 'slack':
                logger.info(f"Would send Slack message to {assigned_users}")
                # await SlackNotifier().send(assigned_users, interaction_id, prompt, ui_schema)
            elif channel == 'discord':
                logger.info(f"Would send Discord message to {assigned_users}")
                # await DiscordNotifier().send(assigned_users, interaction_id, prompt, ui_schema)
            elif channel == 'sms':
                logger.info(f"Would send SMS to {assigned_users}")
                # await SMSNotifier().send(assigned_users, interaction_id, prompt, ui_schema)

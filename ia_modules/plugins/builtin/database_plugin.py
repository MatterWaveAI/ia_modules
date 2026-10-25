"""
Database Plugin

Condition plugins for database-based routing.
"""

from typing import Dict, Any
from ..base import ConditionPlugin, PluginMetadata, PluginType


class DatabaseRecordExists(ConditionPlugin):
    """
    Check if database record exists

    Config:
        - table: Table name
        - id_field: ID field name (default: 'id')
        - id_key: Key in data to use for ID (default: 'id')
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="database_record_exists",
            version="1.0.0",
            author="IA Modules Team",
            description="Check if database record exists",
            plugin_type=PluginType.CONDITION,
            tags=["database", "condition"]
        )

    async def evaluate(self, data: Dict[str, Any]) -> bool:
        """Check if record exists"""
        # Get configuration
        table = self.config.get('table')
        self.config.get('id_field', 'id')
        id_key = self.config.get('id_key', 'id')

        if not table:
            self.logger.error("Missing 'table' in configuration")
            return False

        # Get ID from data
        record_id = data.get(id_key)
        if record_id is None:
            return False

        # Check if record exists in data (simulated)
        # In real implementation, would query actual database
        db_records = data.get('_db_records', {})
        table_records = db_records.get(table, {})

        return record_id in table_records


class DatabaseValueCondition(ConditionPlugin):
    """
    Check database value against condition

    Config:
        - query: SQL query or table name
        - field: Field to check
        - operator: Comparison operator ('eq', 'gt', 'lt', 'gte', 'lte', 'ne')
        - value: Value to compare against
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="database_value_condition",
            version="1.0.0",
            author="IA Modules Team",
            description="Compare database value against condition",
            plugin_type=PluginType.CONDITION,
            tags=["database", "condition", "comparison"]
        )

    async def evaluate(self, data: Dict[str, Any]) -> bool:
        """Evaluate database value condition"""
        field = self.config.get('field')
        operator = self.config.get('operator', 'eq')
        expected_value = self.config.get('value')

        if field is None or expected_value is None:
            return False

        # Get actual value from data
        actual_value = data.get(field)
        if actual_value is None:
            return False

        # Compare based on operator
        if operator == 'eq':
            return actual_value == expected_value
        elif operator == 'ne':
            return actual_value != expected_value
        elif operator == 'gt':
            return actual_value > expected_value
        elif operator == 'gte':
            return actual_value >= expected_value
        elif operator == 'lt':
            return actual_value < expected_value
        elif operator == 'lte':
            return actual_value <= expected_value
        else:
            self.logger.warning(f"Unknown operator: {operator}")
            return False

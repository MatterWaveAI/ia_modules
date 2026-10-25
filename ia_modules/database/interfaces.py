"""
Database interfaces for pluggable backends.

Defines the contract that all database adapters must implement.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any
from enum import Enum
from dataclasses import dataclass


class DatabaseBackend(Enum):
    """Supported database backends"""
    NEXUSQL = "nexusql"
    SQLALCHEMY = "sqlalchemy"


@dataclass
class QueryResult:
    """Standardized query result"""
    success: bool
    data: List[Dict[str, Any]]
    row_count: int
    error_message: Optional[str] = None
    execution_time_ms: Optional[float] = None

    def get_first_row(self) -> Optional[Dict[str, Any]]:
        """Get first row if available"""
        return self.data[0] if self.data else None

    def get_column_values(self, column_name: str) -> List[Any]:
        """Get all values for a specific column"""
        return [row.get(column_name) for row in self.data if column_name in row]


class DatabaseInterface(ABC):
    """
    Abstract database interface for pluggable backends.

    All database adapters must implement this interface.
    """

    @abstractmethod
    def connect(self) -> bool:
        """Connect to the database"""
        pass

    @abstractmethod
    def disconnect(self):
        """Disconnect from the database"""
        pass

    @abstractmethod
    async def close(self):
        """Async-compatible close method"""
        pass

    @abstractmethod
    def execute(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """
        Execute a query with named parameters.

        Args:
            query: SQL query with :param_name placeholders
            params: Dict like {"param_name": "value"}

        Returns:
            List[Dict]: Query results (empty list for non-SELECT queries)
        """
        pass

    @abstractmethod
    async def execute_async(self, query: str, params: Optional[Dict] = None) -> Any:
        """Async-compatible execute method"""
        pass

    @abstractmethod
    def fetch_one(self, query: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Fetch one row with named parameters.

        Args:
            query: SQL with :param_name placeholders
            params: Dict like {"param_name": "value"}

        Returns:
            Optional[Dict]: Single row or None
        """
        pass

    @abstractmethod
    def fetch_all(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """
        Fetch all rows with named parameters.

        Args:
            query: SQL with :param_name placeholders
            params: Dict like {"param_name": "value"}

        Returns:
            List[Dict]: All matching rows
        """
        pass

    @abstractmethod
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists"""
        pass

    @abstractmethod
    async def execute_script(self, script: str) -> QueryResult:
        """Execute a SQL script (multiple statements)"""
        pass

    @abstractmethod
    async def initialize(
        self,
        apply_schema: bool = True,
        app_migration_paths: Optional[List[str]] = None
    ) -> bool:
        """
        Initialize the database connection and optionally apply schema migrations

        Args:
            apply_schema: Whether to apply migrations
            app_migration_paths: List of paths to app-specific migration directories

        Returns:
            bool: True if successful
        """
        pass

    # Context manager support
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


def create_query_result(
    success: bool = True,
    data: Optional[List[Dict[str, Any]]] = None,
    **kwargs
) -> QueryResult:
    """Create a query result with common defaults"""
    return QueryResult(
        success=success,
        data=data or [],
        row_count=len(data) if data else 0,
        **kwargs
    )


def create_error_result(error_message: str) -> QueryResult:
    """Create an error query result"""
    return QueryResult(
        success=False,
        data=[],
        row_count=0,
        error_message=error_message
    )

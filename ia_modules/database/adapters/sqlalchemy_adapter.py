"""
SQLAlchemy adapter - wraps SQLAlchemy to implement DatabaseInterface
"""

from typing import Optional, Dict, List, Any
from pathlib import Path
import logging

try:
    from sqlalchemy import create_engine, text, inspect
    from sqlalchemy.orm import sessionmaker, Session
    from sqlalchemy.pool import NullPool  # noqa: F401
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    create_engine = None
    text = None
    inspect = None
    sessionmaker = None
    Session = None

from ..interfaces import DatabaseInterface, QueryResult, create_query_result, create_error_result

logger = logging.getLogger(__name__)


class SQLAlchemyAdapter(DatabaseInterface):
    """
    Adapter that wraps SQLAlchemy to implement DatabaseInterface.

    Features:
    - Full SQLAlchemy ORM support
    - Advanced query capabilities
    - Connection pooling
    - Support for complex transactions
    - Access to SQLAlchemy's extensive ecosystem

    Note: This adapter provides a simplified interface. For advanced SQLAlchemy
    features (ORM models, relationships, etc.), access the underlying engine
    and session via the `engine` and `session` properties.
    """

    def __init__(self, database_url: str, **engine_kwargs):
        """
        Initialize SQLAlchemy adapter.

        Args:
            database_url: SQLAlchemy connection URL
            **engine_kwargs: Additional arguments passed to create_engine()
        """
        if not SQLALCHEMY_AVAILABLE:
            raise ImportError(
                "sqlalchemy is not installed. Install with: pip install sqlalchemy"
            )

        self.database_url = database_url
        self.engine_kwargs = engine_kwargs
        self._engine = None
        self._session_maker = None
        self._session: Optional[Session] = None

    def connect(self) -> bool:
        """Connect to the database"""
        try:
            # Create engine with sensible defaults
            engine_kwargs = {
                'echo': False,  # Set to True for SQL logging
                'pool_pre_ping': True,  # Verify connections before using
                **self.engine_kwargs
            }

            self._engine = create_engine(self.database_url, **engine_kwargs)  # type: ignore[assignment]

            # Create session maker
            self._session_maker = sessionmaker(bind=self._engine)  # type: ignore[assignment]

            # Create session
            self._session = self._session_maker()  # type: ignore[misc]

            # Test connection
            with self._engine.connect() as conn:  # type: ignore[union-attr]
                conn.execute(text("SELECT 1"))

            logger.info(f"Connected to database via SQLAlchemy: {self.database_url}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return False

    def disconnect(self):
        """Disconnect from the database"""
        if self._session:
            self._session.close()
            self._session = None

        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_maker = None

        logger.info("Disconnected from database")

    async def close(self):
        """Async-compatible close method"""
        self.disconnect()

    def execute(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """
        Execute a query with named parameters.

        Args:
            query: SQL query with :param_name placeholders
            params: Dict like {"param_name": "value"}

        Returns:
            List[Dict]: Query results (empty list for non-SELECT queries)
        """
        if not self._session:
            raise RuntimeError("Database not connected")

        try:
            # Execute with SQLAlchemy
            stmt = text(query)
            result = self._session.execute(stmt, params or {})

            # Check if this is a SELECT query
            query_upper = query.strip().upper()
            if query_upper.startswith('SELECT') or query_upper.startswith('SHOW') or query_upper.startswith('DESCRIBE'):
                # Fetch results for SELECT queries
                rows = result.fetchall()
                if not rows:
                    return []

                # Convert to list of dicts
                columns = result.keys()
                return [dict(zip(columns, row)) for row in rows]
            else:
                # For INSERT/UPDATE/DELETE, commit and return empty list
                self._session.commit()
                return []

        except Exception as e:
            # Rollback on error
            self._session.rollback()
            logger.error(f"Query execution failed: {e}")
            raise

    async def execute_async(self, query: str, params: Optional[Dict] = None) -> Any:
        """Async-compatible execute method"""
        return self.execute(query, params)

    def fetch_one(self, query: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Fetch one row with named parameters.

        Args:
            query: SQL with :param_name placeholders
            params: Dict like {"param_name": "value"}

        Returns:
            Optional[Dict]: Single row or None
        """
        if not self._session:
            raise RuntimeError("Database not connected")

        try:
            stmt = text(query)
            result = self._session.execute(stmt, params or {})
            row = result.fetchone()

            if not row:
                return None

            columns = result.keys()
            return dict(zip(columns, row))

        except Exception as e:
            logger.error(f"fetch_one failed: {e}")
            return None

    def fetch_all(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """
        Fetch all rows with named parameters.

        Args:
            query: SQL with :param_name placeholders
            params: Dict like {"param_name": "value"}

        Returns:
            List[Dict]: All matching rows
        """
        if not self._session:
            raise RuntimeError("Database not connected")

        try:
            stmt = text(query)
            result = self._session.execute(stmt, params or {})
            rows = result.fetchall()

            if not rows:
                return []

            columns = result.keys()
            return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error(f"fetch_all failed: {e}")
            return []

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists"""
        if not self._engine:
            raise RuntimeError("Database not connected")

        try:
            inspector = inspect(self._engine)
            return table_name in inspector.get_table_names()
        except Exception as e:
            logger.error(f"table_exists failed: {e}")
            return False

    async def execute_script(self, script: str) -> QueryResult:
        """Execute a SQL script (multiple statements)"""
        if not self._session:
            raise RuntimeError("Database not connected")

        try:
            # Split script into statements
            statements = [stmt.strip() for stmt in script.split(';') if stmt.strip()]

            for statement in statements:
                stmt = text(statement)
                self._session.execute(stmt)

            self._session.commit()
            return create_query_result(success=True)

        except Exception as e:
            self._session.rollback()
            logger.error(f"Script execution failed: {e}")
            return create_error_result(str(e))

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

        Note: Migration support for SQLAlchemy is limited. Consider using Alembic
        for production migration management.
        """
        if not self.connect():
            return False

        if not apply_schema:
            return True

        logger.warning(
            "SQLAlchemy adapter has limited migration support. "
            "Consider using Alembic for production migrations."
        )

        # Basic migration support - just run SQL files
        if app_migration_paths:
            for migration_path in app_migration_paths:
                path = Path(migration_path)
                if not path.exists():
                    logger.warning(f"Migration path does not exist: {path}")
                    continue

                # Find and execute SQL files
                sql_files = sorted(path.glob("*.sql"))
                for sql_file in sql_files:
                    logger.info(f"Running migration: {sql_file.name}")
                    with open(sql_file, 'r') as f:
                        script = f.read()

                    result = await self.execute_script(script)
                    if not result.success:
                        logger.error(f"Migration failed: {sql_file.name}")
                        return False

        return True

    # Expose underlying SQLAlchemy components for advanced usage
    @property
    def engine(self):
        """Access underlying SQLAlchemy engine"""
        return self._engine

    @property
    def session(self) -> Optional[Session]:
        """Access underlying SQLAlchemy session"""
        return self._session

    def get_new_session(self) -> Session:
        """Create a new SQLAlchemy session"""
        if not self._session_maker:
            raise RuntimeError("Database not connected")
        return self._session_maker()

    def begin_transaction(self):
        """Begin a new transaction"""
        if self._session:
            return self._session.begin()
        raise RuntimeError("Database not connected")

    def commit(self):
        """Commit current transaction"""
        if self._session:
            self._session.commit()

    def rollback(self):
        """Rollback current transaction"""
        if self._session:
            self._session.rollback()

"""
Factory for creating database instances with pluggable backends.
"""

import os
from typing import Optional
import logging

from .interfaces import DatabaseInterface, DatabaseBackend
from .adapters.nexusql_adapter import NexuSQLAdapter
from .adapters.sqlalchemy_adapter import SQLAlchemyAdapter

logger = logging.getLogger(__name__)

# Global default backend
_DEFAULT_BACKEND = DatabaseBackend.NEXUSQL


def set_default_backend(backend: DatabaseBackend):
    """
    Set the default database backend for all future get_database() calls.

    Args:
        backend: DatabaseBackend.NEXUSQL or DatabaseBackend.SQLALCHEMY

    Example:
        from ia_modules.database import set_default_backend, DatabaseBackend
        set_default_backend(DatabaseBackend.SQLALCHEMY)
    """
    global _DEFAULT_BACKEND
    _DEFAULT_BACKEND = backend
    logger.info(f"Default database backend set to: {backend.value}")


def get_database(
    database_url: str,
    backend: Optional[str] = None,
    **kwargs
) -> DatabaseInterface:
    """
    Get a database instance with the specified backend.

    Args:
        database_url: Database connection URL
        backend: Backend to use ("nexusql" or "sqlalchemy"). If None, uses:
                 1. IA_DATABASE_BACKEND environment variable
                 2. Global default (set via set_default_backend())
                 3. Falls back to "nexusql"
        **kwargs: Additional backend-specific arguments

    Returns:
        DatabaseInterface: Database instance

    Raises:
        ValueError: If backend is invalid
        ImportError: If required backend package is not installed

    Examples:
        # Using nexusql (default)
        db = get_database("sqlite:///app.db")

        # Using SQLAlchemy
        db = get_database("sqlite:///app.db", backend="sqlalchemy")

        # Using environment variable
        os.environ["IA_DATABASE_BACKEND"] = "sqlalchemy"
        db = get_database("sqlite:///app.db")

        # With SQLAlchemy-specific options
        db = get_database(
            "postgresql://user:pass@localhost/db",
            backend="sqlalchemy",
            pool_size=10,
            max_overflow=20
        )
    """
    # Determine which backend to use
    if backend is None:
        # Check environment variable
        env_backend = os.getenv("IA_DATABASE_BACKEND")
        if env_backend:
            backend = env_backend
        else:
            # Use global default
            backend = _DEFAULT_BACKEND.value

    # Normalize backend name
    backend = backend.lower().strip()

    # Create appropriate adapter
    if backend == "nexusql":
        logger.debug(f"Creating NexusQL database instance for: {database_url}")
        return NexuSQLAdapter(database_url)

    elif backend == "sqlalchemy":
        logger.debug(f"Creating SQLAlchemy database instance for: {database_url}")
        return SQLAlchemyAdapter(database_url, **kwargs)

    else:
        raise ValueError(
            f"Invalid database backend: {backend}. "
            f"Must be 'nexusql' or 'sqlalchemy'"
        )


def get_nexusql_database(database_url: str) -> NexuSQLAdapter:
    """
    Convenience function to explicitly get a NexusQL database.

    Args:
        database_url: Database connection URL

    Returns:
        NexuSQLAdapter: NexusQL database instance
    """
    return NexuSQLAdapter(database_url)


def get_sqlalchemy_database(database_url: str, **kwargs) -> SQLAlchemyAdapter:
    """
    Convenience function to explicitly get a SQLAlchemy database.

    Args:
        database_url: SQLAlchemy connection URL
        **kwargs: Additional arguments passed to create_engine()

    Returns:
        SQLAlchemyAdapter: SQLAlchemy database instance
    """
    return SQLAlchemyAdapter(database_url, **kwargs)

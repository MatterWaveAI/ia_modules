"""
Unit tests for database layer: NexuSQLAdapter, DatabaseFactory, and DatabaseInterface.

Tests cover initialization, CRUD operations, connection management, error handling,
factory creation logic, and abstract interface compliance.
"""

import asyncio
from abc import ABC
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from ia_modules.database.interfaces import (
    DatabaseInterface,
    DatabaseBackend,
    QueryResult,
    create_query_result,
    create_error_result,
)
from ia_modules.database.factory import (
    get_database,
    get_nexusql_database,
    get_sqlalchemy_database,
    set_default_backend,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class ConcreteDatabaseAdapter(DatabaseInterface):
    """Minimal concrete implementation used to verify the abstract interface."""

    def connect(self) -> bool:
        return True

    def disconnect(self):
        pass

    async def close(self):
        pass

    def execute(self, query, params=None):
        return []

    async def execute_async(self, query, params=None):
        return []

    def fetch_one(self, query, params=None):
        return None

    def fetch_all(self, query, params=None):
        return []

    def table_exists(self, table_name):
        return False

    async def execute_script(self, script):
        return create_query_result()

    async def initialize(self, apply_schema=True, app_migration_paths=None):
        return True


# ===========================================================================
# DatabaseInterface / QueryResult tests
# ===========================================================================

class TestDatabaseInterface:
    """Tests for the abstract DatabaseInterface contract."""

    def test_is_abstract(self):
        """DatabaseInterface cannot be instantiated directly."""
        assert issubclass(DatabaseInterface, ABC)
        with pytest.raises(TypeError):
            DatabaseInterface()

    def test_concrete_subclass_satisfies_interface(self):
        """A concrete subclass with all methods implemented can be instantiated."""
        adapter = ConcreteDatabaseAdapter()
        assert isinstance(adapter, DatabaseInterface)

    def test_context_manager_calls_connect_disconnect(self):
        """__enter__ calls connect and __exit__ calls disconnect."""
        adapter = ConcreteDatabaseAdapter()
        adapter.connect = MagicMock(return_value=True)
        adapter.disconnect = MagicMock()

        with adapter as ctx:
            assert ctx is adapter
            adapter.connect.assert_called_once()

        adapter.disconnect.assert_called_once()

    def test_context_manager_disconnect_on_exception(self):
        """disconnect is called even when an exception occurs inside the block."""
        adapter = ConcreteDatabaseAdapter()
        adapter.connect = MagicMock(return_value=True)
        adapter.disconnect = MagicMock()

        with pytest.raises(RuntimeError):
            with adapter:
                raise RuntimeError("boom")

        adapter.disconnect.assert_called_once()


class TestQueryResult:
    """Tests for QueryResult dataclass."""

    def test_basic_creation(self):
        qr = QueryResult(success=True, data=[{"id": 1}], row_count=1)
        assert qr.success is True
        assert qr.row_count == 1
        assert qr.error_message is None
        assert qr.execution_time_ms is None

    def test_get_first_row(self):
        qr = QueryResult(success=True, data=[{"a": 1}, {"a": 2}], row_count=2)
        assert qr.get_first_row() == {"a": 1}

    def test_get_first_row_empty(self):
        qr = QueryResult(success=True, data=[], row_count=0)
        assert qr.get_first_row() is None

    def test_get_column_values(self):
        qr = QueryResult(
            success=True,
            data=[{"name": "alice"}, {"name": "bob"}, {"age": 30}],
            row_count=3,
        )
        assert qr.get_column_values("name") == ["alice", "bob"]

    def test_get_column_values_missing_column(self):
        qr = QueryResult(success=True, data=[{"a": 1}], row_count=1)
        assert qr.get_column_values("z") == []

    def test_create_query_result_defaults(self):
        qr = create_query_result()
        assert qr.success is True
        assert qr.data == []
        assert qr.row_count == 0

    def test_create_query_result_with_data(self):
        data = [{"x": 1}]
        qr = create_query_result(data=data)
        assert qr.row_count == 1

    def test_create_error_result(self):
        qr = create_error_result("connection lost")
        assert qr.success is False
        assert qr.error_message == "connection lost"
        assert qr.data == []
        assert qr.row_count == 0


class TestDatabaseBackendEnum:
    """Tests for DatabaseBackend enum."""

    def test_values(self):
        assert DatabaseBackend.NEXUSQL.value == "nexusql"
        assert DatabaseBackend.SQLALCHEMY.value == "sqlalchemy"

    def test_members(self):
        assert set(DatabaseBackend.__members__.keys()) == {"NEXUSQL", "SQLALCHEMY"}


# ===========================================================================
# NexuSQLAdapter tests (mocked)
# ===========================================================================

class TestNexuSQLAdapter:
    """Tests for NexuSQLAdapter with mocked nexusql dependency."""

    @pytest.fixture(autouse=True)
    def _patch_nexusql(self):
        """Patch the nexusql import so tests don't need the real package."""
        self.mock_manager_instance = MagicMock()
        self.mock_manager_cls = MagicMock(return_value=self.mock_manager_instance)

        with patch.dict(
            "ia_modules.database.adapters.nexusql_adapter.__dict__",
            {"NEXUSQL_AVAILABLE": True, "NexuSQLManager": self.mock_manager_cls},
        ):
            # Re-import to pick up the patched values
            from ia_modules.database.adapters.nexusql_adapter import NexuSQLAdapter
            self.AdapterClass = NexuSQLAdapter
            yield

    # -- Initialization ------------------------------------------------------

    def test_init_stores_url(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        assert adapter.database_url == "sqlite:///test.db"
        self.mock_manager_cls.assert_called_once_with("sqlite:///test.db")

    def test_init_creates_underlying_manager(self):
        adapter = self.AdapterClass("postgres://localhost/db")
        assert adapter._db is self.mock_manager_instance

    def test_init_raises_when_nexusql_not_available(self):
        with patch.dict(
            "ia_modules.database.adapters.nexusql_adapter.__dict__",
            {"NEXUSQL_AVAILABLE": False, "NexuSQLManager": None},
        ):
            from ia_modules.database.adapters.nexusql_adapter import NexuSQLAdapter
            with pytest.raises(ImportError, match="nexusql is not installed"):
                NexuSQLAdapter("sqlite:///test.db")

    # -- Connection management -----------------------------------------------

    def test_connect_delegates(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        self.mock_manager_instance.connect.return_value = True
        assert adapter.connect() is True
        self.mock_manager_instance.connect.assert_called_once()

    def test_disconnect_delegates(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        adapter.disconnect()
        self.mock_manager_instance.disconnect.assert_called_once()

    def test_close_delegates_async(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        self.mock_manager_instance.close = AsyncMock()
        asyncio.run(adapter.close())
        self.mock_manager_instance.close.assert_awaited_once()

    # -- CRUD operations -----------------------------------------------------

    def test_execute_with_params(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        self.mock_manager_instance.execute.return_value = [{"id": 1}]
        result = adapter.execute("SELECT * FROM t WHERE id = :id", {"id": 1})
        assert result == [{"id": 1}]
        self.mock_manager_instance.execute.assert_called_once_with(
            "SELECT * FROM t WHERE id = :id", {"id": 1}
        )

    def test_execute_without_params(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        self.mock_manager_instance.execute.return_value = []
        result = adapter.execute("INSERT INTO t (a) VALUES (1)")
        assert result == []
        self.mock_manager_instance.execute.assert_called_once_with(
            "INSERT INTO t (a) VALUES (1)", None
        )

    def test_execute_async_delegates(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        self.mock_manager_instance.execute_async = AsyncMock(return_value=[{"id": 2}])
        result = asyncio.run(adapter.execute_async("SELECT 1", {"p": "v"}))
        assert result == [{"id": 2}]
        self.mock_manager_instance.execute_async.assert_awaited_once_with(
            "SELECT 1", {"p": "v"}
        )

    def test_fetch_one_returns_dict(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        self.mock_manager_instance.fetch_one.return_value = {"name": "alice"}
        result = adapter.fetch_one("SELECT * FROM users WHERE id = :id", {"id": 1})
        assert result == {"name": "alice"}

    def test_fetch_one_returns_none(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        self.mock_manager_instance.fetch_one.return_value = None
        assert adapter.fetch_one("SELECT * FROM users WHERE id = :id", {"id": 999}) is None

    def test_fetch_all_returns_list(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        rows = [{"id": 1}, {"id": 2}]
        self.mock_manager_instance.execute.return_value = rows
        result = adapter.fetch_all("SELECT * FROM users")
        assert result == rows

    def test_fetch_all_empty(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        self.mock_manager_instance.execute.return_value = []
        assert adapter.fetch_all("SELECT * FROM users WHERE 1=0") == []

    def test_table_exists_true(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        self.mock_manager_instance.table_exists.return_value = True
        assert adapter.table_exists("users") is True

    def test_table_exists_false(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        self.mock_manager_instance.table_exists.return_value = False
        assert adapter.table_exists("nonexistent") is False

    def test_execute_script_delegates(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        mock_result = MagicMock()
        self.mock_manager_instance.execute_script = AsyncMock(return_value=mock_result)
        result = asyncio.run(adapter.execute_script("CREATE TABLE t (id INT);"))
        assert result is mock_result

    def test_initialize_delegates(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        self.mock_manager_instance.initialize = AsyncMock(return_value=True)
        result = asyncio.run(adapter.initialize(apply_schema=True, app_migration_paths=["/m"]))
        assert result is True
        from ia_modules.database import MIGRATIONS_DIR
        # ia_modules' own schema runs first, then the app's
        self.mock_manager_instance.initialize.assert_awaited_once_with(True, [str(MIGRATIONS_DIR), "/m"])

    def test_initialize_no_schema(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        self.mock_manager_instance.initialize = AsyncMock(return_value=True)
        asyncio.run(adapter.initialize(apply_schema=False))
        from ia_modules.database import MIGRATIONS_DIR
        self.mock_manager_instance.initialize.assert_awaited_once_with(False, [str(MIGRATIONS_DIR)])

    # -- Properties ----------------------------------------------------------

    def test_nexusql_property_returns_underlying_manager(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        assert adapter.nexusql is self.mock_manager_instance

    def test_config_property(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        self.mock_manager_instance.config = {"db_type": "sqlite"}
        assert adapter.config == {"db_type": "sqlite"}

    def test_database_type_property(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        self.mock_manager_instance.config.database_type = "sqlite"
        assert adapter.database_type == "sqlite"

    # -- Error handling ------------------------------------------------------

    def test_execute_propagates_exception(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        self.mock_manager_instance.execute.side_effect = RuntimeError("db error")
        with pytest.raises(RuntimeError, match="db error"):
            adapter.execute("BAD SQL")

    def test_fetch_one_propagates_exception(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        self.mock_manager_instance.fetch_one.side_effect = RuntimeError("db error")
        with pytest.raises(RuntimeError, match="db error"):
            adapter.fetch_one("BAD SQL")

    def test_fetch_all_propagates_exception(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        self.mock_manager_instance.execute.side_effect = RuntimeError("db error")
        with pytest.raises(RuntimeError, match="db error"):
            adapter.fetch_all("BAD SQL")

    def test_connect_propagates_exception(self):
        adapter = self.AdapterClass("sqlite:///test.db")
        self.mock_manager_instance.connect.side_effect = ConnectionError("refused")
        with pytest.raises(ConnectionError, match="refused"):
            adapter.connect()


# ===========================================================================
# DatabaseFactory tests
# ===========================================================================

class TestDatabaseFactory:
    """Tests for get_database factory and related helpers."""

    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch):
        """Ensure IA_DATABASE_BACKEND env var is cleared between tests."""
        monkeypatch.delenv("IA_DATABASE_BACKEND", raising=False)

    # -- Backend selection ---------------------------------------------------

    @patch("ia_modules.database.factory.NexuSQLAdapter")
    def test_default_backend_is_nexusql(self, mock_adapter):
        mock_adapter.return_value = MagicMock()
        _db = get_database("sqlite:///test.db")
        mock_adapter.assert_called_once_with("sqlite:///test.db")

    @patch("ia_modules.database.factory.SQLAlchemyAdapter")
    def test_explicit_sqlalchemy_backend(self, mock_adapter):
        mock_adapter.return_value = MagicMock()
        _db = get_database("sqlite:///test.db", backend="sqlalchemy")
        mock_adapter.assert_called_once_with("sqlite:///test.db")

    @patch("ia_modules.database.factory.NexuSQLAdapter")
    def test_explicit_nexusql_backend(self, mock_adapter):
        mock_adapter.return_value = MagicMock()
        _db = get_database("sqlite:///test.db", backend="nexusql")
        mock_adapter.assert_called_once_with("sqlite:///test.db")

    @patch("ia_modules.database.factory.SQLAlchemyAdapter")
    def test_env_var_backend(self, mock_adapter, monkeypatch):
        monkeypatch.setenv("IA_DATABASE_BACKEND", "sqlalchemy")
        mock_adapter.return_value = MagicMock()
        _db = get_database("sqlite:///test.db")
        mock_adapter.assert_called_once()

    @patch("ia_modules.database.factory.NexuSQLAdapter")
    def test_env_var_nexusql(self, mock_adapter, monkeypatch):
        monkeypatch.setenv("IA_DATABASE_BACKEND", "nexusql")
        mock_adapter.return_value = MagicMock()
        _db = get_database("sqlite:///test.db")
        mock_adapter.assert_called_once()

    def test_invalid_backend_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid database backend"):
            get_database("sqlite:///test.db", backend="mongodb")

    @patch("ia_modules.database.factory.SQLAlchemyAdapter")
    def test_backend_name_case_insensitive(self, mock_adapter):
        mock_adapter.return_value = MagicMock()
        get_database("sqlite:///test.db", backend="  SQLAlchemy  ")
        mock_adapter.assert_called_once()

    # -- Fallback behavior / set_default_backend -----------------------------

    @patch("ia_modules.database.factory.SQLAlchemyAdapter")
    def test_set_default_backend(self, mock_adapter):
        """set_default_backend changes the factory default."""
        mock_adapter.return_value = MagicMock()
        import ia_modules.database.factory as factory_mod

        original = factory_mod._DEFAULT_BACKEND
        try:
            set_default_backend(DatabaseBackend.SQLALCHEMY)
            _db = get_database("sqlite:///test.db")
            mock_adapter.assert_called_once()
        finally:
            # Restore so other tests aren't affected
            factory_mod._DEFAULT_BACKEND = original

    @patch("ia_modules.database.factory.NexuSQLAdapter")
    def test_set_default_backend_nexusql(self, mock_adapter):
        mock_adapter.return_value = MagicMock()
        import ia_modules.database.factory as factory_mod

        original = factory_mod._DEFAULT_BACKEND
        try:
            set_default_backend(DatabaseBackend.NEXUSQL)
            _db = get_database("sqlite:///test.db")
            mock_adapter.assert_called_once()
        finally:
            factory_mod._DEFAULT_BACKEND = original

    # -- kwargs passthrough --------------------------------------------------

    @patch("ia_modules.database.factory.SQLAlchemyAdapter")
    def test_kwargs_passed_to_sqlalchemy(self, mock_adapter):
        mock_adapter.return_value = MagicMock()
        get_database(
            "postgresql://localhost/db",
            backend="sqlalchemy",
            pool_size=10,
            max_overflow=20,
        )
        mock_adapter.assert_called_once_with(
            "postgresql://localhost/db", pool_size=10, max_overflow=20
        )

    # -- Convenience functions -----------------------------------------------

    @patch("ia_modules.database.factory.NexuSQLAdapter")
    def test_get_nexusql_database(self, mock_adapter):
        mock_adapter.return_value = MagicMock()
        _result = get_nexusql_database("sqlite:///test.db")
        mock_adapter.assert_called_once_with("sqlite:///test.db")

    @patch("ia_modules.database.factory.SQLAlchemyAdapter")
    def test_get_sqlalchemy_database(self, mock_adapter):
        mock_adapter.return_value = MagicMock()
        _result = get_sqlalchemy_database("sqlite:///test.db", echo=True)
        mock_adapter.assert_called_once_with("sqlite:///test.db", echo=True)

    # -- Return type ---------------------------------------------------------

    @patch("ia_modules.database.factory.NexuSQLAdapter")
    def test_returns_database_interface(self, mock_adapter):
        mock_instance = MagicMock(spec=DatabaseInterface)
        mock_adapter.return_value = mock_instance
        db = get_database("sqlite:///test.db")
        assert db is mock_instance


# ===========================================================================
# Abstract interface compliance
# ===========================================================================

class TestInterfaceCompliance:
    """Verify that concrete adapters declare all required abstract methods."""

    def test_nexusql_adapter_implements_interface(self):
        """NexuSQLAdapter is a subclass of DatabaseInterface."""
        from ia_modules.database.adapters.nexusql_adapter import NexuSQLAdapter
        assert issubclass(NexuSQLAdapter, DatabaseInterface)

    def test_sqlalchemy_adapter_implements_interface(self):
        """SQLAlchemyAdapter is a subclass of DatabaseInterface."""
        from ia_modules.database.adapters.sqlalchemy_adapter import SQLAlchemyAdapter
        assert issubclass(SQLAlchemyAdapter, DatabaseInterface)

    def test_incomplete_subclass_raises(self):
        """A subclass missing abstract methods cannot be instantiated."""

        class IncompleteAdapter(DatabaseInterface):
            pass

        with pytest.raises(TypeError):
            IncompleteAdapter()

    def test_partial_implementation_raises(self):
        """A subclass implementing only some methods cannot be instantiated."""

        class PartialAdapter(DatabaseInterface):
            def connect(self):
                return True

            def disconnect(self):
                pass

        with pytest.raises(TypeError):
            PartialAdapter()

    def test_required_abstract_methods(self):
        """DatabaseInterface declares the expected abstract methods."""
        expected_methods = {
            "connect",
            "disconnect",
            "close",
            "execute",
            "execute_async",
            "fetch_one",
            "fetch_all",
            "table_exists",
            "execute_script",
            "initialize",
        }
        abstract_methods = DatabaseInterface.__abstractmethods__
        assert expected_methods == abstract_methods


class TestSQLAlchemyPostgresDriver:
    """The postgres extra installs psycopg 3, so the SQLAlchemy backend must ask for it."""

    @pytest.mark.parametrize("url, expected", [
        ("postgresql://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
        ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+asyncpg://u@h/db", "postgresql+asyncpg://u@h/db"),
        ("postgresql+psycopg2://u@h/db", "postgresql+psycopg2://u@h/db"),
        ("sqlite:///x.db", "sqlite:///x.db"),
        ("mysql+pymysql://u@h/db", "mysql+pymysql://u@h/db"),
    ])
    def test_bare_postgres_urls_get_the_psycopg3_driver(self, url, expected):
        from ia_modules.database.adapters.sqlalchemy_adapter import _with_psycopg3_driver
        assert _with_psycopg3_driver(url) == expected


"""
Comprehensive unit tests for pipeline importer

Tests all methods and edge cases in PipelineImportService
"""

import pytest
from unittest.mock import Mock, AsyncMock
from pathlib import Path
import json

from ia_modules.pipeline.importer import PipelineImportService


class TestPipelineImportServiceInit:
    """Test service initialization"""

    def test_init_with_default_directory(self):
        """Test initialization with default pipelines directory"""
        mock_db = Mock()
        service = PipelineImportService(mock_db)

        assert service.db_provider == mock_db
        assert service.pipelines_dir == Path.cwd() / "pipelines"

    def test_init_with_custom_directory(self):
        """Test initialization with custom pipelines directory"""
        mock_db = Mock()
        custom_dir = "/custom/path/to/pipelines"
        service = PipelineImportService(mock_db, custom_dir)

        assert service.db_provider == mock_db
        assert service.pipelines_dir == Path(custom_dir)


class TestSlugGeneration:
    """Test slug generation"""

    def test_generate_slug_basic(self):
        """Test basic slug generation"""
        service = PipelineImportService(Mock())

        slug = service._generate_slug("Test Pipeline", "path/to/pipeline.json")

        assert isinstance(slug, str)
        assert "test-pipeline" in slug
        assert len(slug) > len("test-pipeline")  # Includes hash

    def test_generate_slug_removes_spaces(self):
        """Test slug generation removes spaces"""
        service = PipelineImportService(Mock())

        slug = service._generate_slug("My Test Pipeline", "test.json")

        assert " " not in slug
        assert "-" in slug

    def test_generate_slug_removes_underscores(self):
        """Test slug generation replaces underscores with hyphens"""
        service = PipelineImportService(Mock())

        slug = service._generate_slug("test_pipeline_name", "test.json")

        assert "_" not in slug
        assert "test-pipeline-name" in slug

    def test_generate_slug_removes_special_chars(self):
        """Test slug generation removes special characters"""
        service = PipelineImportService(Mock())

        slug = service._generate_slug("Test@Pipeline#123!", "test.json")

        # Should only contain alphanumeric and hyphens
        assert all(c.isalnum() or c == '-' for c in slug)

    def test_generate_slug_no_double_hyphens(self):
        """Test slug generation removes double hyphens"""
        service = PipelineImportService(Mock())

        slug = service._generate_slug("Test  --  Pipeline", "test.json")

        assert "--" not in slug

    def test_generate_slug_trims_hyphens(self):
        """Test slug generation trims leading/trailing hyphens"""
        service = PipelineImportService(Mock())

        slug = service._generate_slug("---Test Pipeline---", "test.json")

        assert not slug.startswith("-")
        assert not slug.endswith("-")

    def test_generate_slug_different_paths_different_slugs(self):
        """Test same name with different paths generates different slugs"""
        service = PipelineImportService(Mock())

        slug1 = service._generate_slug("Pipeline", "path1/pipeline.json")
        slug2 = service._generate_slug("Pipeline", "path2/pipeline.json")

        assert slug1 != slug2  # Different path hashes

    def test_generate_slug_case_insensitive(self):
        """Test slug generation is case insensitive"""
        service = PipelineImportService(Mock())

        slug = service._generate_slug("Test PIPELINE Name", "test.json")

        assert slug.islower() or all(c.isdigit() or c == '-' for c in slug.split('-')[-1])


class TestContentHash:
    """Test content hash calculation"""

    def test_calculate_content_hash_basic(self):
        """Test basic content hash calculation"""
        service = PipelineImportService(Mock())

        pipeline_data = {"name": "Test", "steps": []}
        hash_value = service._calculate_content_hash(pipeline_data)

        assert isinstance(hash_value, str)
        assert len(hash_value) == 32  # MD5 hash

    def test_calculate_content_hash_consistent(self):
        """Test hash is consistent for same content"""
        service = PipelineImportService(Mock())

        pipeline_data = {"name": "Test", "steps": [], "version": "1.0"}

        hash1 = service._calculate_content_hash(pipeline_data)
        hash2 = service._calculate_content_hash(pipeline_data)
        hash3 = service._calculate_content_hash(pipeline_data)

        assert hash1 == hash2 == hash3

    def test_calculate_content_hash_order_independent(self):
        """Test hash is same regardless of key order"""
        service = PipelineImportService(Mock())

        data1 = {"name": "Test", "version": "1.0", "steps": []}
        data2 = {"steps": [], "name": "Test", "version": "1.0"}

        hash1 = service._calculate_content_hash(data1)
        hash2 = service._calculate_content_hash(data2)

        assert hash1 == hash2  # sort_keys=True makes them identical

    def test_calculate_content_hash_changes_with_content(self):
        """Test hash changes when content changes"""
        service = PipelineImportService(Mock())

        data1 = {"name": "Test", "steps": []}
        data2 = {"name": "Test Modified", "steps": []}

        hash1 = service._calculate_content_hash(data1)
        hash2 = service._calculate_content_hash(data2)

        assert hash1 != hash2

    def test_calculate_content_hash_nested_objects(self):
        """Test hash calculation with nested objects"""
        service = PipelineImportService(Mock())

        pipeline_data = {
            "name": "Test",
            "steps": [
                {"id": "step1", "config": {"param1": "value1"}},
                {"id": "step2", "config": {"param2": "value2"}}
            ]
        }

        hash_value = service._calculate_content_hash(pipeline_data)

        assert isinstance(hash_value, str)
        assert len(hash_value) == 32


class TestClearAllImportedPipelines:
    """Test clearing imported pipelines"""

    @pytest.mark.asyncio
    async def test_clear_all_imported_pipelines_success(self):
        """Test successfully clearing imported pipelines"""
        mock_db = Mock()
        mock_result = Mock(success=True, rows_affected=5)
        mock_db.execute_async = AsyncMock(return_value=mock_result)

        service = PipelineImportService(mock_db)
        deleted_count = await service.clear_all_imported_pipelines()

        assert deleted_count == 5
        mock_db.execute_async.assert_called_once()
        call_args = mock_db.execute_async.call_args[0]
        assert "DELETE FROM pipelines" in call_args[0]
        assert "is_system = 0" in call_args[0]

    @pytest.mark.asyncio
    async def test_clear_all_imported_pipelines_failure(self):
        """Test failure when clearing pipelines"""
        mock_db = Mock()
        mock_result = Mock(success=False)
        mock_db.execute_async = AsyncMock(return_value=mock_result)

        service = PipelineImportService(mock_db)
        deleted_count = await service.clear_all_imported_pipelines()

        assert deleted_count == 0

    @pytest.mark.asyncio
    async def test_clear_all_imported_pipelines_no_rows_affected(self):
        """Test clearing with no rows affected"""
        mock_db = Mock()
        mock_result = Mock(success=True, spec=['success'])  # Explicitly no rows_affected
        mock_db.execute_async = AsyncMock(return_value=mock_result)

        service = PipelineImportService(mock_db)
        deleted_count = await service.clear_all_imported_pipelines()

        assert deleted_count == 0


class TestGetExistingPipeline:
    """Test getting existing pipeline"""

    @pytest.mark.asyncio
    async def test_get_existing_pipeline_found(self):
        """Test getting an existing pipeline"""
        mock_db = Mock()
        mock_result = Mock(
            data=[{"id": "123", "content_hash": "abc123"}]
        )
        mock_db.fetch_one = Mock(return_value=mock_result)  # fetch_one is sync, not async

        service = PipelineImportService(mock_db)
        result = await service._get_existing_pipeline("test-pipeline")

        assert result is not None
        assert result["id"] == "123"
        assert result["content_hash"] == "abc123"

    @pytest.mark.asyncio
    async def test_get_existing_pipeline_not_found(self):
        """Test pipeline not found"""
        mock_db = Mock()
        mock_db.fetch_one = Mock(return_value=None)  # fetch_one is sync, not async

        service = PipelineImportService(mock_db)
        result = await service._get_existing_pipeline("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_existing_pipeline_empty_data(self):
        """Test pipeline with empty data"""
        mock_db = Mock()
        mock_result = Mock(data=None)
        mock_db.fetch_one = Mock(return_value=mock_result)  # fetch_one is sync, not async

        service = PipelineImportService(mock_db)
        result = await service._get_existing_pipeline("test")

        assert result is None


class TestGetPipelineBySlug:
    """Test getting pipeline by slug"""

    @pytest.mark.asyncio
    async def test_get_pipeline_by_slug_success(self):
        """Test successfully getting pipeline by slug"""
        mock_db = Mock()
        pipeline_json = json.dumps({"name": "Test", "steps": []})
        # fetch_one is sync and returns the row itself
        mock_db.fetch_one = Mock(return_value={
            "id": "123",
            "slug": "test-pipeline",
            "name": "Test Pipeline",
            "description": "Test description",
            "version": "1.0",
            "pipeline_json": pipeline_json,
            "file_path": "test.json",
            "is_active": 1,
            "created_at": "2024-01-01",
            "updated_at": "2024-01-01"
        })

        service = PipelineImportService(mock_db)
        result = await service.get_pipeline_by_slug("test-pipeline")

        assert result is not None
        assert result["id"] == "123"
        assert result["slug"] == "test-pipeline"
        assert "pipeline_config" in result
        assert result["pipeline_config"]["name"] == "Test"

    @pytest.mark.asyncio
    async def test_get_pipeline_by_slug_not_found(self):
        """Test pipeline not found by slug"""
        mock_db = Mock()
        mock_db.fetch_one = Mock(return_value=None)  # fetch_one is sync, not async

        service = PipelineImportService(mock_db)
        result = await service.get_pipeline_by_slug("nonexistent")

        assert result is None


class TestImportAllPipelines:
    """Test importing all pipelines"""

    @pytest.mark.asyncio
    async def test_import_all_pipelines_directory_not_exists(self):
        """Test import when directory doesn't exist"""
        mock_db = Mock()
        service = PipelineImportService(mock_db, "/nonexistent/path")

        result = await service.import_all_pipelines()

        assert result["imported"] == 0
        assert result["skipped"] == 0
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_import_all_pipelines_with_clear_existing(self):
        """Test import with clear_existing=True"""
        mock_db = Mock()
        mock_result = Mock(success=True, rows_affected=3)
        mock_db.execute_async = AsyncMock(return_value=mock_result)

        service = PipelineImportService(mock_db, "/nonexistent")
        await service.import_all_pipelines(clear_existing=True)

        # Should have called clear
        mock_db.execute_async.assert_called_once()
        assert "DELETE FROM pipelines" in mock_db.execute_async.call_args[0][0]


class TestErrorHandling:
    """Test error handling scenarios"""

    @pytest.mark.asyncio
    async def test_create_pipeline_database_failure(self):
        """Test _create_pipeline when database fails"""
        mock_db = Mock()
        mock_result = Mock(success=False, error="Database error")
        mock_db.execute_async = AsyncMock(return_value=mock_result)

        service = PipelineImportService(mock_db)
        pipeline_data = {"name": "Test", "description": "Test desc"}

        with pytest.raises(Exception, match="Failed to create pipeline"):
            await service._create_pipeline("test-slug", pipeline_data, "hash123", "test.json")

    @pytest.mark.asyncio
    async def test_update_pipeline_database_failure(self):
        """Test _update_pipeline when database fails"""
        mock_db = Mock()
        mock_result = Mock(success=False, error="Database error")
        mock_db.execute_async = AsyncMock(return_value=mock_result)

        service = PipelineImportService(mock_db)
        pipeline_data = {"name": "Test", "description": "Test desc"}

        with pytest.raises(Exception, match="Failed to update pipeline"):
            await service._update_pipeline("pipeline-id", pipeline_data, "hash123", "test.json")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

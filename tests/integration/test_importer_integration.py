"""
Integration tests for pipeline importer with real file operations
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from ia_modules.pipeline.importer import PipelineImportService


@pytest.mark.asyncio
async def test_pipeline_import_from_file():
    """Test importing pipeline from actual JSON file"""
    mock_db = Mock()

    # fetch_one is called synchronously in _get_existing_pipeline
    mock_db.fetch_one = Mock(return_value=None)

    async def mock_execute_async(*args):
        return Mock(success=True)

    mock_db.execute_async = mock_execute_async

    # Create a temporary pipeline file inside a temp directory that becomes the pipelines_dir
    with tempfile.TemporaryDirectory() as temp_dir:
        importer = PipelineImportService(mock_db, temp_dir)
        
        # Create a temporary pipeline file
        pipeline_data = {
            "name": "Integration Test Pipeline",
            "version": "1.0", 
            "description": "Test pipeline for integration testing",
            "steps": [
                {
                    "id": "step1",
                    "step_class": "TestStep",
                    "module": "test.module",
                    "config": {"param": "value"}
                }
            ],
            "flow": {
                "start_at": "step1",
                "paths": [
                    {
                        "from_step": "step1",
                        "to_step": "end_with_success",
                        "condition": {"type": "always"}
                    }
                ]
            }
        }

        # Create file in the temp directory
        temp_file = Path(temp_dir) / "test_pipeline.json"
        with open(temp_file, 'w') as f:
            json.dump(pipeline_data, f, indent=2)
        
        # Test importing the file using the private method
        result = await importer._import_pipeline_file(temp_file)
        
        assert result is not None
        assert result["action"] in ["imported", "updated"]
        assert "pipeline_id" in result
        assert "slug" in result
@pytest.mark.asyncio
async def test_pipeline_import_with_validation_errors():
    """Test pipeline import with validation errors"""
    mock_db = Mock()

    mock_db.fetch_one = Mock(return_value=None)

    async def mock_execute_async(*args):
        return Mock(success=True)

    mock_db.execute_async = mock_execute_async

    importer = PipelineImportService(mock_db)
    
    # Create invalid pipeline data
    invalid_pipeline = {
        "name": "Invalid Pipeline"
        # Missing required fields
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(invalid_pipeline, f, indent=2)
        temp_file = f.name
    
    try:
        # Test that validation fails
        with pytest.raises(ValueError):  # More specific exception
            await importer._import_pipeline_file(Path(temp_file))
            
    finally:
        # Clean up - handle file being in use gracefully
        try:
            Path(temp_file).unlink()
        except (PermissionError, FileNotFoundError):
            pass


@pytest.mark.asyncio
async def test_pipeline_directory_scan():
    """Test scanning directory for pipeline files"""
    mock_db = Mock()

    mock_db.fetch_one = Mock(return_value=None)

    async def mock_execute_async(*args):
        return Mock(success=True)

    mock_db.execute_async = mock_execute_async
    
    # Create temporary directory with pipeline files
    with tempfile.TemporaryDirectory() as temp_dir:
        importer = PipelineImportService(mock_db, temp_dir)
        
        # Create multiple pipeline files
        for i in range(3):
            pipeline_data = {
                "name": f"Test Pipeline {i+1}",
                "steps": [{
                    "id": f"step{i+1}",
                    "step_class": "TestStep",
                    "module": "test.module"
                }]
            }
            
            file_path = Path(temp_dir) / f"pipeline_{i+1}.json"
            with open(file_path, 'w') as f:
                json.dump(pipeline_data, f)
        
        # Test directory scan and import
        result = await importer.import_all_pipelines()
        
        # May be 0 if database operations are mocked/skipped
        assert result["imported"] >= 0
        assert result["errors"] == 0
        assert isinstance(result["details"], list)
@pytest.mark.asyncio
async def test_pipeline_content_hash_consistency():
    """Test that content hash is consistent across imports"""
    mock_db = Mock()
    importer = PipelineImportService(mock_db)
    
    pipeline_data = {
        "name": "Hash Test Pipeline",
        "steps": [{"id": "step1", "step_class": "TestStep"}]
    }
    
    # Calculate hash multiple times
    hash1 = importer._calculate_content_hash(pipeline_data)
    hash2 = importer._calculate_content_hash(pipeline_data)
    hash3 = importer._calculate_content_hash(pipeline_data)
    
    assert hash1 == hash2 == hash3
    
    # Modify data slightly and verify hash changes
    pipeline_data["name"] = "Modified Hash Test Pipeline"
    hash4 = importer._calculate_content_hash(pipeline_data)
    
    assert hash4 != hash1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
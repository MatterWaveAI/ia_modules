"""
Unit tests for pipeline importer
"""

import asyncio
from unittest.mock import Mock

import pytest

from ia_modules.pipeline.importer import PipelineImportService


def test_pipeline_import_service_creation():
    """Test pipeline import service creation"""
    mock_db = Mock()
    importer = PipelineImportService(mock_db)
    
    assert importer.db_provider == mock_db
    assert importer.pipelines_dir is not None


def test_slug_generation():
    """Test slug generation"""
    mock_db = Mock()
    importer = PipelineImportService(mock_db)
    
    # Test slug generation with name and file path
    slug = importer._generate_slug("Test Pipeline", "test/test.json")
    assert isinstance(slug, str)
    assert len(slug) > 0


def test_content_hash():
    """Test content hash calculation"""
    mock_db = Mock()
    importer = PipelineImportService(mock_db)
    
    pipeline_data = {
        "name": "Test Pipeline",
        "steps": []
    }
    
    hash_value = importer._calculate_content_hash(pipeline_data)
    assert isinstance(hash_value, str)
    assert len(hash_value) == 32  # MD5 hash length


def test_pipeline_validation():
    """Test pipeline configuration validation"""
    mock_db = Mock()
    importer = PipelineImportService(mock_db)
    
    # Test valid pipeline
    valid_pipeline = {
        "name": "Test Pipeline",
        "steps": [
            {
                "id": "step1",
                "step_class": "TestStep",
                "module": "test.module"
            }
        ]
    }
    
    is_valid = asyncio.run(importer.validate_pipeline_config(valid_pipeline))
    assert is_valid is True
    
    # Test invalid pipeline (missing steps)
    invalid_pipeline = {
        "name": "Test Pipeline"
        # Missing steps
    }
    
    is_valid = asyncio.run(importer.validate_pipeline_config(invalid_pipeline))
    assert is_valid is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

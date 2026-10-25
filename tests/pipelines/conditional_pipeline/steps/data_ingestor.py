"""
Data Ingestor Step Implementation
"""

from typing import Dict, Any

from ia_modules.pipeline.core import Step


class DataIngestorStep(Step):
    """Step to ingest data from a source"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        
    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Ingest data from pipeline input"""
        # Get test_data from pipeline input
        test_data = data.get('test_data', [])

        return {
            "ingested_data": test_data,
            "source": "pipeline_input",
            "record_count": len(test_data) if isinstance(test_data, list) else 1
        }

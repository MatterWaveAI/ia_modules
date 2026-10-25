"""
Results Aggregator Step Implementation
"""

from typing import Dict, Any

from ia_modules.pipeline.core import Step


class ResultsAggregatorStep(Step):
    """Step to aggregate results from different processing paths"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        
    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate results from different processing paths"""
        processed_data = data.get('processed_data')

        # Aggregate the results
        aggregation_results = self._aggregate_results(processed_data)
        
        return {
            "aggregated_results": aggregation_results,
            "total_records_processed": len(processed_data) if isinstance(processed_data, list) else 1,
            "processing_summary": self._get_processing_summary(processed_data)
        }
        
    def _aggregate_results(self, data: Any) -> Dict[str, Any]:
        """Aggregate results from processed data"""
        # Simple aggregation - in practice this would be more complex
        if isinstance(data, list):
            return {
                "total_count": len(data),
                "first_record": data[0] if data else None,
                "last_record": data[-1] if data else None
            }
        elif isinstance(data, dict):
            return {
                "total_count": 1,
                "record": data
            }
        else:
            return {}
            
    def _get_processing_summary(self, data: Any) -> Dict[str, Any]:
        """Get a summary of the processing performed"""
        if isinstance(data, list):
            return {
                "records_processed": len(data),
                "data_type": "list",
                "sample_record": data[0] if data else None
            }
        elif isinstance(data, dict):
            return {
                "records_processed": 1,
                "data_type": "dict",
                "record_keys": list(data.keys()) if data else []
            }
        else:
            return {}

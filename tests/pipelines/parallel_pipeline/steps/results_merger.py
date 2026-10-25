"""
Results Merger Step Implementation
"""

from typing import Dict, Any, List

from ia_modules.pipeline.core import Step


class ResultsMergerStep(Step):
    """Step to merge results from parallel processing streams"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Merge results from different parallel processing streams"""
        # Get all the processed data from different streams
        stream_results = []

        # Try to collect results from parallel processors
        # Option 1: Named inputs (processed_data_1, processed_data_2, processed_data_3)
        for i in range(1, 4):
            key = f'processed_data_{i}'
            if key in input and input[key]:
                stream_results.append(input[key])
        
        # Option 2: If no named inputs, try to get the last step's processed_data
        if not stream_results and 'processed_data' in input:
            data = input['processed_data']
            if isinstance(data, list):
                # If it's a list of results from parallel steps, use them
                stream_results = data
            else:
                # Single result - wrap in list
                stream_results = [data]
        
        # Option 3: Try to extract any data that looks like processed results
        if not stream_results:
            for key, value in input.items():
                if 'processed' in key.lower() and isinstance(value, (list, dict)):
                    if isinstance(value, list):
                        stream_results.extend(value)
                    else:
                        stream_results.append(value)
        
        # Merge the results
        merged_data = self._merge_results(stream_results)
        
        return {
            "merged_results": merged_data,
            "stream_count": len(stream_results),
            "total_records": len(merged_data) if isinstance(merged_data, list) else sum(r.get('record_count', 0) for r in stream_results if isinstance(r, dict)),
            "processing_summary": self._get_processing_summary(stream_results)
        }
        
    def _merge_results(self, results: List[Any]) -> Any:
        """Merge multiple result sets"""
        # Simple merge - concatenate lists or combine dictionaries
        if not results:
            return {}
            
        # If all results are lists, concatenate them
        if all(isinstance(r, list) for r in results):
            merged = []
            for result in results:
                if isinstance(result, list):
                    merged.extend(result)
                else:
                    merged.append(result)
            return merged
            
        # If all results are dictionaries, merge them intelligently
        elif all(isinstance(r, dict) for r in results):
            merged = {
                "processed_data": []
            }
            
            # Merge processed_data lists from all streams
            for result in results:
                if isinstance(result, dict):
                    # Extract and merge processed_data
                    if 'processed_data' in result:
                        data = result['processed_data']
                        if isinstance(data, list):
                            merged['processed_data'].extend(data)
                        else:
                            merged['processed_data'].append(data)
                    
                    # Copy other fields from first result
                    for key, value in result.items():
                        if key != 'processed_data' and key not in merged:
                            merged[key] = value
            
            return merged
            
        # Otherwise, just return the first result
        else:
            return results[0] if results else {}
            
    def _get_processing_summary(self, results: List[Any]) -> Dict[str, Any]:
        """Get a summary of the merging process"""
        total_records = 0
        for result in results:
            if isinstance(result, list):
                total_records += len(result)
            elif isinstance(result, dict):
                total_records += 1
                
        return {
            "total_streams": len(results),
            "total_merged_records": total_records,
            "merge_type": "concatenation" if all(isinstance(r, list) for r in results) else "combination"
        }

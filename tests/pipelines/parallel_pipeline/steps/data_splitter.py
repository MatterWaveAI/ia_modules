"""
Data Splitter Step Implementation
"""

from typing import Dict, Any

from ia_modules.pipeline.core import Step


class DataSplitterStep(Step):
    """Step to split data into multiple streams for parallel processing"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Split input data into multiple chunks for parallel processing"""
        # Get the raw data to split
        raw_data = input.get('loaded_data')

        if not raw_data:
            raise ValueError("No data to split")
            
        split_count = self.config.get('split_count', 2)
        
        # Split the data into chunks
        if isinstance(raw_data, list):
            chunk_size = max(1, len(raw_data) // split_count)
            chunks = [raw_data[i:i + chunk_size] for i in range(0, len(raw_data), chunk_size)]
            
            # Ensure we have exactly split_count chunks (pad with empty lists if needed)
            while len(chunks) < split_count:
                chunks.append([])
                
            chunks = chunks[:split_count]
        else:
            # For single record data, create multiple copies
            chunks = [raw_data] * split_count
            
        return {
            "data_chunks": chunks,
            "chunk_count": len(chunks),
            "original_data_size": len(raw_data) if isinstance(raw_data, list) else 1
        }

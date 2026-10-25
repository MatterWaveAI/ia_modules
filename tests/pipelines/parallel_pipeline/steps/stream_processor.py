"""
Stream Processor Step Implementation
"""

from typing import Dict, Any

from ia_modules.pipeline.core import Step


class StreamProcessorStep(Step):
    """Step to process data in a parallel stream"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Process data in the current stream"""
        # Get the chunk of data for this stream
        data_chunks = input.get('data_chunks', [])
        stream_id = self.config.get('stream_id', 1)

        # Get the chunk for this stream (stream_id is 1-based)
        if len(data_chunks) >= stream_id:
            chunk = data_chunks[stream_id - 1]
        else:
            chunk = []
        
        processing_type = self.config.get('processing_type', 'analytics')
        
        # Process based on type
        if processing_type == 'analytics':
            processed_data = self._process_analytics(chunk)
        elif processing_type == 'transform':
            processed_data = self._process_transform(chunk)
        else:
            processed_data = chunk
            
        return {
            "stream_id": self.config.get('stream_id'),
            "processing_type": processing_type,
            "processed_data": processed_data,
            "record_count": len(processed_data) if isinstance(processed_data, list) else 1
        }
        
    def _process_analytics(self, data: Any) -> Any:
        """Perform analytics processing"""
        # Simple example - in practice this would be more complex
        if isinstance(data, dict):
            return self._process_record_analytics(data)
        elif isinstance(data, list):
            return [self._process_record_analytics(record) for record in data]
        else:
            return data
            
    def _process_transform(self, data: Any) -> Any:
        """Perform transformation processing"""
        # Simple example - in practice this would be more complex
        if isinstance(data, dict):
            return self._transform_record(data)
        elif isinstance(data, list):
            return [self._transform_record(record) for record in data]
        else:
            return data
            
    def _process_record_analytics(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single record for analytics"""
        # Add some analytics fields
        processed = record.copy()
        
        # Example - add computed fields
        if 'sales' in processed and 'quantity' in processed:
            processed['revenue'] = processed['sales'] * processed['quantity']
            
        return processed
        
    def _transform_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Transform a single record"""
        # Simple transformation - convert to lowercase keys
        transformed = {}
        for key, value in record.items():
            transformed[key.lower()] = value
            
        return transformed

"""
Initial Processing Step for HITL Pipeline Testing
Simulates automated processing with configurable quality outcomes
"""
import uuid
import random
from typing import Dict, Any
from ia_modules.pipeline.core import Step


class InitialProcessingStep(Step):
    """
    Initial automated processing step that simulates content processing
    with varying quality levels to trigger different HITL paths
    """
    
    async def run(self, data: Dict[str, Any]) -> Any:
        # Simulate processing the input content
        content = data.get("content", "Default test content for HITL processing")
        processing_type = self.config.get("processing_type", "automated")
        
        # Simulate some processing time and results
        processed_content = f"[PROCESSED] {content}"
        
        # Generate random quality metrics to test different paths
        quality_score = random.uniform(0.6, 0.95)
        confidence = random.uniform(0.7, 0.9)
        
        # Simulate potential issues that might require human intervention
        issues_detected = []
        if quality_score < 0.8:
            issues_detected.append("Low quality score detected")
        if confidence < 0.85:
            issues_detected.append("Low confidence in automated processing")
        if len(content.split()) < 5:
            issues_detected.append("Content too short for reliable processing")
            
        processing_id = str(uuid.uuid4())
        
        return {
            "processing_id": processing_id,
            "original_content": content,
            "processed_content": processed_content,
            "quality_score": quality_score,
            "confidence": confidence,
            "processing_type": processing_type,
            "issues_detected": issues_detected,
            "timestamp": "2025-09-25T10:00:00Z",
            "metadata": {
                "processor_version": "1.0.0",
                "processing_duration_ms": random.randint(100, 500),
                "word_count": len(content.split())
            }
        }
"""
Manual Enhancement Step for HITL Pipeline Testing
Demonstrates iterative refinement pattern
"""
import uuid
from typing import Dict, Any
from ia_modules.pipeline.core import Step


class ManualEnhancementStep(Step):
    """
    Allows iterative manual enhancement of content
    Demonstrates the progressive enhancement HITL pattern
    """
    
    async def run(self, data: Dict[str, Any]) -> Any:
        self.config.get("enhancement_type", "iterative")
        max_iterations = self.config.get("max_iterations", 3)
        timeout_seconds = self.config.get("timeout_seconds", 600)
        
        # Get current iteration or start at 1
        current_iteration = data.get("enhancement_iteration", 1)
        
        # Get content to enhance
        current_content = data.get("processed_content", "")
        enhancement_history = data.get("enhancement_history", [])
        human_feedback = data.get("human_feedback", "")
        
        interaction_id = str(uuid.uuid4())
        
        # Check if we've reached max iterations
        if current_iteration > max_iterations:
            return {
                **data,
                "status": "max_iterations_reached",
                "final_enhanced_content": current_content,
                "total_iterations": current_iteration - 1,
                "enhancement_complete": True
            }
        
        # Create UI schema for manual enhancement
        ui_schema = {
            "type": "iterative_enhancement",
            "title": f"Content Enhancement - Iteration {current_iteration}",
            "description": f"Manual enhancement based on feedback: {human_feedback}",
            "fields": [
                {
                    "name": "enhanced_content",
                    "type": "textarea",
                    "label": f"Enhanced Content (Iteration {current_iteration})",
                    "default": current_content,
                    "rows": 10,
                    "required": True
                },
                {
                    "name": "enhancement_notes",
                    "type": "textarea",
                    "label": "Enhancement Notes",
                    "placeholder": "Describe the changes you made...",
                    "required": False
                },
                {
                    "name": "continue_enhancing",
                    "type": "checkbox",
                    "label": "Continue to next iteration?",
                    "default": False
                },
                {
                    "name": "enhancement_type",
                    "type": "select",
                    "label": "Type of Enhancement",
                    "options": [
                        {"value": "grammar", "label": "Grammar & Style"},
                        {"value": "clarity", "label": "Clarity & Structure"},
                        {"value": "content", "label": "Content & Detail"},
                        {"value": "formatting", "label": "Formatting & Layout"},
                        {"value": "other", "label": "Other"}
                    ]
                },
                {
                    "name": "confidence_rating",
                    "type": "number",
                    "label": "Confidence in Enhancement (1-10)",
                    "min": 1,
                    "max": 10,
                    "default": 7
                }
            ]
        }
        
        # For testing - simulate manual enhancement
        simulated_enhanced_content = f"[ENHANCED-{current_iteration}] {current_content} - Additional improvements made."
        simulated_continue = current_iteration < 2  # Continue for first iteration only
        
        # Record this enhancement iteration
        enhancement_record = {
            "iteration": current_iteration,
            "original_content": current_content,
            "enhanced_content": simulated_enhanced_content,
            "enhancement_notes": f"Iteration {current_iteration}: Improved clarity and detail",
            "enhancement_type": "clarity",
            "confidence_rating": 8,
            "timestamp": "2025-09-25T10:03:00Z"
        }
        
        enhancement_history.append(enhancement_record)
        
        # Determine if we should continue
        if simulated_continue and current_iteration < max_iterations:
            return {
                **data,
                "status": "enhancement_iteration_complete",
                "interaction_id": interaction_id,
                "ui_schema": ui_schema,
                "timeout_seconds": timeout_seconds,
                "processed_content": simulated_enhanced_content,
                "enhancement_iteration": current_iteration + 1,
                "enhancement_history": enhancement_history,
                "continue_enhancing": True,
                "current_enhancement": enhancement_record
            }
        else:
            return {
                **data,
                "status": "enhancement_complete",
                "final_enhanced_content": simulated_enhanced_content,
                "processed_content": simulated_enhanced_content,
                "total_iterations": current_iteration,
                "enhancement_history": enhancement_history,
                "enhancement_complete": True,
                "final_enhancement": enhancement_record
            }
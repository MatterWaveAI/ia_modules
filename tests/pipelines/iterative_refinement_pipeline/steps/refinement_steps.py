"""
Steps for iterative refinement pipeline demo
"""

from typing import Dict, Any
from ia_modules.pipeline.core import Step
from ia_modules.pipeline.iterative_refinement import IterativeRefinementStep, ProcessRefinementResponseStep


class GenerateInitialDraftStep(Step):
    """Generate initial draft for refinement"""

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a simple initial draft"""
        topic = data.get('topic', 'AI and Machine Learning')

        # Simulate generating an initial draft
        initial_draft = f"""# {topic}

## Introduction
This is an initial draft about {topic}. It covers basic concepts and provides
an overview of the field.

## Key Concepts
- Concept 1: Basic definition
- Concept 2: Important principles
- Concept 3: Applications

## Conclusion
In summary, {topic} is an important and growing field.
"""

        return {
            "current_result": initial_draft,
            "topic": topic,
            "iteration": 1
        }


class FinalizeDocumentStep(Step):
    """Finalize the refined document"""

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Finalize and format the document"""
        final_result = data.get('final_result', '')
        iterations_completed = data.get('iterations_completed', 0)
        refinement_history = data.get('refinement_history', [])

        # Add metadata
        finalized = {
            "document": final_result,
            "metadata": {
                "iterations": iterations_completed,
                "refinements": len(refinement_history),
                "refinement_notes": [r.get('notes', '') for r in refinement_history if r.get('notes')]
            },
            "status": "finalized"
        }

        return finalized


# Re-export the iterative refinement steps for use in pipeline
class RefineContentStep(IterativeRefinementStep):
    """Alias for IterativeRefinementStep"""
    pass


class ProcessRefinementStep(ProcessRefinementResponseStep):
    """Alias for ProcessRefinementResponseStep"""
    pass

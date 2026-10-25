"""
Loop detection and cycle analysis for graph validation.

This module provides tools to detect, analyze, and validate loops (cycles)
in pipeline graphs. Supports both simple cycles and complex loop patterns.
"""
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
import logging

from ia_modules.pipeline.flow import normalize_flow

logger = logging.getLogger(__name__)


@dataclass
class Loop:
    """Represents a detected loop in the graph."""

    steps: List[str]  # List of step IDs in the loop
    entry_point: str  # First step in the loop
    exit_conditions: List[Dict]  # Conditions that exit the loop

    def __str__(self) -> str:
        cycle_path = ' -> '.join(self.steps) + f' -> {self.steps[0]}'
        return f"Loop: {cycle_path}"

    def __repr__(self) -> str:
        return (
            f"Loop(steps={self.steps}, "
            f"entry={self.entry_point}, "
            f"exits={len(self.exit_conditions)})"
        )


class LoopDetector:
    """
    Detects and analyzes loops in pipeline graphs.

    Uses depth-first search (DFS) to find all cycles in the directed graph,
    then analyzes exit conditions to determine if loops are safe.
    """

    def __init__(self, flow: Dict):
        """
        Initialize loop detector.

        Args:
            flow: Pipeline flow definition with 'paths' list
        """
        self.flow = normalize_flow(flow)
        self.transitions = self.flow.get('paths', [])
        self._graph = None

    def detect_loops(self) -> List[Loop]:
        """
        Detect all loops in the graph using DFS.

        Returns:
            List of Loop objects representing detected cycles

        Example:
            >>> flow = {
            ...     'paths': [
            ...         {'from': 'a', 'to': 'b'},
            ...         {'from': 'b', 'to': 'a', 'condition': {...}}
            ...     ]
            ... }
            >>> detector = LoopDetector(flow)
            >>> loops = detector.detect_loops()
            >>> len(loops)
            1
        """
        loops: list[list[str]] = []
        visited: set[str] = set()
        rec_stack: list[str] = []

        # Build adjacency list
        graph = self._build_graph()

        # DFS from each node
        for node in graph.keys():
            if node not in visited:
                self._detect_loops_dfs(node, graph, visited, rec_stack, loops)

        return loops

    def _build_graph(self) -> Dict[str, List[Tuple[str, Dict]]]:
        """
        Build adjacency list representation of the graph.

        Returns:
            Dict mapping step_id -> list of (neighbor_id, condition) tuples
        """
        if self._graph is not None:
            return self._graph

        graph: dict[str, list[str]] = {}
        for transition in self.transitions:
            from_step = transition['from']
            to_step = transition['to']
            condition = transition.get('condition', {'type': 'always'})

            if from_step not in graph:
                graph[from_step] = []
            graph[from_step].append((to_step, condition))

        self._graph = graph
        return graph

    def _detect_loops_dfs(
        self,
        node: str,
        graph: Dict,
        visited: Set[str],
        rec_stack: List[str],
        loops: List[Loop]
    ):
        """
        DFS to detect cycles.

        Args:
            node: Current node being visited
            graph: Adjacency list
            visited: Set of all visited nodes
            rec_stack: Current recursion stack (for cycle detection)
            loops: List to append detected loops to
        """
        visited.add(node)
        rec_stack.append(node)

        for neighbor, condition in graph.get(node, []):
            if neighbor not in visited:
                self._detect_loops_dfs(neighbor, graph, visited, rec_stack, loops)
            elif neighbor in rec_stack:
                # Found a cycle!
                cycle_start = rec_stack.index(neighbor)
                cycle_steps = rec_stack[cycle_start:]

                # Find exit conditions
                exit_conditions = self._find_exit_conditions(cycle_steps, graph)

                loop = Loop(
                    steps=cycle_steps,
                    entry_point=neighbor,
                    exit_conditions=exit_conditions
                )

                # Only add if not duplicate
                if not self._is_duplicate_loop(loop, loops):
                    loops.append(loop)
                    logger.debug(f"Detected {loop}")

        rec_stack.pop()

    def _is_duplicate_loop(self, loop: Loop, loops: List[Loop]) -> bool:
        """Check if loop is already in the list (same cycle, different entry)."""
        loop_set = set(loop.steps)
        for existing in loops:
            if set(existing.steps) == loop_set:
                return True
        return False

    def _find_exit_conditions(
        self,
        loop_steps: List[str],
        graph: Dict
    ) -> List[Dict]:
        """
        Find conditions that exit the loop.

        An exit condition is an edge from a loop step to a non-loop step.

        Args:
            loop_steps: Steps in the loop
            graph: Adjacency list

        Returns:
            List of exit condition dicts
        """
        exit_conditions = []
        loop_set = set(loop_steps)

        for step in loop_steps:
            for neighbor, condition in graph.get(step, []):
                if neighbor not in loop_set:
                    # This edge exits the loop
                    exit_conditions.append({
                        'from': step,
                        'to': neighbor,
                        'condition': condition
                    })

        return exit_conditions

    def validate_loops(self, max_iterations: int = 100) -> List[str]:
        """
        Validate that loops have proper exit conditions.

        Checks for:
        - Loops without any exit condition (infinite loop)
        - Loop edges with 'always' condition (potential infinite loop)

        Args:
            max_iterations: Maximum allowed iterations (not used yet, for future)

        Returns:
            List of validation error messages

        Example:
            >>> detector = LoopDetector(flow)
            >>> errors = detector.validate_loops()
            >>> if errors:
            ...     print("Validation failed:", errors)
        """
        errors = []
        loops = self.detect_loops()

        for loop in loops:
            # Check if loop has exit condition
            if not loop.exit_conditions:
                errors.append(
                    f"{loop} has no exit condition - this will cause an infinite loop!"
                )

            # Check for 'always' conditions in loop (may cause infinite loop)
            for i, step in enumerate(loop.steps):
                next_step = loop.steps[(i + 1) % len(loop.steps)]
                transition = self._find_transition(step, next_step)

                if transition:
                    condition = transition.get('condition', {'type': 'always'})
                    if condition.get('type') == 'always' and not loop.exit_conditions:
                        errors.append(
                            f"Loop edge {step} -> {next_step} has 'always' condition "
                            f"with no exit path - this will cause an infinite loop"
                        )

        return errors

    def _find_transition(self, from_step: str, to_step: str) -> Optional[Dict]:
        """
        Find transition between two steps.

        Args:
            from_step: Source step ID
            to_step: Target step ID

        Returns:
            Transition dict or None if not found
        """
        for transition in self.transitions:
            if transition['from'] == from_step and transition['to'] == to_step:
                return transition
        return None

    def get_loop_for_step(self, step_id: str) -> Optional[Loop]:
        """
        Get the loop that contains the given step.

        Args:
            step_id: Step ID to search for

        Returns:
            Loop containing the step, or None
        """
        loops = self.detect_loops()
        for loop in loops:
            if step_id in loop.steps:
                return loop
        return None

    def is_in_loop(self, step_id: str) -> bool:
        """
        Check if a step is part of any loop.

        Args:
            step_id: Step ID to check

        Returns:
            True if step is in a loop
        """
        return self.get_loop_for_step(step_id) is not None

    def get_loop_id(self, step_id: str) -> Optional[str]:
        """
        Get a unique identifier for the loop containing the step.

        Args:
            step_id: Step ID

        Returns:
            Loop ID (based on entry point) or None
        """
        loop = self.get_loop_for_step(step_id)
        if loop:
            return f"loop_{loop.entry_point}"
        return None

    def visualize_loops(self) -> str:
        """
        Create a text visualization of detected loops.

        Returns:
            Multi-line string showing loops

        Example:
            >>> detector = LoopDetector(flow)
            >>> print(detector.visualize_loops())
            Detected 2 loops:

            Loop 1: draft -> review -> draft
              Entry: draft
              Exit conditions: 2
                - review -> publish (if approved == true)

            Loop 2: fetch -> process -> validate -> fetch
              Entry: fetch
              Exit conditions: 1
                - validate -> store (if valid == true)
        """
        loops = self.detect_loops()

        if not loops:
            return "No loops detected in pipeline graph."

        lines = [f"Detected {len(loops)} loop(s):\n"]

        for i, loop in enumerate(loops, 1):
            lines.append(f"Loop {i}: {' -> '.join(loop.steps)} -> {loop.steps[0]}")
            lines.append(f"  Entry point: {loop.entry_point}")
            lines.append(f"  Exit conditions: {len(loop.exit_conditions)}")

            for exit_cond in loop.exit_conditions:
                cond_str = self._format_condition(exit_cond['condition'])
                lines.append(
                    f"    - {exit_cond['from']} -> {exit_cond['to']} ({cond_str})"
                )

            lines.append("")  # Blank line between loops

        return '\n'.join(lines)

    def _format_condition(self, condition: Dict) -> str:
        """Format condition for display."""
        cond_type = condition.get('type', 'always')

        if cond_type == 'always':
            return 'always'
        elif cond_type == 'expression':
            config = condition.get('config', {})
            source = config.get('source', '?')
            operator = config.get('operator', '?')
            value = config.get('value', '?')
            return f"if {source} {operator} {value}"
        else:
            return cond_type

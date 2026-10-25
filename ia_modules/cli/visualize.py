"""
Pipeline Visualization

Generate visual representations of pipeline flow using graphviz.
"""

from typing import Dict, Any, Optional
from pathlib import Path


def visualize_pipeline(
    pipeline_data: Dict[str, Any],
    output_path: str,
    format: str = 'png'
) -> None:
    """
    Generate a visualization of the pipeline flow

    Args:
        pipeline_data: Pipeline JSON data
        output_path: Path to save the visualization
        format: Output format (png, svg, pdf, dot)

    Raises:
        ImportError: If graphviz is not installed
        ValueError: If pipeline structure is invalid
    """
    try:
        import graphviz
    except ImportError:
        raise ImportError(
            "Graphviz is required for visualization. "
            "Install with: pip install graphviz"
        )

    # Create directed graph
    dot = graphviz.Digraph(
        name=pipeline_data.get('name', 'pipeline'),
        format=format.replace('.', ''),
        graph_attr={
            'rankdir': 'TB',
            'bgcolor': 'white',
            'fontname': 'Arial',
            'fontsize': '12'
        },
        node_attr={
            'shape': 'box',
            'style': 'rounded,filled',
            'fillcolor': 'lightblue',
            'fontname': 'Arial',
            'fontsize': '11'
        },
        edge_attr={
            'fontname': 'Arial',
            'fontsize': '9',
            'color': 'gray30'
        }
    )

    # Add title
    dot.attr(label=pipeline_data.get('name', 'Pipeline'), labelloc='t', fontsize='16')

    # Extract step names
    steps = pipeline_data.get('steps', [])
    step_names = {step['name'] for step in steps if isinstance(step, dict) and 'name' in step}

    # Add step nodes
    for step in steps:
        if not isinstance(step, dict) or 'name' not in step:
            continue

        step_name = step['name']
        step_class = step.get('class', 'Step')

        # Customize appearance based on step properties
        node_attrs = {}

        # Check if step has error handling
        if 'error_handling' in step.get('config', {}):
            node_attrs['fillcolor'] = 'lightgreen'

        # Check if step is parallel
        if step.get('parallel', False):
            node_attrs['fillcolor'] = 'lightyellow'

        dot.node(
            step_name,
            f"{step_name}\n<{step_class}>",
            **node_attrs
        )

    # Add flow edges
    flow = pipeline_data.get('flow', {})

    # Add start marker
    start_step = flow.get('start_at')
    if start_step:
        dot.node('START', 'START', shape='circle', fillcolor='lightgray')
        dot.edge('START', start_step)

    # Add transitions/paths
    if 'transitions' in flow:
        _add_transitions(dot, flow['transitions'], step_names)
    elif 'paths' in flow:
        _add_paths(dot, flow['paths'], step_names)

    # Add end markers if referenced
    end_nodes = set()
    for path in flow.get('paths', []) + flow.get('transitions', []):
        to_step = path.get('to_step') or path.get('to')
        if to_step and to_step.startswith('end_'):
            end_nodes.add(to_step)

    for end_node in end_nodes:
        dot.node(end_node, end_node.upper(), shape='circle', fillcolor='lightcoral')

    # Render to file
    output_file = Path(output_path)
    output_base = str(output_file.with_suffix(''))

    dot.render(output_base, cleanup=True)


def _add_transitions(dot, transitions: list, step_names: set) -> None:
    """Add transitions (graph-based flow) to the graph"""
    for transition in transitions:
        if not isinstance(transition, dict):
            continue

        from_step = transition.get('from')
        to_step = transition.get('to')

        if not from_step or not to_step:
            continue

        # Format edge label
        label = _format_condition_label(transition.get('condition'))

        dot.edge(from_step, to_step, label=label)


def _add_paths(dot, paths: list, step_names: set) -> None:
    """Add paths (linear flow) to the graph"""
    for path in paths:
        if not isinstance(path, dict):
            continue

        from_step = path.get('from_step')
        to_step = path.get('to_step')

        if not from_step or not to_step:
            continue

        # Format edge label
        label = _format_condition_label(path.get('condition'))

        dot.edge(from_step, to_step, label=label)


def _format_condition_label(condition: Optional[Dict[str, Any]]) -> str:
    """Format condition as edge label"""
    if not condition:
        return ''

    condition_type = condition.get('type', '')

    # Simple condition types
    if condition_type == 'always':
        return ''
    elif condition_type == 'field_equals':
        field = condition.get('field', '')
        value = condition.get('value', '')
        return f"{field} == {value}"
    elif condition_type == 'field_exists':
        field = condition.get('field', '')
        return f"exists({field})"
    elif condition_type == 'field_greater_than':
        field = condition.get('field', '')
        value = condition.get('value', '')
        return f"{field} > {value}"
    elif condition_type == 'field_less_than':
        field = condition.get('field', '')
        value = condition.get('value', '')
        return f"{field} < {value}"
    elif condition_type == 'not':
        return "NOT"
    elif condition_type == 'all':
        return "ALL"
    elif condition_type == 'any':
        return "ANY"
    elif condition_type == 'custom':
        func = condition.get('function', '')
        return f"custom: {func}"
    elif condition_type == 'plugin':
        plugin = condition.get('plugin', '')
        return f"plugin: {plugin}"

    return condition_type

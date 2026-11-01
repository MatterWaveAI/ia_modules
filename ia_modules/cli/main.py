"""
Main CLI Entry Point

Provides command-line interface for pipeline operations.
"""

import sys
import json
import codecs
import argparse
import asyncio
from pathlib import Path
from typing import Optional

from .validate import validate_pipeline, ValidationResult
from .visualize import visualize_pipeline


# What a console that cannot show a character gets instead: an ASCII stand-in for
# the symbols the CLI prints, '?' for anything else. A Windows console on cp1252,
# or output redirected to a file or pipe there, cannot encode ✓ ✗ •.
_ASCII_FALLBACKS = {
    "✓": "+", "✗": "x", "•": "-", "→": "->", "←": "<-",
    "—": "--", "–": "-", "…": "...", "⚠": "!",
}
_CONSOLE_ERRORS = "ia_modules.ascii_fallback"


def _ascii_fallback(error: UnicodeError):
    if not isinstance(error, UnicodeEncodeError):
        raise error
    text = error.object[error.start:error.end]
    return "".join(_ASCII_FALLBACKS.get(ch, "?") for ch in text), error.end


codecs.register_error(_CONSOLE_ERRORS, _ascii_fallback)


def _make_console_safe(*streams) -> None:
    """Never fail writing to a console that cannot encode a character."""
    for stream in streams:
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors=_CONSOLE_ERRORS)
        except (ValueError, OSError):  # closed, or not a reconfigurable stream
            pass


def _read_json(path: Path):
    # JSON is UTF-8 by definition; the platform default is cp1252 on Windows
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI"""
    parser = argparse.ArgumentParser(
        prog='ia-modules',
        description='Pipeline validation, visualization, and management tool'
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Validate command
    validate_parser = subparsers.add_parser(
        'validate',
        help='Validate a pipeline definition'
    )
    validate_parser.add_argument(
        'pipeline',
        type=str,
        help='Path to pipeline JSON file'
    )
    validate_parser.add_argument(
        '--strict',
        action='store_true',
        help='Treat warnings as errors'
    )
    validate_parser.add_argument(
        '--json',
        action='store_true',
        help='Output results in JSON format'
    )
    validate_parser.add_argument(
        '--working-dir',
        type=str,
        help='Working directory for relative module imports (as for run)'
    )

    # Visualize command
    visualize_parser = subparsers.add_parser(
        'visualize',
        help='Visualize a pipeline as a graph'
    )
    visualize_parser.add_argument(
        'pipeline',
        type=str,
        help='Path to pipeline JSON file'
    )
    visualize_parser.add_argument(
        '--output',
        type=str,
        help='Output file path (default: pipeline.png)'
    )
    visualize_parser.add_argument(
        '--format',
        type=str,
        choices=['png', 'svg', 'pdf', 'dot'],
        default='png',
        help='Output format (default: png)'
    )

    # Format command
    format_parser = subparsers.add_parser(
        'format',
        help='Format and prettify a pipeline JSON file'
    )
    format_parser.add_argument(
        'pipeline',
        type=str,
        help='Path to pipeline JSON file'
    )
    format_parser.add_argument(
        '--in-place',
        action='store_true',
        help='Edit file in place'
    )

    # Run command
    run_parser = subparsers.add_parser(
        'run',
        help='Execute a pipeline from JSON configuration'
    )
    run_parser.add_argument(
        'pipeline',
        type=str,
        help='Path to pipeline JSON file'
    )
    run_parser.add_argument(
        '--input',
        type=str,
        help='Path to JSON file with input data'
    )
    run_parser.add_argument(
        '--working-dir',
        type=str,
        help='Working directory for relative module imports'
    )
    run_parser.add_argument(
        '--output',
        type=str,
        help='Path to save output JSON (default: print to stdout)'
    )

    return parser


def cmd_validate(args) -> int:
    """Execute validate command"""
    pipeline_path = Path(args.pipeline)

    if not pipeline_path.exists():
        print(f"Error: Pipeline file not found: {pipeline_path}", file=sys.stderr)
        return 1

    try:
        pipeline_data = _read_json(pipeline_path)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {pipeline_path}: {e}", file=sys.stderr)
        return 1

    # Step modules are imported to check them, so they need the same path as run
    if args.working_dir and args.working_dir not in sys.path:
        sys.path.insert(0, args.working_dir)

    # Run validation
    result = validate_pipeline(pipeline_data, strict=args.strict)

    # Output results
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print_validation_result(result)

    return 0 if result.is_valid else 1


def cmd_visualize(args) -> int:
    """Execute visualize command"""
    pipeline_path = Path(args.pipeline)

    if not pipeline_path.exists():
        print(f"Error: Pipeline file not found: {pipeline_path}", file=sys.stderr)
        return 1

    try:
        pipeline_data = _read_json(pipeline_path)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {pipeline_path}: {e}", file=sys.stderr)
        return 1

    # Determine output path
    output_path = args.output or f"pipeline.{args.format}"

    # Generate visualization
    try:
        visualize_pipeline(
            pipeline_data,
            output_path=output_path,
            format=args.format
        )
        print(f"Pipeline visualization saved to: {output_path}")
        return 0
    except Exception as e:
        print(f"Error generating visualization: {e}", file=sys.stderr)
        return 1


def cmd_format(args) -> int:
    """Execute format command"""
    pipeline_path = Path(args.pipeline)

    if not pipeline_path.exists():
        print(f"Error: Pipeline file not found: {pipeline_path}", file=sys.stderr)
        return 1

    try:
        pipeline_data = _read_json(pipeline_path)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {pipeline_path}: {e}", file=sys.stderr)
        return 1

    # Format JSON, keeping non-ASCII text as written rather than as \u escapes
    formatted = json.dumps(pipeline_data, indent=2, sort_keys=False, ensure_ascii=False)

    if args.in_place:
        with open(pipeline_path, 'w', encoding='utf-8') as f:
            f.write(formatted)
        print(f"Formatted {pipeline_path}")
    else:
        print(formatted)

    return 0


def cmd_run(args) -> int:
    """Execute run command"""
    from ia_modules.pipeline.graph_pipeline_runner import GraphPipelineRunner
    from ia_modules.pipeline.services import ServiceRegistry
    from ia_modules.pipeline.core import ExecutionContext

    pipeline_path = Path(args.pipeline)

    if not pipeline_path.exists():
        print(f"Error: Pipeline file not found: {pipeline_path}", file=sys.stderr)
        return 1

    # Load input data if provided
    input_data = {}
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file not found: {input_path}", file=sys.stderr)
            return 1
        try:
            input_data = _read_json(input_path)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {input_path}: {e}", file=sys.stderr)
            return 1

    # Load pipeline config
    try:
        pipeline_config = _read_json(pipeline_path)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {pipeline_path}: {e}", file=sys.stderr)
        return 1

    # Create services registry
    services = ServiceRegistry()

    # Add working directory to sys.path for step imports
    if args.working_dir:
        if args.working_dir not in sys.path:
            sys.path.insert(0, args.working_dir)

    # Create execution context
    execution_context = ExecutionContext(
        execution_id='cli-run',
        pipeline_id=pipeline_path.stem,
        user_id='cli-user'
    )

    # Run pipeline via GraphPipelineRunner
    try:
        runner = GraphPipelineRunner(services=services)
        result = asyncio.run(runner.run_pipeline_from_json(
            pipeline_config,
            input_data,
            execution_context=execution_context
        ))

        # Output result
        output_json = json.dumps(result, indent=2, default=str)

        if args.output:
            output_path = Path(args.output)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(output_json)
            print(f"Pipeline result saved to: {output_path}")
        else:
            print(output_json)

        return 0
    except Exception as e:
        print(f"Error executing pipeline: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def print_validation_result(result: ValidationResult) -> None:
    """Print validation result in human-readable format"""
    # Print header
    if result.is_valid:
        print("✓ Pipeline validation PASSED")
    else:
        print("✗ Pipeline validation FAILED")

    print()

    # Print errors
    if result.errors:
        print(f"Errors ({len(result.errors)}):")
        for error in result.errors:
            print(f"  • {error}")
        print()

    # Print warnings
    if result.warnings:
        print(f"Warnings ({len(result.warnings)}):")
        for warning in result.warnings:
            print(f"  • {warning}")
        print()

    # Print info
    if result.info:
        print(f"Info ({len(result.info)}):")
        for info in result.info:
            print(f"  • {info}")
        print()


def cli(argv: Optional[list] = None) -> int:
    """Main CLI entry point"""
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch to command handler
    if args.command == 'validate':
        return cmd_validate(args)
    elif args.command == 'visualize':
        return cmd_visualize(args)
    elif args.command == 'format':
        return cmd_format(args)
    elif args.command == 'run':
        return cmd_run(args)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1


def main():
    """Entry point for console script"""
    _make_console_safe(sys.stdout, sys.stderr)
    sys.exit(cli())


if __name__ == '__main__':
    main()

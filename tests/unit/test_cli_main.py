"""
Tests for CLI Main Entry Point

Tests command-line interface including:
- Command parsing
- Validate command
- Format command
- Visualize command (basic)
"""

import pytest
import json
import tempfile
from pathlib import Path
from ia_modules.cli.main import cli, create_parser


class TestArgumentParsing:
    """Test command-line argument parsing"""

    def test_parser_creation(self):
        """Test parser is created successfully"""
        parser = create_parser()
        assert parser is not None
        assert parser.prog == 'ia-modules'

    def test_no_command_shows_help(self, capsys):
        """Test that no command returns error"""
        result = cli([])
        assert result == 1

    def test_validate_command_requires_pipeline(self):
        """Test validate command requires pipeline argument"""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(['validate'])

    def test_validate_command_parsing(self):
        """Test validate command argument parsing"""
        parser = create_parser()
        args = parser.parse_args(['validate', 'pipeline.json'])
        assert args.command == 'validate'
        assert args.pipeline == 'pipeline.json'
        assert args.strict is False
        assert args.json is False

    def test_validate_command_with_strict(self):
        """Test validate command with strict flag"""
        parser = create_parser()
        args = parser.parse_args(['validate', 'pipeline.json', '--strict'])
        assert args.strict is True

    def test_validate_command_with_json_output(self):
        """Test validate command with JSON output flag"""
        parser = create_parser()
        args = parser.parse_args(['validate', 'pipeline.json', '--json'])
        assert args.json is True

    def test_format_command_parsing(self):
        """Test format command argument parsing"""
        parser = create_parser()
        args = parser.parse_args(['format', 'pipeline.json'])
        assert args.command == 'format'
        assert args.pipeline == 'pipeline.json'
        assert args.in_place is False

    def test_format_command_with_in_place(self):
        """Test format command with in-place flag"""
        parser = create_parser()
        args = parser.parse_args(['format', 'pipeline.json', '--in-place'])
        assert args.in_place is True

    def test_visualize_command_parsing(self):
        """Test visualize command argument parsing"""
        parser = create_parser()
        args = parser.parse_args(['visualize', 'pipeline.json'])
        assert args.command == 'visualize'
        assert args.pipeline == 'pipeline.json'
        assert args.format == 'png'
        assert args.output is None

    def test_visualize_command_with_output(self):
        """Test visualize command with output file"""
        parser = create_parser()
        args = parser.parse_args(['visualize', 'pipeline.json', '--output', 'diagram.svg'])
        assert args.output == 'diagram.svg'

    def test_visualize_command_with_format(self):
        """Test visualize command with format option"""
        parser = create_parser()
        args = parser.parse_args(['visualize', 'pipeline.json', '--format', 'svg'])
        assert args.format == 'svg'


class TestValidateCommand:
    """Test validate command execution"""

    def test_validate_nonexistent_file(self, capsys):
        """Test error when pipeline file doesn't exist"""
        result = cli(['validate', 'nonexistent.json'])
        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err.lower()

    def test_validate_invalid_json(self, capsys):
        """Test error when file contains invalid JSON"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json {")
            temp_file = f.name

        try:
            result = cli(['validate', temp_file])
            assert result == 1
            captured = capsys.readouterr()
            assert "invalid json" in captured.err.lower()
        finally:
            Path(temp_file).unlink()

    def test_validate_valid_pipeline(self, capsys):
        """Test validation of valid pipeline"""
        pipeline = {
            "name": "test_pipeline",
            "steps": [
                {
                    "name": "step1",
                    "module": "ia_modules.pipeline.core",
                    "class": "Step"
                }
            ],
            "flow": {
                "start_at": "step1"
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(pipeline, f)
            temp_file = f.name

        try:
            result = cli(['validate', temp_file])
            assert result == 0
            captured = capsys.readouterr()
            assert "PASSED" in captured.out
        finally:
            Path(temp_file).unlink()

    def test_validate_invalid_pipeline(self, capsys):
        """Test validation of invalid pipeline"""
        pipeline = {
            "name": "test_pipeline",
            "steps": [],
            "flow": {}
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(pipeline, f)
            temp_file = f.name

        try:
            result = cli(['validate', temp_file])
            assert result == 1
            captured = capsys.readouterr()
            assert "FAILED" in captured.out
        finally:
            Path(temp_file).unlink()

    def test_validate_json_output(self, capsys):
        """Test validation with JSON output format"""
        pipeline = {
            "name": "test_pipeline",
            "steps": [
                {
                    "name": "step1",
                    "module": "ia_modules.pipeline.core",
                    "class": "Step"
                }
            ],
            "flow": {
                "start_at": "step1"
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(pipeline, f)
            temp_file = f.name

        try:
            cli(['validate', temp_file, '--json'])
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert 'is_valid' in output
            assert 'errors' in output
            assert 'warnings' in output
        finally:
            Path(temp_file).unlink()

    def test_validate_strict_mode(self, capsys):
        """Test validation in strict mode"""
        pipeline = {
            "name": "test_pipeline",
            "steps": [],  # Empty steps will trigger warning
            "flow": {}
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(pipeline, f)
            temp_file = f.name

        try:
            result = cli(['validate', temp_file, '--strict'])
            assert result == 1
            captured = capsys.readouterr()
            assert "[STRICT]" in captured.out
        finally:
            Path(temp_file).unlink()


class TestFormatCommand:
    """Test format command execution"""

    def test_format_nonexistent_file(self, capsys):
        """Test error when pipeline file doesn't exist"""
        result = cli(['format', 'nonexistent.json'])
        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err.lower()

    def test_format_invalid_json(self, capsys):
        """Test error when file contains invalid JSON"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json {")
            temp_file = f.name

        try:
            result = cli(['format', temp_file])
            assert result == 1
            captured = capsys.readouterr()
            assert "invalid json" in captured.err.lower()
        finally:
            Path(temp_file).unlink()

    def test_format_to_stdout(self, capsys):
        """Test formatting output to stdout"""
        pipeline = {"name": "test", "steps": [], "flow": {}}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(pipeline, f)
            temp_file = f.name

        try:
            result = cli(['format', temp_file])
            assert result == 0
            captured = capsys.readouterr()
            # Should output formatted JSON
            output = json.loads(captured.out)
            assert output['name'] == 'test'
        finally:
            Path(temp_file).unlink()

    def test_format_in_place(self, capsys):
        """Test formatting file in place"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            # Write unformatted JSON
            f.write('{"name":"test","steps":[],"flow":{}}')
            temp_file = f.name

        try:
            result = cli(['format', temp_file, '--in-place'])
            assert result == 0

            # Read back and verify formatting
            with open(temp_file, 'r') as f:
                content = f.read()
                # Should have proper indentation now
                assert '\n' in content
                assert '  ' in content
        finally:
            Path(temp_file).unlink()


class TestVisualizeCommand:
    """Test visualize command execution (basic tests without graphviz)"""

    def test_visualize_nonexistent_file(self, capsys):
        """Test error when pipeline file doesn't exist"""
        result = cli(['visualize', 'nonexistent.json'])
        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err.lower()

    def test_visualize_invalid_json(self, capsys):
        """Test error when file contains invalid JSON"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json {")
            temp_file = f.name

        try:
            result = cli(['visualize', temp_file])
            assert result == 1
            captured = capsys.readouterr()
            assert "invalid json" in captured.err.lower()
        finally:
            Path(temp_file).unlink()

    def test_visualize_without_graphviz(self, capsys):
        """Test error when graphviz is not installed"""
        pipeline = {
            "name": "test_pipeline",
            "steps": [{"name": "step1", "module": "test", "class": "Step"}],
            "flow": {"start_at": "step1"}
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(pipeline, f)
            temp_file = f.name

        try:
            # This will fail if graphviz is not installed
            result = cli(['visualize', temp_file])
            # Either succeeds (if graphviz is installed) or fails with import error
            if result == 1:
                captured = capsys.readouterr()
                # Could be either import error or other visualization error
                assert len(captured.err) > 0
        finally:
            Path(temp_file).unlink()


class TestUnknownCommand:
    """Test handling of unknown commands"""

    def test_unknown_command(self, capsys):
        """Test error for unknown command"""
        # argparse will exit with status 2 for invalid choice
        with pytest.raises(SystemExit) as exc_info:
            cli(['unknown-command'])
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "invalid choice" in captured.err.lower()

"""
The CLI must not crash on a console that cannot encode its symbols (a Windows
console on cp1252, or output redirected to a file or pipe there), and must read
and write pipeline JSON as UTF-8 whatever the platform's default encoding is.

Each test runs the real entry point in a subprocess with the console encoding
forced, so the behaviour is the same on every OS.
"""
import json
import os
import subprocess
import sys

import ia_modules.cli.main  # noqa: F401  (registers the console error handler)

ENTRY = "from ia_modules.cli.main import main; main()"
# Turn any open() without an explicit encoding in the CLI module into an error,
# so a platform-default read is caught on Linux CI as well as on Windows.
STRICT_ENCODING = ("-X", "warn_default_encoding", "-W", "error::EncodingWarning:ia_modules.cli.main")


def _write_pipeline(tmp_path, valid=True, description="An example"):
    pipeline = {
        "name": "p",
        "description": description,
        "steps": [{"id": "a", "name": "A", "module": "ia_modules.pipeline.core", "step_class": "Step"}],
        "flow": {"start_at": "a" if valid else "missing", "paths": [{"from": "a", "to": "end_with_success"}]},
    }
    path = tmp_path / "pipeline.json"
    path.write_text(json.dumps(pipeline, ensure_ascii=False), encoding="utf-8")
    return path


def _cli(args, console_encoding, python_flags=()):
    env = {**os.environ, "PYTHONIOENCODING": console_encoding}
    env.pop("PYTHONUTF8", None)
    return subprocess.run(
        [sys.executable, *python_flags, "-c", ENTRY, *args],
        capture_output=True, env=env, timeout=120,
    )


def test_validate_on_a_console_that_cannot_show_its_symbols(tmp_path):
    result = _cli(["validate", str(_write_pipeline(tmp_path))], "cp1252")

    assert b"Traceback" not in result.stderr, result.stderr.decode("cp1252", "replace")
    assert result.returncode == 0
    out = result.stdout.decode("cp1252")
    assert "+ Pipeline validation PASSED" in out  # cp1252 has no ✓
    assert "  • Step" in out  # but it does have •, so the bullets stay


def test_failures_fall_back_too(tmp_path):
    result = _cli(["validate", str(_write_pipeline(tmp_path, valid=False))], "cp1252")

    assert b"Traceback" not in result.stderr
    assert result.returncode == 1
    out = result.stdout.decode("cp1252")
    assert "x Pipeline validation FAILED" in out
    assert "  • Start step 'missing' is not defined in steps" in out


def test_a_console_that_can_show_them_keeps_them(tmp_path):
    result = _cli(["validate", str(_write_pipeline(tmp_path))], "utf-8")

    assert result.returncode == 0
    out = result.stdout.decode("utf-8")
    assert "✓ Pipeline validation PASSED" in out
    assert "  • Step" in out


def test_pipeline_json_is_read_as_utf8(tmp_path):
    # ← is E2 86 90 in UTF-8, and 0x90 is undefined in cp1252
    path = _write_pipeline(tmp_path, description="Arrows ← and dashes —")

    result = _cli(["validate", str(path)], "utf-8", STRICT_ENCODING)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")

    result = _cli(["format", str(path)], "cp1252", STRICT_ENCODING)
    assert result.returncode == 0, result.stderr.decode("cp1252", "replace")
    # cp1252 has — but not ←
    assert '"description": "Arrows <- and dashes —"' in result.stdout.decode("cp1252")


def test_run_reads_input_and_writes_output_as_utf8(tmp_path):
    pipeline = {
        "name": "p",
        "steps": [{"id": "a", "name": "A", "module": "tests.pipelines.simple_pipeline.steps.step1", "step_class": "Step1"}],
        "flow": {"start_at": "a", "paths": [{"from": "a", "to": "end_with_success"}]},
    }
    (tmp_path / "pipeline.json").write_text(json.dumps(pipeline), encoding="utf-8")
    (tmp_path / "input.json").write_text(json.dumps({"topic": "café ←"}, ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "out.json"
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    result = _cli(
        ["run", str(tmp_path / "pipeline.json"), "--input", str(tmp_path / "input.json"),
         "--output", str(output), "--working-dir", repo_root],
        "cp1252", STRICT_ENCODING,
    )

    assert result.returncode == 0, result.stderr.decode("cp1252", "replace")
    assert json.loads(output.read_text(encoding="utf-8"))["output"]["topic"] == "PROCESSED_CAFÉ ←"


def test_format_in_place_keeps_text_as_written(tmp_path):
    path = _write_pipeline(tmp_path, description="Arrows ← and dashes —")

    result = _cli(["format", "--in-place", str(path)], "cp1252", STRICT_ENCODING)

    assert result.returncode == 0, result.stderr.decode("cp1252", "replace")
    text = path.read_text(encoding="utf-8")
    assert "Arrows ← and dashes —" in text
    assert "\\u2190" not in text


def test_the_error_handler_maps_symbols_and_replaces_the_rest():
    text = "✓ ok • done → next — ☃"
    # Only characters the encoding lacks are replaced
    assert text.encode("ascii", "ia_modules.ascii_fallback") == b"+ ok - done -> next -- ?"
    assert text.encode("cp1252", "ia_modules.ascii_fallback") == "+ ok • done -> next — ?".encode("cp1252")

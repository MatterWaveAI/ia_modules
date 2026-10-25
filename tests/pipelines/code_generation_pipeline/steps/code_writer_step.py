"""Code writer step - saves generated code to files."""
from typing import Dict, Any
from pathlib import Path
from ia_modules.pipeline.core import Step


class CodeWriterStep(Step):
    """Write generated code to files."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.output_dir = config.get("output_dir", "generated_code")

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Write code to file."""
        code = data.get("generated_code", "")
        filename = data.get("filename", "generated.py")

        if not code:
            self.logger.warning("No code to write")
            return data

        # Get output directory relative to pipeline
        pipeline_dir = Path(__file__).parent.parent
        output_path = pipeline_dir / self.output_dir
        output_path.mkdir(parents=True, exist_ok=True)

        # Write code file
        file_path = output_path / filename
        file_path.write_text(code, encoding="utf-8")

        self.logger.info(f"Wrote code to: {file_path}")

        data["output_file"] = str(file_path)
        data["code_size"] = len(code)

        return data

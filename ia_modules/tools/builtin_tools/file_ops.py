"""
File operations tool for reading and writing files.

Provides safe file operations with access controls and validation.
"""

import asyncio
import logging
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class FileOperationsTool:
    """
    File operations tool for safe file access.

    Features:
    - Read/write files
    - JSON handling
    - Directory operations
    - Path validation
    - Access controls
    - Error handling

    Security Note: This tool should be used with caution and proper
    access controls. Consider implementing additional security measures
    for production use.

    Example:
        >>> tool = FileOperationsTool(base_path="/safe/directory")
        >>> await tool.write_file("output.txt", "Hello, World!")
        >>> content = await tool.read_file("output.txt")
        >>> print(content)  # "Hello, World!"
    """

    def __init__(
        self,
        base_path: Optional[str] = None,
        allowed_extensions: Optional[List[str]] = None,
        max_file_size_mb: float = 10.0
    ):
        """
        Initialize file operations tool.

        Args:
            base_path: Base directory for file operations (None = current dir)
            allowed_extensions: List of allowed file extensions (None = all)
            max_file_size_mb: Maximum file size in MB
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.allowed_extensions = allowed_extensions or [
            ".txt", ".json", ".csv", ".md", ".yaml", ".yml"
        ]
        self.max_file_size_bytes = int(max_file_size_mb * 1024 * 1024)
        self.logger = logging.getLogger("FileOperationsTool")

    def _validate_path(self, file_path: str) -> Path:
        """
        Validate and resolve file path.

        Args:
            file_path: File path to validate

        Returns:
            Resolved Path object

        Raises:
            ValueError: If path is invalid or outside base path
        """
        # Resolve path relative to base path
        full_path = (self.base_path / file_path).resolve()

        # Check if path is within base path
        try:
            full_path.relative_to(self.base_path.resolve())
        except ValueError:
            raise ValueError(f"Path outside base directory: {file_path}")

        # Check extension if restrictions apply
        if self.allowed_extensions and full_path.suffix not in self.allowed_extensions:
            raise ValueError(
                f"File extension {full_path.suffix} not allowed. "
                f"Allowed: {', '.join(self.allowed_extensions)}"
            )

        return full_path

    async def read_file(self, file_path: str, encoding: str = "utf-8") -> str:
        """
        Read file contents.

        Args:
            file_path: Path to file
            encoding: Text encoding

        Returns:
            File contents as string
        """
        full_path = self._validate_path(file_path)

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not full_path.is_file():
            raise ValueError(f"Not a file: {file_path}")

        # Check file size
        if full_path.stat().st_size > self.max_file_size_bytes:
            raise ValueError(
                f"File too large: {full_path.stat().st_size / 1024 / 1024:.2f}MB "
                f"(max: {self.max_file_size_bytes / 1024 / 1024:.2f}MB)"
            )

        # Read file
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(
            None,
            lambda: full_path.read_text(encoding=encoding)
        )

        self.logger.info(f"Read file: {file_path}")
        return content

    async def write_file(
        self,
        file_path: str,
        content: str,
        encoding: str = "utf-8",
        create_dirs: bool = True
    ) -> Dict[str, Any]:
        """
        Write content to file.

        Args:
            file_path: Path to file
            content: Content to write
            encoding: Text encoding
            create_dirs: Whether to create parent directories

        Returns:
            Dictionary with write result
        """
        full_path = self._validate_path(file_path)

        # Create parent directories if needed
        if create_dirs and not full_path.parent.exists():
            full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: full_path.write_text(content, encoding=encoding)
        )

        self.logger.info(f"Wrote file: {file_path}")

        return {
            "path": file_path,
            "size": len(content),
            "success": True
        }

    async def read_json(self, file_path: str) -> Any:
        """
        Read and parse JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            Parsed JSON data
        """
        content = await self.read_file(file_path)
        return json.loads(content)

    async def write_json(
        self,
        file_path: str,
        data: Any,
        indent: int = 2,
        create_dirs: bool = True
    ) -> Dict[str, Any]:
        """
        Write data to JSON file.

        Args:
            file_path: Path to JSON file
            data: Data to write
            indent: JSON indentation
            create_dirs: Whether to create parent directories

        Returns:
            Dictionary with write result
        """
        content = json.dumps(data, indent=indent)
        return await self.write_file(file_path, content, create_dirs=create_dirs)

    async def list_files(
        self,
        directory: str = ".",
        pattern: str = "*",
        recursive: bool = False
    ) -> List[str]:
        """
        List files in directory.

        Args:
            directory: Directory to list
            pattern: Glob pattern (e.g., "*.txt")
            recursive: Whether to search recursively

        Returns:
            List of file paths
        """
        dir_path = self._validate_path(directory)

        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        if not dir_path.is_dir():
            raise ValueError(f"Not a directory: {directory}")

        # List files
        if recursive:
            files = dir_path.rglob(pattern)
        else:
            files = dir_path.glob(pattern)

        # Filter to only files and make relative to base path
        result = []
        for file_path in files:
            if file_path.is_file():
                try:
                    rel_path = file_path.relative_to(self.base_path)
                    result.append(str(rel_path))
                except ValueError:
                    pass  # Skip files outside base path

        return sorted(result)

    async def delete_file(self, file_path: str) -> Dict[str, Any]:
        """
        Delete a file.

        Args:
            file_path: Path to file

        Returns:
            Dictionary with delete result
        """
        full_path = self._validate_path(file_path)

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not full_path.is_file():
            raise ValueError(f"Not a file: {file_path}")

        # Delete file
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, full_path.unlink)

        self.logger.info(f"Deleted file: {file_path}")

        return {
            "path": file_path,
            "success": True
        }


async def file_ops_function(
    operation: str,
    file_path: str,
    content: Optional[str] = None,
    data: Optional[Any] = None,
    pattern: Optional[str] = None,
    recursive: bool = False
) -> Dict[str, Any]:
    """
    File operations function for tool execution.

    Args:
        operation: Operation to perform (read, write, read_json, write_json, list, delete)
        file_path: Path to file/directory
        content: Content to write (for write operation)
        data: Data to write (for write_json operation)
        pattern: Glob pattern (for list operation)
        recursive: Recursive search (for list operation)

    Returns:
        Dictionary with operation results
    """
    tool = FileOperationsTool()

    if operation == "read":
        content = await tool.read_file(file_path)
        return {"content": content, "path": file_path}

    elif operation == "write":
        if content is None:
            raise ValueError("'content' required for write operation")
        result = await tool.write_file(file_path, content)
        return result

    elif operation == "read_json":
        data = await tool.read_json(file_path)
        return {"data": data, "path": file_path}

    elif operation == "write_json":
        if data is None:
            raise ValueError("'data' required for write_json operation")
        result = await tool.write_json(file_path, data)
        return result

    elif operation == "list":
        files = await tool.list_files(
            file_path,
            pattern=pattern or "*",
            recursive=recursive
        )
        return {"files": files, "count": len(files)}

    elif operation == "delete":
        result = await tool.delete_file(file_path)
        return result

    else:
        raise ValueError(f"Unknown operation: {operation}")


def create_file_ops_tool():
    """
    Create a file operations tool definition.

    Returns:
        ToolDefinition for file operations
    """
    from ..core import ToolDefinition

    return ToolDefinition(
        name="file_operations",
        description="Perform file operations (read, write, list, delete)",
        parameters={
            "operation": {
                "type": "string",
                "required": True,
                "description": "Operation: read, write, read_json, write_json, list, delete"
            },
            "file_path": {
                "type": "string",
                "required": True,
                "description": "Path to file or directory"
            },
            "content": {
                "type": "string",
                "required": False,
                "description": "Content to write (for write operation)"
            },
            "data": {
                "type": "object",
                "required": False,
                "description": "Data to write (for write_json operation)"
            },
            "pattern": {
                "type": "string",
                "required": False,
                "description": "Glob pattern for list operation (default: *)"
            },
            "recursive": {
                "type": "boolean",
                "required": False,
                "description": "Recursive search for list operation (default: false)"
            }
        },
        function=file_ops_function,
        requires_approval=True,  # Requires approval for safety
        metadata={
            "category": "file",
            "tags": ["file", "io", "storage"],
            "security_level": "high"
        }
    )

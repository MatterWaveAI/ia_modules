"""Document loader step for RAG pipeline."""
from typing import Dict, Any
from pathlib import Path
from ia_modules.pipeline.core import Step

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


class DocumentLoaderStep(Step):
    """Load documents from filesystem."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.docs_dir = config.get("docs_dir", "sample_docs")
        self.file_types = config.get("file_types", [".txt", ".md", ".json", ".pdf"])

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Load all documents from directory."""
        # Get absolute path relative to pipeline directory
        pipeline_dir = Path(__file__).parent.parent
        docs_path = pipeline_dir / self.docs_dir

        if not docs_path.exists():
            raise FileNotFoundError(f"Documents directory not found: {docs_path}")

        documents = []

        # Load all files
        for file_path in docs_path.glob("*"):
            if file_path.suffix in self.file_types:
                self.logger.info(f"Loading document: {file_path.name}")

                # Handle PDF files
                if file_path.suffix == ".pdf":
                    if not PDF_AVAILABLE:
                        self.logger.warning(f"Skipping PDF {file_path.name} - PyPDF2 not installed")
                        continue

                    content = self._extract_pdf_text(file_path)
                else:
                    content = file_path.read_text(encoding="utf-8")

                documents.append({
                    "filename": file_path.name,
                    "path": str(file_path),
                    "type": file_path.suffix,
                    "content": content,
                    "size": len(content)
                })

        self.logger.info(f"Loaded {len(documents)} documents")

        data["documents"] = documents
        data["num_documents"] = len(documents)

        return data

    def _extract_pdf_text(self, pdf_path: Path) -> str:
        """Extract text from PDF file."""
        text_parts = []

        with open(pdf_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            num_pages = len(pdf_reader.pages)

            self.logger.info(f"Extracting text from {num_pages} pages")

            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                if text.strip():
                    text_parts.append(text)

        return "\n\n".join(text_parts)

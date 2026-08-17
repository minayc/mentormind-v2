import pathlib
from pypdf import PdfReader
from backend.core.schemas import Chunk
from backend.exceptions import DocumentNotFoundError


class DocumentProcessor:
    SUPPORTED_EXTENSIONS = {".txt", ".pdf"}

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def read(self, file_path: str) -> str:
        path = pathlib.Path(file_path)

        if not path.exists():
            raise DocumentNotFoundError(f"File not found: {file_path}")

        if path.suffix not in self.SUPPORTED_EXTENSIONS:
            raise DocumentNotFoundError(
                f"Unsupported file type: '{path.suffix}'. "
                f"Supported types: {', '.join(self.SUPPORTED_EXTENSIONS)}"
            )

        if path.suffix == ".txt":
            return path.read_text(encoding="utf-8")
        elif path.suffix == ".pdf":
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)

    def chunk(self, text: str, source: str) -> list[Chunk]:
        chunks = []
        start = 0
        while start < len(text):
            chunk_text = text[start: start + self.chunk_size]
            chunks.append(Chunk(
                id=f"{source}_{len(chunks)}",
                text=chunk_text,
                source=source
            ))
            start += self.chunk_size - self.overlap
        return chunks

    def process(self, file_path: str) -> list[Chunk]:
        text = self.read(file_path)
        return self.chunk(text, pathlib.Path(file_path).stem)
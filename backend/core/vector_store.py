import chromadb
import ollama
from backend.core.schemas import Chunk
from backend.exceptions import EmbeddingError


class VectorStore:

    def __init__(self, path: str = "./chroma_db", collection_name: str = "mentormind"):
        self.path = path
        self.collection_name = collection_name
        self.client = chromadb.PersistentClient(path=self.path)
        self.collection = self.client.get_or_create_collection(self.collection_name)

    def _embed(self, text: str) -> list[float]:
        response = ollama.embeddings(model="nomic-embed-text", prompt=text)
        if "embedding" not in response:
            raise EmbeddingError("Nothing has returned.")
        return response["embedding"]

    def store(self, chunks: list[Chunk]) -> None:
        ids = []
        embeddings = []
        documents = []
        metadata = []
        for chunk in chunks:
            ids.append(chunk.id)
            embeddings.append(self._embed(chunk.text))
            documents.append(chunk.text)
            metadata.append({"source": chunk.source})
        self.collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadata)

    def search(self, query: str, n_results: int = 3, sources: list[str] = None) -> list[Chunk]:
        embedding = self._embed(query)
        where = {"source": {"$in": sources}} if sources else None
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where
        )
        docs = results.get("documents", [[]])[0] or []
        metas = results.get("metadatas", [[]])[0] or []
        chunks = []
        for i, (text, meta) in enumerate(zip(docs, metas)):
            chunks.append(Chunk(id=f"result_{i}", text=text, source=meta["source"]))
        return chunks

    def list_sources(self) -> list[str]:
        results = self.collection.get(include=["metadatas"])
        sources = {meta["source"] for meta in results["metadatas"]}
        return sorted(list(sources))

    def clear(self):
        ids = self.collection.get()["ids"]
        if ids:
            self.collection.delete(ids=ids)
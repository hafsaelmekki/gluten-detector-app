from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from langchain_community.document_loaders import TextLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class RAGSettings:
    file_path: str = "regles_gluten.txt"
    chunk_size: int = 300
    chunk_overlap: int = 50
    model_name: str = "all-MiniLM-L6-v2"


class GlutenRAG:
    """Minimal RAG pipeline to ground gluten rules."""

    def __init__(self, settings: Optional[RAGSettings] = None) -> None:
        self.settings = settings or RAGSettings()
        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.settings.model_name
        )
        self.vector_store = self._build_index()

    def _build_index(self) -> FAISS:
        """Load, split, and index the rules file."""
        path = Path(self.settings.file_path)
        if not path.exists():
            print(
                f"[WARN] Rules file {path} missing. RAG will return fallback text."
            )
            return FAISS.from_texts(
                ["Aucune regle medicale disponible."], self.embeddings
            )

        loader = TextLoader(str(path), encoding="utf-8")
        docs = loader.load()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )
        chunks = splitter.split_documents(docs)
        return FAISS.from_documents(chunks, self.embeddings)

    def search_rules(self, ingredients_text: str, k: int = 2) -> str:
        """Return the top-k rules that match the ingredient string."""
        results = self.vector_store.similarity_search(ingredients_text, k=k)
        if not results:
            return "Aucune regle medicale specifique trouvee."
        return "\n".join(doc.page_content for doc in results)

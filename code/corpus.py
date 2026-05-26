import re
from pathlib import Path
from typing import List, Tuple
from rank_bm25 import BM25Okapi
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

HEADERS_TO_SPLIT = [("#", "h1"), ("##", "h2"), ("###", "h3")]
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64
RRF_K = 60
DOMAIN_BOOST = 1.2

def _tokenize(text: str) -> List[str]:
    return re.findall(r'\w+', text.lower())

class Corpus:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.repo_root = self.data_dir.parent
        self._build()

    def _chunk_file(self, md_file: Path) -> List[Tuple[str, str]]:
        text = md_file.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            return []
        rel_path = str(md_file.relative_to(self.repo_root))
        header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=HEADERS_TO_SPLIT, strip_headers=False
        )
        char_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        )
        chunks = []
        for doc in header_splitter.split_text(text):
            for sub in char_splitter.split_text(doc.page_content):
                if sub.strip():
                    chunks.append((rel_path, sub.strip()))
        return chunks

    def _build(self):
        all_chunks: List[Tuple[str, str]] = []
        for md_file in sorted(self.data_dir.rglob("*.md")):
            all_chunks.extend(self._chunk_file(md_file))
        self.paths = [c[0] for c in all_chunks]
        self.texts = [c[1] for c in all_chunks]
        self.bm25 = BM25Okapi([_tokenize(t) for t in self.texts])

    @property
    def num_chunks(self) -> int:
        return len(self.paths)

    def _bm25_top(self, query: str, k: int) -> List[int]:
        scores = self.bm25.get_scores(_tokenize(query))
        return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

    def search_multi(
        self,
        queries: List[str],
        k: int = 5,
        domain_boost: str = "unknown",
    ) -> List[Tuple[str, str, float]]:
        rrf_scores: dict = {}
        pool = k * 5

        for query in queries:
            ranked = self._bm25_top(query, pool)
            for rank, idx in enumerate(ranked):
                rrf = 1.0 / (RRF_K + rank + 1)
                if domain_boost != "unknown" and domain_boost in self.paths[idx]:
                    rrf *= DOMAIN_BOOST
                rrf_scores[idx] = rrf_scores.get(idx, 0.0) + rrf

        top_indices = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:k]
        if not top_indices:
            return []

        max_score = rrf_scores[top_indices[0]]
        return [
            (
                self.paths[idx],
                self.texts[idx],
                rrf_scores[idx] / max_score if max_score > 0 else 0.0,
            )
            for idx in top_indices
        ]

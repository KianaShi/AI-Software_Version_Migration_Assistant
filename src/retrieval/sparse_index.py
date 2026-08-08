import math
import re
from collections import Counter
from dataclasses import dataclass, field

from src.retrieval.models import Chunk, RetrievedChunk

"""
Sparse retrieval baseline: a hand-rolled Okapi BM25 index, no new
dependency (this repo builds its RAG pipeline from scratch rather than
pulling in high-level frameworks, per the README).

The tokenizer is symbol-aware: a dotted/scoped identifier like
`FooClient.create` is kept as one token *and* split into its parts
(`fooclient`, `create`), so a query for the bare method name still
matches. This is the main reason to have a sparse baseline at all --
package/class/parameter names are exactly what dense embeddings tend to
blur together and exact/sub-token matching handles precisely.
"""

_TOKEN_RE = re.compile(r"[A-Za-z_]\w*(?:[.:#]{1,2}[A-Za-z_]\w*)*|\d+(?:\.\d+)*")

K1 = 1.5
B = 0.75


def tokenize(text: str) -> list[str]:
    tokens = []
    for match in _TOKEN_RE.finditer(text):
        raw = match.group(0)
        tokens.append(raw.lower())
        if re.search(r"[.:#]", raw):
            tokens.extend(part.lower() for part in re.split(r"[.:#]+", raw) if part)
    return tokens


@dataclass
class BM25Index:
    chunk_ids: list[str] = field(default_factory=list)
    term_freqs: list[Counter] = field(default_factory=list)
    doc_lengths: list[int] = field(default_factory=list)
    doc_freq: Counter = field(default_factory=Counter)
    avg_doc_length: float = 0.0

    @property
    def n_docs(self) -> int:
        return len(self.chunk_ids)

    def _idf(self, term: str) -> float:
        n_containing = self.doc_freq.get(term, 0)
        return math.log(1 + (self.n_docs - n_containing + 0.5) / (n_containing + 0.5))

    def score(self, chunk_index: int, query_terms: list[str]) -> float:
        freqs = self.term_freqs[chunk_index]
        doc_length = self.doc_lengths[chunk_index]
        total = 0.0
        for term in query_terms:
            f = freqs.get(term, 0)
            if f == 0:
                continue
            idf = self._idf(term)
            denom = f + K1 * (1 - B + B * doc_length / (self.avg_doc_length or 1))
            total += idf * (f * (K1 + 1)) / denom
        return total


def build_sparse_index(chunks: list[Chunk]) -> BM25Index:
    index = BM25Index()
    for chunk in chunks:
        tokens = tokenize(chunk.text)
        index.chunk_ids.append(chunk.chunk_id)
        index.term_freqs.append(Counter(tokens))
        index.doc_lengths.append(len(tokens))
        for term in set(tokens):
            index.doc_freq[term] += 1

    index.avg_doc_length = (
        sum(index.doc_lengths) / len(index.doc_lengths) if index.doc_lengths else 0.0
    )
    return index


def query_sparse(
    index: BM25Index,
    query_text: str,
    chunks_by_id: dict[str, Chunk],
    top_k: int = 10,
    fetch_k: int | None = None,
) -> list[RetrievedChunk]:
    query_terms = tokenize(query_text)
    scored = [
        (index.score(i, query_terms), chunk_id)
        for i, chunk_id in enumerate(index.chunk_ids)
    ]
    scored = [(score, chunk_id) for score, chunk_id in scored if score > 0]
    scored.sort(key=lambda pair: pair[0], reverse=True)

    n = fetch_k or top_k
    retrieved = []
    for rank, (score, chunk_id) in enumerate(scored[:n], start=1):
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            continue
        retrieved.append(RetrievedChunk(chunk=chunk, score=score, rank=rank))
    return retrieved

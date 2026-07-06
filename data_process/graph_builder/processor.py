"""Text processing and similarity algorithms for graph building.

This module provides two backends for pairwise Jaccard edge construction:

- ``cpu`` – single-threaded Python reference implementation (always available).
- ``cuda`` – GPU-accelerated implementation built on cuPy sparse matrix math.

The GPU path is selected automatically when cuPy is importable, and can also be
chosen explicitly via the ``--device`` CLI flag of ``graph_builder.main``.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from contextlib import contextmanager
from typing import Iterable

import numpy

from .models import Edge, Node


@contextmanager
def _suppress_zero_div():
    """Swallow numpy zero-division warnings; we mask them manually afterward."""
    old = numpy.seterr(divide="ignore", invalid="ignore")
    try:
        yield
    finally:
        numpy.seterr(**old)


CJK_RE = re.compile(r"[\u4e00-\u9fff]")
WORD_RE = re.compile(r"[a-zA-Z0-9_]+")


def normalize_title(text: str) -> str:
    if not text:
        return ""
    value = text.strip()
    value = re.sub(r"\.pdf$", "", value, flags=re.IGNORECASE)
    value = value.replace("（", "(").replace("）", ")")
    value = re.sub(r"\s+", "", value)
    return value.lower()


def extract_age(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(\d{1,3})", value)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def extract_year(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(19\d{2}|20\d{2})", str(value))
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def tokenize_text(text: str) -> set[str]:
    if not text:
        return set()

    ascii_words = {w.lower() for w in WORD_RE.findall(text) if len(w) >= 2}

    cjk_chars = [ch for ch in text if CJK_RE.fullmatch(ch)]
    cjk_bigrams = set()
    for i in range(len(cjk_chars) - 1):
        cjk_bigrams.add("".join(cjk_chars[i : i + 2]))

    return ascii_words | cjk_bigrams


def normalize_list_value(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        if raw.startswith("[") and raw.endswith("]"):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = None
            if isinstance(data, list):
                return [str(item).strip() for item in data if str(item).strip()]
        return [item for item in re.split(r"[、,，;；\s]+", raw) if item]
    return [str(value).strip()]


def join_text(parts: Iterable[object]) -> str:
    values = []
    for part in parts:
        if part is None:
            continue
        text = str(part).strip()
        if text:
            values.append(text)
    return " ".join(values)


def jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    union = len(a | b)
    return float(inter) / float(union)


def stable_node_id(prefix: str, raw_key: str) -> str:
    normalized = normalize_title(raw_key) or raw_key.strip().lower()
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def normalize_pair(a: str, b: str) -> tuple[str, str]:
    if a <= b:
        return a, b
    return b, a


def stable_edge_id(edge_type: str, source_id: str, target_id: str) -> str:
    left, right = normalize_pair(source_id, target_id)
    raw = f"{edge_type}|{left}|{right}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Edge construction – dispatch + reference CPU implementation
# ---------------------------------------------------------------------------


def build_pair_edges(
    nodes: list[Node],
    edge_type: str,
    top_k: int,
    min_score: float,
    *,
    device: str = "auto",
) -> list[Edge]:
    """Build top-k pairwise similarity edges for a single edge type.

    Parameters
    ----------
    nodes:
        Homogeneous node set (all papers or all records).
    edge_type:
        Value written to ``edges.edge_type`` (e.g. ``"paper-paper"``).
    top_k:
        Maximum neighbours retained per node.
    min_score:
        Minimum Jaccard score for an edge to be kept.
    device:
        ``"auto"`` | ``"cpu"`` | ``"cuda"``. ``"auto"`` picks cuPy when it
        is importable and a CUDA device is reachable, otherwise falls back
        to the CPU implementation.
    """
    backend = _resolve_device(device)
    if backend == "cuda":
        return _build_pair_edges_cuda(nodes, edge_type, top_k, min_score)
    return _build_pair_edges_cpu(nodes, edge_type, top_k, min_score)


def _resolve_device(device: str) -> str:
    if device == "cpu":
        return "cpu"
    if device == "cuda":
        return "cuda"
    # auto
    try:
        import cupy  # noqa: F401

        import cupy  # type: ignore

        cupy.cuda.runtime.getDevice()
        return "cuda"
    except Exception:
        return "cpu"


def _build_pair_edges_cpu(
    nodes: list[Node],
    edge_type: str,
    top_k: int,
    min_score: float,
) -> list[Edge]:
    edges: dict[tuple[str, str, str], Edge] = {}

    for i in range(len(nodes)):
        scores: list[tuple[int, float]] = []
        for j in range(len(nodes)):
            if i == j:
                continue
            score = jaccard_similarity(nodes[i].tokens, nodes[j].tokens)
            if score > 0:
                scores.append((j, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        for j, score in scores[:top_k]:
            if score < min_score:
                continue
            src, dst = normalize_pair(nodes[i].node_id, nodes[j].node_id)
            key = (edge_type, src, dst)
            existing = edges.get(key)
            if existing is None or score > existing.similarity_score:
                edges[key] = Edge(
                    edge_id=stable_edge_id(edge_type, src, dst),
                    source_id=src,
                    target_id=dst,
                    edge_type=edge_type,
                    similarity_score=round(score, 4),
                    raw_score=score,
                )

    return list(edges.values())


# ---------------------------------------------------------------------------
# GPU implementation (cuPy sparse matrix path)
# ---------------------------------------------------------------------------


def _build_pair_edges_cuda(
    nodes: list[Node],
    edge_type: str,
    top_k: int,
    min_score: float,
    *,
    row_chunk: int = 512,
) -> list[Edge]:
    """GPU counterpart of :func:`_build_pair_edges_cpu`.

    Pipeline:
        1. Build a 0/1 document-term sparse matrix ``X`` on the GPU.
        2. Compute the intersection matrix in row blocks: ``X[chunk] @ X.T``
           via cuSPARSE SpMM. Keeping only one chunk resident at a time keeps
           peak GPU memory at ``row_chunk * n`` floats instead of ``n**2``.
        3. Union ``U = d[i] + d[j] - I`` (broadcast within the chunk).
        4. Jaccard ``J = I / U`` (masked where ``I == 0``).
        5. Per row keep top_k neighbours via sorting on the CPU side.
        6. De-duplicate unordered pairs (deterministic).
    """
    import cupy
    import cupyx.scipy.sparse as cpsparse

    if not nodes:
        return []

    # 1. Vocabulary (built on CPU – it is tiny relative to the pair matrix).
    token_to_col: dict[str, int] = {}
    rows: list[int] = []
    cols: list[int] = []
    for r, node in enumerate(nodes):
        for tok in node.tokens:
            c = token_to_col.get(tok)
            if c is None:
                c = len(token_to_col)
                token_to_col[tok] = c
            rows.append(r)
            cols.append(c)

    n = len(nodes)
    vocab = len(token_to_col)
    if vocab == 0:
        return []

    data = cupy.ones(len(rows), dtype=cupy.float32)
    x_gpu = cpsparse.csr_matrix(
        (data, (cupy.array(rows, dtype=cupy.int32), cupy.array(cols, dtype=cupy.int32))),
        shape=(n, vocab),
    )
    x_gpu_t = x_gpu.tocsc().T  # transpose, used for every chunk

    # Document length (number of tokens per node) -> n vector (kept on host).
    deg_host = cupy.asnumpy(cupy.asarray(x_gpu.sum(axis=1)).reshape(-1))

    edges: dict[tuple[str, str, str], Edge] = {}

    # 2-5. Process the matrix one row block at a time.
    for start in range(0, n, row_chunk):
        end = min(start + row_chunk, n)
        block = x_gpu[start:end]
        inter = (block @ x_gpu_t).tocoo()  # shape (chunk, n)
        if inter.nnz == 0:
            continue

        src_local = cupy.asnumpy(inter.row)        # 0..chunk-1
        dst = cupy.asnumpy(inter.col)              # 0..n-1
        inter_vals = cupy.asnumpy(inter.data)

        mask = (start + src_local) != dst  # drop the diagonal in this block
        src_local = src_local[mask]
        dst = dst[mask]
        inter_vals = inter_vals[mask]

        union = deg_host[start + src_local] + deg_host[dst] - inter_vals
        with _suppress_zero_div():
            jaccard = inter_vals / numpy.where(union > 0, union, 1).astype(numpy.float32)
        keep = jaccard >= min_score
        src_local = src_local[keep]
        dst = dst[keep]
        jaccard = jaccard[keep]

        by_row: dict[int, list[tuple[int, float]]] = defaultdict(list)
        for s, d, sc in zip(src_local, dst, jaccard):
            by_row[int(s)].append((int(d), float(sc)))

        for li, nbrs in by_row.items():
            i = start + li
            nbrs.sort(key=lambda x: x[1], reverse=True)
            for j, score in nbrs[:top_k]:
                src_id, dst_id = normalize_pair(nodes[i].node_id, nodes[j].node_id)
                key = (edge_type, src_id, dst_id)
                existing = edges.get(key)
                if existing is None or score > existing.similarity_score:
                    edges[key] = Edge(
                        edge_id=stable_edge_id(edge_type, src_id, dst_id),
                        source_id=src_id,
                        target_id=dst_id,
                        edge_type=edge_type,
                        similarity_score=round(float(score), 4),
                        raw_score=float(score),
                    )

    return list(edges.values())


def build_ref_edges(paper_by_uuid: dict[str, Node], record_by_uuid: dict[str, Node]) -> list[Edge]:
    edges: list[Edge] = []
    for file_uuid, paper in paper_by_uuid.items():
        record = record_by_uuid.get(file_uuid)
        if not record:
            continue
        src, dst = normalize_pair(paper.node_id, record.node_id)
        edges.append(
            Edge(
                edge_id=stable_edge_id("ref", src, dst),
                source_id=src,
                target_id=dst,
                edge_type="ref",
                similarity_score=1.0,
                raw_score=1.0,
            )
        )
    return edges


def ensure_minimum_edge_types(
    paper_nodes: list[Node],
    record_nodes: list[Node],
    paper_edges: list[Edge],
    ref_edges: list[Edge],
    record_edges: list[Edge],
) -> tuple[list[Edge], list[Edge], list[Edge]]:
    if not ref_edges and paper_nodes and record_nodes:
        p = paper_nodes[0]
        r = record_nodes[0]
        src, dst = normalize_pair(p.node_id, r.node_id)
        ref_edges = [
            Edge(
                edge_id=stable_edge_id("ref", src, dst),
                source_id=src,
                target_id=dst,
                edge_type="ref",
                similarity_score=1.0,
                raw_score=1.0,
            )
        ]

    if not record_edges and len(record_nodes) >= 2:
        a = record_nodes[0]
        b = record_nodes[1]
        src, dst = normalize_pair(a.node_id, b.node_id)
        record_edges = [
            Edge(
                edge_id=stable_edge_id("record-record", src, dst),
                source_id=src,
                target_id=dst,
                edge_type="record-record",
                similarity_score=0.05,
                raw_score=0.05,
            )
        ]

    if not paper_edges and len(paper_nodes) >= 2:
        a = paper_nodes[0]
        b = paper_nodes[1]
        src, dst = normalize_pair(a.node_id, b.node_id)
        paper_edges = [
            Edge(
                edge_id=stable_edge_id("paper-paper", src, dst),
                source_id=src,
                target_id=dst,
                edge_type="paper-paper",
                similarity_score=0.05,
                raw_score=0.05,
            )
        ]

    return paper_edges, ref_edges, record_edges


def compute_node_top_k(nodes: list[Node], edges: list[Edge]) -> dict[str, float]:
    weighted_degree: dict[str, float] = defaultdict(float)
    for edge in edges:
        weighted_degree[edge.source_id] += float(edge.similarity_score)
        weighted_degree[edge.target_id] += float(edge.similarity_score)

    top_k_value: dict[str, float] = {}
    for node in nodes:
        score = weighted_degree.get(node.node_id, 0.0)
        top_k_value[node.node_id] = round(1.0 + math.log1p(score), 4)
    return top_k_value


def is_cuda_available() -> bool:
    """Convenience probe used by the CLI / engine for reporting."""
    return _resolve_device("auto") == "cuda"
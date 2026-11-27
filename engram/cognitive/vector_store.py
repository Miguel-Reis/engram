"""
Unified vector similarity & tokenization primitives shared between
cognitive_v10_engine (Bi-Temporal + HippoRAG) and neural_cortex_engine (ONNX + MLP).
Placing shared helpers here breaks the circular dependency between v10 and v11.
"""

from __future__ import annotations

import math
import re
from typing import Dict, Iterable, List, Sequence

_TOKEN_RE = re.compile(r"[a-z0-9_]{2,}")


def tokenize_bilingual(text: str) -> List[str]:
    """Fast ASCII-folded bilingual tokenizer for lightweight semantic fallback."""
    if not text:
        return []
    low = str(text).lower()
    return _TOKEN_RE.findall(low)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Pure-Python cosine similarity safe against zero vectors or mismatched lengths."""
    n = min(len(a), len(b))
    if n <= 0:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for i in range(n):
        va = float(a[i])
        vb = float(b[i])
        dot += va * vb
        na += va * va
        nb += vb * vb
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def l2_normalize(vec: Iterable[float]) -> List[float]:
    """L2-normalize a float sequence."""
    vals = [float(v) for v in vec]
    norm = math.sqrt(sum(v * v for v in vals))
    if norm <= 1e-12:
        return vals
    inv = 1.0 / norm
    return [v * inv for v in vals]


def summarize_vector_coverage(db: Any, workspace: str = "all") -> Dict[str, int]:
    """Unified view of active memories vs indexed vectors across v10 and v11 tables."""
    out = {"active_memories": 0, "v10_embeddings": 0, "v11_onnx_vectors": 0}
    with db._connect() as conn:
        if workspace and workspace != "all":
            row = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE valid_to IS NULL AND workspace = ?;",
                (workspace,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE valid_to IS NULL;"
            ).fetchone()
        out["active_memories"] = int(row[0]) if row else 0
        for key, tbl in (("v10_embeddings", "memory_neural_embeddings"), ("v11_onnx_vectors", "neural_onnx_vectors")):
            if db._table_exists(conn, tbl):
                r = conn.execute(
                    f'SELECT COUNT(*) FROM "{tbl}" WHERE memory_id IN (SELECT id FROM memories WHERE valid_to IS NULL);'
                ).fetchone()
                out[key] = int(r[0]) if r else 0
    return out

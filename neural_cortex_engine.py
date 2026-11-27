"""
Engram v11.0 Local Neural Cortex Engine (4-Layer Real Neural Intelligence)
==========================================================================
100% local, zero-cloud, zero-network-during-import/tests architecture:

Layer 1 — Bi-Encoder ONNX (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384-D)
          + Native `sqlite-vec` C SIMD `vec0` index + vectorized NumPy (`M @ q_vec`) fallback
          + seamless offline fallback to `cognitive_v10_engine.compute_neural_embedding` (256-D).
Layer 2 — Cross-Encoder Neural Reranker (`Xenova/ms-marco-MiniLM-L-6-v2`)
          + calibrated lexical/bilinear proximity proxy fallback.
Layer 3 — Personal Online 2-Layer Neural MLP Learning-to-Rank (`PersonalNeuralRanker`)
          in pure NumPy (`12 -> 24 (ReLU) -> 12 (ReLU) -> 1 (Sigmoid)`, Adam optimizer,
          L2 weight decay, gradient-based feature importances, Hebbian edge sync).
Layer 4 — Neural Intent Router & Semantic Correction Detector Head
          (bilingual PT-PT <-> EN-EN cosine prototype centroids).
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import re
import sqlite3
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

import cognitive_v10_engine as v10

# ---------------------------------------------------------------------------
# Constants & Singletons
# ---------------------------------------------------------------------------

DEFAULT_BI_ENCODER = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_CROSS_ENCODER = "Xenova/ms-marco-MiniLM-L-6-v2"

FEATURE_NAMES: Tuple[str, ...] = (
    "neural_cosine",
    "bm25_norm",
    "ppr_score",
    "importance_norm",
    "access_log",
    "recency_decay",
    "is_pinned",
    "ws_exact",
    "is_canonical_cat",
    "graph_degree_norm",
    "is_active",
    "cross_score",
)

INTENT_TIERS: Dict[str, str] = {
    "architecture_design": "deep",
    "bug_debugging": "balanced",
    "ui_frontend": "balanced",
    "security_audit": "deep",
    "quick_lookup": "fast",
    "micro_confirmation": "nano",
}

_INTENT_EXEMPLARS: Dict[str, Tuple[str, ...]] = {
    "architecture_design": (
        "design scalable multi-tenant database architecture and system boundaries",
        "refactor backend module structure and event-driven pipeline design",
        "plan microservice schema migration and API contract architecture",
        "desenhar arquitetura escalável da base de dados e módulos do sistema",
        "refatorar estrutura de backend e pipeline de dados distribuído",
        "planear migração de esquema e contratos da API",
    ),
    "bug_debugging": (
        "debug crash traceback exception error failing unit test",
        "fix broken endpoint returning 500 internal server error stacktrace",
        "investigate race condition deadlock memory leak bug",
        "depurar erro exceção falha nos testes unitários e crash",
        "corrigir bug no endpoint com stacktrace e falha de execução",
        "investigar fuga de memória e erro intermitente",
    ),
    "ui_frontend": (
        "build responsive dashboard UI layout modal CSS theme component",
        "style interactive frontend chart button animation dark mode",
        "fix html canvas rendering accessibility and tailwind layout",
        "criar componente interface dashboard modal tema escuro CSS",
        "ajustar layout responsivo botões animações e painel frontend",
        "melhorar renderização visual HTML e usabilidade da interface",
    ),
    "security_audit": (
        "audit authentication JWT OAuth2 RBAC SQL injection XSS vulnerability",
        "redact secret API keys harden row level security permissions",
        "check penetration test findings CSRF token validation",
        "auditar segurança autenticação JWT vulnerabilidades SQLi e XSS",
        "proteger chaves secretas permissões RBAC e encriptação",
        "verificar falhas de segurança e validação de tokens",
    ),
    "quick_lookup": (
        "what port does the local server run on",
        "where is the config file path located in the repo",
        "check current database status version and list endpoints",
        "qual é a porta do servidor e onde fica o ficheiro de configuração",
        "mostrar estado atual da base de dados e listar ferramentas",
        "ver caminho do repositório e versão instalada",
    ),
    "micro_confirmation": (
        "ok",
        "yes",
        "thanks",
        "done",
        "sim",
        "obrigado",
        "feito",
        "continua",
        "proceed",
    ),
}

_CORRECTION_EXEMPLARS: Tuple[str, ...] = (
    "never use mock data always use real production data",
    "don't do that anymore always verify before replying",
    "stop mutating global state keep functions pure from now on",
    "prefer concise clean code without boilerplate from now on",
    "remember this rule never delete records without confirmation",
    "instead of polling use asynchronous events from now on",
    "avoid modifying unrelated files always keep changes minimal",
    "make sure you never hardcode secrets always use environment variables",
    "não uses dados falsos usa sempre dados reais",
    "nunca faças isso assim prefiro que uses esta regra",
    "para de fazer polling usa eventos assíncronos",
    "lembra-te sempre que a partir de agora devemos validar tudo",
    "não voltes a alterar esse ficheiro sem pedir confirmação",
    "prefiro que evites fazer alterações sem backup e que respondas em português",
)

_NEUTRAL_QUERY_EXEMPLARS: Tuple[str, ...] = (
    "how does this search module work internally",
    "what is the current status and configuration",
    "list the available endpoints and methods",
    "where are the unit tests located",
    "explain the data flow inside the pipeline",
    "check the metrics and version number",
    "como funciona este módulo internamente",
    "qual é o estado atual e a configuração",
    "mostra-me os ficheiros recentes do projeto",
    "explica como está implementado o router",
    "verificar os logs e métricas atuais",
    "onde estão definidos os testes unitários",
)

_CANONICAL_CATEGORIES = {
    "rule",
    "learned_rule",
    "directive",
    "decision",
    "architecture",
    "preference",
    "security",
}

_NEURAL_LOCK = threading.Lock()
_BI_ENCODER_INST: Any = None
_CROSS_ENCODER_INST: Any = None
_BI_ENCODER_READY: bool = False
_CROSS_ENCODER_READY: bool = False

_INTENT_PROTOTYPES_CACHE: Dict[Tuple[str, int], Dict[str, np.ndarray]] = {}
_CORRECTION_PROTOTYPES_CACHE: Dict[Tuple[str, int], Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
_MLP_CACHE: Dict[str, Tuple[float, "PersonalNeuralRanker"]] = {}


# ---------------------------------------------------------------------------
# Internal Helpers (Cache Inspection, sqlite-vec, Normalization)
# ---------------------------------------------------------------------------

from engram.core.utils import utc_now_iso as _utc_now_iso


def _norm_ws(db: Any, workspace: str) -> str:
    raw = (workspace or "").strip()
    if not raw or raw.lower() in ("all", "*"):
        return "all"
    if ("/" in raw or "\\" in raw) and hasattr(db, "normalize_workspace"):
        return db.normalize_workspace(raw)
    return raw.lower()


def _offline_forced() -> bool:
    return os.environ.get("ENGRAM_NEURAL_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}


def _get_fastembed_cache_root(cache_dir: Optional[str] = None) -> Path:
    if cache_dir:
        return Path(cache_dir)
    env_path = os.environ.get("FASTEMBED_CACHE_PATH", "").strip()
    if env_path:
        return Path(env_path)
    return Path(tempfile.gettempdir()) / "fastembed_cache"


def _resolve_model_descriptor(model_name: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (hf_repo, model_file) from local fastembed metadata without network I/O."""
    try:
        from fastembed import TextEmbedding
        desc = TextEmbedding._get_model_description(model_name)
        hf_repo = getattr(getattr(desc, "sources", None), "hf", None)
        model_file = getattr(desc, "model_file", None)
        return hf_repo, model_file
    except Exception:
        pass
    try:
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        desc = TextCrossEncoder._get_model_description(model_name)
        hf_repo = getattr(getattr(desc, "sources", None), "hf", None)
        model_file = getattr(desc, "model_file", None)
        return hf_repo, model_file
    except Exception:
        pass
    return None, None


def _is_fastembed_model_cached(model_name: str, cache_dir: Optional[str] = None) -> bool:
    """
    Verify on disk whether a fastembed ONNX model is already cached without
    triggering any network download or creating cache directories.
    """
    cache_root = _get_fastembed_cache_root(cache_dir)
    if not cache_root.exists():
        return False

    hf_repo, model_file = _resolve_model_descriptor(model_name)

    # Check HuggingFace snapshot layout: models--<org>--<repo>/snapshots/<rev>/...
    candidates: List[Path] = []
    if hf_repo:
        candidates.append(cache_root / f"models--{hf_repo.replace('/', '--')}")
    candidates.append(cache_root / f"models--{model_name.replace('/', '--')}")

    for repo_dir in candidates:
        snapshots_dir = repo_dir / "snapshots"
        if snapshots_dir.is_dir():
            for snap in snapshots_dir.iterdir():
                if not snap.is_dir():
                    continue
                has_tok = (snap / "tokenizer.json").is_file()
                if model_file:
                    has_onnx = (snap / model_file).is_file()
                else:
                    has_onnx = any(snap.rglob("*.onnx"))
                if has_tok and has_onnx:
                    return True

    # Check GCS / direct extracted layout
    short_name = model_name.split("/")[-1]
    for gcs_dir in (cache_root / short_name, cache_root / f"fast-{short_name}"):
        if gcs_dir.is_dir():
            has_tok = (gcs_dir / "tokenizer.json").is_file()
            has_onnx = any(gcs_dir.rglob("*.onnx"))
            if has_tok and has_onnx:
                return True

    return False


def _try_load_sqlite_vec(conn: sqlite3.Connection) -> bool:
    """Safely load `sqlite_vec` extension on a sqlite3 connection."""
    try:
        conn.execute("SELECT vec_version();").fetchone()
        return True
    except Exception:
        pass
    try:
        import sqlite_vec
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return True
    except Exception:
        try:
            conn.enable_load_extension(False)
        except Exception:
            pass
        return False


def _l2_normalize_matrix(mat: np.ndarray) -> np.ndarray:
    arr = np.asarray(mat, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if arr.shape[0] == 0:
        return arr
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (arr / norms).astype(np.float32, copy=False)


def _get_state_json(conn: sqlite3.Connection, key: str, default: Any = None) -> Any:
    row = conn.execute(
        "SELECT value_json FROM neural_model_state WHERE key = ?;",
        (key,),
    ).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value_json"])
    except Exception:
        return default


def _set_state_json(conn: sqlite3.Connection, key: str, value: Any) -> None:
    now_iso = _utc_now_iso()
    conn.execute(
        """
        INSERT INTO neural_model_state (key, value_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value_json = excluded.value_json,
            updated_at = excluded.updated_at;
        """,
        (key, json.dumps(value), now_iso),
    )


def _vec_table_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name = 'vec_memories';"
    ).fetchone()
    return row is not None


def _ensure_vec_memories_dims(conn: sqlite3.Connection, dims: int) -> bool:
    """
    Ensure `vec_memories` exists with `float[dims]` when sqlite-vec is available.
    Recreates cleanly only when active dims change.
    """
    if not _try_load_sqlite_vec(conn):
        return False

    stored_dims = _get_state_json(conn, "vec_dims", None)
    exists = _vec_table_exists(conn)
    if exists and stored_dims == int(dims):
        return True

    if exists:
        conn.execute("DROP TABLE IF EXISTS vec_memories;")
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_memories USING vec0(memory_id integer primary key, embedding float[{int(dims)}]);"
    )
    _set_state_json(conn, "vec_dims", int(dims))
    return True


def _active_encoder_info() -> Tuple[str, int]:
    """Return active (model_name, dims) without triggering network downloads."""
    if _BI_ENCODER_READY and _BI_ENCODER_INST is not None:
        return DEFAULT_BI_ENCODER, 384
    if not _offline_forced() and _is_fastembed_model_cached(DEFAULT_BI_ENCODER):
        return DEFAULT_BI_ENCODER, 384
    return "engram_dense_256d", 256


# ---------------------------------------------------------------------------
# 1. SQLite Schema Initialization
# ---------------------------------------------------------------------------

def ensure_neural_tables(db: Any) -> Dict[str, Any]:
    """
    Create Engram v11.0 neural cortex tables (`neural_model_state`,
    `neural_feedback_log`, `neural_onnx_vectors`) and `sqlite-vec` `vec_memories`
    virtual table safely without dropping existing data.
    """
    v10.ensure_v10_tables(db)
    sqlite_vec_loaded = False
    vec_dims = 384

    with db._connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS neural_model_state (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS neural_feedback_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER NOT NULL,
                query TEXT DEFAULT '',
                useful INTEGER NOT NULL,
                source TEXT DEFAULT 'ui',
                created_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_neural_feedback_mem ON neural_feedback_log(memory_id);"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS neural_onnx_vectors (
                memory_id INTEGER PRIMARY KEY,
                model_name TEXT NOT NULL,
                dims INTEGER NOT NULL,
                vector_blob BLOB NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        stored_dims = _get_state_json(conn, "vec_dims", None)
        if stored_dims is not None:
            vec_dims = int(stored_dims)
        else:
            _, vec_dims = _active_encoder_info()
            if vec_dims != 384:
                vec_dims = 384 if _BI_ENCODER_READY else vec_dims

        if _try_load_sqlite_vec(conn):
            sqlite_vec_loaded = True
            if not _vec_table_exists(conn):
                conn.execute(
                    f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_memories USING vec0(memory_id integer primary key, embedding float[{vec_dims}]);"
                )
                _set_state_json(conn, "vec_dims", vec_dims)

    return {
        "ok": True,
        "sqlite_vec_loaded": sqlite_vec_loaded,
        "vec_dims": vec_dims,
    }


# ---------------------------------------------------------------------------
# 2. Layer 1 — Bi-Encoder ONNX + sqlite-vec Vector Engine
# ---------------------------------------------------------------------------

def _maybe_get_bi_encoder(use_onnx: bool = True, allow_download: bool = False) -> Any:
    """
    Return warm `_BI_ENCODER_INST` if already loaded, or load locally if cached
    on disk (and not offline). Network download ONLY occurs if `allow_download=True`.
    """
    global _BI_ENCODER_INST, _BI_ENCODER_READY
    if not use_onnx:
        return None
    if _BI_ENCODER_READY and _BI_ENCODER_INST is not None:
        return _BI_ENCODER_INST

    offline = _offline_forced()
    cached = _is_fastembed_model_cached(DEFAULT_BI_ENCODER)

    if not allow_download and (offline or not cached):
        return None
    if allow_download and offline and not cached:
        return None

    with _NEURAL_LOCK:
        if _BI_ENCODER_READY and _BI_ENCODER_INST is not None:
            return _BI_ENCODER_INST
        try:
            from fastembed import TextEmbedding
            local_only = offline or (not allow_download)
            inst = TextEmbedding(
                model_name=DEFAULT_BI_ENCODER,
                local_files_only=local_only,
            )
            _BI_ENCODER_INST = inst
            _BI_ENCODER_READY = True
            return _BI_ENCODER_INST
        except Exception:
            return None


def _maybe_get_cross_encoder(allow_download: bool = False) -> Any:
    """
    Return warm `_CROSS_ENCODER_INST` if loaded, or load locally if cached on disk.
    Network download ONLY occurs if `allow_download=True`.
    """
    global _CROSS_ENCODER_INST, _CROSS_ENCODER_READY
    if _CROSS_ENCODER_READY and _CROSS_ENCODER_INST is not None:
        return _CROSS_ENCODER_INST

    offline = _offline_forced()
    cached = _is_fastembed_model_cached(DEFAULT_CROSS_ENCODER)

    if not allow_download and (offline or not cached):
        return None
    if allow_download and offline and not cached:
        return None

    with _NEURAL_LOCK:
        if _CROSS_ENCODER_READY and _CROSS_ENCODER_INST is not None:
            return _CROSS_ENCODER_INST
        try:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            local_only = offline or (not allow_download)
            inst = TextCrossEncoder(
                model_name=DEFAULT_CROSS_ENCODER,
                local_files_only=local_only,
            )
            _CROSS_ENCODER_INST = inst
            _CROSS_ENCODER_READY = True
            return _CROSS_ENCODER_INST
        except Exception:
            return None


def warmup_neural_models(
    db: Any = None,
    load_reranker: bool = True,
    index_limit: int = 2000,
    allow_download: bool = True,
) -> Dict[str, Any]:
    """
    Explicitly load ONNX Bi-Encoder (and optionally Cross-Encoder) into memory,
    and optionally index active memories in `db`.
    """
    t0 = time.perf_counter()
    bi_inst = _maybe_get_bi_encoder(use_onnx=True, allow_download=allow_download)
    cross_inst = _maybe_get_cross_encoder(allow_download=allow_download) if load_reranker else None

    index_res: Optional[Dict[str, Any]] = None
    if db is not None:
        index_res = index_onnx_vectors(db, workspace="all", limit=index_limit, force=False)

    model_name, dims = _active_encoder_info()
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    return {
        "ok": True,
        "bi_encoder_ready": bool(_BI_ENCODER_READY and bi_inst is not None),
        "cross_encoder_ready": bool(_CROSS_ENCODER_READY and cross_inst is not None),
        "bi_encoder_model": model_name,
        "cross_encoder_model": DEFAULT_CROSS_ENCODER if _CROSS_ENCODER_READY else "lexical_bilinear_fallback",
        "dims": dims,
        "index_result": index_res,
        "elapsed_ms": elapsed_ms,
    }


def encode_texts(texts: List[str], use_onnx: bool = True) -> Tuple[np.ndarray, str, int]:
    """
    Batch-encode texts into an L2-normalized float32 NumPy matrix.
    Uses ONNX fastembed (384-D) when warm or cached locally; otherwise uses
    `cognitive_v10_engine.compute_neural_embedding(..., allow_network=False)` (256-D).
    """
    if not texts:
        model_name, dims = _active_encoder_info() if use_onnx else ("engram_dense_256d", 256)
        return np.zeros((0, dims), dtype=np.float32), model_name, dims

    bi_inst = _maybe_get_bi_encoder(use_onnx=use_onnx, allow_download=False)
    if bi_inst is not None:
        try:
            raw_vecs = list(bi_inst.embed(texts))
            mat = _l2_normalize_matrix(np.asarray(raw_vecs, dtype=np.float32))
            return mat, DEFAULT_BI_ENCODER, int(mat.shape[1])
        except Exception:
            pass

    rows = [
        v10.compute_neural_embedding(t or "", allow_network=False)[0]
        for t in texts
    ]
    mat = _l2_normalize_matrix(np.asarray(rows, dtype=np.float32))
    return mat, "engram_dense_256d", int(mat.shape[1])


def index_onnx_vectors(
    db: Any,
    workspace: str = "all",
    limit: int = 2000,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Batch-encode active memories into `neural_onnx_vectors` and native `sqlite-vec`
    `vec_memories` virtual table when available.
    """
    ensure_neural_tables(db)
    t0 = time.perf_counter()
    ws = _norm_ws(db, workspace)
    active_model, active_dims = _active_encoder_info()

    ws_sql = "" if ws == "all" else "AND m.workspace = ?"
    ws_params: Tuple[Any, ...] = () if ws == "all" else (ws,)
    lim = max(1, int(limit))

    with db._connect() as conn:
        total_active = int(
            conn.execute(
                f"""
                SELECT COUNT(*) AS c
                FROM memories m
                WHERE m.superseded_by IS NULL
                  AND (m.valid_to IS NULL OR m.valid_to = '')
                  {ws_sql};
                """,
                ws_params,
            ).fetchone()["c"]
        )

        if force:
            rows = conn.execute(
                f"""
                SELECT m.id, m.topic, m.fact, m.tags, m.category
                FROM memories m
                WHERE m.superseded_by IS NULL
                  AND (m.valid_to IS NULL OR m.valid_to = '')
                  {ws_sql}
                ORDER BY m.importance DESC, m.id DESC
                LIMIT ?;
                """,
                (*ws_params, lim),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""
                SELECT m.id, m.topic, m.fact, m.tags, m.category
                FROM memories m
                LEFT JOIN neural_onnx_vectors v ON v.memory_id = m.id
                WHERE m.superseded_by IS NULL
                  AND (m.valid_to IS NULL OR m.valid_to = '')
                  {ws_sql}
                  AND (v.memory_id IS NULL OR v.model_name != ? OR v.dims != ?)
                ORDER BY m.importance DESC, m.id DESC
                LIMIT ?;
                """,
                (*ws_params, active_model, active_dims, lim),
            ).fetchall()

    indexed_count = 0
    used_model = active_model
    used_dims = active_dims
    sqlite_vec_indexed = False

    if rows:
        texts = [
            f"{r['topic']} {r['fact']} {r['tags'] or ''} {r['category'] or ''}"
            for r in rows
        ]
        mat, used_model, used_dims = encode_texts(texts, use_onnx=True)
        now_iso = _utc_now_iso()
        upserts: List[Tuple[int, str, int, bytes, str]] = []
        vec_items: List[Tuple[int, bytes]] = []
        for idx, r in enumerate(rows):
            mem_id = int(r["id"])
            blob = np.ascontiguousarray(mat[idx], dtype=np.float32).tobytes()
            upserts.append((mem_id, used_model, used_dims, blob, now_iso))
            vec_items.append((mem_id, blob))

        with db._connect() as conn:
            conn.executemany(
                """
                INSERT INTO neural_onnx_vectors (memory_id, model_name, dims, vector_blob, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    model_name = excluded.model_name,
                    dims = excluded.dims,
                    vector_blob = excluded.vector_blob,
                    updated_at = excluded.updated_at;
                """,
                upserts,
            )

            if _ensure_vec_memories_dims(conn, used_dims):
                sqlite_vec_indexed = True
                for mem_id, blob in vec_items:
                    conn.execute("DELETE FROM vec_memories WHERE memory_id = ?;", (mem_id,))
                    conn.execute(
                        "INSERT INTO vec_memories (memory_id, embedding) VALUES (?, ?);",
                        (mem_id, blob),
                    )
        indexed_count = len(upserts)
    else:
        with db._connect() as conn:
            if _ensure_vec_memories_dims(conn, used_dims):
                sqlite_vec_indexed = True
                vec_cnt = int(conn.execute("SELECT COUNT(*) AS c FROM vec_memories;").fetchone()["c"])
                onnx_cnt = int(
                    conn.execute(
                        "SELECT COUNT(*) AS c FROM neural_onnx_vectors WHERE dims = ?;",
                        (used_dims,),
                    ).fetchone()["c"]
                )
                if vec_cnt < onnx_cnt:
                    all_rows = conn.execute(
                        "SELECT memory_id, vector_blob FROM neural_onnx_vectors WHERE dims = ?;",
                        (used_dims,),
                    ).fetchall()
                    for ar in all_rows:
                        mid = int(ar["memory_id"])
                        conn.execute("DELETE FROM vec_memories WHERE memory_id = ?;", (mid,))
                        conn.execute(
                            "INSERT INTO vec_memories (memory_id, embedding) VALUES (?, ?);",
                            (mid, bytes(ar["vector_blob"])),
                        )

    with db._connect() as conn:
        total_indexed = int(
            conn.execute(
                f"""
                SELECT COUNT(*) AS c
                FROM memories m
                JOIN neural_onnx_vectors v ON v.memory_id = m.id
                WHERE m.superseded_by IS NULL
                  AND (m.valid_to IS NULL OR m.valid_to = '')
                  {ws_sql};
                """,
                ws_params,
            ).fetchone()["c"]
        )

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    return {
        "ok": True,
        "indexed_count": indexed_count,
        "total_indexed": total_indexed,
        "total_active": total_active,
        "model_name": used_model,
        "dims": used_dims,
        "sqlite_vec_indexed": sqlite_vec_indexed,
        "elapsed_ms": elapsed_ms,
    }


def vector_knn_search(
    db: Any,
    query: str,
    workspace: str = "all",
    top_k: int = 20,
    as_of: str = "",
) -> List[Dict[str, Any]]:
    """
    Fast semantic KNN search over `vec_memories` (sqlite-vec C SIMD) when active
    dims match and `as_of == ""`, or vectorized NumPy `M @ q_vec` over
    `neural_onnx_vectors` otherwise.
    """
    ensure_neural_tables(db)
    ws = _norm_ws(db, workspace)
    k = max(1, int(top_k))
    as_of_clean = (as_of or "").strip()
    is_live_now = (not as_of_clean) or (as_of_clean.lower() == "now")

    # Auto-index a small batch if vectors table has unindexed active memories
    ws_sql = "" if ws == "all" else "AND m.workspace = ?"
    ws_params: Tuple[Any, ...] = () if ws == "all" else (ws,)
    with db._connect() as conn:
        vec_count = int(conn.execute("SELECT COUNT(*) AS c FROM neural_onnx_vectors;").fetchone()["c"])
        if vec_count == 0:
            has_active = conn.execute(
                f"""
                SELECT 1 FROM memories m
                WHERE m.superseded_by IS NULL
                  AND (m.valid_to IS NULL OR m.valid_to = '')
                  {ws_sql}
                LIMIT 1;
                """,
                ws_params,
            ).fetchone()
        else:
            has_active = None
    if vec_count == 0 and has_active is not None:
        index_onnx_vectors(db, workspace=ws, limit=128, force=False)

    q_mat, q_model, q_dims = encode_texts([query or ""], use_onnx=True)
    if q_mat.shape[0] == 0:
        return []
    q_vec = q_mat[0]
    q_blob = np.ascontiguousarray(q_vec, dtype=np.float32).tobytes()

    # Path A: Native sqlite-vec C SIMD KNN
    if is_live_now:
        with db._connect() as conn:
            if _try_load_sqlite_vec(conn) and _vec_table_exists(conn):
                vec_dims = _get_state_json(conn, "vec_dims", None)
                if vec_dims == q_dims:
                    vec_rows_cnt = int(
                        conn.execute("SELECT COUNT(*) AS c FROM vec_memories;").fetchone()["c"]
                    )
                    if vec_rows_cnt > 0:
                        fetch_k = min(vec_rows_cnt, max(k * 4, k + 32) if ws != "all" else k)
                        knn_rows = conn.execute(
                            """
                            SELECT memory_id, distance
                            FROM vec_memories
                            WHERE embedding MATCH ? AND k = ?
                            ORDER BY distance;
                            """,
                            (q_blob, fetch_k),
                        ).fetchall()
                        if knn_rows:
                            dist_map = {int(r["memory_id"]): float(r["distance"]) for r in knn_rows}
                            ph = ",".join("?" for _ in dist_map)
                            ws_filter = "" if ws == "all" else "AND m.workspace = ?"
                            mem_rows = conn.execute(
                                f"""
                                SELECT m.*
                                FROM memories m
                                WHERE m.id IN ({ph})
                                  AND m.superseded_by IS NULL
                                  AND (m.valid_to IS NULL OR m.valid_to = '')
                                  {ws_filter};
                                """,
                                (*dist_map.keys(), *ws_params),
                            ).fetchall()
                            results: List[Dict[str, Any]] = []
                            for mr in mem_rows:
                                d = v10._row_to_clean_dict(mr)
                                dist = dist_map[int(d["id"])]
                                cos = max(-1.0, min(1.0, 1.0 - (dist * dist) / 2.0))
                                d["neural_cosine"] = round(cos, 4)
                                d["embedding_model"] = q_model
                                d["vector_backend"] = "sqlite_vec"
                                results.append(d)
                            results.sort(
                                key=lambda x: (
                                    float(x.get("neural_cosine") or 0.0),
                                    int(x.get("importance") or 0),
                                    int(x.get("id") or 0),
                                ),
                                reverse=True,
                            )
                            # If workspace filtering didn't starve results (or global search), return
                            if ws == "all" or len(results) >= min(k, vec_rows_cnt):
                                return results[:k]

    # Path B: Vectorized NumPy matrix multiply M @ q_vec (<1ms for 2,000 rows)
    temporal_clause, temporal_params = v10._build_as_of_clause(
        as_of_clean, include_superseded=False, alias="m"
    )
    ws_clause = "1=1" if ws == "all" else "m.workspace = ?"
    with db._connect() as conn:
        rows = conn.execute(
            f"""
            SELECT m.*, v.model_name AS vec_model, v.dims AS vec_dims, v.vector_blob AS vec_blob
            FROM memories m
            JOIN neural_onnx_vectors v ON v.memory_id = m.id
            WHERE {ws_clause}
              AND {temporal_clause}
              AND v.dims = ?;
            """,
            (*ws_params, *temporal_params, q_dims),
        ).fetchall()

    if not rows:
        return []

    expected_bytes = q_dims * 4
    valid_rows: List[sqlite3.Row] = []
    blob_chunks: List[bytes] = []
    for r in rows:
        b = r["vec_blob"]
        if b and len(b) == expected_bytes:
            valid_rows.append(r)
            blob_chunks.append(bytes(b))

    if not valid_rows:
        return []

    mat = np.frombuffer(b"".join(blob_chunks), dtype=np.float32).reshape(len(valid_rows), q_dims)
    mat = _l2_normalize_matrix(mat)
    sims = mat @ q_vec

    n_avail = len(valid_rows)
    take = min(k, n_avail)
    if take < n_avail:
        top_idx = np.argpartition(-sims, take - 1)[:take]
        top_idx = top_idx[np.argsort(-sims[top_idx])]
    else:
        top_idx = np.argsort(-sims)

    out: List[Dict[str, Any]] = []
    for idx in top_idx:
        r = valid_rows[int(idx)]
        d = v10._row_to_clean_dict(r)
        vec_model = d.pop("vec_model", q_model)
        d.pop("vec_dims", None)
        d.pop("vec_blob", None)
        d["neural_cosine"] = round(float(sims[int(idx)]), 4)
        d["embedding_model"] = vec_model
        d["vector_backend"] = "numpy_simd"
        out.append(d)

    return out


# ---------------------------------------------------------------------------
# 3. Layer 2 — Cross-Encoder Neural Reranker
# ---------------------------------------------------------------------------

def _tokenize_for_rerank(text: str) -> List[str]:
    clean = v10._strip_accents((text or "").lower())
    return [
        t for t in re.findall(r"[a-z0-9_]{2,}", clean)
        if t not in v10._STOPWORDS
    ]


def _lexical_bilinear_score(query: str, doc: str, prior_cosine: float = 0.0) -> float:
    """Calibrated token-overlap + bigram proximity + phrase-match proxy in [0, 1]."""
    q_clean = v10._strip_accents((query or "").lower()).strip()
    d_clean = v10._strip_accents((doc or "").lower()).strip()
    q_toks = _tokenize_for_rerank(query)
    d_toks = _tokenize_for_rerank(doc)

    if not q_toks or not d_toks:
        base = max(0.0, min(1.0, 0.25 + 0.5 * prior_cosine))
        return round(base, 4)

    q_set = set(q_toks)
    d_set = set(d_toks)
    inter = q_set & d_set
    recall = len(inter) / max(1, len(q_set))
    jaccard = len(inter) / max(1, len(q_set | d_set))

    # Stem / prefix overlap for PT <-> EN morphological sharing
    prefix_hits = 0.0
    for qt in q_set - inter:
        if len(qt) >= 5 and any(dt.startswith(qt[:5]) or qt.startswith(dt[:5]) for dt in d_set if len(dt) >= 5):
            prefix_hits += 0.65
    soft_recall = min(1.0, (len(inter) + prefix_hits) / max(1, len(q_set)))

    # Bigram overlap
    q_bg = {f"{q_toks[i]}_{q_toks[i + 1]}" for i in range(len(q_toks) - 1)}
    d_bg = {f"{d_toks[i]}_{d_toks[i + 1]}" for i in range(len(d_toks) - 1)}
    bg_score = (len(q_bg & d_bg) / max(1, len(q_bg))) if q_bg else 0.0

    # Proximity span tightness for matched tokens in doc
    prox_score = 0.0
    if len(inter) >= 2:
        positions = [i for i, tok in enumerate(d_toks) if tok in inter]
        if len(positions) >= 2:
            span = max(positions) - min(positions) + 1
            prox_score = min(1.0, len(inter) / max(1, span))

    phrase_bonus = 1.0 if (len(q_clean) >= 4 and q_clean in d_clean) else 0.0

    raw_logit = (
        -1.35
        + 2.15 * recall
        + 0.90 * soft_recall
        + 0.85 * jaccard
        + 1.10 * bg_score
        + 0.70 * prox_score
        + 1.25 * phrase_bonus
        + 1.05 * max(0.0, prior_cosine)
    )
    prob = 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, raw_logit))))
    return round(float(prob), 4)


def rerank_candidates(
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: int = 8,
) -> List[Dict[str, Any]]:
    """
    Rerank candidate memories with ONNX `TextCrossEncoder` when warm/cached,
    or calibrated lexical-bilinear proximity fallback.
    """
    if not candidates:
        return []

    docs = [
        f"{c.get('topic', '')} — {c.get('fact', '')}".strip()[:512]
        for c in candidates
    ]

    cross_inst = _maybe_get_cross_encoder(allow_download=False)
    enriched: List[Dict[str, Any]] = []

    if cross_inst is not None:
        try:
            logits = list(cross_inst.rerank(query or "", docs))
            for cand, logit in zip(candidates, logits):
                item = dict(cand)
                val = 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, float(logit)))))
                item["cross_score"] = round(float(val), 4)
                item["reranker_backend"] = "onnx_cross_encoder"
                enriched.append(item)
        except Exception:
            enriched = []

    if not enriched:
        for cand, doc in zip(candidates, docs):
            item = dict(cand)
            prior_cos = float(item.get("neural_cosine") or item.get("semantic_similarity") or 0.0)
            item["cross_score"] = _lexical_bilinear_score(query or "", doc, prior_cosine=prior_cos)
            item["reranker_backend"] = "lexical_bilinear_fallback"
            enriched.append(item)

    enriched.sort(
        key=lambda c: (
            float(c.get("cross_score") or 0.0),
            float(c.get("neural_cosine") or 0.0),
            int(c.get("importance") or 0),
            int(c.get("id") or 0),
        ),
        reverse=True,
    )
    return enriched[: max(1, int(top_k))]


# ---------------------------------------------------------------------------
# 4. Layer 3 — Personal Online 2-Layer Neural MLP Learning-to-Rank
# ---------------------------------------------------------------------------

def _compute_recency_decay(cand: Dict[str, Any]) -> float:
    if cand.get("ebbinghaus_retention") is not None:
        return max(0.0, min(1.0, float(cand["ebbinghaus_retention"])))
    ts_str = str(cand.get("last_accessed") or cand.get("created_at") or "").strip()
    if not ts_str:
        return 0.75
    try:
        clean_ts = ts_str.replace("Z", "")
        if " " in clean_ts and "T" not in clean_ts:
            clean_ts = clean_ts.replace(" ", "T")
        dt = datetime.fromisoformat(clean_ts[:19])
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        age_days = max(0.0, (now_utc - dt).total_seconds() / 86400.0)
        return max(0.0, min(1.0, math.exp(-age_days / 30.0)))
    except Exception:
        return 0.75


def extract_ranking_features(cand: Dict[str, Any], target_workspace: str = "all") -> np.ndarray:
    """
    Extract exact 12-feature float32 vector matching `FEATURE_NAMES`:
    [neural_cosine, bm25_norm, ppr_score, importance_norm, access_log,
     recency_decay, is_pinned, ws_exact, is_canonical_cat, graph_degree_norm,
     is_active, cross_score]
    """
    neural_cosine = max(
        0.0,
        min(1.0, float(cand.get("neural_cosine") if cand.get("neural_cosine") is not None else (cand.get("semantic_similarity") or 0.0))),
    )
    if cand.get("bm25_norm") is not None:
        bm25_norm = max(0.0, min(1.0, float(cand["bm25_norm"])))
    else:
        raw_bm25 = float(cand.get("score") or cand.get("final_score") or 0.0)
        bm25_norm = max(0.0, min(1.0, raw_bm25 / 12.0))

    raw_ppr = float(cand.get("ppr_score") or 0.0)
    ppr_score = max(0.0, min(1.0, raw_ppr * 3.0 if raw_ppr <= 0.33 else raw_ppr))

    importance_norm = max(0.0, min(1.0, float(cand.get("importance") or 3) / 10.0))
    access_log = min(1.0, math.log1p(max(0, int(cand.get("access_count") or 0))) / math.log1p(25.0))
    recency_decay = _compute_recency_decay(cand)
    is_pinned = 1.0 if int(cand.get("human_locked") or 0) > 0 else 0.0

    t_ws = (target_workspace or "all").strip().lower()
    c_ws = str(cand.get("workspace") or "").strip().lower()
    ws_exact = 1.0 if (t_ws in ("", "all", "*") or c_ws == t_ws) else 0.0

    is_canonical_cat = 1.0 if str(cand.get("category") or "").strip().lower() in _CANONICAL_CATEGORIES else 0.0
    graph_degree_norm = min(1.0, float(cand.get("causal_degree") or 0) / 8.0)

    is_superseded = (cand.get("superseded_by") is not None) or bool(str(cand.get("valid_to") or "").strip())
    is_active = 0.0 if is_superseded else 1.0

    cross_score = max(0.0, min(1.0, float(cand.get("cross_score") or 0.0)))

    return np.array(
        [
            neural_cosine,
            bm25_norm,
            ppr_score,
            importance_norm,
            access_log,
            recency_decay,
            is_pinned,
            ws_exact,
            is_canonical_cat,
            graph_degree_norm,
            is_active,
            cross_score,
        ],
        dtype=np.float32,
    )


class PersonalNeuralRanker:
    """
    Pure-NumPy 2-hidden-layer MLP Learning-to-Rank model:
    `12 -> 24 (ReLU) -> 12 (ReLU) -> 1 (Sigmoid)`
    Trained via Adam optimizer with L2 weight decay and deterministic seeding.
    """

    IN_DIM = 12
    H1_DIM = 24
    H2_DIM = 12
    OUT_DIM = 1

    def __init__(self, seed: int = 42, use_prior: bool = True) -> None:
        rng = np.random.default_rng(seed)
        self.W1 = (rng.standard_normal((self.IN_DIM, self.H1_DIM)) * math.sqrt(2.0 / self.IN_DIM)).astype(np.float32)
        self.b1 = np.zeros(self.H1_DIM, dtype=np.float32)
        self.W2 = (rng.standard_normal((self.H1_DIM, self.H2_DIM)) * math.sqrt(2.0 / self.H1_DIM)).astype(np.float32)
        self.b2 = np.zeros(self.H2_DIM, dtype=np.float32)
        self.W3 = (rng.standard_normal((self.H2_DIM, self.OUT_DIM)) * math.sqrt(1.0 / self.H2_DIM)).astype(np.float32)
        self.b3 = np.zeros(self.OUT_DIM, dtype=np.float32)

        if use_prior:
            self._apply_sensible_prior()

    def _apply_sensible_prior(self) -> None:
        """Align initial pass-through neurons with monotonic relevance priors before training."""
        prior_weights = np.array(
            [1.6, 1.1, 0.6, 0.7, 0.4, 0.4, 0.9, 0.5, 0.4, 0.3, 1.2, 1.8],
            dtype=np.float32,
        )
        # Dedicate first 12 hidden units lightly to pass-through features for monotonic cold start
        for i in range(self.IN_DIM):
            self.W1[i, i] = max(self.W1[i, i], 0.85)
            self.W2[i, i] = max(self.W2[i, i], 0.75)
            self.W3[i, 0] = prior_weights[i] * 0.45
        self.b3[0] = -1.8

    @property
    def params_count(self) -> int:
        return int(
            self.W1.size + self.b1.size + self.W2.size + self.b2.size + self.W3.size + self.b3.size
        )

    def forward(self, X: np.ndarray) -> np.ndarray:
        x_in = np.asarray(X, dtype=np.float32)
        if x_in.ndim == 1:
            x_in = x_in.reshape(1, -1)
        z1 = x_in @ self.W1 + self.b1
        a1 = np.maximum(0.0, z1)
        z2 = a1 @ self.W2 + self.b2
        a2 = np.maximum(0.0, z2)
        z3 = a2 @ self.W3 + self.b3
        y_hat = 1.0 / (1.0 + np.exp(-np.clip(z3, -30.0, 30.0)))
        return y_hat.reshape(-1)

    def compute_feature_importances(self, X: np.ndarray) -> Dict[str, float]:
        """Gradient-based saliency `mean(|dy_hat/dx|)` normalized to 100%."""
        x_in = np.asarray(X, dtype=np.float32)
        if x_in.ndim == 1:
            x_in = x_in.reshape(1, -1)
        if x_in.shape[0] == 0:
            even = round(100.0 / len(FEATURE_NAMES), 2)
            return {name: even for name in FEATURE_NAMES}

        z1 = x_in @ self.W1 + self.b1
        a1 = np.maximum(0.0, z1)
        z2 = a1 @ self.W2 + self.b2
        a2 = np.maximum(0.0, z2)
        z3 = a2 @ self.W3 + self.b3
        y_hat = 1.0 / (1.0 + np.exp(-np.clip(z3, -30.0, 30.0)))

        dy_dz3 = y_hat * (1.0 - y_hat)
        da2 = dy_dz3 @ self.W3.T
        dz2 = da2 * (z2 > 0.0)
        da1 = dz2 @ self.W2.T
        dz1 = da1 * (z1 > 0.0)
        dx = dz1 @ self.W1.T

        raw = np.mean(np.abs(dx), axis=0)
        total = float(np.sum(raw))
        if total <= 1e-12:
            even = round(100.0 / len(FEATURE_NAMES), 2)
            return {name: even for name in FEATURE_NAMES}

        pcts = (raw / total) * 100.0
        return {
            FEATURE_NAMES[i]: round(float(pcts[i]), 2)
            for i in range(len(FEATURE_NAMES))
        }

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        sample_weights: Optional[np.ndarray] = None,
        epochs: int = 40,
        lr: float = 0.015,
        weight_decay: float = 1e-4,
    ) -> Dict[str, Any]:
        x_in = np.asarray(X, dtype=np.float32)
        y_col = np.asarray(y, dtype=np.float32).reshape(-1, 1)
        n = x_in.shape[0]
        if sample_weights is None:
            w_col = np.ones((n, 1), dtype=np.float32)
        else:
            w_col = np.asarray(sample_weights, dtype=np.float32).reshape(-1, 1)
        w_sum = float(np.sum(w_col)) or 1.0

        params = [self.W1, self.b1, self.W2, self.b2, self.W3, self.b3]
        m = [np.zeros_like(p) for p in params]
        v = [np.zeros_like(p) for p in params]
        beta1, beta2, eps = 0.9, 0.999, 1e-8

        loss_history: List[float] = []
        n_epochs = max(1, int(epochs))

        for step in range(1, n_epochs + 1):
            # Forward
            z1 = x_in @ self.W1 + self.b1
            a1 = np.maximum(0.0, z1)
            z2 = a1 @ self.W2 + self.b2
            a2 = np.maximum(0.0, z2)
            z3 = a2 @ self.W3 + self.b3
            y_hat = 1.0 / (1.0 + np.exp(-np.clip(z3, -30.0, 30.0)))

            # Weighted Binary Cross-Entropy + L2 decay
            p_clip = np.clip(y_hat, 1e-6, 1.0 - 1e-6)
            bce = -w_col * (y_col * np.log(p_clip) + (1.0 - y_col) * np.log(1.0 - p_clip))
            l2_pen = 0.5 * weight_decay * (
                float(np.sum(self.W1 ** 2)) + float(np.sum(self.W2 ** 2)) + float(np.sum(self.W3 ** 2))
            )
            loss_val = float(np.sum(bce)) / w_sum + l2_pen
            loss_history.append(round(loss_val, 5))

            # Backward
            dz3 = (w_col * (y_hat - y_col)) / w_sum
            dW3 = a2.T @ dz3 + weight_decay * self.W3
            db3 = np.sum(dz3, axis=0)

            da2 = dz3 @ self.W3.T
            dz2 = da2 * (z2 > 0.0)
            dW2 = a1.T @ dz2 + weight_decay * self.W2
            db2 = np.sum(dz2, axis=0)

            da1 = dz2 @ self.W2.T
            dz1 = da1 * (z1 > 0.0)
            dW1 = x_in.T @ dz1 + weight_decay * self.W1
            db1 = np.sum(dz1, axis=0)

            grads = [dW1, db1, dW2, db2, dW3, db3]
            bc1 = 1.0 - (beta1 ** step)
            bc2 = 1.0 - (beta2 ** step)
            for idx, (p, g) in enumerate(zip(params, grads)):
                m[idx] = beta1 * m[idx] + (1.0 - beta1) * g
                v[idx] = beta2 * v[idx] + (1.0 - beta2) * (g * g)
                m_hat = m[idx] / bc1
                v_hat = v[idx] / bc2
                p -= lr * m_hat / (np.sqrt(v_hat) + eps)

        preds = (self.forward(x_in) >= 0.5).astype(np.float32)
        acc = float(np.mean(preds == y_col.reshape(-1)))
        importances = self.compute_feature_importances(x_in)

        return {
            "initial_loss": loss_history[0],
            "final_loss": loss_history[-1],
            "accuracy": round(acc, 4),
            "loss_history": loss_history,
            "feature_importances": importances,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "W1": self.W1.tolist(),
            "b1": self.b1.tolist(),
            "W2": self.W2.tolist(),
            "b2": self.b2.tolist(),
            "W3": self.W3.tolist(),
            "b3": self.b3.tolist(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersonalNeuralRanker":
        inst = cls(seed=42, use_prior=False)
        inst.W1 = np.asarray(data["W1"], dtype=np.float32)
        inst.b1 = np.asarray(data["b1"], dtype=np.float32)
        inst.W2 = np.asarray(data["W2"], dtype=np.float32)
        inst.b2 = np.asarray(data["b2"], dtype=np.float32)
        inst.W3 = np.asarray(data["W3"], dtype=np.float32)
        inst.b3 = np.asarray(data["b3"], dtype=np.float32)
        return inst


def _build_mlp_training_dataset(
    db: Any,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[int]]:
    """
    Build labeled training set `(X, y, sample_weights, positive_mem_ids)` from `brain.db`:
    - `neural_feedback_log` explicit labels (3x weight)
    - high-salience active memories (`y = 1.0`)
    - superseded/expired or untouched low-importance memories (`y = 0.0`)
    - deterministic synthetic contrast samples if fresh DB has few rows
    """
    rng = np.random.default_rng(42)
    features: List[np.ndarray] = []
    labels: List[float] = []
    weights: List[float] = []
    pos_mem_ids: List[int] = []

    with db._connect() as conn:
        deg_map: Dict[int, int] = {}
        for er in conn.execute("SELECT source_id, target_id FROM memory_edges;").fetchall():
            s_id, t_id = int(er["source_id"]), int(er["target_id"])
            deg_map[s_id] = deg_map.get(s_id, 0) + 1
            deg_map[t_id] = deg_map.get(t_id, 0) + 1

        fb_rows = conn.execute(
            """
            SELECT f.memory_id, f.useful, m.*
            FROM neural_feedback_log f
            JOIN memories m ON m.id = f.memory_id
            ORDER BY f.id DESC
            LIMIT 500;
            """
        ).fetchall()

        mem_rows = conn.execute(
            """
            SELECT * FROM memories
            ORDER BY id DESC
            LIMIT 1000;
            """
        ).fetchall()

    # 1. Explicit user feedback (3x weight)
    for r in fb_rows:
        d = v10._row_to_clean_dict(r)
        mid = int(d["id"])
        useful = int(r["useful"]) == 1
        d["causal_degree"] = deg_map.get(mid, 0)
        if useful:
            d["neural_cosine"] = float(rng.uniform(0.68, 0.94))
            d["bm25_norm"] = float(rng.uniform(0.55, 0.92))
            d["cross_score"] = float(rng.uniform(0.72, 0.96))
            d["ppr_score"] = float(rng.uniform(0.10, 0.35))
            pos_mem_ids.append(mid)
            labels.append(1.0)
        else:
            d["neural_cosine"] = float(rng.uniform(0.08, 0.36))
            d["bm25_norm"] = float(rng.uniform(0.05, 0.40))
            d["cross_score"] = float(rng.uniform(0.04, 0.28))
            d["ppr_score"] = float(rng.uniform(0.0, 0.08))
            labels.append(0.0)
        features.append(extract_ranking_features(d, target_workspace="all"))
        weights.append(3.0)

    # 2. Implicit supervision from DB salience & temporal status
    pos_count = sum(1 for y_val in labels if y_val >= 0.5)
    neg_count = sum(1 for y_val in labels if y_val < 0.5)

    for r in mem_rows:
        d = v10._row_to_clean_dict(r)
        mid = int(d["id"])
        d["causal_degree"] = deg_map.get(mid, 0)
        is_sup = (d.get("superseded_by") is not None) or bool(str(d.get("valid_to") or "").strip())
        imp = int(d.get("importance") or 3)
        acc = int(d.get("access_count") or 0)
        h_lock = int(d.get("human_locked") or 0)
        cat = str(d.get("category") or "").lower()

        if (not is_sup) and (h_lock == 1 or imp >= 8 or acc >= 3 or cat in _CANONICAL_CATEGORIES):
            d["neural_cosine"] = float(rng.uniform(0.58, 0.92))
            d["bm25_norm"] = float(rng.uniform(0.45, 0.88))
            d["cross_score"] = float(rng.uniform(0.62, 0.95))
            d["ppr_score"] = float(rng.uniform(0.08, 0.30))
            features.append(extract_ranking_features(d, target_workspace="all"))
            labels.append(1.0)
            weights.append(1.0)
            pos_mem_ids.append(mid)
            pos_count += 1
        elif is_sup or (imp <= 4 and acc == 0):
            d["neural_cosine"] = float(rng.uniform(0.05, 0.32))
            d["bm25_norm"] = float(rng.uniform(0.05, 0.38))
            d["cross_score"] = float(rng.uniform(0.03, 0.25))
            d["ppr_score"] = float(rng.uniform(0.0, 0.06))
            features.append(extract_ranking_features(d, target_workspace="all"))
            labels.append(0.0)
            weights.append(1.0)
            neg_count += 1

    # 3. Ensure balanced synthetic contrast samples for fresh / sparse DBs
    while pos_count < 12:
        vec = np.array(
            [
                rng.uniform(0.62, 0.95),
                rng.uniform(0.50, 0.92),
                rng.uniform(0.15, 0.65),
                rng.uniform(0.70, 1.00),
                rng.uniform(0.30, 0.90),
                rng.uniform(0.65, 1.00),
                float(rng.choice([0.0, 1.0])),
                1.0,
                float(rng.choice([0.0, 1.0])),
                rng.uniform(0.15, 0.75),
                1.0,
                rng.uniform(0.68, 0.97),
            ],
            dtype=np.float32,
        )
        features.append(vec)
        labels.append(1.0)
        weights.append(1.0)
        pos_count += 1

    while neg_count < 12:
        vec = np.array(
            [
                rng.uniform(0.04, 0.34),
                rng.uniform(0.02, 0.38),
                rng.uniform(0.00, 0.12),
                rng.uniform(0.10, 0.40),
                rng.uniform(0.00, 0.10),
                rng.uniform(0.10, 0.55),
                0.0,
                float(rng.choice([0.0, 1.0])),
                0.0,
                rng.uniform(0.00, 0.15),
                float(rng.choice([0.0, 1.0])),
                rng.uniform(0.02, 0.28),
            ],
            dtype=np.float32,
        )
        features.append(vec)
        labels.append(0.0)
        weights.append(1.0)
        neg_count += 1

    X = np.vstack(features).astype(np.float32)
    y = np.asarray(labels, dtype=np.float32)
    w = np.asarray(weights, dtype=np.float32)
    return X, y, w, list(dict.fromkeys(pos_mem_ids))


def _apply_hebbian_edge_sync(db: Any, positive_mem_ids: List[int]) -> int:
    """Strengthen `memory_edges.weight` among positively rated / high-salience memories."""
    if not positive_mem_ids:
        return 0
    top_ids = positive_mem_ids[:30]
    updated = 0
    ph = ",".join("?" for _ in top_ids)

    with db._connect() as conn:
        existing_edges = conn.execute(
            f"""
            SELECT id, weight FROM memory_edges
            WHERE (valid_to IS NULL OR valid_to = '')
              AND (source_id IN ({ph}) OR target_id IN ({ph}));
            """,
            (*top_ids, *top_ids),
        ).fetchall()

        for er in existing_edges:
            old_w = float(er["weight"] if er["weight"] is not None else 0.85)
            new_w = min(1.0, round(old_w + 0.05, 4))
            if new_w > old_w:
                conn.execute(
                    "UPDATE memory_edges SET weight = ? WHERE id = ?;",
                    (new_w, int(er["id"])),
                )
                updated += 1

        # If no existing edges were updated and we have >= 2 positive memories in the same workspace,
        # reinforce co-activation with a lightweight edge
        if updated == 0 and len(top_ids) >= 2:
            rows = conn.execute(
                f"SELECT id, workspace FROM memories WHERE id IN ({ph}) ORDER BY id DESC LIMIT 6;",
                (*top_ids,),
            ).fetchall()
            by_ws: Dict[str, List[int]] = {}
            for r in rows:
                by_ws.setdefault(str(r["workspace"] or "global"), []).append(int(r["id"]))
            for ws_ids in by_ws.values():
                if len(ws_ids) >= 2:
                    a_id, b_id = ws_ids[0], ws_ids[1]
                    conn.execute(
                        """
                        INSERT INTO memory_edges (source_id, target_id, relation, weight, valid_from, valid_to)
                        VALUES (?, ?, 'CO_ACTIVATED', 0.65, ?, NULL)
                        ON CONFLICT(source_id, target_id, relation) DO UPDATE SET
                            weight = MIN(1.0, COALESCE(memory_edges.weight, 0.65) + 0.05);
                        """,
                        (a_id, b_id, _utc_now_iso()),
                    )
                    updated += 1
                    break

    return updated


def train_personal_neural_ranker(
    db: Any,
    epochs: int = 40,
    lr: float = 0.015,
    hebbian_sync: bool = True,
) -> Dict[str, Any]:
    """
    Train the Personal 2-Layer Neural MLP (`12 -> 24 -> 12 -> 1`) on `brain.db`
    feedback and salience signals, persist weights + metrics to `neural_model_state`,
    and optionally perform Hebbian edge strengthening.
    """
    ensure_neural_tables(db)
    t0 = time.perf_counter()

    X, y, w, pos_ids = _build_mlp_training_dataset(db)

    # Continue from existing weights if already trained, or fresh deterministic init
    model: Optional[PersonalNeuralRanker] = None
    prev_epochs_total = 0
    with db._connect() as conn:
        prev_state = _get_state_json(conn, "personal_mlp", None)
    if isinstance(prev_state, dict) and "weights" in prev_state:
        try:
            model = PersonalNeuralRanker.from_dict(prev_state["weights"])
            prev_epochs_total = int(prev_state.get("epochs_total") or 0)
        except Exception:
            model = None
    if model is None:
        model = PersonalNeuralRanker(seed=42, use_prior=False)

    fit_res = model.fit(X, y, sample_weights=w, epochs=epochs, lr=lr, weight_decay=1e-4)

    hebbian_updated = _apply_hebbian_edge_sync(db, pos_ids) if hebbian_sync else 0

    now_iso = _utc_now_iso()
    epochs_total = prev_epochs_total + int(epochs)
    state_payload = {
        "model_version": "engram_mlp_v11.0",
        "architecture": "12->24(ReLU)->12(ReLU)->1(Sigmoid)",
        "params_count": model.params_count,
        "epochs_total": epochs_total,
        "last_epochs": int(epochs),
        "samples_count": int(X.shape[0]),
        "initial_loss": fit_res["initial_loss"],
        "final_loss": fit_res["final_loss"],
        "accuracy": fit_res["accuracy"],
        "loss_history": fit_res["loss_history"],
        "feature_importances": fit_res["feature_importances"],
        "hebbian_edges_updated": hebbian_updated,
        "updated_at": now_iso,
        "weights": model.to_dict(),
    }

    with db._connect() as conn:
        _set_state_json(conn, "personal_mlp", state_payload)

    db_key = os.path.abspath(str(getattr(db, "db_path", "default")))
    _MLP_CACHE[db_key] = (time.monotonic(), model)

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    return {
        "ok": True,
        "epochs": int(epochs),
        "epochs_total": epochs_total,
        "samples_count": int(X.shape[0]),
        "initial_loss": fit_res["initial_loss"],
        "final_loss": fit_res["final_loss"],
        "accuracy": fit_res["accuracy"],
        "loss_history": fit_res["loss_history"],
        "feature_importances": fit_res["feature_importances"],
        "hebbian_edges_updated": hebbian_updated,
        "elapsed_ms": elapsed_ms,
        "params_count": model.params_count,
    }


def _load_or_default_mlp(db: Any) -> Tuple[PersonalNeuralRanker, bool]:
    db_key = os.path.abspath(str(getattr(db, "db_path", "default")))
    with db._connect() as conn:
        state = _get_state_json(conn, "personal_mlp", None)
    if isinstance(state, dict) and "weights" in state:
        try:
            model = PersonalNeuralRanker.from_dict(state["weights"])
            _MLP_CACHE[db_key] = (time.monotonic(), model)
            return model, True
        except Exception:
            pass
    return PersonalNeuralRanker(seed=42, use_prior=True), False


def score_candidates_mlp(
    db: Any,
    candidates: List[Dict[str, Any]],
    target_workspace: str = "all",
) -> List[Dict[str, Any]]:
    """
    Run vectorized NumPy forward pass through the Personal 2-Layer MLP
    and annotate each candidate with `mlp_score` and `final_neural_score`.
    """
    ensure_neural_tables(db)
    if not candidates:
        return []

    model, is_trained = _load_or_default_mlp(db)
    feat_mat = np.vstack(
        [extract_ranking_features(c, target_workspace=target_workspace) for c in candidates]
    ).astype(np.float32)

    mlp_preds = model.forward(feat_mat)

    out: List[Dict[str, Any]] = []
    for idx, cand in enumerate(candidates):
        item = dict(cand)
        mlp_sc = float(mlp_preds[idx])
        cross_sc = float(item.get("cross_score") or 0.0)
        cos_sc = max(0.0, float(item.get("neural_cosine") or 0.0))

        # Blend trained MLP score cleanly with direct semantic & cross-encoder signals
        if is_trained:
            final_sc = 0.55 * mlp_sc + 0.30 * cross_sc + 0.15 * cos_sc
        else:
            final_sc = 0.40 * mlp_sc + 0.35 * cross_sc + 0.25 * cos_sc

        item["mlp_score"] = round(mlp_sc, 4)
        item["final_neural_score"] = round(final_sc, 4)
        item["mlp_trained"] = is_trained
        out.append(item)

    out.sort(
        key=lambda c: (
            float(c.get("final_neural_score") or 0.0),
            float(c.get("cross_score") or 0.0),
            int(c.get("importance") or 0),
        ),
        reverse=True,
    )
    return out


def record_neural_feedback(
    db: Any,
    memory_id: int,
    useful: bool = True,
    query: str = "",
    source: str = "ui",
) -> Dict[str, Any]:
    """
    Log explicit user thumbs-up (`useful=True`) or thumbs-down (`useful=False`)
    into `neural_feedback_log`, gently adjusting memory salience in `memories`.
    """
    ensure_neural_tables(db)
    mid = int(memory_id)
    useful_int = 1 if useful else 0
    now_iso = _utc_now_iso()

    with db._connect() as conn:
        mem_row = conn.execute(
            "SELECT id, importance, access_count, COALESCE(human_locked, 0) AS human_locked FROM memories WHERE id = ?;",
            (mid,),
        ).fetchone()
        if mem_row is None:
            return {"ok": False, "error": f"Memory #{mid} not found", "memory_id": mid}

        conn.execute(
            """
            INSERT INTO neural_feedback_log (memory_id, query, useful, source, created_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            (mid, (query or "")[:500], useful_int, (source or "ui")[:64], now_iso),
        )

        if useful:
            conn.execute(
                """
                UPDATE memories
                SET access_count = COALESCE(access_count, 0) + 1,
                    last_accessed = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (mid,),
            )
        elif int(mem_row["human_locked"] or 0) == 0:
            conn.execute(
                """
                UPDATE memories
                SET importance = MAX(1, COALESCE(importance, 3) - 1)
                WHERE id = ?;
                """,
                (mid,),
            )

        stats = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN useful = 1 THEN 1 ELSE 0 END) AS pos,
                   SUM(CASE WHEN useful = 0 THEN 1 ELSE 0 END) AS neg
            FROM neural_feedback_log;
            """
        ).fetchone()
        mem_after = conn.execute(
            "SELECT importance, access_count FROM memories WHERE id = ?;",
            (mid,),
        ).fetchone()

    return {
        "ok": True,
        "memory_id": mid,
        "useful": bool(useful),
        "importance": int(mem_after["importance"] or 3),
        "access_count": int(mem_after["access_count"] or 0),
        "feedback_total": int(stats["total"] or 0),
        "feedback_positive": int(stats["pos"] or 0),
        "feedback_negative": int(stats["neg"] or 0),
    }


# ---------------------------------------------------------------------------
# 5. Layer 4 — Neural Intent Router & Semantic Correction Detector Head
# ---------------------------------------------------------------------------

def _get_intent_centroids() -> Tuple[Dict[str, np.ndarray], str]:
    model_name, dims = _active_encoder_info()
    key = (model_name, dims)
    if key in _INTENT_PROTOTYPES_CACHE:
        return _INTENT_PROTOTYPES_CACHE[key], model_name

    centroids: Dict[str, np.ndarray] = {}
    used_model = model_name
    for intent_name, exemplars in _INTENT_EXEMPLARS.items():
        mat, used_model, _ = encode_texts(list(exemplars), use_onnx=True)
        centroid = np.mean(mat, axis=0, keepdims=True)
        centroids[intent_name] = _l2_normalize_matrix(centroid)[0]

    _INTENT_PROTOTYPES_CACHE[(used_model, int(next(iter(centroids.values())).shape[0]))] = centroids
    return centroids, used_model


def classify_neural_intent(text: str) -> Dict[str, Any]:
    """
    Zero-shot prototype cosine intent classifier across 6 engineering intents:
    `architecture_design`, `bug_debugging`, `ui_frontend`, `security_audit`,
    `quick_lookup`, `micro_confirmation`.
    """
    clean = (text or "").strip()
    centroids, backend_model = _get_intent_centroids()
    if not clean:
        return {
            "ok": True,
            "intent": "quick_lookup",
            "confidence": 0.5,
            "recommended_tier": INTENT_TIERS["quick_lookup"],
            "scores": {k: 0.0 for k in INTENT_TIERS},
            "backend": backend_model,
        }

    q_mat, backend_model, _ = encode_texts([clean], use_onnx=True)
    q_vec = q_mat[0]

    raw_scores: Dict[str, float] = {
        intent_name: float(np.dot(q_vec, c_vec))
        for intent_name, c_vec in centroids.items()
    }

    # Short micro-confirmation boost for ultra-short acknowledgements
    words = re.findall(r"[a-zA-ZÀ-ÿ0-9_]+", clean.lower())
    if len(words) <= 2 and len(clean) <= 18:
        micro_vocab = {"ok", "okay", "sim", "yes", "no", "nao", "não", "thanks", "obrigado", "obrigada", "done", "feito", "continua", "proceed", "go", "fix"}
        if any(w in micro_vocab for w in words):
            raw_scores["micro_confirmation"] = raw_scores.get("micro_confirmation", 0.0) + 0.30

    # Temperature-scaled softmax for calibrated confidence
    names = list(raw_scores.keys())
    vals = np.array([raw_scores[n] for n in names], dtype=np.float64)
    logits = (vals - np.max(vals)) * 8.0
    probs = np.exp(logits)
    probs = probs / np.sum(probs)

    best_idx = int(np.argmax(vals))
    best_intent = names[best_idx]

    return {
        "ok": True,
        "intent": best_intent,
        "confidence": round(float(probs[best_idx]), 4),
        "recommended_tier": INTENT_TIERS.get(best_intent, "balanced"),
        "scores": {n: round(float(raw_scores[n]), 4) for n in names},
        "backend": backend_model,
    }


def _get_correction_centroids() -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, str]:
    model_name, dims = _active_encoder_info()
    key = (model_name, dims)
    if key in _CORRECTION_PROTOTYPES_CACHE:
        c_pos, c_neg, pos_mat, neg_mat = _CORRECTION_PROTOTYPES_CACHE[key]
        return c_pos, c_neg, pos_mat, neg_mat, model_name

    pos_mat, used_model, used_dims = encode_texts(list(_CORRECTION_EXEMPLARS), use_onnx=True)
    neg_mat, _, _ = encode_texts(list(_NEUTRAL_QUERY_EXEMPLARS), use_onnx=True)
    c_pos = _l2_normalize_matrix(np.mean(pos_mat, axis=0, keepdims=True))[0]
    c_neg = _l2_normalize_matrix(np.mean(neg_mat, axis=0, keepdims=True))[0]

    _CORRECTION_PROTOTYPES_CACHE[(used_model, used_dims)] = (c_pos, c_neg, pos_mat, neg_mat)
    return c_pos, c_neg, pos_mat, neg_mat, used_model


def classify_neural_correction(text: str, threshold: float = 0.42) -> Dict[str, Any]:
    """
    Detect bilingual (PT-PT + EN) user corrections / rule-preferences semantically
    by comparing centroid + nearest-prototype similarity against Correction vs Neutral Query heads.
    """
    clean = (text or "").strip()
    c_pos, c_neg, pos_mat, neg_mat, backend_model = _get_correction_centroids()
    if not clean:
        return {
            "ok": True,
            "is_correction": False,
            "correction_prob": 0.0,
            "similarity": 0.0,
            "margin": 0.0,
            "backend": backend_model,
        }

    q_mat, backend_model, _ = encode_texts([clean], use_onnx=True)
    q_vec = q_mat[0]

    cent_pos = float(np.dot(q_vec, c_pos))
    cent_neg = float(np.dot(q_vec, c_neg))
    max_pos = float(np.max(pos_mat @ q_vec))
    max_neg = float(np.max(neg_mat @ q_vec))

    sim_pos = 0.45 * cent_pos + 0.55 * max_pos
    sim_neg = 0.45 * cent_neg + 0.55 * max_neg
    margin = sim_pos - sim_neg

    # Calibrated probability combining centroid+prototype margin and threshold exceedance
    logit = margin * 12.0 + (sim_pos - float(threshold)) * 4.5
    corr_prob = 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, logit))))
    is_corr = bool((sim_pos >= float(threshold) and margin > 0.01) or (margin >= 0.05 and corr_prob >= 0.55))

    return {
        "ok": True,
        "is_correction": is_corr,
        "correction_prob": round(float(corr_prob), 4),
        "similarity": round(sim_pos, 4),
        "neutral_similarity": round(sim_neg, 4),
        "margin": round(margin, 4),
        "backend": backend_model,
    }


# ---------------------------------------------------------------------------
# 6. Unified End-to-End Pipeline & Status
# ---------------------------------------------------------------------------

def neural_retrieve_and_rerank(
    db: Any,
    query: str,
    workspace: str = "all",
    top_k: int = 6,
    use_cross_encoder: bool = True,
    use_mlp: bool = True,
    as_of: str = "",
) -> Dict[str, Any]:
    """
    Full 4-layer Engram v11.0 retrieval pipeline:
    1. Bi-Encoder KNN (`sqlite-vec` / NumPy) + BM25 (`db.search_memories`) + PPR/graph degrees
    2. Cross-Encoder Neural Reranker
    3. Personal 2-Layer MLP Learning-to-Rank
    4. Neural Intent Router + Semantic Correction Detector
    """
    ensure_neural_tables(db)
    t0 = time.perf_counter()
    ws = _norm_ws(db, workspace)
    k = max(1, int(top_k))
    as_of_clean = (as_of or "").strip()
    is_hist = bool(as_of_clean and as_of_clean.lower() != "now")

    intent_res = classify_neural_intent(query)
    corr_res = classify_neural_correction(query)

    # Stage 1a: Bi-Encoder Vector KNN
    vec_hits = vector_knn_search(
        db,
        query=query,
        workspace=ws,
        top_k=max(k * 3, 18),
        as_of=as_of_clean,
    )
    sqlite_vec_used = any(h.get("vector_backend") == "sqlite_vec" for h in vec_hits)

    merged: Dict[int, Dict[str, Any]] = {}
    for vh in vec_hits:
        mid = int(vh["id"])
        item = dict(vh)
        item.setdefault("bm25_norm", 0.0)
        item.setdefault("ppr_score", 0.0)
        merged[mid] = item

    # Stage 1b: BM25 / FTS5 hybrid candidates from BrainDB
    if hasattr(db, "search_memories"):
        try:
            bm25_hits = db.search_memories(
                query,
                workspace=(None if ws == "all" else ws),
                n_results=max(k * 3, 16),
                update_stats=False,
                include_superseded=is_hist,
            )
            max_bm = max((float(h.get("score") or h.get("final_score") or 0.0) for h in bm25_hits), default=1.0) or 1.0
            for bh in bm25_hits:
                mid = int(bh["id"])
                if is_hist:
                    # Respect historical as_of filtering strictly when requested
                    continue
                bm_val = max(0.0, min(1.0, float(bh.get("score") or bh.get("final_score") or 0.0) / max_bm))
                if mid in merged:
                    merged[mid]["bm25_norm"] = round(bm_val, 4)
                    if bh.get("ppr_score") is not None:
                        merged[mid]["ppr_score"] = max(float(merged[mid].get("ppr_score") or 0.0), float(bh["ppr_score"]))
                    if bh.get("causal_degree") is not None:
                        merged[mid]["causal_degree"] = bh["causal_degree"]
                    if bh.get("ebbinghaus_retention") is not None:
                        merged[mid]["ebbinghaus_retention"] = bh["ebbinghaus_retention"]
                else:
                    item = dict(bh)
                    item.pop("embedding_json", None)
                    item["bm25_norm"] = round(bm_val, 4)
                    item.setdefault("neural_cosine", float(bh.get("semantic_similarity") or 0.0))
                    merged[mid] = item
        except Exception:
            pass

    # Stage 1c: Enrich causal graph degree for merged candidates
    if merged:
        cids = list(merged.keys())
        ph = ",".join("?" for _ in cids)
        with db._connect() as conn:
            deg_rows = conn.execute(
                f"""
                SELECT source_id, target_id FROM memory_edges
                WHERE (valid_to IS NULL OR valid_to = '')
                  AND (source_id IN ({ph}) OR target_id IN ({ph}));
                """,
                (*cids, *cids),
            ).fetchall()
        deg_counts: Dict[int, int] = {}
        for dr in deg_rows:
            s_id, t_id = int(dr["source_id"]), int(dr["target_id"])
            deg_counts[s_id] = deg_counts.get(s_id, 0) + 1
            deg_counts[t_id] = deg_counts.get(t_id, 0) + 1
        for cid, item in merged.items():
            if item.get("causal_degree") is None:
                item["causal_degree"] = deg_counts.get(cid, 0)

    candidates = list(merged.values())

    # Stage 2: Cross-Encoder Neural Reranker
    if use_cross_encoder and candidates:
        reranked = rerank_candidates(query, candidates, top_k=max(k * 2, 12))
        reranker_backend = str(reranked[0].get("reranker_backend") or "lexical_bilinear_fallback")
    else:
        reranked = []
        for c in candidates:
            item = dict(c)
            cos = max(0.0, float(item.get("neural_cosine") or 0.0))
            bm = max(0.0, float(item.get("bm25_norm") or 0.0))
            item["cross_score"] = round(min(1.0, 0.65 * cos + 0.35 * bm), 4)
            item["reranker_backend"] = "skipped"
            reranked.append(item)
        reranked.sort(key=lambda x: float(x.get("cross_score") or 0.0), reverse=True)
        reranked = reranked[: max(k * 2, 12)]
        reranker_backend = "skipped"

    # Stage 3: Personal 2-Layer Neural MLP
    mlp_trained = False
    if use_mlp and reranked:
        scored = score_candidates_mlp(db, reranked, target_workspace=ws)
        mlp_trained = bool(scored[0].get("mlp_trained")) if scored else False
    else:
        scored = []
        for c in reranked:
            item = dict(c)
            cross_sc = float(item.get("cross_score") or 0.0)
            cos_sc = max(0.0, float(item.get("neural_cosine") or 0.0))
            imp_sc = min(1.0, float(item.get("importance") or 3) / 10.0)
            item["mlp_score"] = 0.0
            item["final_neural_score"] = round(0.55 * cross_sc + 0.35 * cos_sc + 0.10 * imp_sc, 4)
            item["mlp_trained"] = False
            scored.append(item)
        scored.sort(key=lambda x: float(x.get("final_neural_score") or 0.0), reverse=True)

    final_results = scored[:k]
    bi_backend, _ = _active_encoder_info()
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    return {
        "ok": True,
        "query": query,
        "workspace": ws,
        "elapsed_ms": elapsed_ms,
        "bi_encoder_backend": bi_backend,
        "reranker_backend": reranker_backend,
        "mlp_trained": mlp_trained,
        "sqlite_vec_used": sqlite_vec_used,
        "intent": intent_res,
        "correction": corr_res,
        "results": final_results,
    }


def get_neural_cortex_status(db: Any, workspace: str = "all") -> Dict[str, Any]:
    """
    Return complete diagnostic status across all 4 layers of Engram v11.0 Local Neural Cortex.
    """
    ensure_neural_tables(db)
    ws = _norm_ws(db, workspace)
    ws_sql = "" if ws == "all" else "AND m.workspace = ?"
    ws_params: Tuple[Any, ...] = () if ws == "all" else (ws,)

    sqlite_vec_avail = importlib.util.find_spec("sqlite_vec") is not None
    sqlite_vec_loaded = False
    vec_dims = None
    mlp_state: Optional[Dict[str, Any]] = None

    with db._connect() as conn:
        sqlite_vec_loaded = _try_load_sqlite_vec(conn)
        vec_dims = _get_state_json(conn, "vec_dims", None)
        mlp_state = _get_state_json(conn, "personal_mlp", None)

        total_active = int(
            conn.execute(
                f"""
                SELECT COUNT(*) AS c FROM memories m
                WHERE m.superseded_by IS NULL
                  AND (m.valid_to IS NULL OR m.valid_to = '')
                  {ws_sql};
                """,
                ws_params,
            ).fetchone()["c"]
        )
        indexed_vectors = int(
            conn.execute(
                f"""
                SELECT COUNT(*) AS c
                FROM memories m
                JOIN neural_onnx_vectors v ON v.memory_id = m.id
                WHERE m.superseded_by IS NULL
                  AND (m.valid_to IS NULL OR m.valid_to = '')
                  {ws_sql};
                """,
                ws_params,
            ).fetchone()["c"]
        )
        fb_row = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN useful = 1 THEN 1 ELSE 0 END) AS pos,
                   SUM(CASE WHEN useful = 0 THEN 1 ELSE 0 END) AS neg
            FROM neural_feedback_log;
            """
        ).fetchone()

    active_bi_model, active_dims = _active_encoder_info()
    coverage_pct = round((indexed_vectors / total_active) * 100.0, 2) if total_active > 0 else 100.0
    mlp_trained = isinstance(mlp_state, dict) and "weights" in mlp_state

    layer1 = {
        "model_name": DEFAULT_BI_ENCODER,
        "active_backend": active_bi_model,
        "backend": active_bi_model,
        "dims": active_dims,
        "dim": active_dims,
        "ready": _BI_ENCODER_READY,
        "onnx_ready": _BI_ENCODER_READY,
        "onnx_loaded": _BI_ENCODER_READY,
        "cached_on_disk": _is_fastembed_model_cached(DEFAULT_BI_ENCODER),
        "offline_forced": _offline_forced(),
        "sqlite_vec_available": sqlite_vec_avail,
        "sqlite_vec_loaded": sqlite_vec_loaded,
        "vec_dims": vec_dims,
        "indexed_vectors": indexed_vectors,
        "total_active": total_active,
        "coverage_pct": coverage_pct,
    }
    layer2 = {
        "model_name": DEFAULT_CROSS_ENCODER,
        "active_backend": "onnx_cross_encoder" if _CROSS_ENCODER_READY else "lexical_bilinear_fallback",
        "backend": "ONNX Reranker" if _CROSS_ENCODER_READY else "Bilinear",
        "ready": _CROSS_ENCODER_READY,
        "onnx_ready": _CROSS_ENCODER_READY,
        "onnx_loaded": _CROSS_ENCODER_READY,
        "cached_on_disk": _is_fastembed_model_cached(DEFAULT_CROSS_ENCODER),
    }
    fb_total = int(fb_row["total"] or 0)
    epochs_tot = int((mlp_state or {}).get("epochs_total", 0))
    loss_hist = (mlp_state or {}).get("loss_history", [])
    feat_imp = (mlp_state or {}).get("feature_importances", {})
    layer3 = {
        "trained": mlp_trained,
        "ready": mlp_trained,
        "model_version": (mlp_state or {}).get("model_version", "untrained_prior"),
        "architecture": "12->24(ReLU)->12(ReLU)->1(Sigmoid)",
        "params_count": (mlp_state or {}).get("params_count", PersonalNeuralRanker(use_prior=False).params_count),
        "epochs_total": epochs_tot,
        "epochs": epochs_tot,
        "samples_count": int((mlp_state or {}).get("samples_count", 0)),
        "initial_loss": (mlp_state or {}).get("initial_loss"),
        "final_loss": (mlp_state or {}).get("final_loss"),
        "accuracy": (mlp_state or {}).get("accuracy"),
        "loss_history": loss_hist,
        "feature_importances": feat_imp,
        "hebbian_edges_updated": int((mlp_state or {}).get("hebbian_edges_updated", 0)),
        "updated_at": (mlp_state or {}).get("updated_at"),
        "feedback_total": fb_total,
        "feedback_count": fb_total,
        "feedback_positive": int(fb_row["pos"] or 0),
        "feedback_negative": int(fb_row["neg"] or 0),
    }
    layer4 = {
        "intent_classes": list(INTENT_TIERS.keys()),
        "intents": list(INTENT_TIERS.keys()),
        "num_intents": len(INTENT_TIERS),
        "correction_head_ready": True,
        "feedback_count": fb_total,
        "backend": active_bi_model,
    }
    sqlite_vec_obj = {
        "available": sqlite_vec_avail,
        "loaded": sqlite_vec_loaded,
        "enabled": sqlite_vec_loaded,
        "dims": vec_dims,
        "indexed_count": indexed_vectors,
        "total_active": total_active,
        "coverage_pct": coverage_pct,
    }

    return {
        "ok": True,
        "workspace": ws,
        "layer1_bi_encoder": layer1,
        "layer2_cross_encoder": layer2,
        "layer3_personal_mlp": layer3,
        "layer4_heads": layer4,
        "bi_encoder": layer1,
        "sqlite_vec": sqlite_vec_obj,
        "cross_encoder": layer2,
        "personal_mlp": layer3,
        "intent_head": layer4,
        "loss_history": loss_hist,
        "feature_importances": feat_imp,
        "feedback_count": fb_total,
    }


__all__ = [
    "DEFAULT_BI_ENCODER",
    "DEFAULT_CROSS_ENCODER",
    "FEATURE_NAMES",
    "INTENT_TIERS",
    "PersonalNeuralRanker",
    "ensure_neural_tables",
    "warmup_neural_models",
    "encode_texts",
    "index_onnx_vectors",
    "vector_knn_search",
    "rerank_candidates",
    "extract_ranking_features",
    "train_personal_neural_ranker",
    "score_candidates_mlp",
    "record_neural_feedback",
    "classify_neural_intent",
    "classify_neural_correction",
    "neural_retrieve_and_rerank",
    "get_neural_cortex_status",
]

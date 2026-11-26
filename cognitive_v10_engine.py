"""
Engram v10.0 Core Cognitive Engine
Zero-mandatory-dependency cognitive pillars on top of SQLite BrainDB:
1. Bi-Temporal Knowledge Graph (Graphiti/Zep valid_from / valid_to / SUPERSEDES)
2. Local Neural Embeddings (Ollama / sqlite-vec / 256-D bilingual PT-PT <-> EN-EN fallback)
3. HippoRAG Personalized PageRank (PPR) Multi-Hop Retrieval (<10ms)
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
import sqlite3
import struct
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Constants & Bilingual Concept Clusters (256-D Dense Semantic Space)
# ---------------------------------------------------------------------------

OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

OLLAMA_EMBED_MODEL_DIMS: Dict[str, int] = {
    "nomic-embed-text": 768,
    "bge-m3": 1024,
    "mxbai-embed-large": 1024,
    "all-minilm": 384,
    "snowflake-arctic-embed": 1024,
    "qwen3-embedding": 1024,
}

_EMBED_BACKEND_CACHE: Dict[str, Any] = {"ts": 0.0, "data": None}
_BACKEND_CACHE_TTL_SEC = 60.0

_STOPWORDS: Set[str] = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "was", "were",
    "with", "will", "into", "using", "use", "via",
    "o", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "por", "para", "com", "sem", "sob", "sobre",
    "que", "e", "ou", "se", "ao", "aos", "a", "pelo", "pela", "como", "mais",
    "foi", "sao", "ser", "esta", "este", "isso", "isto", "tem", "ter",
}

_SUPERSEDING_PHRASES: Tuple[str, ...] = (
    "trocámos", "trocam", "trocamos",
    "mudámos", "mudam", "mudamos",
    "substituímos", "substituim", "substituimos",
    "renomeámos", "renomeam", "renomeamos",
    "replaced", "migrated from", "renamed", "deprecated",
    "instead of", "em vez de",
)

# 32 canonical bilingual PT-PT <-> EN-EN engineering concepts -> dims 224..255
_BILINGUAL_CONCEPTS: Tuple[Tuple[str, ...], ...] = (
    # 0: memory
    ("memory", "memories", "memoria", "memorias", "remember", "recall", "lembrar", "recordar", "forget", "esquecer", "engram", "episodic", "episodica", "semantic", "semantica", "working memory"),
    # 1: latency / speed / performance
    ("latency", "latencia", "speed", "velocidade", "fast", "rapido", "rapida", "rapidez", "slow", "lento", "lenta", "lentidao", "performance", "desempenho", "optimize", "optimization", "otimizacao", "otimizar", "benchmark", "throughput", "acelerar", "accelerate"),
    # 2: database / storage
    ("database", "databases", "db", "base de dados", "bases de dados", "dados", "sqlite", "sql", "postgres", "postgresql", "mysql", "schema", "esquema", "table", "tabela", "tabelas", "query", "queries", "consulta", "consultas", "index", "indice", "indices", "migration", "migracao", "orm", "pragma", "wal", "sqlite_vec"),
    # 3: security / auth
    ("security", "seguranca", "auth", "authentication", "autenticacao", "authorization", "autorizacao", "jwt", "oauth", "oauth2", "token", "password", "senha", "secret", "segredo", "encryption", "encriptacao", "rls", "vulnerability", "vulnerabilidade", "xss", "sqli", "rbac"),
    # 4: graph / ppr / multi-hop
    ("graph", "grafo", "grafos", "edge", "edges", "aresta", "arestas", "node", "nodes", "no", "nos", "network", "rede", "ppr", "pagerank", "hipporag", "traversal", "multi-hop", "multihop", "causal", "relation", "relacao"),
    # 5: voice / speech
    ("voice", "voz", "speech", "fala", "audio", "stt", "tts", "whisper", "microphone", "microfone", "transcribe", "transcricao"),
    # 6: cache
    ("cache", "caching", "redis", "memcached", "ttl", "invalidation", "invalidacao", "memoize", "hit", "miss"),
    # 7: quota / budget / tokens
    ("quota", "rate limit", "limite", "token diet", "tokens", "budget", "orcamento", "cost", "custo", "window", "janela", "economizar", "economy"),
    # 8: router / model
    ("router", "routing", "roteamento", "route", "rota", "fallback", "model", "modelo", "modelos", "ollama", "local llm", "gemini", "claude", "deepseek", "llama"),
    # 9: deploy / server / infra
    ("deploy", "deployment", "release", "launch", "docker", "kubernetes", "pipeline", "production", "producao", "server", "servidor", "hosting", "infra", "infraestrutura"),
    # 10: bug / error / fix
    ("bug", "bugs", "erro", "erros", "error", "errors", "crash", "failure", "falha", "exception", "excecao", "fix", "corrigir", "correcao", "debug", "depurar", "traceback", "stacktrace"),
    # 11: test / verification
    ("test", "tests", "teste", "testes", "pytest", "unittest", "assert", "smoke", "coverage", "cobertura", "mock", "regression", "regressao", "verify", "verificar"),
    # 12: refactor / architecture
    ("refactor", "refatorar", "refatoracao", "clean", "cleanup", "limpeza", "modular", "architecture", "arquitetura", "pattern", "padrao", "design"),
    # 13: ui / frontend
    ("ui", "ux", "interface", "frontend", "html", "css", "javascript", "typescript", "react", "dashboard", "painel", "component", "componente", "layout", "theme", "tema", "dark mode", "modal"),
    # 14: api / backend / mcp
    ("api", "rest", "graphql", "endpoint", "http", "https", "webhook", "mcp", "rpc", "request", "response", "backend", "fastapi", "flask"),
    # 15: temporal / history / supersede
    ("temporal", "bi-temporal", "bitemporal", "history", "historico", "timeline", "cronologia", "supersede", "supersedes", "valid_from", "valid_to", "as_of", "version", "versao", "outdated", "desatualizado", "obsoleto"),
    # 16: embedding / vector / search
    ("embedding", "embeddings", "vector", "vetor", "vetores", "cosine", "cosseno", "similarity", "similaridade", "neural", "dense", "bm25", "fts5", "search", "pesquisa", "busca", "retrieval", "recuperacao"),
    # 17: file / storage / path
    ("file", "files", "ficheiro", "ficheiros", "arquivo", "arquivos", "directory", "diretorio", "pasta", "path", "caminho", "disk", "disco", "blob", "upload", "download", "read", "write"),
    # 18: concurrency / async
    ("async", "asyncio", "thread", "threading", "process", "multiprocessing", "lock", "mutex", "parallel", "paralelo", "concurrent", "concorrente", "queue", "fila", "worker"),
    # 19: config / env
    ("config", "configuration", "configuracao", "settings", "definicoes", "env", "environment", "ambiente", "variable", "variavel", "flag", "flags", "option", "opcao"),
    # 20: agent / swarm
    ("agent", "agente", "agentes", "subagent", "subagente", "swarm", "enxame", "orchestrator", "orquestrador", "coordinator", "coordenador", "lane", "delegation", "delegacao"),
    # 21: logging / telemetry / observability
    ("log", "logs", "logging", "registo", "metrics", "metricas", "trace", "tracing", "telemetry", "telemetria", "monitor", "audit", "auditoria", "status", "estado"),
    # 22: git / vcs
    ("git", "commit", "branch", "ramo", "merge", "diff", "pull request", "pr", "repo", "repository", "repositorio", "checkout", "revert"),
    # 23: build / package
    ("build", "compile", "compilar", "bundle", "package", "pacote", "dependency", "dependencia", "dependencias", "pip", "npm", "uv", "wheel"),
    # 24: user / human / directive
    ("user", "utilizador", "usuario", "human", "humano", "preference", "preferencia", "directive", "diretiva", "rule", "regra", "feedback"),
    # 25: docs / markdown / plan
    ("doc", "docs", "documentation", "documentacao", "markdown", "readme", "spec", "especificacao", "plan", "plano", "comment", "comentario"),
    # 26: data format / serialization
    ("parse", "parser", "serialize", "json", "yaml", "xml", "csv", "struct", "binary", "binario", "float32", "encode", "decode"),
    # 27: network / socket
    ("socket", "tcp", "udp", "dns", "proxy", "tls", "ssl", "localhost", "port", "porta", "timeout", "urllib"),
    # 28: state / session / checkpoint
    ("state", "session", "sessao", "checkpoint", "context", "contexto", "turn", "turno", "conversation", "conversa", "persist", "persistencia"),
    # 29: math / scoring / ranking
    ("algorithm", "algoritmo", "matrix", "matriz", "score", "pontuacao", "weight", "peso", "rank", "ranking", "threshold", "limiar", "decay", "decaimento", "jaccard", "rrf"),
    # 30: schedule / cron / timer
    ("schedule", "agendar", "cron", "timer", "temporizador", "periodic", "periodico", "background", "segundo plano", "interval", "intervalo"),
    # 31: os / shell / cli
    ("windows", "linux", "macos", "sistema operativo", "powershell", "bash", "shell", "terminal", "cli", "command", "comando"),
)


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _strip_accents(text: str) -> str:
    """Fast ASCII folding for Portuguese/Latin diacritics without unicodedata overhead."""
    trans = str.maketrans(
        "áàâãäéèêëíìîïóòôõöúùûüçñÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ",
        "aaaaaeeeeiiiiooooouuuucnAAAAAEEEEIIIIOOOOOUUUUCN",
    )
    return text.translate(trans)


def _norm_ws(db: Any, workspace: str) -> str:
    raw = (workspace or "").strip()
    if not raw or raw.lower() in ("all", "*"):
        return "all"
    if ("/" in raw or "\\" in raw) and hasattr(db, "normalize_workspace"):
        return db.normalize_workspace(raw)
    return raw.lower()


def _normalize_ts(ts: str, end_of_day: bool = False) -> str:
    """Normalize YYYY-MM-DD or SQLite 'YYYY-MM-DD HH:MM:SS' or ISO-8601 into 'YYYY-MM-DDTHH:MM:SSZ'."""
    s = (ts or "").strip()
    if not s:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return f"{s}T23:59:59Z" if end_of_day else f"{s}T00:00:00Z"
    if len(s) >= 19 and s[10] == " ":
        s = s[:10] + "T" + s[11:]
    if len(s) == 19:
        s = s + "Z"
    return s


def _ts_cmp_key(ts: str) -> str:
    """Return 19-char 'YYYY-MM-DDTHH:MM:SS' key for lexicographical UTC comparison."""
    norm = _normalize_ts(ts, end_of_day=False)
    return norm[:19] if len(norm) >= 19 else norm


def _significant_tokens(text: str) -> Set[str]:
    clean = _strip_accents((text or "").lower())
    return {
        tok
        for tok in re.findall(r"[a-z0-9_]{2,}", clean)
        if tok not in _STOPWORDS
    }


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    union = len(a | b)
    return (len(a & b) / union) if union else 0.0


def _l2_normalize(vec: List[float]) -> List[float]:
    norm_sq = sum(v * v for v in vec)
    if norm_sq <= 1e-12:
        return vec
    inv = 1.0 / math.sqrt(norm_sq)
    return [v * inv for v in vec]


def _signed_hash_index(token: str, dim_count: int) -> Tuple[int, float]:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    val = int.from_bytes(digest, "little", signed=False)
    idx = val % dim_count
    sign = 1.0 if ((val >> 63) & 1) == 0 else -1.0
    return idx, sign


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return dot / math.sqrt(na * nb)


def _compute_dense_256d(text: str) -> List[float]:
    """
    Deterministic 256-D float32 bilingual (PT-PT <-> EN-EN) semantic embedding:
    - Dims   0..159 (160): word unigrams + bigrams via signed feature hashing (energy 0.35)
    - Dims 160..223 ( 64): char 3-grams & 4-grams via signed feature hashing (energy 0.20)
    - Dims 224..255 ( 32): 32 canonical bilingual semantic concepts (energy 0.45)
    """
    clean = _strip_accents((text or "").lower())
    raw_words = re.findall(r"[a-z0-9_]+", clean)
    tokens = [w for w in raw_words if len(w) >= 2 and w not in _STOPWORDS]
    token_set = set(tokens)

    # 1. Subspace 0..159: unigrams + bigrams
    lex_vec = [0.0] * 160
    for tok in tokens:
        idx, sign = _signed_hash_index(f"w:{tok}", 160)
        lex_vec[idx] += sign
        # Also hash 5-char stem for morphological PT/EN bridging
        if len(tok) >= 6:
            s_idx, s_sign = _signed_hash_index(f"st:{tok[:5]}", 160)
            lex_vec[s_idx] += s_sign * 0.5
    for i in range(len(tokens) - 1):
        bg = f"bg:{tokens[i]}_{tokens[i + 1]}"
        idx, sign = _signed_hash_index(bg, 160)
        lex_vec[idx] += sign * 1.15

    # 2. Subspace 160..223: character 3-grams and 4-grams
    char_vec = [0.0] * 64
    compact = " ".join(tokens) if tokens else re.sub(r"\s+", " ", clean).strip()
    if len(compact) >= 3:
        for n in (3, 4):
            if len(compact) >= n:
                for i in range(len(compact) - n + 1):
                    gram = compact[i : i + n]
                    if " " in gram and gram.strip() == gram:
                        continue
                    idx, sign = _signed_hash_index(f"c{n}:{gram}", 64)
                    char_vec[idx] += sign

    # 3. Subspace 224..255: 32 canonical bilingual PT-PT <-> EN-EN concept clusters
    concept_vec = [0.0] * 32
    padded_clean = f" {clean} "
    for c_idx, keywords in enumerate(_BILINGUAL_CONCEPTS):
        hits = 0.0
        for kw in keywords:
            kw_clean = _strip_accents(kw.lower())
            if " " in kw_clean:
                if f" {kw_clean} " in padded_clean:
                    hits += 1.5
            elif kw_clean in token_set:
                hits += 1.0
            elif len(kw_clean) >= 6 and any(t.startswith(kw_clean[:6]) for t in token_set):
                hits += 0.65
        if hits > 0.0:
            concept_vec[c_idx] = min(2.0, math.sqrt(hits))

    # Balance subspace energies and L2-normalize full 256-D unit vector
    lex_norm = math.sqrt(sum(v * v for v in lex_vec))
    char_norm = math.sqrt(sum(v * v for v in char_vec))
    con_norm = math.sqrt(sum(v * v for v in concept_vec))

    full_vec = [0.0] * 256
    if lex_norm > 1e-12:
        scale = math.sqrt(0.35) / lex_norm
        for i in range(160):
            full_vec[i] = lex_vec[i] * scale
    if char_norm > 1e-12:
        scale = math.sqrt(0.20) / char_norm
        for i in range(64):
            full_vec[160 + i] = char_vec[i] * scale
    if con_norm > 1e-12:
        scale = math.sqrt(0.45) / con_norm
        for i in range(32):
            full_vec[224 + i] = concept_vec[i] * scale

    return _l2_normalize(full_vec)


def _row_to_clean_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    # Keep payloads concise without large raw embedding JSON arrays if present
    d.pop("embedding_json", None)
    return d


def _build_as_of_clause(as_of: str, include_superseded: bool, alias: str = "") -> Tuple[str, List[Any]]:
    prefix = f"{alias}." if alias else ""
    as_of_clean = (as_of or "").strip()
    if as_of_clean and as_of_clean.lower() != "now":
        as_of_norm = _normalize_ts(as_of_clean, end_of_day=True)
        as_of_cmp = _ts_cmp_key(as_of_norm)
        clause = (
            f"REPLACE(SUBSTR(COALESCE(NULLIF({prefix}valid_from, ''), {prefix}created_at, ''), 1, 19), ' ', 'T') <= ? "
            f"AND ({prefix}valid_to IS NULL OR {prefix}valid_to = '' "
            f"OR REPLACE(SUBSTR({prefix}valid_to, 1, 19), ' ', 'T') > ?)"
        )
        return clause, [as_of_cmp, as_of_cmp]
    if not include_superseded:
        clause = f"({prefix}valid_to IS NULL OR {prefix}valid_to = '') AND {prefix}superseded_by IS NULL"
        return clause, []
    return "1=1", []


# ---------------------------------------------------------------------------
# Schema Initialization
# ---------------------------------------------------------------------------

def ensure_v10_tables(db: Any) -> None:
    """
    Safely ensure Engram v10.0 bi-temporal columns on `memories` & `memory_edges`,
    temporal indexes, and `memory_neural_embeddings` table without dropping data.
    """
    with db._connect() as conn:
        mem_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(memories);").fetchall()
        }
        for col_name, col_def in (
            ("valid_from", "TEXT DEFAULT NULL"),
            ("valid_to", "TEXT DEFAULT NULL"),
            ("invalidated_by", "INTEGER DEFAULT NULL"),
            ("superseded_by", "INTEGER DEFAULT NULL"),
        ):
            if col_name not in mem_cols:
                conn.execute(f"ALTER TABLE memories ADD COLUMN {col_name} {col_def};")

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_valid_to ON memories(workspace, valid_to);"
        )

        edge_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(memory_edges);").fetchall()
        }
        for col_name, col_def in (
            ("valid_from", "TEXT DEFAULT NULL"),
            ("valid_to", "TEXT DEFAULT NULL"),
        ):
            if col_name not in edge_cols:
                conn.execute(f"ALTER TABLE memory_edges ADD COLUMN {col_name} {col_def};")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_neural_embeddings (
                memory_id INTEGER PRIMARY KEY,
                model_name TEXT NOT NULL,
                dims INTEGER NOT NULL,
                vector_blob BLOB NOT NULL,
                norm REAL NOT NULL DEFAULT 1.0,
                updated_at TEXT NOT NULL
            );
            """
        )


# ---------------------------------------------------------------------------
# Pillar 1 — Bi-Temporal Knowledge Graph (Graphiti / Zep Pattern)
# ---------------------------------------------------------------------------

def store_temporal_fact(
    db: Any,
    topic: str,
    fact: str,
    workspace: str = "brain_mcp",
    category: str = "decision",
    tags: str = "",
    importance: int = 8,
    valid_from: str = "",
    auto_supersede: bool = True,
) -> Dict[str, Any]:
    """
    Store a new fact with explicit bi-temporal validity (`valid_from`) and optionally
    auto-supersede outdated active facts in the same workspace, creating directed
    `SUPERSEDES` edges while preserving full historical rows.
    """
    ensure_v10_tables(db)

    clean_topic = topic.strip()
    clean_fact = fact.strip()
    if hasattr(db, "strip_control_tags") and hasattr(db, "redact_secrets"):
        clean_topic = db.redact_secrets(db.strip_control_tags(clean_topic))
        clean_fact = db.redact_secrets(db.strip_control_tags(clean_fact))

    ws = _norm_ws(db, workspace)
    if ws == "all":
        ws = "global"

    imp_val = max(1, min(10, int(importance)))
    now_iso = (
        _normalize_ts(valid_from, end_of_day=False)
        if (valid_from or "").strip()
        else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    norm_new_topic = re.sub(r"\s+", " ", clean_topic.lower())
    new_topic_tokens = _significant_tokens(clean_topic)
    new_fact_tokens = _significant_tokens(clean_fact)
    new_all_tokens = new_topic_tokens | new_fact_tokens
    fact_low_folded = _strip_accents(clean_fact.lower())
    has_supersede_cue = any(
        _strip_accents(phrase) in fact_low_folded for phrase in _SUPERSEDING_PHRASES
    )

    resolved_tier = (
        db.classify_memory_tier(category, clean_topic, clean_fact, tags)
        if hasattr(db, "classify_memory_tier")
        else "semantic"
    )
    sem_vec = (
        db.compute_semantic_vector(f"{clean_topic} {clean_fact} {tags} {category}")
        if hasattr(db, "compute_semantic_vector")
        else []
    )
    emb_json = json.dumps(sem_vec)
    emb_bq = (
        db.quantize_vector_128bit(sem_vec)
        if hasattr(db, "quantize_vector_128bit") and sem_vec
        else ""
    )

    base_hash = (
        db._compute_hash(clean_topic, clean_fact, ws)
        if hasattr(db, "_compute_hash")
        else hashlib.sha256(f"{ws}::{clean_topic.lower()}::{clean_fact.lower()}".encode("utf-8")).hexdigest()[:32]
    )

    superseded_ids: List[int] = []
    new_id: Optional[int] = None

    with db._connect() as conn:
        active_rows = conn.execute(
            """
            SELECT id, topic, fact, category, tags, importance, valid_from, COALESCE(human_locked, 0) AS human_locked
            FROM memories
            WHERE workspace = ?
              AND superseded_by IS NULL
              AND (valid_to IS NULL OR valid_to = '')
            ORDER BY id DESC;
            """,
            (ws,),
        ).fetchall()

        # Idempotency check: exact same active topic & fact already current
        for row in active_rows:
            r_topic = re.sub(r"\s+", " ", str(row["topic"] or "").strip().lower())
            r_fact = str(row["fact"] or "").strip()
            if r_topic == norm_new_topic and r_fact == clean_fact:
                new_id = int(row["id"])
                break

        if new_id is None:
            if auto_supersede:
                for row in active_rows:
                    old_id = int(row["id"])
                    old_topic = str(row["topic"] or "")
                    old_fact = str(row["fact"] or "")
                    if old_fact.strip() == clean_fact:
                        continue
                    norm_old_topic = re.sub(r"\s+", " ", old_topic.strip().lower())
                    old_cat = str(row["category"] or "").lower()
                    old_topic_tokens = _significant_tokens(old_topic)
                    old_all_tokens = old_topic_tokens | _significant_tokens(old_fact)

                    same_topic_changed = norm_old_topic == norm_new_topic
                    same_cat_jaccard = (
                        old_cat == category.lower()
                        and len(new_topic_tokens & old_topic_tokens) >= 1
                        and _jaccard(new_topic_tokens, old_topic_tokens) >= 0.50
                    )
                    explicit_phrase_match = (
                        has_supersede_cue
                        and len(new_all_tokens & old_all_tokens) >= 1
                    )

                    if same_topic_changed or same_cat_jaccard or explicit_phrase_match:
                        superseded_ids.append(old_id)

            # Ensure unique fact_hash even if re-introducing a previously superseded fact
            f_hash = base_hash
            hash_conflict = conn.execute(
                "SELECT id FROM memories WHERE fact_hash = ?;", (f_hash,)
            ).fetchone()
            if hash_conflict is not None:
                f_hash = hashlib.sha256(
                    f"{base_hash}::{now_iso}::{time.monotonic_ns()}".encode("utf-8")
                ).hexdigest()[:32]

            cur = conn.execute(
                """
                INSERT INTO memories (
                    topic, fact, workspace, category, tags, importance, tier,
                    fact_hash, embedding_json, embedding_bq, source_agent,
                    trust_score, human_locked, valid_from, valid_to, last_accessed
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'bitemporal_v10', 0.9, 0, ?, NULL, CURRENT_TIMESTAMP);
                """,
                (
                    clean_topic,
                    clean_fact,
                    ws,
                    category,
                    tags,
                    imp_val,
                    resolved_tier,
                    f_hash,
                    emb_json,
                    emb_bq,
                    now_iso,
                ),
            )
            new_id = int(cur.lastrowid)

            for old_id in superseded_ids:
                conn.execute(
                    """
                    UPDATE memories
                    SET superseded_by = ?,
                        invalidated_by = ?,
                        valid_to = ?,
                        valid_until = ?
                    WHERE id = ?;
                    """,
                    (new_id, new_id, now_iso, now_iso, old_id),
                )
                conn.execute(
                    """
                    INSERT INTO memory_edges (source_id, target_id, relation, weight, valid_from, valid_to)
                    VALUES (?, ?, 'SUPERSEDES', 1.0, ?, NULL)
                    ON CONFLICT(source_id, target_id, relation) DO UPDATE SET
                        weight = 1.0,
                        valid_from = COALESCE(memory_edges.valid_from, excluded.valid_from);
                    """,
                    (new_id, old_id, now_iso),
                )

    # Fast (<1ms) dense 256-D neural embedding update for new_id
    neural_vec, neural_model = compute_neural_embedding(
        f"{clean_topic} {clean_fact} {tags} {category}",
        allow_network=False,
    )
    dims = len(neural_vec)
    blob = struct.pack(f"{dims}f", *neural_vec)
    norm_val = math.sqrt(sum(x * x for x in neural_vec)) or 1.0
    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with db._connect() as conn:
        conn.execute(
            """
            INSERT INTO memory_neural_embeddings (memory_id, model_name, dims, vector_blob, norm, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(memory_id) DO UPDATE SET
                model_name = excluded.model_name,
                dims = excluded.dims,
                vector_blob = excluded.vector_blob,
                norm = excluded.norm,
                updated_at = excluded.updated_at;
            """,
            (new_id, neural_model, dims, blob, norm_val, updated_at),
        )

    return {
        "ok": True,
        "memory_id": new_id,
        "topic": clean_topic,
        "workspace": ws,
        "valid_from": now_iso,
        "superseded_ids": superseded_ids,
        "supersedes_edges": len(superseded_ids),
    }


def query_temporal_as_of(
    db: Any,
    query: str = "",
    workspace: str = "all",
    as_of: str = "",
    include_superseded: bool = False,
    limit: int = 12,
) -> Dict[str, Any]:
    """
    Time-travel query across bi-temporal memories.
    - `as_of="YYYY-MM-DD"` or ISO timestamp returns facts valid at that exact moment.
    - `as_of=""` or `"now"` returns current truth (unless `include_superseded=True`).
    """
    ensure_v10_tables(db)
    ws = _norm_ws(db, workspace)
    temporal_clause, temporal_params = _build_as_of_clause(as_of, include_superseded)

    ws_clause = "1=1" if ws == "all" else "workspace = ?"
    ws_params: List[Any] = [] if ws == "all" else [ws]

    with db._connect() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM memories
            WHERE {ws_clause}
              AND {temporal_clause}
            ORDER BY importance DESC, id DESC;
            """,
            (*ws_params, *temporal_params),
        ).fetchall()

        active_count = conn.execute(
            f"""
            SELECT COUNT(*) AS c FROM memories
            WHERE {ws_clause}
              AND superseded_by IS NULL
              AND (valid_to IS NULL OR valid_to = '');
            """,
            (*ws_params,),
        ).fetchone()["c"]

        superseded_count = conn.execute(
            f"""
            SELECT COUNT(*) AS c FROM memories
            WHERE {ws_clause}
              AND (superseded_by IS NOT NULL OR (valid_to IS NOT NULL AND valid_to != ''));
            """,
            (*ws_params,),
        ).fetchone()["c"]

        chain_ws_filter = "" if ws == "all" else "AND (s.workspace = ? OR t.workspace = ?)"
        chain_params: Tuple[Any, ...] = () if ws == "all" else (ws, ws)
        chain_rows = conn.execute(
            f"""
            SELECT e.id AS edge_id,
                   e.source_id,
                   s.topic AS source_topic,
                   s.fact AS source_fact,
                   e.target_id,
                   t.topic AS target_topic,
                   t.fact AS target_fact,
                   e.relation,
                   COALESCE(e.valid_from, e.created_at) AS valid_from
            FROM memory_edges e
            JOIN memories s ON s.id = e.source_id
            JOIN memories t ON t.id = e.target_id
            WHERE UPPER(e.relation) = 'SUPERSEDES'
              {chain_ws_filter}
            ORDER BY e.id DESC
            LIMIT 20;
            """,
            chain_params,
        ).fetchall()

    results = [_row_to_clean_dict(r) for r in rows]
    clean_query = (query or "").strip()
    if clean_query and results:
        q_tokens = _significant_tokens(clean_query)
        q_vec = _compute_dense_256d(clean_query)
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for item in results:
            blob_txt = f"{item.get('topic', '')} {item.get('fact', '')} {item.get('tags', '')}"
            t_tokens = _significant_tokens(blob_txt)
            overlap = len(q_tokens & t_tokens)
            substr_bonus = 1.0 if _strip_accents(clean_query.lower()) in _strip_accents(blob_txt.lower()) else 0.0
            d_vec = _compute_dense_256d(blob_txt)
            cos = _cosine(q_vec, d_vec)
            rel_score = overlap * 1.5 + substr_bonus * 2.0 + cos * 3.0 + float(item.get("importance") or 3) * 0.05
            item["temporal_relevance"] = round(rel_score, 4)
            scored.append((rel_score, item))
        scored.sort(key=lambda pair: (pair[0], int(pair[1].get("importance") or 0), int(pair[1].get("id") or 0)), reverse=True)
        results = [pair[1] for pair in scored[: max(1, int(limit))]]
    else:
        results = results[: max(1, int(limit))]

    supersession_chain = [dict(cr) for cr in chain_rows]

    return {
        "ok": True,
        "as_of": (as_of or "").strip() or "now",
        "workspace": ws,
        "active_count": int(active_count),
        "superseded_count": int(superseded_count),
        "results": results,
        "supersession_chain": supersession_chain,
    }


def get_temporal_history(
    db: Any,
    memory_id: int = 0,
    topic: str = "",
    workspace: str = "all",
) -> Dict[str, Any]:
    """
    Walk `SUPERSEDES` / `superseded_by` / `invalidated_by` links backward and forward
    to return the full chronological evolution chain of a memory or topic.
    """
    ensure_v10_tables(db)
    ws = _norm_ws(db, workspace)

    with db._connect() as conn:
        start_ids: List[int] = []
        if memory_id and int(memory_id) > 0:
            row = conn.execute(
                "SELECT id FROM memories WHERE id = ?;", (int(memory_id),)
            ).fetchone()
            if row:
                start_ids.append(int(row["id"]))
        elif (topic or "").strip():
            clean_top = topic.strip()
            ws_sql = "" if ws == "all" else "AND workspace = ?"
            params: List[Any] = [clean_top]
            if ws != "all":
                params.append(ws)
            rows = conn.execute(
                f"""
                SELECT id FROM memories
                WHERE LOWER(TRIM(topic)) = LOWER(TRIM(?)) {ws_sql}
                ORDER BY id DESC;
                """,
                params,
            ).fetchall()
            if not rows:
                like_params: List[Any] = [f"%{clean_top}%"]
                if ws != "all":
                    like_params.append(ws)
                rows = conn.execute(
                    f"""
                    SELECT id FROM memories
                    WHERE LOWER(topic) LIKE LOWER(?) {ws_sql}
                    ORDER BY id DESC LIMIT 5;
                    """,
                    like_params,
                ).fetchall()
            start_ids = [int(r["id"]) for r in rows]

        if not start_ids:
            return {
                "ok": True,
                "memory_id": int(memory_id or 0),
                "topic": topic,
                "workspace": ws,
                "chain_length": 0,
                "chain": [],
                "edges": [],
            }

        visited: Set[int] = set(start_ids)
        queue: deque[int] = deque(start_ids)
        collected_edges: Dict[Tuple[int, int, str], Dict[str, Any]] = {}

        while queue:
            curr = queue.popleft()
            row = conn.execute(
                "SELECT id, superseded_by, invalidated_by FROM memories WHERE id = ?;",
                (curr,),
            ).fetchone()
            if row:
                for col in ("superseded_by", "invalidated_by"):
                    nxt = row[col]
                    if nxt and int(nxt) not in visited:
                        visited.add(int(nxt))
                        queue.append(int(nxt))

            prev_rows = conn.execute(
                "SELECT id FROM memories WHERE superseded_by = ? OR invalidated_by = ?;",
                (curr, curr),
            ).fetchall()
            for pr in prev_rows:
                pid = int(pr["id"])
                if pid not in visited:
                    visited.add(pid)
                    queue.append(pid)

            edge_rows = conn.execute(
                """
                SELECT id, source_id, target_id, relation, weight,
                       COALESCE(valid_from, created_at) AS valid_from
                FROM memory_edges
                WHERE (source_id = ? OR target_id = ?)
                  AND UPPER(relation) = 'SUPERSEDES';
                """,
                (curr, curr),
            ).fetchall()
            for er in edge_rows:
                s_id = int(er["source_id"])
                t_id = int(er["target_id"])
                rel = str(er["relation"])
                collected_edges[(s_id, t_id, rel)] = dict(er)
                for neighbor in (s_id, t_id):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

        ph = ",".join("?" for _ in visited)
        mem_rows = conn.execute(
            f"SELECT * FROM memories WHERE id IN ({ph});",
            tuple(visited),
        ).fetchall()

    chain = [_row_to_clean_dict(r) for r in mem_rows]
    chain.sort(
        key=lambda m: (
            _ts_cmp_key(str(m.get("valid_from") or m.get("created_at") or "")),
            int(m.get("id") or 0),
        )
    )
    return {
        "ok": True,
        "memory_id": int(memory_id or 0),
        "topic": topic,
        "workspace": ws,
        "chain_length": len(chain),
        "chain": chain,
        "edges": list(collected_edges.values()),
    }


# ---------------------------------------------------------------------------
# Pillar 2 — Local Neural Embeddings (Ollama / sqlite-vec / 256-D Fallback)
# ---------------------------------------------------------------------------

def _check_v11_onnx_status() -> Tuple[bool, bool]:
    """Check `fastembed` availability and warm ONNX Bi-Encoder state without network I/O."""
    onnx_fastembed_available = importlib.util.find_spec("fastembed") is not None
    onnx_bi_encoder_ready = False
    try:
        import neural_cortex_engine as _nce
        onnx_bi_encoder_ready = bool(getattr(_nce, "_BI_ENCODER_READY", False))
    except Exception:
        onnx_bi_encoder_ready = False
    return onnx_fastembed_available, onnx_bi_encoder_ready


def detect_local_embedding_backend(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Probe local Ollama (60s TTL cache, 180ms timeout), `sqlite_vec`, and
    Engram v11.0 `fastembed` ONNX readiness without triggering network downloads.
    Falls back cleanly to deterministic 256-D bilingual embeddings when offline.
    """
    now = time.monotonic()
    cached = _EMBED_BACKEND_CACHE.get("data")
    if (
        not force_refresh
        and cached is not None
        and (now - float(_EMBED_BACKEND_CACHE.get("ts", 0.0))) < _BACKEND_CACHE_TTL_SEC
    ):
        out = dict(cached)
        onnx_avail, onnx_ready = _check_v11_onnx_status()
        out["onnx_fastembed_available"] = onnx_avail
        out["onnx_bi_encoder_ready"] = onnx_ready
        return out

    sqlite_vec_available = importlib.util.find_spec("sqlite_vec") is not None
    onnx_fastembed_available, onnx_bi_encoder_ready = _check_v11_onnx_status()
    found_models: List[str] = []

    try:
        req = urllib.request.Request(OLLAMA_TAGS_URL, method="GET")
        with urllib.request.urlopen(req, timeout=0.18) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        for entry in payload.get("models", []):
            name = str(entry.get("name") or "").strip()
            base = name.split(":")[0].lower()
            if any(base == known or known in base for known in OLLAMA_EMBED_MODEL_DIMS):
                found_models.append(name)
    except Exception:
        found_models = []

    if found_models:
        chosen = found_models[0]
        base = chosen.split(":")[0].lower()
        dims = 768
        for known, known_dims in OLLAMA_EMBED_MODEL_DIMS.items():
            if base == known or known in base:
                dims = known_dims
                break
        result: Dict[str, Any] = {
            "backend": "ollama",
            "model_name": chosen,
            "dims": dims,
            "ollama_embed_models": found_models,
            "sqlite_vec_available": sqlite_vec_available,
            "onnx_fastembed_available": onnx_fastembed_available,
            "onnx_bi_encoder_ready": onnx_bi_encoder_ready,
        }
    else:
        result = {
            "backend": "engram_dense_256d",
            "model_name": "engram_dense_256d",
            "dims": 256,
            "ollama_embed_models": [],
            "sqlite_vec_available": sqlite_vec_available,
            "onnx_fastembed_available": onnx_fastembed_available,
            "onnx_bi_encoder_ready": onnx_bi_encoder_ready,
        }

    _EMBED_BACKEND_CACHE["ts"] = now
    _EMBED_BACKEND_CACHE["data"] = dict(result)
    return result


def compute_neural_embedding(
    text: str,
    backend_info: Optional[Dict[str, Any]] = None,
    allow_network: bool = True,
) -> Tuple[List[float], str]:
    """
    Compute L2-normalized dense neural embedding via local Ollama when enabled & reachable,
    or deterministic 256-D bilingual PT-PT <-> EN-EN semantic embedding (`engram_dense_256d`).
    """
    if backend_info is None:
        info = (
            detect_local_embedding_backend()
            if allow_network
            else {"backend": "engram_dense_256d", "model_name": "engram_dense_256d", "dims": 256}
        )
    else:
        info = backend_info

    if info.get("backend") == "ollama" and allow_network:
        model_name = str(info.get("model_name") or "nomic-embed-text")
        try:
            body = json.dumps({"model": model_name, "prompt": (text or "")[:4000]}).encode("utf-8")
            req = urllib.request.Request(
                OLLAMA_EMBED_URL,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            raw_vec = data.get("embedding")
            if isinstance(raw_vec, list) and len(raw_vec) >= 64:
                vec = _l2_normalize([float(x) for x in raw_vec])
                return vec, model_name
        except Exception:
            pass

    return _compute_dense_256d(text), "engram_dense_256d"


def index_neural_embeddings(
    db: Any,
    workspace: str = "all",
    limit: int = 200,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Index active memories into `memory_neural_embeddings` using local Ollama or `engram_dense_256d`.
    """
    ensure_v10_tables(db)
    t0 = time.perf_counter()
    ws = _norm_ws(db, workspace)
    backend_info = detect_local_embedding_backend()
    backend = str(backend_info["backend"])
    model_name = str(backend_info["model_name"])
    dims = int(backend_info["dims"])
    allow_net = backend == "ollama"

    ws_sql = "" if ws == "all" else "AND m.workspace = ?"
    ws_params: Tuple[Any, ...] = () if ws == "all" else (ws,)

    with db._connect() as conn:
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
                (*ws_params, max(1, int(limit))),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""
                SELECT m.id, m.topic, m.fact, m.tags, m.category
                FROM memories m
                LEFT JOIN memory_neural_embeddings e ON e.memory_id = m.id
                WHERE m.superseded_by IS NULL
                  AND (m.valid_to IS NULL OR m.valid_to = '')
                  {ws_sql}
                  AND (e.memory_id IS NULL OR e.model_name != ?)
                ORDER BY m.importance DESC, m.id DESC
                LIMIT ?;
                """,
                (*ws_params, model_name, max(1, int(limit))),
            ).fetchall()

    indexed_count = 0
    actual_model = model_name
    actual_dims = dims
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if rows:
        upserts: List[Tuple[int, str, int, bytes, float, str]] = []
        for r in rows:
            txt = f"{r['topic']} {r['fact']} {r['tags'] or ''} {r['category'] or ''}"
            vec, used_model = compute_neural_embedding(
                txt, backend_info=backend_info, allow_network=allow_net
            )
            v_dims = len(vec)
            blob = struct.pack(f"{v_dims}f", *vec)
            norm_val = math.sqrt(sum(x * x for x in vec)) or 1.0
            upserts.append((int(r["id"]), used_model, v_dims, blob, norm_val, now_iso))
            actual_model = used_model
            actual_dims = v_dims
            indexed_count += 1

        with db._connect() as conn:
            conn.executemany(
                """
                INSERT INTO memory_neural_embeddings (memory_id, model_name, dims, vector_blob, norm, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    model_name = excluded.model_name,
                    dims = excluded.dims,
                    vector_blob = excluded.vector_blob,
                    norm = excluded.norm,
                    updated_at = excluded.updated_at;
                """,
                upserts,
            )

    with db._connect() as conn:
        total_indexed = int(
            conn.execute(
                f"""
                SELECT COUNT(*) AS c
                FROM memories m
                JOIN memory_neural_embeddings e ON e.memory_id = m.id
                WHERE m.superseded_by IS NULL
                  AND (m.valid_to IS NULL OR m.valid_to = '')
                  {ws_sql};
                """,
                ws_params,
            ).fetchone()["c"]
        )

    coverage_pct = round((total_indexed / total_active) * 100.0, 2) if total_active > 0 else 100.0
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    return {
        "ok": True,
        "indexed_count": indexed_count,
        "total_indexed": total_indexed,
        "total_active": total_active,
        "coverage_pct": coverage_pct,
        "backend": backend if actual_model != "engram_dense_256d" else "engram_dense_256d",
        "model_name": actual_model,
        "dims": actual_dims,
        "elapsed_ms": elapsed_ms,
    }


def neural_vector_search(
    db: Any,
    query: str,
    workspace: str = "all",
    top_k: int = 10,
    as_of: str = "",
) -> List[Dict[str, Any]]:
    """
    Search temporally valid memories using cosine similarity over `memory_neural_embeddings`.
    """
    ensure_v10_tables(db)
    ws = _norm_ws(db, workspace)
    temporal_clause, temporal_params = _build_as_of_clause(as_of, include_superseded=False, alias="m")
    ws_clause = "1=1" if ws == "all" else "m.workspace = ?"
    ws_params: List[Any] = [] if ws == "all" else [ws]

    with db._connect() as conn:
        rows = conn.execute(
            f"""
            SELECT m.*, e.model_name AS emb_model_name, e.dims AS emb_dims,
                   e.vector_blob AS emb_blob, e.norm AS emb_norm
            FROM memories m
            JOIN memory_neural_embeddings e ON e.memory_id = m.id
            WHERE {ws_clause}
              AND {temporal_clause};
            """,
            (*ws_params, *temporal_params),
        ).fetchall()

    if not rows:
        return []

    query_vecs_by_key: Dict[Tuple[str, int], Tuple[List[float], float]] = {}
    scored: List[Tuple[float, Dict[str, Any]]] = []

    for r in rows:
        m_name = str(r["emb_model_name"] or "engram_dense_256d")
        dims = int(r["emb_dims"] or 256)
        cache_key = (m_name, dims)
        if cache_key not in query_vecs_by_key:
            if m_name == "engram_dense_256d" or dims == 256:
                qv, _ = compute_neural_embedding(query, allow_network=False)
            else:
                qv, used_m = compute_neural_embedding(
                    query,
                    backend_info={"backend": "ollama", "model_name": m_name, "dims": dims},
                    allow_network=True,
                )
                if len(qv) != dims:
                    qv = []
            q_norm = math.sqrt(sum(x * x for x in qv)) if qv else 0.0
            query_vecs_by_key[cache_key] = (qv, q_norm)

        q_vec, q_norm = query_vecs_by_key[cache_key]
        if not q_vec or q_norm <= 1e-12 or len(q_vec) != dims:
            continue

        blob = r["emb_blob"]
        expected_bytes = dims * 4
        if not blob or len(blob) != expected_bytes:
            continue

        m_vec = struct.unpack(f"{dims}f", blob)
        m_norm = float(r["emb_norm"] or 1.0) or 1.0
        dot = sum(a * b for a, b in zip(q_vec, m_vec))
        cos = dot / (q_norm * m_norm)

        d = _row_to_clean_dict(r)
        d.pop("emb_blob", None)
        d.pop("emb_norm", None)
        d.pop("emb_dims", None)
        emb_m = d.pop("emb_model_name", m_name)
        d["embedding_model"] = emb_m
        d["neural_cosine"] = round(cos, 4)
        scored.append((cos, d))

    scored.sort(key=lambda pair: (pair[0], int(pair[1].get("importance") or 0), int(pair[1].get("id") or 0)), reverse=True)
    return [pair[1] for pair in scored[: max(1, int(top_k))]]


# ---------------------------------------------------------------------------
# Pillar 3 — HippoRAG Personalized PageRank (PPR) Multi-Hop Retrieval
# ---------------------------------------------------------------------------

def _index_missing_fast_256d(db: Any, ws: str, max_items: int = 60) -> None:
    """Fast (<5ms) on-demand 256-D indexing for unindexed active memories."""
    ws_sql = "" if ws == "all" else "AND m.workspace = ?"
    ws_params: Tuple[Any, ...] = () if ws == "all" else (ws,)
    with db._connect() as conn:
        missing = conn.execute(
            f"""
            SELECT m.id, m.topic, m.fact, m.tags, m.category
            FROM memories m
            LEFT JOIN memory_neural_embeddings e ON e.memory_id = m.id
            WHERE m.superseded_by IS NULL
              AND (m.valid_to IS NULL OR m.valid_to = '')
              {ws_sql}
              AND e.memory_id IS NULL
            ORDER BY m.importance DESC, m.id DESC
            LIMIT ?;
            """,
            (*ws_params, max_items),
        ).fetchall()
        if not missing:
            return
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        upserts: List[Tuple[int, str, int, bytes, float, str]] = []
        for r in missing:
            vec = _compute_dense_256d(f"{r['topic']} {r['fact']} {r['tags'] or ''} {r['category'] or ''}")
            blob = struct.pack("256f", *vec)
            norm_val = math.sqrt(sum(x * x for x in vec)) or 1.0
            upserts.append((int(r["id"]), "engram_dense_256d", 256, blob, norm_val, now_iso))
        conn.executemany(
            """
            INSERT OR IGNORE INTO memory_neural_embeddings (memory_id, model_name, dims, vector_blob, norm, updated_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            upserts,
        )


def hipporag_ppr_retrieve(
    db: Any,
    query: str,
    workspace: str = "all",
    top_k: int = 8,
    damping: float = 0.85,
    iterations: int = 12,
    hops: int = 2,
    as_of: str = "",
) -> Dict[str, Any]:
    """
    HippoRAG-style Personalized PageRank over `memory_edges` for multi-hop memory retrieval.
    Discovers indirect memories (`A -> B -> C`) even when `C` shares zero lexical tokens with query.
    """
    ensure_v10_tables(db)
    t0 = time.perf_counter()
    ws = _norm_ws(db, workspace)
    as_of_clean = (as_of or "").strip()
    is_historical_as_of = bool(as_of_clean and as_of_clean.lower() != "now")

    # Auto-index up to 60 unindexed active memories on the fly via fast local 256-D
    _index_missing_fast_256d(db, ws, max_items=60)

    temporal_clause, temporal_params = _build_as_of_clause(as_of_clean, include_superseded=False)
    ws_clause = "1=1" if ws == "all" else "workspace = ?"
    ws_params: List[Any] = [] if ws == "all" else [ws]

    with db._connect() as conn:
        valid_rows = conn.execute(
            f"""
            SELECT * FROM memories
            WHERE {ws_clause}
              AND {temporal_clause};
            """,
            (*ws_params, *temporal_params),
        ).fetchall()

        if is_historical_as_of:
            as_of_cmp = _ts_cmp_key(_normalize_ts(as_of_clean, end_of_day=True))
            edge_rows = conn.execute(
                """
                SELECT source_id, target_id, COALESCE(relation, 'evolves') AS relation,
                       COALESCE(weight, 0.85) AS weight
                FROM memory_edges
                WHERE (valid_from IS NULL OR valid_from = '' OR REPLACE(SUBSTR(valid_from, 1, 19), ' ', 'T') <= ?)
                  AND (valid_to IS NULL OR valid_to = '' OR REPLACE(SUBSTR(valid_to, 1, 19), ' ', 'T') > ?);
                """,
                (as_of_cmp, as_of_cmp),
            ).fetchall()
        else:
            edge_rows = conn.execute(
                """
                SELECT source_id, target_id, COALESCE(relation, 'evolves') AS relation,
                       COALESCE(weight, 0.85) AS weight
                FROM memory_edges
                WHERE valid_to IS NULL OR valid_to = '';
                """
            ).fetchall()

    valid_map: Dict[int, Dict[str, Any]] = {int(r["id"]): _row_to_clean_dict(r) for r in valid_rows}
    if not valid_map:
        return {
            "ok": True,
            "query": query,
            "workspace": ws,
            "as_of": as_of_clean or "now",
            "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            "seeds_count": 0,
            "graph_nodes_visited": 0,
            "multi_hop_discoveries": 0,
            "results": [],
        }

    # Step 1: Collect seed scores combining db.search_memories + neural_vector_search + lexical check
    seed_scores: Dict[int, float] = {}
    q_tokens = _significant_tokens(query)
    q_clean_folded = _strip_accents((query or "").lower())

    if hasattr(db, "search_memories"):
        try:
            bm25_hits = db.search_memories(
                query,
                workspace=(None if ws == "all" else ws),
                n_results=max(top_k, 10),
                update_stats=False,
                include_superseded=is_historical_as_of,
            )
            max_bm25 = max((float(h.get("final_score") or 0.0) for h in bm25_hits), default=1.0) or 1.0
            for h in bm25_hits:
                hid = int(h["id"])
                if hid not in valid_map:
                    continue
                txt_folded = _strip_accents(f"{h.get('topic', '')} {h.get('fact', '')} {h.get('tags', '')}".lower())
                tok_overlap = len(q_tokens & _significant_tokens(txt_folded))
                sem_val = float(h.get("semantic_similarity") or 0.0)
                if tok_overlap > 0 or sem_val >= 0.22:
                    norm_s = max(0.05, float(h.get("final_score") or 0.0) / max_bm25)
                    seed_scores[hid] = max(seed_scores.get(hid, 0.0), norm_s)
        except Exception:
            pass

    vec_hits = neural_vector_search(db, query, workspace=ws, top_k=max(top_k, 12), as_of=as_of_clean)
    for vh in vec_hits:
        vid = int(vh["id"])
        if vid not in valid_map:
            continue
        cos = float(vh.get("neural_cosine") or 0.0)
        txt_folded = _strip_accents(f"{vh.get('topic', '')} {vh.get('fact', '')} {vh.get('tags', '')}".lower())
        tok_overlap = len(q_tokens & _significant_tokens(txt_folded))
        if cos >= 0.22 or tok_overlap > 0:
            seed_scores[vid] = seed_scores.get(vid, 0.0) + max(0.0, cos)

    # Exact lexical / substring safety pass over valid_map (handles workspace="all" & fresh un-BM25'd rows)
    for nid, item in valid_map.items():
        txt = f"{item.get('topic', '')} {item.get('fact', '')} {item.get('tags', '')}"
        txt_folded = _strip_accents(txt.lower())
        overlap = len(q_tokens & _significant_tokens(txt))
        exact_sub = 1.0 if (q_clean_folded and q_clean_folded in txt_folded) else 0.0
        if overlap > 0 or exact_sub > 0.0:
            lex_sc = overlap * 0.45 + exact_sub * 1.2
            seed_scores[nid] = seed_scores.get(nid, 0.0) + lex_sc

    # Fallback if no strong anchor matched: take top 2 positive neural_vector_search hits
    if not seed_scores and vec_hits:
        for vh in vec_hits[:2]:
            vid = int(vh["id"])
            if vid in valid_map and float(vh.get("neural_cosine") or 0.0) > 0.02:
                seed_scores[vid] = max(0.05, float(vh["neural_cosine"]))

    if not seed_scores:
        return {
            "ok": True,
            "query": query,
            "workspace": ws,
            "as_of": as_of_clean or "now",
            "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            "seeds_count": 0,
            "graph_nodes_visited": 0,
            "multi_hop_discoveries": 0,
            "results": [],
        }

    # Step 2: Build bidirectional weighted adjacency graph over valid_map
    adj: Dict[int, List[Tuple[int, float, str, str]]] = {}
    for er in edge_rows:
        s_id = int(er["source_id"])
        t_id = int(er["target_id"])
        if s_id not in valid_map or t_id not in valid_map or s_id == t_id:
            continue
        rel = str(er["relation"] or "evolves")
        w = max(0.1, float(er["weight"] or 0.85))
        adj.setdefault(s_id, []).append((t_id, w, rel, "->"))
        adj.setdefault(t_id, []).append((s_id, w * 0.85, rel, "<-"))

    # Lightweight shared-tag bridge edges only for seed nodes with 0 explicit DB edges
    seeds_without_edges = [sid for sid in seed_scores if not adj.get(sid)]
    if seeds_without_edges:
        tag_index: Dict[str, List[int]] = {}
        for nid, item in valid_map.items():
            raw_tags = str(item.get("tags") or "")
            for tag in [t.strip().lower() for t in re.split(r"[,;\s]+", raw_tags) if len(t.strip()) >= 2]:
                tag_index.setdefault(tag, []).append(nid)
        for sid in seeds_without_edges:
            s_ws = valid_map[sid].get("workspace")
            s_tags = [t.strip().lower() for t in re.split(r"[,;\s]+", str(valid_map[sid].get("tags") or "")) if len(t.strip()) >= 2]
            bridged: Set[int] = set()
            for tag in s_tags:
                for cand_id in tag_index.get(tag, []):
                    if cand_id != sid and cand_id not in bridged and valid_map[cand_id].get("workspace") == s_ws:
                        bridged.add(cand_id)
                        adj.setdefault(sid, []).append((cand_id, 0.35, f"SHARED_TAG:{tag}", "<->"))
                        adj.setdefault(cand_id, []).append((sid, 0.35, f"SHARED_TAG:{tag}", "<->"))
                        if len(bridged) >= 6:
                            break
                if len(bridged) >= 6:
                    break

    # BFS up to `hops` from seed nodes to record hop distance & path provenance
    hop_distance: Dict[int, int] = {sid: 0 for sid in seed_scores}
    parent_edge: Dict[int, Tuple[int, str, str]] = {}
    bfs_q: deque[int] = deque(sorted(seed_scores.keys(), key=lambda x: seed_scores[x], reverse=True))
    max_hops = max(1, int(hops))

    while bfs_q:
        u = bfs_q.popleft()
        d_u = hop_distance[u]
        if d_u >= max_hops:
            continue
        for v, _w, rel, arrow in adj.get(u, []):
            if v not in hop_distance:
                hop_distance[v] = d_u + 1
                parent_edge[v] = (u, rel, arrow)
                bfs_q.append(v)

    visited_nodes = sorted(hop_distance.keys())

    # Step 3: Exact Personalized PageRank power iteration on visited subgraph
    total_seed = sum(seed_scores.values()) or 1.0
    p0: Dict[int, float] = {nid: seed_scores.get(nid, 0.0) / total_seed for nid in visited_nodes}

    visited_set = set(visited_nodes)
    norm_adj: Dict[int, List[Tuple[int, float]]] = {}
    for u in visited_nodes:
        nbr_weights: Dict[int, float] = {}
        for v, w, _rel, _arrow in adj.get(u, []):
            if v in visited_set:
                nbr_weights[v] = nbr_weights.get(v, 0.0) + w
        out_sum = sum(nbr_weights.values())
        if out_sum > 0.0:
            norm_adj[u] = [(v, w / out_sum) for v, w in nbr_weights.items()]

    r: Dict[int, float] = dict(p0)
    damp = max(0.05, min(0.99, float(damping)))
    iters = max(1, int(iterations))

    for _ in range(iters):
        new_r = {nid: (1.0 - damp) * p0.get(nid, 0.0) for nid in visited_nodes}
        dangling_mass = 0.0
        for u in visited_nodes:
            nbrs = norm_adj.get(u)
            if not nbrs:
                dangling_mass += r[u]
            else:
                ru_damp = damp * r[u]
                for v, prob in nbrs:
                    new_r[v] += ru_damp * prob
        if dangling_mass > 0.0:
            for nid in visited_nodes:
                new_r[nid] += damp * dangling_mass * p0.get(nid, 0.0)
        r = new_r

    # Step 4: Annotate & rank results
    ranked_ids = sorted(
        visited_nodes,
        key=lambda nid: (
            r.get(nid, 0.0),
            seed_scores.get(nid, 0.0),
            int(valid_map[nid].get("importance") or 0),
            nid,
        ),
        reverse=True,
    )[: max(1, int(top_k))]

    results: List[Dict[str, Any]] = []
    multi_hop_discoveries = 0
    for nid in ranked_ids:
        item = dict(valid_map[nid])
        h_dist = hop_distance.get(nid, 0)
        is_multi = h_dist >= 1
        if is_multi:
            multi_hop_discoveries += 1
            p_id, rel, arrow = parent_edge[nid]
            p_topic = str(valid_map.get(p_id, {}).get("topic") or f"#{p_id}")
            path_reason = f"{h_dist}-hop via [{rel}] {arrow} {p_topic}"
        else:
            path_reason = "direct semantic anchor"

        item["ppr_score"] = round(r.get(nid, 0.0), 6)
        item["seed_score"] = round(seed_scores.get(nid, 0.0), 4)
        item["hop_distance"] = h_dist
        item["is_multi_hop"] = is_multi
        item["path_reason"] = path_reason
        item["valid_from"] = item.get("valid_from") or item.get("created_at")
        item["valid_to"] = item.get("valid_to")
        results.append(item)

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    return {
        "ok": True,
        "query": query,
        "workspace": ws,
        "as_of": as_of_clean or "now",
        "elapsed_ms": elapsed_ms,
        "seeds_count": len(seed_scores),
        "graph_nodes_visited": len(visited_nodes),
        "multi_hop_discoveries": multi_hop_discoveries,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Status Summary
# ---------------------------------------------------------------------------

def get_v10_cognitive_status(db: Any, workspace: str = "all") -> Dict[str, Any]:
    """
    Return clean JSON status across all three Engram v10.0 cognitive pillars.
    """
    ensure_v10_tables(db)
    ws = _norm_ws(db, workspace)
    ws_clause = "1=1" if ws == "all" else "workspace = ?"
    ws_params: Tuple[Any, ...] = () if ws == "all" else (ws,)

    with db._connect() as conn:
        active_memories = int(
            conn.execute(
                f"""
                SELECT COUNT(*) AS c FROM memories
                WHERE {ws_clause}
                  AND superseded_by IS NULL
                  AND (valid_to IS NULL OR valid_to = '');
                """,
                ws_params,
            ).fetchone()["c"]
        )
        superseded_memories = int(
            conn.execute(
                f"""
                SELECT COUNT(*) AS c FROM memories
                WHERE {ws_clause}
                  AND (superseded_by IS NOT NULL OR (valid_to IS NOT NULL AND valid_to != ''));
                """,
                ws_params,
            ).fetchone()["c"]
        )
        supersedes_edges = int(
            conn.execute(
                "SELECT COUNT(*) AS c FROM memory_edges WHERE UPPER(relation) = 'SUPERSEDES';"
            ).fetchone()["c"]
        )
        total_edges = int(
            conn.execute(
                "SELECT COUNT(*) AS c FROM memory_edges WHERE valid_to IS NULL OR valid_to = '';"
            ).fetchone()["c"]
        )
        edge_endpoints = conn.execute(
            "SELECT source_id, target_id FROM memory_edges WHERE valid_to IS NULL OR valid_to = '';"
        ).fetchall()

        indexed_active = int(
            conn.execute(
                f"""
                SELECT COUNT(*) AS c
                FROM memories m
                JOIN memory_neural_embeddings e ON e.memory_id = m.id
                WHERE {"1=1" if ws == "all" else "m.workspace = ?"}
                  AND m.superseded_by IS NULL
                  AND (m.valid_to IS NULL OR m.valid_to = '');
                """,
                ws_params,
            ).fetchone()["c"]
        )

    connected_ids: Set[int] = set()
    for er in edge_endpoints:
        connected_ids.add(int(er["source_id"]))
        connected_ids.add(int(er["target_id"]))

    backend_info = detect_local_embedding_backend()
    coverage_pct = round((indexed_active / active_memories) * 100.0, 2) if active_memories > 0 else 100.0

    return {
        "ok": True,
        "workspace": ws,
        "bitemporal": {
            "active_memories": active_memories,
            "active_facts": active_memories,
            "superseded_memories": superseded_memories,
            "superseded_facts": superseded_memories,
            "supersedes_edges": supersedes_edges,
            "supersession_edges": supersedes_edges,
        },
        "hipporag": {
            "active_edges": total_edges,
            "edges_indexed": total_edges,
            "connected_nodes": len(connected_ids),
            "ready": True,
        },
        "neural_embeddings": {
            "backend": backend_info["backend"],
            "model_name": backend_info["model_name"],
            "dims": backend_info["dims"],
            "sqlite_vec_available": backend_info["sqlite_vec_available"],
            "ollama_embed_models": backend_info["ollama_embed_models"],
            "indexed_active": indexed_active,
            "indexed_count": indexed_active,
            "total_active": active_memories,
            "coverage_pct": coverage_pct,
        },
    }


__all__ = [
    "ensure_v10_tables",
    "store_temporal_fact",
    "query_temporal_as_of",
    "get_temporal_history",
    "detect_local_embedding_backend",
    "compute_neural_embedding",
    "index_neural_embeddings",
    "neural_vector_search",
    "hipporag_ppr_retrieve",
    "get_v10_cognitive_status",
]

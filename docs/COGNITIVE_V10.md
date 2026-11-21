# Cognitive Memory v10.0 (`cognitive_v10_engine.py`)

← [Back to README](../README.md)

Engram v10.0 upgrades flat keyword/vector recall into a **tiered cognitive memory system** combining **Bi-Temporal Knowledge Graphs**, **HippoRAG Personalized PageRank (PPR)**, **Local Neural Embeddings**, and **GBrain Orthogonal Salience × Recency** — all with zero mandatory external dependencies.

---

## 1. Bi-Temporal Knowledge Graph *(Graphiti / Zep Pattern)*

Traditional vector/FTS memory stores suffer from **fact contradiction**: when an architecture decision changes, old and new facts compete equally in search results.

Engram v10.0 adds bi-temporal validity columns to `memories` (`valid_from`, `valid_to`, `invalidated_by`, `superseded_by`) and `memory_edges` (`valid_from`, `valid_to`):

- **Automatic Supersession (`store_temporal_fact`)**:
  - Detects conflicting active facts in the same workspace via topic/entity overlap or explicit supersession phrasing (`renamed`, `migrated from`, `replaced`, `trocámos`, `em vez de`, etc.).
  - Marks the outdated fact with `valid_to = now_iso` and `invalidated_by = new_id` (excluding it automatically from default `search_memories` recall) while preserving full history.
  - Inserts a directed `SUPERSEDES` edge in `memory_edges` (`new_id → old_id`).
- **Point-in-Time Time-Travel (`query_temporal_as_of`)**:
  - `as_of=""` (now): returns only currently active truth.
  - `as_of="2026-03-01"`: reconstructs the exact knowledge state valid on that historical date (`valid_from <= as_of AND (valid_to IS NULL OR valid_to > as_of)`).
- **Evolution Lineage (`get_temporal_history`)**: Walks `SUPERSEDES` links backward and forward to inspect how any decision evolved over time.

---

## 2. HippoRAG — Personalized PageRank (PPR) Multi-Hop Retrieval

Standard RAG retrieves isolated chunks and misses multi-hop dependencies (`A → B → C` where `C` shares zero lexical keywords with the query for `A`).

`hipporag_ppr_retrieve()` implements neurobiologically inspired **Personalized PageRank** in pure Python:

1. **Entry-Point Anchoring**: Combines hybrid FTS5 BM25 + Local Neural Embeddings to rank direct seed nodes `p₀(v)` while respecting temporal validity (`as_of`).
2. **Graph Expansion**: Loads active `memory_edges` (`SUPERSEDES`, `DEPENDS_ON`, `CAUSES`, synaptic links) within `hops` (default `2`) of the seed anchors.
3. **Power Iteration**: Computes $\mathbf{r}^{(t+1)} = (1 - \alpha)\,\mathbf{p}_0 + \alpha\,M\,\mathbf{r}^{(t)}$ (`damping = 0.85`, `iterations = 12`).
4. **Explainable Multi-Hop Results**: Tags each hit with `ppr_score`, `hop_distance` (`0` = direct anchor, `1`/`2` = multi-hop discovery), `is_multi_hop`, and `path_reason` (e.g., `2-hop via [DEPENDS_ON] -> ...`).
5. **PreInvocation Augmentation**: For complex queries (`>= 24` chars), `brain_inject.py` automatically appends the top multi-hop discovery as a single telegraphic line (`🧠[HIPPO_2HOP]`).

---

## 3. Local Neural Embeddings (100% Offline, Zero Cloud Cost)

Stored as compact packed `float32` blobs in SQLite table `memory_neural_embeddings`:

- **Auto-Detected Local Backends (`detect_local_embedding_backend`)**:
  1. **Local Ollama** (`127.0.0.1:11434`): automatically uses installed embedding models (`nomic-embed-text`, `bge-m3`, `mxbai-embed-large`, `all-minilm`, `snowflake-arctic-embed`, `qwen3-embedding`).
  2. **`sqlite_vec` Detection**: automatically reports `sqlite_vec` extension availability when installed.
  3. **Built-in Bilingual Dense 256-D Float32 Engine (`engram_dense_256d`)**: zero-dependency deterministic fallback combining signed word/bigram hashing (`0..159`), character 3/4-gram hashing (`160..223`), and **32 bilingual PT-PT ⇄ EN-EN engineering concept projections** (`224..255`), matching cross-lingual queries like `"velocidade da base de dados"` ↔ `"SQLite database latency optimization"` offline in `<0.4ms`.

---

## 4. GBrain Orthogonal Axes, Skill Resolver & Compiled Dossiers

- **Salience × Recency (`brain_explain_ranking`)**: Separates evergreen canonical truth (`CANONICAL_TRUTH`, zero time decay) from episodic Ebbinghaus time decay, with transparent BM25/LSH/PPR scoring breakdown.
- **Local Skill Resolver (`skill_resolver_engine.py`)**: Indexes all local `SKILL.md` files across installed plugins in `~1ms` warm, rescuing skills omitted from context budgets (`brain_resolve_skill`).
- **Compiled Vault Dossiers (`.brain_vault/<workspace>/*.md`)**: Two-zone Markdown dossiers (`Compiled Truth` + `Chronological Timeline`) with automated bidirectional `[[wiki-links]]` verification.

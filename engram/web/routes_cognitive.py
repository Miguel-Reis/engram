"""Declarative HTTP route handlers for Cognitive v10.0 & Local Neural Cortex v11.0."""

from __future__ import annotations

from typing import Any, Callable, Dict

from engram.core.logging import log_error
from engram.core.utils import safe_int
from engram.web.router import RouteRegistry


def _safe_bool(val: Any, default: bool = False) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return default
    s = str(val).strip().lower()
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off"):
        return False
    return default


def _safe_float(val: Any, default: float = 0.0, min_v: float | None = None, max_v: float | None = None) -> float:
    try:
        parsed = float(val)
    except (TypeError, ValueError):
        parsed = float(default)
    if min_v is not None and parsed < min_v:
        parsed = min_v
    if max_v is not None and parsed > max_v:
        parsed = max_v
    return parsed


def register_cognitive_routes(
    router: RouteRegistry,
    db_factory: Callable[[], Any],
    invalidate_cache: Callable[[], None],
) -> None:
    """Register all /api/v10/* and /api/v11/* endpoints cleanly on RouteRegistry."""

    @router.get("/api/v10/status")
    def _v10_status(handler: Any, qs: Dict[str, Any], **_kw: Any) -> None:
        ws = qs.get("workspace", ["all"])[0] or "all"
        try:
            from cognitive_v10_engine import get_v10_cognitive_status

            handler._send_json(get_v10_cognitive_status(db_factory(), workspace=ws))
        except Exception as exc:
            log_error("routes_cognitive", "GET /api/v10/status", exc)
            handler._send_json({"ok": False, "error": str(exc), "workspace": ws, "fallback": True}, 500)

    @router.get("/api/v10/hipporag")
    def _v10_hipporag(handler: Any, qs: Dict[str, Any], **_kw: Any) -> None:
        q = qs.get("q", [""])[0]
        ws = qs.get("workspace", ["all"])[0] or "all"
        top_k = safe_int(qs.get("top_k", ["8"])[0], default=8, min_v=1, max_v=50)
        hops = safe_int(qs.get("hops", ["2"])[0], default=2, min_v=1, max_v=4)
        as_of = qs.get("as_of", [""])[0]
        try:
            from cognitive_v10_engine import hipporag_ppr_retrieve

            handler._send_json(
                hipporag_ppr_retrieve(db_factory(), query=q, workspace=ws, top_k=top_k, hops=hops, as_of=as_of)
            )
        except Exception as exc:
            log_error("routes_cognitive", "GET /api/v10/hipporag", exc)
            handler._send_json({"ok": False, "error": str(exc), "query": q, "workspace": ws, "fallback": True}, 500)

    @router.get("/api/v10/temporal")
    def _v10_temporal(handler: Any, qs: Dict[str, Any], **_kw: Any) -> None:
        q = qs.get("q", [""])[0]
        ws = qs.get("workspace", ["all"])[0] or "all"
        as_of = qs.get("as_of", [""])[0]
        inc_sup = _safe_bool(qs.get("include_superseded", ["0"])[0], default=False)
        limit = safe_int(qs.get("limit", ["12"])[0], default=12, min_v=1, max_v=100)
        try:
            from cognitive_v10_engine import query_temporal_as_of

            handler._send_json(
                query_temporal_as_of(
                    db_factory(),
                    query=q,
                    workspace=ws,
                    as_of=as_of,
                    include_superseded=inc_sup,
                    limit=limit,
                )
            )
        except Exception as exc:
            log_error("routes_cognitive", "GET /api/v10/temporal", exc)
            handler._send_json({"ok": False, "error": str(exc), "query": q, "workspace": ws, "fallback": True}, 500)

    @router.get("/api/v11/neural/status")
    def _v11_status(handler: Any, qs: Dict[str, Any], **_kw: Any) -> None:
        ws = qs.get("workspace", ["all"])[0] or "all"
        try:
            from neural_cortex_engine import get_neural_cortex_status

            handler._send_json(get_neural_cortex_status(db_factory(), workspace=ws))
        except Exception as exc:
            log_error("routes_cognitive", "GET /api/v11/neural/status", exc)
            handler._send_json({"ok": False, "error": str(exc), "workspace": ws, "fallback": True}, 500)

    @router.get("/api/v11/neural/search")
    def _v11_search(handler: Any, qs: Dict[str, Any], **_kw: Any) -> None:
        q = qs.get("q", [""])[0]
        ws = qs.get("workspace", ["all"])[0] or "all"
        top_k = safe_int(qs.get("top_k", ["6"])[0], default=6, min_v=1, max_v=50)
        rerank = _safe_bool(qs.get("rerank", ["1"])[0], default=True)
        mlp = _safe_bool(qs.get("mlp", ["1"])[0], default=True)
        as_of = qs.get("as_of", [""])[0]
        try:
            from neural_cortex_engine import neural_retrieve_and_rerank

            handler._send_json(
                neural_retrieve_and_rerank(
                    db_factory(),
                    query=q,
                    workspace=ws,
                    top_k=top_k,
                    use_cross_encoder=rerank,
                    use_mlp=mlp,
                    as_of=as_of,
                )
            )
        except Exception as exc:
            log_error("routes_cognitive", "GET /api/v11/neural/search", exc)
            handler._send_json({"ok": False, "error": str(exc), "query": q, "workspace": ws, "fallback": True}, 500)

    @router.post("/api/v10/temporal/store")
    def _v10_temporal_store(handler: Any, body: Any, db: Any, **_kw: Any) -> None:
        data = body if isinstance(body, dict) else {}
        topic = str(data.get("topic", "")).strip()
        fact = str(data.get("fact", "")).strip()
        if not topic or not fact:
            handler._send_json({"ok": False, "error": "topic and fact are required"}, 400)
            return
        ws = str(data.get("workspace", "brain_mcp")).strip() or "brain_mcp"
        category = str(data.get("category", "decision")).strip() or "decision"
        tags = str(data.get("tags", "")).strip()
        importance = safe_int(data.get("importance", 8), default=8, min_v=1, max_v=10)
        valid_from = str(data.get("valid_from", "")).strip()
        auto_supersede = bool(data.get("auto_supersede", True))
        try:
            from cognitive_v10_engine import get_v10_cognitive_status, store_temporal_fact

            res = store_temporal_fact(
                db,
                topic=topic,
                fact=fact,
                workspace=ws,
                category=category,
                tags=tags,
                importance=importance,
                valid_from=valid_from,
                auto_supersede=auto_supersede,
            )
            invalidate_cache()
            status = get_v10_cognitive_status(db, workspace=ws)
            out = dict(res) if isinstance(res, dict) else {"result": res}
            out["ok"] = bool(out.get("ok", True))
            out["result"] = res
            out["status"] = status
            handler._send_json(out)
        except Exception as exc:
            log_error("routes_cognitive", "POST /api/v10/temporal/store", exc)
            handler._send_json({"ok": False, "error": str(exc), "workspace": ws, "fallback": True}, 500)

    @router.post("/api/v10/embeddings/index")
    def _v10_embed_index(handler: Any, body: Any, db: Any, **_kw: Any) -> None:
        data = body if isinstance(body, dict) else {}
        ws = str(data.get("workspace", "all")).strip() or "all"
        limit = safe_int(data.get("limit", 200), default=200, min_v=1, max_v=5000)
        force = bool(data.get("force", False))
        try:
            from cognitive_v10_engine import get_v10_cognitive_status, index_neural_embeddings

            res = index_neural_embeddings(db, workspace=ws, limit=limit, force=force)
            invalidate_cache()
            status = get_v10_cognitive_status(db, workspace=ws)
            out = dict(res) if isinstance(res, dict) else {"result": res}
            out["ok"] = bool(out.get("ok", True))
            out["result"] = res
            out["status"] = status
            handler._send_json(out)
        except Exception as exc:
            log_error("routes_cognitive", "POST /api/v10/embeddings/index", exc)
            handler._send_json({"ok": False, "error": str(exc), "workspace": ws, "fallback": True}, 500)

    @router.post("/api/v11/neural/train")
    def _v11_train(handler: Any, body: Any, db: Any, **_kw: Any) -> None:
        data = body if isinstance(body, dict) else {}
        epochs = safe_int(data.get("epochs", 40), default=40, min_v=1, max_v=500)
        lr = _safe_float(data.get("lr", 0.015), default=0.015, min_v=1e-5, max_v=1.0)
        hebbian_sync = _safe_bool(data.get("hebbian_sync", True), default=True)
        try:
            from neural_cortex_engine import get_neural_cortex_status, train_personal_neural_ranker

            res = train_personal_neural_ranker(db, epochs=epochs, lr=lr, hebbian_sync=hebbian_sync)
            invalidate_cache()
            status = get_neural_cortex_status(db)
            handler._send_json({"ok": True, "training": res, "status": status})
        except Exception as exc:
            log_error("routes_cognitive", "POST /api/v11/neural/train", exc)
            handler._send_json({"ok": False, "error": str(exc), "fallback": True}, 500)

    @router.post("/api/v11/neural/feedback")
    def _v11_feedback(handler: Any, body: Any, db: Any, **_kw: Any) -> None:
        data = body if isinstance(body, dict) else {}
        memory_id = safe_int(data.get("memory_id"), default=0, min_v=0)
        if memory_id <= 0:
            handler._send_json({"ok": False, "error": "memory_id is required"}, 400)
            return
        useful = _safe_bool(data.get("useful", True), default=True)
        query = str(data.get("query", "") or "").strip()
        source = str(data.get("source", "ui") or "ui").strip() or "ui"
        try:
            from neural_cortex_engine import get_neural_cortex_status, record_neural_feedback

            res = record_neural_feedback(db, memory_id=memory_id, useful=useful, query=query, source=source)
            status = get_neural_cortex_status(db)
            handler._send_json({"ok": True, "feedback": res, "status": status})
        except Exception as exc:
            log_error("routes_cognitive", "POST /api/v11/neural/feedback", exc)
            handler._send_json({"ok": False, "error": str(exc), "fallback": True}, 500)

    @router.post("/api/v11/neural/warmup")
    def _v11_warmup(handler: Any, body: Any, db: Any, **_kw: Any) -> None:
        data = body if isinstance(body, dict) else {}
        load_reranker = _safe_bool(data.get("load_reranker", True), default=True)
        index_limit = safe_int(data.get("index_limit", 2000), default=2000, min_v=0, max_v=20000)
        try:
            from neural_cortex_engine import get_neural_cortex_status, warmup_neural_models

            res = warmup_neural_models(db=db, load_reranker=load_reranker, index_limit=index_limit)
            invalidate_cache()
            status = get_neural_cortex_status(db)
            handler._send_json({"ok": True, "warmup": res, "status": status})
        except Exception as exc:
            log_error("routes_cognitive", "POST /api/v11/neural/warmup", exc)
            handler._send_json({"ok": False, "error": str(exc), "fallback": True}, 500)

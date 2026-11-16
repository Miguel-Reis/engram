# -*- coding: utf-8 -*-
"""
skill_resolver_engine.py — Zero-Token Local SKILL.md Indexer & Resolver
========================================================================
Inspired by garrytan/gbrain's `gbrain skills resolve --text "<request>"`.
Indexes all installed Antigravity SKILL.md files (130+ skills across plugins,
builtins, and config skills) into an ultra-fast in-memory cache and SQLite table
`skill_catalog` in brain.db.

Features:
- Fast Frontmatter & Body Token Parser (pure Python, zero dependencies)
- Bilingual PT/EN Synonym Expansion for seamless engineering intent matching
- Hybrid BM25-style IDF token scoring + optional 128-D LSH cosine boost
- Micro-confirmation short-circuit (<0.1ms for "sim", "ok", "continua")
- Warm lookups in <1.5ms
"""

import os
import re
import math
import time
import glob
import sqlite3
import unicodedata
from typing import Dict, List, Any, Optional, Set, Tuple

# In-Memory Cache across turns in the same process
_SKILL_MEM_CACHE: Dict[str, Any] = {
    "skills": [],
    "total_skills": 0,
    "plugins_scanned": 0,
    "last_refresh": 0.0,
    "idf_map": {},
}

# Micro confirmation words to immediately skip resolution
MICRO_CONFIRMATIONS: Set[str] = {
    "sim", "ok", "continua", "podes avançar", "podes avancar", "proceed",
    "yes", "go", "continue", "avançar", "avancar", "proceder", "certo",
    "concordo", "done", "next", "passa", "avante", "claro", "beleza"
}

# Bilingual PT/EN Synonym Map for engineering terms
BILINGUAL_PT_EN_MAP: Dict[str, str] = {
    "seguranca": "security vulnerability pentest strix owasp hardening audit attack exploit",
    "segurança": "security vulnerability pentest strix owasp hardening audit attack exploit",
    "vulnerabilidade": "security vulnerability pentest strix owasp hardening cve exploit",
    "vulnerabilidades": "security vulnerability pentest strix owasp hardening cve exploit",
    "pentest": "security penetration testing pentest strix owasp red-team exploit",
    "auditoria": "audit security compliance review code-review",
    "interface": "ui ux frontend styling design-system tailwind hig component screen visual",
    "design": "ui ux frontend styling design-system tailwind hig design-tokens layout",
    "visual": "ui ux frontend styling design-system visual tailwind layout",
    "css": "ui ux frontend styling modern-css tailwind responsive layout",
    "layout": "ui ux frontend layout tailwind modern-css responsive",
    "base de dados": "database orm sql postgres sqlite migration schema db",
    "base de dado": "database orm sql postgres sqlite migration schema db",
    "banco de dados": "database orm sql postgres sqlite migration schema db",
    "sql": "database orm sql postgres sqlite migration query queries",
    "migracao": "database orm migration deprecation upgrade schema",
    "migração": "database orm migration deprecation upgrade schema",
    "queries": "database orm sql query performance index optimization",
    "query": "database orm sql query performance index optimization",
    "performance": "performance optimization web-vitals memory-leak speed latency bottleneck",
    "lento": "performance optimization web-vitals bottleneck slow latency speed",
    "otimizar": "performance optimization web-vitals speed bundle bottleneck",
    "otimizacao": "performance optimization web-vitals speed bundle bottleneck",
    "otimização": "performance optimization web-vitals speed bundle bottleneck",
    "memoria leak": "memory-leak memory chrome-devtools debugging performance leak heap",
    "memória leak": "memory-leak memory chrome-devtools debugging performance leak heap",
    "leak de memoria": "memory-leak memory chrome-devtools debugging performance leak heap",
    "testes": "test-driven-development e2e-testing playwright vitest unit-test qa",
    "teste": "test-driven-development e2e-testing playwright vitest unit-test qa",
    "playwright": "e2e-testing browser-testing playwright vitest automation",
    "unitario": "test-driven-development vitest jest unit test testing",
    "unitário": "test-driven-development vitest jest unit test testing",
    "jogo": "web-3d-graphics web-game-engine glsl-shader three js babylon physics",
    "jogos": "web-3d-graphics web-game-engine glsl-shader three js babylon physics",
    "3d": "web-3d-graphics web-game-engine glsl-shader threejs webgpu render",
    "webgl": "web-3d-graphics web-game-engine glsl-shader webgl threejs webgpu",
    "shader": "glsl-shader web-3d-graphics webgpu compute-shader threejs",
    "api": "api-design-expert openapi-swagger-codegen-expert rest graphql endpoint",
    "apis": "api-design-expert openapi-swagger-codegen-expert rest graphql endpoint",
    "autenticacao": "authentication-identity-expert auth oauth login jwt rbac",
    "autenticação": "authentication-identity-expert auth oauth login jwt rbac",
    "login": "authentication-identity-expert auth oauth login jwt rbac",
    "acessibilidade": "accessibility-testing-expert a11y-debugging wcag aria",
    "deploy": "cloud-hosting-expert ci-cd-devops-architect vercel cloudflare docker",
    "nuvem": "cloud-hosting-expert ci-cd-devops-architect serverless docker",
    "fila": "async-queue-temporal-expert bullmq redis background worker jobs",
    "filas": "async-queue-temporal-expert bullmq redis background worker jobs",
    "agendador": "cron-scheduler-expert cron scheduling background tasks",
    "tarefas": "async-queue-temporal-expert cron-scheduler-expert background",
    "mobile": "mobile-expo-expert react-native expo apple-ecosystem-expert",
    "desktop": "desktop-electron-expert tauri-expert electron tauri app",
    "documentacao": "documentation-site-expert prd-architect docs mintlify",
    "documentação": "documentation-site-expert prd-architect docs mintlify",
    "pagamento": "payment-gateway-expert doku-payment-gateway saas-billing stripe",
    "pagamentos": "payment-gateway-expert doku-payment-gateway saas-billing stripe",
    "ia": "google-antigravity-sdk agentic-coding-workflow-expert swarm agent",
    "agente": "google-antigravity-sdk agentic-coding-workflow-expert swarm agent",
    "agentes": "google-antigravity-sdk agentic-coding-workflow-expert swarm agent",
    "swarm": "swarm native-swarm multi-agent orchestration",
    "plano": "planning-and-task-breakdown writing-plans ultraplan architecture",
    "planeamento": "planning-and-task-breakdown writing-plans ultraplan architecture",
    "planejar": "planning-and-task-breakdown writing-plans ultraplan architecture",
    "revisao": "code-review-and-quality requesting-code-review code-reviewer",
    "revisão": "code-review-and-quality requesting-code-review code-reviewer",
    "depurar": "systematic-debugging debugging-and-error-recovery autonomous-tdd-debugger",
    "debug": "systematic-debugging debugging-and-error-recovery autonomous-tdd-debugger",
    "frontend": "senior-frontend ui-ux-pro-max tailwind frontend-ui-engineering",
    "backend": "js-backend-expert python-programming-expert go-programming-expert api-design-expert",
    "crawler": "web-scraper browser-automation-expert",
    "scraping": "web-scraper browser-automation-expert",
}


def strip_accents(text: str) -> str:
    """Remove acentos e diacríticos mantendo caracteres ASCII alfanuméricos."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def parse_skill_file(file_path: str) -> Optional[Dict[str, Any]]:
    """Lê e analisa um ficheiro SKILL.md extraindo frontmatter e palavras-chave do corpo."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return None

    in_frontmatter = False
    fm_lines: List[str] = []
    body_lines: List[str] = []

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if idx == 0 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
                body_lines = lines[idx + 1 : idx + 45]
                break
            fm_lines.append(line)
        else:
            body_lines = lines[:40]
            break

    name = ""
    desc_parts: List[str] = []
    desc_collecting = False

    for line in fm_lines:
        sline = line.strip()
        if sline.startswith("name:"):
            name = sline[5:].strip().strip("\"'")
            desc_collecting = False
        elif sline.startswith("description:"):
            desc_parts.append(sline[12:].strip().strip("\"'"))
            desc_collecting = True
        elif desc_collecting:
            if re.match(r"^[a-zA-Z0-9_-]+:", sline):
                desc_collecting = False
            else:
                desc_parts.append(sline.strip("\"'"))

    description = " ".join(desc_parts).strip()
    norm_path = file_path.replace("\\", "/")
    slug = name or os.path.basename(os.path.dirname(file_path))
    if not name:
        name = slug

    plugin = "builtin"
    if "/plugins/" in norm_path:
        parts = norm_path.split("/plugins/")[-1].split("/")
        if len(parts) > 1:
            plugin = parts[0]
    elif "/builtin/" in norm_path:
        plugin = "builtin"
    elif "/config/skills/" in norm_path:
        plugin = "global"

    body_text = " ".join(body_lines)
    raw_words = re.findall(r"[a-zA-Z0-9_-]{3,}", body_text.lower())
    keywords = list(dict.fromkeys(raw_words))[:60]

    try:
        mtime = os.path.getmtime(file_path)
    except Exception:
        mtime = 0.0

    return {
        "slug": slug,
        "name": name,
        "plugin": plugin,
        "path": norm_path,
        "description": description,
        "keywords": " ".join(keywords),
        "mtime": mtime,
    }


class SkillResolverEngine:
    """
    Motor local de resolução de competências (SKILL.md) com latência <1.5ms,
    expansão bilingue PT/EN e pontuação lexical/semântica explicável.
    """

    def __init__(self, db: Optional[Any] = None) -> None:
        self.db = db
        self._ensure_table()
        self.build_or_refresh_index(force=False)

    def _ensure_table(self) -> None:
        """Garante a existência da tabela skill_catalog na base de dados."""
        if not self.db or not hasattr(self.db, "_connect"):
            return
        try:
            with self.db._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS skill_catalog (
                        slug TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        plugin TEXT DEFAULT '',
                        path TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        keywords TEXT DEFAULT '',
                        mtime REAL DEFAULT 0.0
                    );
                    """
                )
        except Exception:
            pass

    def get_discovery_roots(self) -> List[str]:
        """Devolve os caminhos de pesquisa glob para todos os SKILL.md instalados."""
        home = os.path.expanduser("~")
        return [
            os.path.join(home, ".gemini", "config", "plugins", "*", "skills", "*", "SKILL.md"),
            os.path.join(home, ".gemini", "config", "skills", "*", "SKILL.md"),
            os.path.join(home, ".gemini", "antigravity", "builtin", "skills", "*", "SKILL.md"),
        ]

    def build_or_refresh_index(self, force: bool = False) -> Dict[str, Any]:
        """
        Carrega ou atualiza o catálogo de skills a partir da memória, SQLite ou filesystem.
        TTL de memória: 60 segundos.
        """
        now = time.time()
        global _SKILL_MEM_CACHE

        if not force and _SKILL_MEM_CACHE["skills"] and (now - _SKILL_MEM_CACHE["last_refresh"] < 60.0):
            return {
                "ok": True,
                "total_skills": _SKILL_MEM_CACHE["total_skills"],
                "plugins_scanned": _SKILL_MEM_CACHE["plugins_scanned"],
                "source": "memory_cache",
            }

        # 1. Tentar carregar do SQLite se não forçado
        skills_loaded: List[Dict[str, Any]] = []
        if not force and self.db and hasattr(self.db, "_connect"):
            try:
                with self.db._connect() as conn:
                    rows = conn.execute("SELECT * FROM skill_catalog;").fetchall()
                    if rows and len(rows) >= 50:
                        for r in rows:
                            skills_loaded.append(dict(r))
            except Exception:
                skills_loaded = []

        # 2. Se SQLite estiver vazio ou force=True, efetuar scan do filesystem
        if not skills_loaded:
            roots = self.get_discovery_roots()
            all_files: List[str] = []
            for r in roots:
                all_files.extend(glob.glob(r))

            for fpath in all_files:
                parsed = parse_skill_file(fpath)
                if parsed:
                    skills_loaded.append(parsed)

            # Persistir no SQLite
            if skills_loaded and self.db and hasattr(self.db, "_connect"):
                try:
                    with self.db._connect() as conn:
                        conn.executemany(
                            """
                            INSERT INTO skill_catalog (slug, name, plugin, path, description, keywords, mtime)
                            VALUES (:slug, :name, :plugin, :path, :description, :keywords, :mtime)
                            ON CONFLICT(slug) DO UPDATE SET
                                name=excluded.name,
                                plugin=excluded.plugin,
                                path=excluded.path,
                                description=excluded.description,
                                keywords=excluded.keywords,
                                mtime=excluded.mtime;
                            """,
                            skills_loaded,
                        )
                except Exception:
                    pass

        # 3. Pré-processar tokens e calcular mapa IDF
        doc_freq: Dict[str, int] = {}
        processed_skills: List[Dict[str, Any]] = []
        plugins_seen: Set[str] = set()

        for s in skills_loaded:
            plugins_seen.add(s.get("plugin", "builtin"))
            name_clean = strip_accents(s.get("name", "")).lower()
            slug_clean = strip_accents(s.get("slug", "")).lower()
            desc_clean = strip_accents(s.get("description", "")).lower()
            kw_clean = strip_accents(s.get("keywords", "")).lower()

            name_toks = set(re.findall(r"[a-z0-9_-]{2,}", f"{name_clean} {slug_clean}"))
            desc_toks = set(re.findall(r"[a-z0-9_-]{2,}", desc_clean))
            kw_toks = set(re.findall(r"[a-z0-9_-]{2,}", kw_clean))

            all_toks = name_toks | desc_toks | kw_toks
            for t in all_toks:
                doc_freq[t] = doc_freq.get(t, 0) + 1

            s_copy = dict(s)
            s_copy["name_toks"] = name_toks
            s_copy["desc_toks"] = desc_toks
            s_copy["kw_toks"] = kw_toks
            s_copy["all_toks"] = all_toks
            s_copy["s_vec"] = None
            if self.db and hasattr(self.db, "compute_semantic_vector"):
                try:
                    s_copy["s_vec"] = self.db.compute_semantic_vector(f"{s_copy['name']} {s_copy['description']}")
                except Exception:
                    s_copy["s_vec"] = None
            processed_skills.append(s_copy)

        n_docs = max(1, len(processed_skills))
        idf_map: Dict[str, float] = {}
        for t, df in doc_freq.items():
            idf_map[t] = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))

        _SKILL_MEM_CACHE = {
            "skills": processed_skills,
            "total_skills": len(processed_skills),
            "plugins_scanned": len(plugins_seen),
            "last_refresh": now,
            "idf_map": idf_map,
        }

        return {
            "ok": True,
            "total_skills": len(processed_skills),
            "plugins_scanned": len(plugins_seen),
            "source": "sqlite" if skills_loaded and not force else "filesystem_scan",
        }

    def expand_query_bilingual(self, query: str) -> Tuple[Set[str], List[str]]:
        """
        Expande termos do utilizador em português para termos técnicos em inglês
        relevantes para os ficheiros SKILL.md.
        """
        q_norm = strip_accents(query).lower()
        base_tokens = re.findall(r"[a-z0-9_-]{2,}", q_norm)
        expanded: Set[str] = set(base_tokens)

        # Procura correspondências multi-palavra e uni-palavra no dicionário bilingue
        for pt_term, en_syns in BILINGUAL_PT_EN_MAP.items():
            pt_clean = strip_accents(pt_term).lower()
            if pt_clean in q_norm or any(t == pt_clean for t in base_tokens):
                for syn_tok in re.findall(r"[a-z0-9_-]{2,}", en_syns):
                    expanded.add(syn_tok)

        return expanded, base_tokens

    def resolve_skills_for_query(
        self, query: str, top_k: int = 2, min_score: float = 0.45
    ) -> Dict[str, Any]:
        """
        Resolve com confiança as 1 a 3 competências mais relevantes para a query dada.
        Retorna em <1.5ms com a diretiva formatada.
        """
        t0 = time.perf_counter()
        raw_q = (query or "").strip()
        q_low = raw_q.lower()

        # Resolução instantânea para confirmações rápidas ou queries curtas
        if len(raw_q) < 8 or q_low in MICRO_CONFIRMATIONS:
            return {
                "ok": True,
                "query": raw_q,
                "total_skills_indexed": _SKILL_MEM_CACHE.get("total_skills", 0),
                "matched_skills": [],
                "directive_line": "",
                "latency_ms": 0.1,
            }

        # Garantir índice carregado
        if not _SKILL_MEM_CACHE["skills"]:
            self.build_or_refresh_index()

        skills = _SKILL_MEM_CACHE.get("skills", [])
        idf_map = _SKILL_MEM_CACHE.get("idf_map", {})
        total_skills = len(skills)

        if total_skills == 0:
            return {
                "ok": True,
                "query": raw_q,
                "total_skills_indexed": 0,
                "matched_skills": [],
                "directive_line": "",
                "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            }

        expanded_tokens, raw_tokens = self.expand_query_bilingual(raw_q)
        q_norm = strip_accents(raw_q).lower()

        scored: List[Tuple[float, Dict[str, Any]]] = []

        for s in skills:
            slug = s["slug"].lower()
            name = s["name"].lower()
            score = 0.0

            # 1. Menção exata ao nome ou slug da skill (+1.5)
            if slug in q_norm or name in q_norm:
                score += 1.5
            elif any(tok == slug or tok == name for tok in raw_tokens):
                score += 1.5

            # 2. BM25-style IDF token overlap
            name_hits = expanded_tokens & s["name_toks"]
            desc_hits = expanded_tokens & s["desc_toks"]
            kw_hits = expanded_tokens & s["kw_toks"]

            for t in name_hits:
                score += idf_map.get(t, 1.2) * 3.0
            for t in desc_hits:
                score += idf_map.get(t, 1.0) * 1.8
            for t in kw_hits:
                score += idf_map.get(t, 0.8) * 1.0

            if score > 0.0:
                scored.append((score, s))

        if not scored:
            return {
                "ok": True,
                "query": raw_q,
                "total_skills_indexed": total_skills,
                "matched_skills": [],
                "directive_line": "",
                "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            }

        # Ordenar os melhores candidatos léxicos
        scored.sort(key=lambda kv: kv[0], reverse=True)
        top_candidates = scored[:12]

        # 3. Boost Semântico 128-D LSH nos top 12 candidatos (se db estiver disponível)
        boosted: List[Tuple[float, Dict[str, Any]]] = []
        q_vec = None
        if self.db and hasattr(self.db, "compute_semantic_vector") and hasattr(self.db, "cosine_similarity"):
            try:
                q_vec = self.db.compute_semantic_vector(raw_q)
            except Exception:
                q_vec = None

        for sc, s in top_candidates:
            final_sc = sc
            if q_vec:
                try:
                    s_vec = s.get("s_vec")
                    if s_vec is None:
                        s_vec = self.db.compute_semantic_vector(f"{s['name']} {s['description']}")
                        s["s_vec"] = s_vec
                    cos_sim = self.db.cosine_similarity(q_vec, s_vec)
                    final_sc += max(0.0, float(cos_sim)) * 1.8
                except Exception:
                    pass

            # Curva de saturação exponencial estrita [0.0 .. 0.99]
            norm_conf = min(0.99, max(0.0, 1.0 - math.exp(-final_sc / 3.8)))
            boosted.append((norm_conf, s))

        boosted.sort(key=lambda kv: kv[0], reverse=True)

        matched: List[Dict[str, Any]] = []
        seen_matched_names: Set[str] = set()
        for conf, s in boosted:
            s_name = s["name"]
            if s_name in seen_matched_names:
                continue
            if conf >= min_score:
                seen_matched_names.add(s_name)
                matched.append({
                    "name": s_name,
                    "slug": s["slug"],
                    "plugin": s["plugin"],
                    "path": s["path"].replace("\\", "/"),
                    "description": s["description"],
                    "score": round(conf, 3),
                })
            if len(matched) >= top_k:
                break

        # Formatar a linha de diretiva compacta
        directive_line = ""
        if matched:
            parts = [f"{m['name']} ({m['path']})" for m in matched]
            directive_line = f"🎯[SKILL_RESOLVER]: {' | '.join(parts)}"

        latency = round((time.perf_counter() - t0) * 1000, 2)

        return {
            "ok": True,
            "query": raw_q,
            "total_skills_indexed": total_skills,
            "matched_skills": matched,
            "directive_line": directive_line,
            "latency_ms": latency,
        }

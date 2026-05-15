"""Expert Search Engine for Reality OS.

Domain-specific knowledge retrieval that manages configurable sources,
optimizes queries, scores results on 7 dimensions, auto-absorbs high-quality
findings, and supports scheduled searches. Thread-safe via core._lock.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from .knowledge_core import get_core, _utc_now_iso, _new_id, tokenize, STOPWORDS
from .security_scanner import has_blocking_finding, scan_text

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SearchSource:
    id: str; domain: str; name: str; url_pattern: str; trust_score: float
    category: str; enabled: bool; fetch_interval_minutes: int; last_fetched: str | None
    def to_dict(self) -> dict[str, Any]:
        return vars(self) | {"trust_score": round(self.trust_score, 3)}

@dataclass
class SearchResult:
    id: str; title: str; snippet: str; url: str; source_id: str
    published_date: str | None; scores: dict[str, float]; total_score: float; absorbed: bool
    security_flags: list[str] = field(default_factory=list); content_role: str = "evidence"
    snapshot_id: str | None = None; excerpt_hash: str | None = None
    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title, "snippet": self.snippet,
                "url": self.url, "source_id": self.source_id,
                "published_date": self.published_date,
                "scores": {k: round(v, 3) for k, v in self.scores.items()},
                "total_score": round(self.total_score, 3), "absorbed": self.absorbed,
                "security_flags": list(self.security_flags), "content_role": self.content_role,
                "snapshot_id": self.snapshot_id, "excerpt_hash": self.excerpt_hash}

@dataclass
class AutoSearchTask:
    id: str; tenant_id: str; query: str; sources: list[str]
    schedule: str; last_run: str | None; enabled: bool
    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "tenant_id": self.tenant_id, "query": self.query,
                "sources": list(self.sources), "schedule": self.schedule,
                "last_run": self.last_run, "enabled": self.enabled}

# ---------------------------------------------------------------------------
# Preset domain sources
# ---------------------------------------------------------------------------

def _src(domain: str, name: str, score: float, cat: str, pattern: str) -> dict[str, Any]:
    return {"domain": domain, "name": name, "trust_score": score,
            "category": cat, "url_pattern": pattern}

PRESET_SOURCES: list[dict[str, Any]] = [
    # AI / Tech
    _src("arxiv.org", "arXiv", 0.95, "ai_tech", "https://arxiv.org/search/?query={q}"),
    _src("huggingface.co", "Hugging Face", 0.9, "ai_tech", "https://huggingface.co/search?q={q}"),
    _src("github.com", "GitHub", 0.85, "ai_tech", "https://github.com/search?q={q}"),
    _src("openai.com", "OpenAI", 0.9, "ai_tech", "https://openai.com/search?q={q}"),
    _src("anthropic.com", "Anthropic", 0.9, "ai_tech", "https://anthropic.com/search?q={q}"),
    # Finance
    _src("bloomberg.com", "Bloomberg", 0.95, "finance", "https://www.bloomberg.com/search?query={q}"),
    _src("ft.com", "Financial Times", 0.9, "finance", "https://www.ft.com/search?q={q}"),
    _src("sec.gov", "SEC EDGAR", 0.95, "finance", "https://efts.sec.gov/LATEST/search-index?q={q}"),
    _src("seekingalpha.com", "Seeking Alpha", 0.7, "finance", "https://seekingalpha.com/search?q={q}"),
    # Crypto
    _src("coingecko.com", "CoinGecko", 0.85, "crypto", "https://www.coingecko.com/en/search?query={q}"),
    _src("defillama.com", "DefiLlama", 0.8, "crypto", "https://defillama.com/search?q={q}"),
    _src("etherscan.io", "Etherscan", 0.85, "crypto", "https://etherscan.io/search?q={q}"),
    # Business
    _src("hbr.org", "Harvard Business Review", 0.9, "business", "https://hbr.org/search?term={q}"),
    _src("mckinsey.com", "McKinsey", 0.85, "business", "https://www.mckinsey.com/search?q={q}"),
    _src("a16z.com", "a16z", 0.8, "business", "https://a16z.com/search?q={q}"),
    _src("ycombinator.com", "Y Combinator", 0.8, "business", "https://www.ycombinator.com/search?q={q}"),
    # Social / Trends
    _src("twitter.com", "Twitter/X", 0.6, "social_trends", "https://twitter.com/search?q={q}"),
    _src("youtube.com", "YouTube", 0.5, "social_trends", "https://www.youtube.com/results?search_query={q}"),
    _src("reddit.com", "Reddit", 0.55, "social_trends", "https://www.reddit.com/search/?q={q}"),
    # General
    _src("wikipedia.org", "Wikipedia", 0.8, "general", "https://en.wikipedia.org/w/index.php?search={q}"),
    _src("scholar.google.com", "Google Scholar", 0.9, "general", "https://scholar.google.com/scholar?q={q}"),
]

# ---------------------------------------------------------------------------
# Scoring engine — 7 weighted dimensions
# ---------------------------------------------------------------------------

_SCORE_WEIGHTS = {
    "authority": 0.25, "freshness": 0.20, "relevance": 0.20,
    "evidence_density": 0.15, "uniqueness": 0.10, "verifiability": 0.05, "controversy": 0.05}
_EVIDENCE_RE = re.compile(
    r"\d+%|\$[\d,.]+|€[\d,.]+|¥[\d,.]+|\[\d+\]|fig\.\s*\d|table\s*\d|p\s*[<>=]\s*0\.\d", re.I)
_CONTROVERSY_RE = re.compile(
    r"\bhowever\b|\bbut\b|\bconversely\b|\bdebat|\bcontrovers|\bdisputed\b"
    r"|\b然而\b|\b但是\b|\b争议\b|\b相反\b", re.I)


def score_search_result(
    *, title: str, snippet: str, url: str, source_trust: float,
    published_date: str | None, query: str, existing_titles: list[str] | None = None,
) -> dict[str, float]:
    """Score a result on 7 dimensions. Returns per-dimension + total."""
    text = f"{title} {snippet}"
    authority = min(1.0, source_trust * 1.05)
    # Freshness — exponential decay (1.0 today, ~0.5 at 30d, ~0.1 at 365d)
    freshness = 0.5
    if published_date:
        try:
            pub = datetime.fromisoformat(published_date.replace("Z", "+00:00"))
            freshness = math.exp(-0.0231 * max(0, (datetime.now(timezone.utc) - pub).days))
        except (ValueError, TypeError):
            pass
    # Relevance — token overlap
    q_tok = set(tokenize(query)) - STOPWORDS
    relevance = min(1.0, len(q_tok & (set(tokenize(text)) - STOPWORDS)) / max(len(q_tok), 1)) if q_tok else 0.3
    # Evidence density
    evidence_density = min(1.0, len(_EVIDENCE_RE.findall(text)) * 0.2)
    # Uniqueness
    uniqueness = 1.0
    if existing_titles:
        tl = title.lower()
        for ex in existing_titles:
            if ex.lower() in tl or tl in ex.lower():
                uniqueness = 0.3; break
            if set(tokenize(title)) & set(tokenize(ex)):
                tt, et = set(tokenize(title)), set(tokenize(ex))
                if tt and len(tt & et) / max(len(tt), 1) > 0.7:
                    uniqueness = 0.5; break
    # Verifiability
    verifiability = min(1.0, (0.4 if url else 0) + (0.3 if published_date else 0)
                        + (0.3 if len(snippet) > 80 else 0))
    # Controversy
    controversy = min(1.0, len(_CONTROVERSY_RE.findall(text)) * 0.25)

    scores = {"authority": authority, "freshness": freshness, "relevance": relevance,
              "evidence_density": evidence_density, "uniqueness": uniqueness,
              "verifiability": verifiability, "controversy": controversy}
    scores["total"] = sum(scores[d] * _SCORE_WEIGHTS[d] for d in _SCORE_WEIGHTS)
    return scores

# ---------------------------------------------------------------------------
# Query optimizer
# ---------------------------------------------------------------------------

def optimize_query(query: str, language: str = "en",
                   target_categories: list[str] | None = None) -> dict[str, Any]:
    """Optimize raw query into precise search terms. Tries LLM, falls back deterministic."""
    original = query.strip()
    keywords = [t for t in tokenize(original) if t not in STOPWORDS and len(t) > 2]
    # Attempt LLM expansion (graceful fallback to deterministic)
    try:
        from .model_registry import get_registry
        slot = get_registry().get_slot("generator")
        if slot and slot.enabled:
            raise NotImplementedError("LLM expansion placeholder")
    except Exception:
        pass
    seen: set[str] = set()
    terms = [kw for kw in keywords if not (kw in seen or seen.add(kw))]  # type: ignore[func-returns-value]
    optimized = " ".join(terms[:10])
    # Determine target sources
    targets = ([s["domain"] for s in PRESET_SOURCES if s["category"] in target_categories]
               if target_categories else _infer_sources(original))
    return {"original": original, "optimized": optimized,
            "search_terms": keywords[:10], "target_sources": targets}


def _infer_sources(query: str) -> list[str]:
    """Infer relevant source domains from query keywords."""
    lower = query.lower()
    triggers = {
        "ai_tech": ["ai", "model", "llm", "neural", "transformer", "gpt", "深度学习"],
        "finance": ["stock", "market", "invest", "earnings", "financial", "股票"],
        "crypto": ["crypto", "bitcoin", "ethereum", "defi", "blockchain", "加密"],
        "business": ["strategy", "startup", "venture", "management", "创业"],
        "social_trends": ["trending", "viral", "opinion", "热门"],
    }
    cats = {c for c, kws in triggers.items() if any(k in lower for k in kws)} or {"general", "ai_tech"}
    return [s["domain"] for s in PRESET_SOURCES if s["category"] in cats]

# ---------------------------------------------------------------------------
# Main search function
# ---------------------------------------------------------------------------

def expert_search(*, tenant_id: str, query: str, language: str = "en",
                  sources: list[str] | None = None, auto_absorb: bool = False,
                  run_id: str | None = None, actor: str = "user",
                  use_strategy_engine: bool = True,
                  use_model_optimization: bool = True) -> dict[str, Any]:
    """Execute expert search across configured domain sources.

    Scores results on 7 dimensions, optionally absorbs high-quality (>= 0.7).

    When use_strategy_engine=True, uses SearchStrategyEngine to select the best
    search strategy based on query intent signals instead of hardcoded logic.

    When use_model_optimization=True, calls optimize_query_with_model() for
    semantic query expansion and merges results from both original and optimized
    queries (union by URL, keeping highest score).

    Response includes: strategy_name, original_query, optimized_query, optimization_source.
    """
    from .trace import finish_run, record_step, start_run
    from .search_strategy import SearchStrategyEngine

    run_id = run_id or start_run(
        tenant_id=tenant_id,
        user_id=actor,
        entrypoint="expert_search",
        input_value=query,
        metadata={"language": language, "auto_absorb": auto_absorb, "source_count": len(sources or [])},
    )
    core = get_core()

    # --- Strategy engine integration ---
    strategy_name: str = "default"
    original_query: str = query
    optimized_query_str: str | None = None
    optimization_source: str = "deterministic"
    weight_adjustments: dict[str, float] = {}

    if use_strategy_engine:
        engine = SearchStrategyEngine()
        strategy_result = engine.select_strategy(
            query=query, language=language, tenant_id=tenant_id,
        )
        strategy_name = strategy_result.strategy_name
        optimization_source = strategy_result.optimization_source
        weight_adjustments = strategy_result.weight_adjustments

        record_step(
            run_id=run_id,
            step_type="search_strategy_select",
            input_value=query,
            output_value={
                "strategy_name": strategy_name,
                "source_selection": strategy_result.source_selection,
                "weight_adjustments": weight_adjustments,
            },
            metadata={"optimization_source": optimization_source},
        )

        # Use strategy engine's source selection (unless explicit sources provided)
        if sources:
            active = [s for s in PRESET_SOURCES if s["domain"] in sources]
        else:
            active = [s for s in PRESET_SOURCES if s["domain"] in strategy_result.source_selection]
        if not active:
            active = [s for s in PRESET_SOURCES if s["category"] == "general"]

        # Model-based query optimization
        if use_model_optimization:
            model_optimized, expanded_terms = engine.optimize_query_with_model(
                query=query, language=language, run_id=run_id,
            )
            if model_optimized:
                optimized_query_str = model_optimized
                optimization_source = "model"
    else:
        # Legacy path: use existing optimize_query logic
        opt = optimize_query(query, language)
        record_step(
            run_id=run_id,
            step_type="search_query_optimize",
            input_value=query,
            output_value=opt,
            metadata={"target_source_count": len(opt.get("target_sources", []))},
        )
        # Resolve active sources
        active = ([s for s in PRESET_SOURCES if s["domain"] in sources] if sources
                  else [s for s in PRESET_SOURCES if s["domain"] in opt["target_sources"]])
        if not active:
            active = [s for s in PRESET_SOURCES if s["category"] == "general"]

    # Build the deterministic optimized query for search execution
    opt = optimize_query(query, language)

    # Existing titles for uniqueness scoring
    with core._lock, core._connect() as db:
        rows = db.execute(
            "SELECT title FROM knowledge_items WHERE tenant_id = ? ORDER BY created_at DESC LIMIT 100",
            (tenant_id,)).fetchall()
        existing = [r["title"] for r in rows]

    # Effective score weights (apply strategy adjustments)
    effective_weights = dict(_SCORE_WEIGHTS)
    if weight_adjustments:
        for dim, weight in weight_adjustments.items():
            if dim in effective_weights:
                effective_weights[dim] = weight

    # --- Execute search with original query ---
    results: list[SearchResult] = []
    seen_urls: set[str] = set()

    def _execute_search(search_query: str, source_list: list[dict[str, Any]]) -> list[SearchResult]:
        """Execute search for a given query against source list, return scored results."""
        search_results: list[SearchResult] = []
        for src in source_list:
            for mock in _mock_results(src, opt["optimized"], search_query):
                findings = scan_text(mock["snippet"], source=f"expert_search:{src['domain']}")
                security_flags = [finding.pattern_id for finding in findings]
                sc = score_search_result(
                    title=mock["title"], snippet=mock["snippet"], url=mock["url"],
                    source_trust=src["trust_score"], published_date=mock.get("published_date"),
                    query=search_query, existing_titles=existing)
                # Apply weight adjustments if strategy engine provided them
                if weight_adjustments:
                    adjusted_total = sum(
                        sc.get(d, 0.0) * effective_weights.get(d, 0.0)
                        for d in effective_weights if d in sc
                    )
                    sc["total"] = adjusted_total
                result_id = _new_id("sr")
                snapshot = core.create_evidence_snapshot(
                    tenant_id=tenant_id,
                    title=mock["title"],
                    content=mock["snippet"],
                    source_kind="expert_search",
                    source_url=mock["url"],
                    publisher=src["domain"],
                    published_at=mock.get("published_date"),
                    credibility_score=sc["total"],
                    retrieval_score=sc.get("relevance"),
                    metadata={"run_id": run_id, "result_id": result_id, "source_id": src["domain"]},
                )
                search_results.append(SearchResult(
                    id=result_id, title=mock["title"], snippet=mock["snippet"],
                    url=mock["url"], source_id=src["domain"],
                    published_date=mock.get("published_date"),
                    scores={k: v for k, v in sc.items() if k != "total"},
                    total_score=sc["total"], absorbed=False,
                    security_flags=security_flags, content_role="evidence",
                    snapshot_id=snapshot.snapshot_id, excerpt_hash=snapshot.excerpt_hash))
        return search_results

    # Execute search with original query
    original_results = _execute_search(query, active)
    for r in original_results:
        if r.url not in seen_urls:
            results.append(r)
            seen_urls.add(r.url)

    # Execute search with model-optimized query (if available) and merge
    if optimized_query_str:
        optimized_results = _execute_search(optimized_query_str, active)
        for r in optimized_results:
            if r.url not in seen_urls:
                results.append(r)
                seen_urls.add(r.url)
            else:
                # URL already seen — keep the one with the highest score
                for i, existing_r in enumerate(results):
                    if existing_r.url == r.url and r.total_score > existing_r.total_score:
                        results[i] = r
                        break

    results.sort(key=lambda r: r.total_score, reverse=True)
    record_step(
        run_id=run_id,
        step_type="search_fetch",
        input_value={"query": query, "sources": [s["domain"] for s in active]},
        output_value=[r.id for r in results],
        metadata={
            "result_count": len(results),
            "flagged_results": sum(1 for r in results if r.security_flags),
            "fetch_mode": "mock",
            "optimized_query_used": optimized_query_str is not None,
        },
    )
    # Auto-absorb high-quality results
    absorbed = 0
    if auto_absorb:
        for r in results:
            findings = scan_text(r.snippet, source=f"expert_search:{r.source_id}")
            if r.total_score >= 0.7 and not has_blocking_finding(findings):
                try:
                    core.absorb(tenant_id=tenant_id, title=r.title, body=r.snippet,
                                source_kind="expert_search", source_url=r.url,
                                tags=["expert_search", r.source_id],
                                freshness_date=r.published_date, language=language,
                                actor="expert_search", snapshot_id=r.snapshot_id)
                    r.absorbed = True; absorbed += 1
                except (ValueError, sqlite3.IntegrityError):
                    pass
        record_step(
            run_id=run_id,
            step_type="search_auto_absorb",
            input_value={"result_count": len(results)},
            output_value={"absorbed_count": absorbed},
            metadata={"blocked_by_security": sum(1 for r in results if r.security_flags)},
        )

    response = {"run_id": run_id, "optimized_query": opt, "results": [r.to_dict() for r in results],
                "total_results": len(results), "absorbed_count": absorbed,
                "sources_searched": [s["domain"] for s in active],
                "strategy_name": strategy_name,
                "original_query": original_query,
                "optimized_query_model": optimized_query_str,
                "optimization_source": optimization_source}
    finish_run(
        run_id,
        output_value={
            "total_results": len(results),
            "absorbed_count": absorbed,
            "sources_searched": [s["domain"] for s in active],
            "strategy_name": strategy_name,
        },
    )
    return response
def _mock_results(src: dict[str, Any], opt_q: str, raw_q: str) -> list[dict[str, Any]]:
    """Deterministic mock results per source. Placeholder for real HTTP."""
    url = src["url_pattern"].format(q=opt_q.replace(" ", "+"))
    now = _utc_now_iso()
    return [{"title": f"[{src['name']}] Expert analysis: {raw_q[:60]}",
             "snippet": f"Coverage from {src['name']} on {opt_q}. "
                        "42% improvement noted, peer-reviewed [1][2].",
             "url": url, "published_date": now},
            {"title": f"[{src['name']}] Recent: {raw_q[:40]}",
             "snippet": f"Latest from {src['domain']}. However, some dispute this. "
                        "Revenue impact: $2.3M annually.",
             "url": f"https://{src['domain']}/a/{_new_id('art')}", "published_date": now}]

# ---------------------------------------------------------------------------
# Source management (SQLite-backed)
# ---------------------------------------------------------------------------

def ensure_search_schema(db: sqlite3.Connection) -> None:
    """Create expert search tables if they don't exist."""
    db.executescript(
        "CREATE TABLE IF NOT EXISTS search_sources ("
        "id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, domain TEXT NOT NULL,"
        "name TEXT NOT NULL, url_pattern TEXT NOT NULL,"
        "trust_score REAL NOT NULL DEFAULT 0.5, category TEXT NOT NULL DEFAULT 'general',"
        "enabled INTEGER NOT NULL DEFAULT 1, fetch_interval_minutes INTEGER NOT NULL DEFAULT 60,"
        "last_fetched TEXT, created_at TEXT NOT NULL);"
        "CREATE INDEX IF NOT EXISTS idx_search_sources_tenant ON search_sources(tenant_id, enabled);"
        "CREATE TABLE IF NOT EXISTS auto_search_tasks ("
        "id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, query TEXT NOT NULL,"
        "sources_json TEXT NOT NULL DEFAULT '[]', schedule TEXT NOT NULL DEFAULT 'daily',"
        "last_run TEXT, enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);"
        "CREATE INDEX IF NOT EXISTS idx_auto_search_tenant ON auto_search_tasks(tenant_id, enabled);"
    )


def list_sources(tenant_id: str) -> list[SearchSource]:
    """List all configured search sources for a tenant."""
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_search_schema(db)
        rows = db.execute(
            "SELECT * FROM search_sources WHERE tenant_id = ? ORDER BY category, domain",
            (tenant_id,)).fetchall()
        return [_row_to_source(r) for r in rows]


def add_source(tenant_id: str, *, domain: str, name: str, url_pattern: str,
               trust_score: float = 0.5, category: str = "general",
               fetch_interval_minutes: int = 60) -> SearchSource:
    """Add a new search source for a tenant."""
    core = get_core()
    sid = _new_id("src")
    now = _utc_now_iso()
    with core._lock, core._connect() as db:
        ensure_search_schema(db)
        db.execute("INSERT INTO search_sources VALUES (?,?,?,?,?,?,?,1,?,NULL,?)",
                   (sid, tenant_id, domain, name, url_pattern, trust_score,
                    category, fetch_interval_minutes, now))
    return SearchSource(id=sid, domain=domain, name=name, url_pattern=url_pattern,
                        trust_score=trust_score, category=category, enabled=True,
                        fetch_interval_minutes=fetch_interval_minutes, last_fetched=None)


def update_source(tenant_id: str, source_id: str, **kwargs: Any) -> SearchSource | None:
    """Update fields on an existing search source."""
    allowed = {"domain", "name", "url_pattern", "trust_score", "category",
               "enabled", "fetch_interval_minutes", "last_fetched"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return None
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_search_schema(db)
        clause = ", ".join(f"{k} = ?" for k in updates)
        db.execute(f"UPDATE search_sources SET {clause} WHERE tenant_id = ? AND id = ?",
                   [*updates.values(), tenant_id, source_id])
        row = db.execute("SELECT * FROM search_sources WHERE id = ? AND tenant_id = ?",
                         (source_id, tenant_id)).fetchone()
        return _row_to_source(row) if row else None


def delete_source(tenant_id: str, source_id: str) -> bool:
    """Delete a search source. Returns True if deleted."""
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_search_schema(db)
        return db.execute("DELETE FROM search_sources WHERE id = ? AND tenant_id = ?",
                          (source_id, tenant_id)).rowcount > 0


def get_preset_sources() -> list[dict[str, Any]]:
    """Return the built-in preset source list."""
    return list(PRESET_SOURCES)


def _row_to_source(row: sqlite3.Row) -> SearchSource:
    return SearchSource(id=row["id"], domain=row["domain"], name=row["name"],
                        url_pattern=row["url_pattern"], trust_score=row["trust_score"],
                        category=row["category"], enabled=bool(row["enabled"]),
                        fetch_interval_minutes=row["fetch_interval_minutes"],
                        last_fetched=row["last_fetched"])

# ---------------------------------------------------------------------------
# Auto-search task management
# ---------------------------------------------------------------------------

def create_auto_search(tenant_id: str, *, query: str,
                       sources: list[str] | None = None,
                       schedule: str = "daily") -> AutoSearchTask:
    """Create a new automatic search task."""
    core = get_core()
    tid = _new_id("ast")
    now = _utc_now_iso()
    src_list = sources or []
    with core._lock, core._connect() as db:
        ensure_search_schema(db)
        db.execute("INSERT INTO auto_search_tasks VALUES (?,?,?,?,?,NULL,1,?)",
                   (tid, tenant_id, query, json.dumps(src_list), schedule, now))
    return AutoSearchTask(id=tid, tenant_id=tenant_id, query=query,
                          sources=src_list, schedule=schedule,
                          last_run=None, enabled=True)


def list_auto_searches(tenant_id: str) -> list[AutoSearchTask]:
    """List all auto-search tasks for a tenant."""
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_search_schema(db)
        rows = db.execute(
            "SELECT * FROM auto_search_tasks WHERE tenant_id = ? ORDER BY created_at DESC",
            (tenant_id,)).fetchall()
        return [AutoSearchTask(id=r["id"], tenant_id=r["tenant_id"], query=r["query"],
                               sources=json.loads(r["sources_json"]), schedule=r["schedule"],
                               last_run=r["last_run"], enabled=bool(r["enabled"]))
                for r in rows]


def run_auto_search(tenant_id: str, task_id: str) -> dict[str, Any] | None:
    """Execute an auto-search task. Returns None if task not found or disabled."""
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_search_schema(db)
        row = db.execute(
            "SELECT * FROM auto_search_tasks WHERE id = ? AND tenant_id = ? AND enabled = 1",
            (task_id, tenant_id)).fetchone()
        if not row:
            return None
        query = row["query"]
        srcs = json.loads(row["sources_json"]) or None

    results = expert_search(tenant_id=tenant_id, query=query,
                            sources=srcs, auto_absorb=True)
    now = _utc_now_iso()
    with core._lock, core._connect() as db:
        db.execute("UPDATE auto_search_tasks SET last_run = ? WHERE id = ?", (now, task_id))

    results["task_id"] = task_id
    results["run_at"] = now
    return results

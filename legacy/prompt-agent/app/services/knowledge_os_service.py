from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.core.config import settings
from app.services.personal_wiki_service import PersonalWikiService, open_allowed_path


VALID_CLAIM_STATUSES = {"needs_review", "supported", "contradicted", "outdated", "disputed"}
VALID_REVIEW_STATUSES = {"pending", "approved", "rejected"}


class KnowledgeOSService:
    def __init__(self, root_path: Path | None = None) -> None:
        self.root_path = root_path or settings.knowledge_os_path
        self.personal_wiki = PersonalWikiService(self.root_path)

    @property
    def sources_path(self) -> Path:
        return self.root_path / "wiki" / "sources"

    @property
    def claims_path(self) -> Path:
        return self.root_path / "claims" / "claims.jsonl"

    @property
    def nodes_path(self) -> Path:
        return self.root_path / "graph" / "nodes.jsonl"

    @property
    def edges_path(self) -> Path:
        return self.root_path / "graph" / "edges.jsonl"

    @property
    def review_queue_path(self) -> Path:
        return self.root_path / "graph" / "review_queue.jsonl"

    @property
    def log_path(self) -> Path:
        return self.root_path / "log.md"

    def ensure_structure(self) -> None:
        for path in [self.sources_path, self.claims_path.parent, self.nodes_path.parent, self.root_path / "skills"]:
            path.mkdir(parents=True, exist_ok=True)
        for file in [self.claims_path, self.nodes_path, self.edges_path, self.review_queue_path]:
            if not file.exists():
                file.write_text("", encoding="utf-8")
        if not self.log_path.exists():
            self.log_path.write_text("# Knowledge OS Log\n\n", encoding="utf-8")
        self.personal_wiki.ensure_structure()

    def list_sources(self, query: str = "", collection: str = "", tag: str = "") -> list[dict[str, Any]]:
        self.ensure_structure()
        items = [self._source_item(path) for path in sorted(self.sources_path.glob("*.md"), reverse=True)]
        if query.strip():
            needle = query.strip().lower()
            items = [
                item
                for item in items
                if needle in f"{item['title']} {item['filename']} {item.get('summary', '')} {' '.join(item.get('tags', []))}".lower()
            ]
        if collection.strip():
            items = [item for item in items if item.get("collection", "").lower() == collection.strip().lower()]
        if tag.strip():
            needle = tag.strip().lower()
            items = [item for item in items if needle in [value.lower() for value in item.get("tags", [])]]
        return items

    def get_source(self, source_id: str) -> dict[str, Any]:
        path = self._source_path(source_id)
        item = self._source_item(path)
        item["content"] = path.read_text(encoding="utf-8")
        return item

    def update_source(self, source_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        path = self._source_path(source_id)
        meta, body = _frontmatter(path.read_text(encoding="utf-8"))
        if updates.get("content") is not None:
            incoming_meta, incoming_body = _frontmatter(str(updates["content"]))
            meta.update(incoming_meta)
            body = incoming_body
        for key in ["title", "summary", "collection"]:
            if updates.get(key) is not None:
                meta[key] = str(updates[key]).strip()
        if updates.get("tags") is not None:
            meta["tags"] = ", ".join(_normalize_list(updates["tags"]))
        meta["last_updated"] = _now()
        path.write_text(_compose_markdown(meta, body), encoding="utf-8")
        self.append_log("update_source", {"id": source_id, "filename": path.name})
        return self.get_source(source_id)

    def delete_source(self, source_id: str) -> None:
        path = self._source_path(source_id)
        path.unlink()
        self.append_log("delete_source", {"id": source_id, "filename": path.name})

    def open_root_folder(self) -> tuple[bool, str, Path]:
        self.ensure_structure()
        path = self.root_path.resolve()
        opened, message = open_allowed_path(path, self.root_path)
        return opened, message, path

    def open_source_file(self, source_id: str) -> tuple[bool, str, Path]:
        path = self._source_path(source_id).resolve()
        opened, message = open_allowed_path(path, self.root_path)
        return opened, message, path

    def search(self, query: str = "", collection: str = "", tag: str = "") -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        for source in self.list_sources(query=query, collection=collection, tag=tag):
            results.append(
                {
                    "type": "source",
                    "id": str(source["id"]),
                    "title": str(source["title"]),
                    "filename": str(source["filename"]),
                    "snippet": str(source.get("summary", ""))[:240],
                }
            )
        needle = query.strip().lower()
        for claim in self.list_claims():
            if needle and needle not in f"{claim.get('text', '')} {claim.get('source_page', '')}".lower():
                continue
            results.append(
                {
                    "type": "claim",
                    "id": str(claim["id"]),
                    "title": str(claim.get("text", ""))[:80],
                    "filename": str(claim.get("source_page", "")),
                    "snippet": str(claim.get("text", ""))[:240],
                }
            )
        return results

    def list_claims(self, query: str = "", status: str = "", min_confidence: float | None = None) -> list[dict[str, Any]]:
        self.ensure_structure()
        claims = [self._normalize_claim(item, index) for index, item in enumerate(_read_jsonl(self.claims_path))]
        if query.strip():
            needle = query.strip().lower()
            claims = [item for item in claims if needle in f"{item.get('text', '')} {item.get('source_page', '')}".lower()]
        if status.strip():
            claims = [item for item in claims if item.get("status") == status.strip()]
        if min_confidence is not None:
            claims = [item for item in claims if float(item.get("confidence") or 0) >= min_confidence]
        return claims

    def update_claim(self, claim_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        claim_id = _safe_id(claim_id)
        claims = self.list_claims()
        for claim in claims:
            if claim["id"] != claim_id:
                continue
            if updates.get("text") is not None:
                claim["text"] = str(updates["text"]).strip()
            if updates.get("status") is not None:
                status = str(updates["status"]).strip()
                if status not in VALID_CLAIM_STATUSES:
                    raise ValueError("Unknown claim status.")
                claim["status"] = status
            if updates.get("confidence") is not None:
                claim["confidence"] = float(updates["confidence"])
            if updates.get("evidence") is not None:
                claim["evidence"] = updates["evidence"]
            if updates.get("source_page") is not None:
                claim["source_page"] = str(updates["source_page"]).strip()
            claim["updated_at"] = _now()
            _write_jsonl(self.claims_path, claims)
            self.append_log("update_claim", {"id": claim_id})
            return claim
        raise FileNotFoundError("Claim not found.")

    def delete_claim(self, claim_id: str) -> None:
        claim_id = _safe_id(claim_id)
        claims = self.list_claims()
        next_claims = [item for item in claims if item["id"] != claim_id]
        if len(next_claims) == len(claims):
            raise FileNotFoundError("Claim not found.")
        _write_jsonl(self.claims_path, next_claims)
        self.append_log("delete_claim", {"id": claim_id})

    def list_review_queue(self) -> list[dict[str, Any]]:
        self.ensure_structure()
        return [self._review_summary(item, index) for index, item in enumerate(_read_jsonl(self.review_queue_path))]

    def get_review_item(self, review_id: str) -> dict[str, Any]:
        item, _ = self._find_review_item(review_id)
        return item

    def update_review_item(self, review_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        item, items = self._find_review_item(review_id)
        for key in ["summary", "claims", "nodes", "edges", "evidence"]:
            if updates.get(key) is not None:
                item[key] = updates[key]
        if updates.get("status") is not None:
            status = str(updates["status"]).strip()
            if status not in VALID_REVIEW_STATUSES:
                raise ValueError("Unknown review status.")
            item["status"] = status
        item["updated_at"] = _now()
        _write_jsonl(self.review_queue_path, items)
        self.append_log("update_review_item", {"id": review_id})
        return item

    def approve_review_item(self, review_id: str) -> dict[str, Any]:
        item, items = self._find_review_item(review_id)
        nodes = [self._normalize_node(node, index) for index, node in enumerate(item.get("nodes") or [])]
        edges = [self._normalize_edge(edge, index) for index, edge in enumerate(item.get("edges") or [])]
        self._append_unique(self.nodes_path, nodes, "id")
        self._append_unique(self.edges_path, edges, "id")
        item["status"] = "approved"
        item["approved_at"] = _now()
        _write_jsonl(self.review_queue_path, items)
        self.append_log("approve_review_item", {"id": review_id, "nodes": len(nodes), "edges": len(edges)})
        return item

    def reject_review_item(self, review_id: str) -> dict[str, Any]:
        item, items = self._find_review_item(review_id)
        item["status"] = "rejected"
        item["rejected_at"] = _now()
        _write_jsonl(self.review_queue_path, items)
        self.append_log("reject_review_item", {"id": review_id})
        return item

    def list_nodes(self, query: str = "") -> list[dict[str, Any]]:
        self.ensure_structure()
        nodes = [self._normalize_node(item, index) for index, item in enumerate(_read_jsonl(self.nodes_path))]
        if query.strip():
            needle = query.strip().lower()
            nodes = [item for item in nodes if needle in json.dumps(item, ensure_ascii=False).lower()]
        return nodes

    def update_node(self, node_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        node_id = _safe_id(node_id)
        nodes = self.list_nodes()
        for node in nodes:
            if node["id"] != node_id:
                continue
            for key in ["type", "name", "source"]:
                if updates.get(key) is not None:
                    node[key] = str(updates[key]).strip()
            if updates.get("aliases") is not None:
                node["aliases"] = _normalize_list(updates["aliases"])
            node["updated_at"] = _now()
            _write_jsonl(self.nodes_path, nodes)
            self.append_log("update_graph_node", {"id": node_id})
            return node
        raise FileNotFoundError("Graph node not found.")

    def delete_node(self, node_id: str) -> None:
        node_id = _safe_id(node_id)
        nodes = self.list_nodes()
        next_nodes = [item for item in nodes if item["id"] != node_id]
        if len(next_nodes) == len(nodes):
            raise FileNotFoundError("Graph node not found.")
        _write_jsonl(self.nodes_path, next_nodes)
        self.append_log("delete_graph_node", {"id": node_id})

    def list_edges(self, query: str = "") -> list[dict[str, Any]]:
        self.ensure_structure()
        edges = [self._normalize_edge(item, index) for index, item in enumerate(_read_jsonl(self.edges_path))]
        if query.strip():
            needle = query.strip().lower()
            edges = [item for item in edges if needle in json.dumps(item, ensure_ascii=False).lower()]
        return edges

    def update_edge(self, edge_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        edge_id = _safe_id(edge_id)
        edges = self.list_edges()
        for edge in edges:
            if edge["id"] != edge_id:
                continue
            for key in ["type", "to", "source"]:
                if updates.get(key) is not None:
                    edge[key] = str(updates[key]).strip()
            if updates.get("from_node") is not None:
                edge["from"] = str(updates["from_node"]).strip()
            if updates.get("from") is not None:
                edge["from"] = str(updates["from"]).strip()
            if updates.get("confidence") is not None:
                edge["confidence"] = float(updates["confidence"])
            edge["updated_at"] = _now()
            _write_jsonl(self.edges_path, edges)
            self.append_log("update_graph_edge", {"id": edge_id})
            return edge
        raise FileNotFoundError("Graph edge not found.")

    def delete_edge(self, edge_id: str) -> None:
        edge_id = _safe_id(edge_id)
        edges = self.list_edges()
        next_edges = [item for item in edges if item["id"] != edge_id]
        if len(next_edges) == len(edges):
            raise FileNotFoundError("Graph edge not found.")
        _write_jsonl(self.edges_path, next_edges)
        self.append_log("delete_graph_edge", {"id": edge_id})

    def open_graph_folder(self) -> tuple[bool, str, Path]:
        self.ensure_structure()
        path = (self.root_path / "graph").resolve()
        opened, message = open_allowed_path(path, self.root_path)
        return opened, message, path

    def logs(self) -> dict[str, Any]:
        self.ensure_structure()
        content = self.log_path.read_text(encoding="utf-8")
        entries = [line for line in content.splitlines() if line.strip().startswith("- ")]
        return {"content": content, "entries": entries[-200:]}

    def open_log_file(self) -> tuple[bool, str, Path]:
        self.ensure_structure()
        path = self.log_path.resolve()
        opened, message = open_allowed_path(path, self.root_path)
        return opened, message, path

    def level_up(self, payload: dict[str, Any], provider: Any = None) -> dict[str, Any]:
        self.ensure_structure()
        text = str(payload.get("selected_text") or "").strip()
        if not text:
            raise ValueError("Level Up content is required.")
        collection = str(payload.get("collection") or "level-up").strip() or "level-up"
        tags = _normalize_list(payload.get("tags") or ["level-up"]) or ["level-up"]
        capture_id = str(uuid.uuid4())

        # LLM-enhanced extraction when a real provider is available
        llm_data: dict[str, Any] = {}
        if provider is not None:
            try:
                from app.providers.mock import MockProvider as _Mock
                if not isinstance(provider, _Mock):
                    from app.services.level_up_llm import extract_knowledge
                    llm_data = extract_knowledge(text, provider)
            except Exception:  # noqa: BLE001
                pass

        title = (
            str(llm_data.get("title") or payload.get("title") or "").strip()
            or _first_line(text)
            or "Level Up Source"
        )
        summary = str(llm_data.get("summary") or "").strip() or _summarize(text, 420)

        source_page = self._write_source(capture_id, title, text, collection, tags, str(payload.get("url") or ""))

        # Build claims from LLM output or fall back to rule-based
        llm_claims = llm_data.get("claims") or []
        if llm_claims:
            claims = [
                {
                    "id": f"claim_{capture_id}_{i}",
                    "text": str(c.get("text", "")).strip(),
                    "status": "needs_review",
                    "confidence": float(c.get("confidence", 0.5)),
                    "evidence": [{"source_page": source_page, "quote": text[:240]}],
                    "source_page": source_page,
                    "created_at": _now(),
                }
                for i, c in enumerate(llm_claims)
                if c.get("text")
            ]
        else:
            claims = [
                {
                    "id": f"claim_{capture_id}",
                    "text": _first_sentence(text) or summary,
                    "status": "needs_review",
                    "confidence": 0.5,
                    "evidence": [{"source_page": source_page, "quote": text[:240]}],
                    "source_page": source_page,
                    "created_at": _now(),
                }
            ]

        # Build nodes from LLM output or fall back to single source node
        llm_nodes = llm_data.get("nodes") or []
        if llm_nodes:
            nodes = [
                {
                    "id": f"node_{capture_id}_{i}",
                    "type": str(n.get("type", "Concept")).strip(),
                    "name": str(n.get("name", "")).strip(),
                    "aliases": list(n.get("aliases") or []),
                    "source": source_page,
                }
                for i, n in enumerate(llm_nodes)
                if n.get("name")
            ]
        else:
            nodes = [
                {
                    "id": f"source_{capture_id}",
                    "type": "Source",
                    "name": title,
                    "aliases": [],
                    "source": source_page,
                }
            ]

        # Build edges from LLM output
        llm_edges = llm_data.get("edges") or []
        edges = [
            {
                "from": str(e.get("from", "")).strip(),
                "type": str(e.get("type", "related_to")).strip(),
                "to": str(e.get("to", "")).strip(),
                "confidence": float(e.get("confidence", 0.6)),
                "source": source_page,
            }
            for e in llm_edges
            if e.get("from") and e.get("to")
        ]

        review_item_id = f"review_{capture_id}"
        review_item = {
            "id": review_item_id,
            "source_title": title,
            "source_page": source_page,
            "summary": summary,
            "claims": claims,
            "nodes": nodes,
            "edges": edges,
            "evidence": [{"source_page": source_page, "quote": text[:500]}],
            "status": "pending",
            "created_at": _now(),
        }
        self._append_unique(self.claims_path, claims, "id")
        self._append_unique(self.review_queue_path, [review_item], "id")
        self.append_log(
            "level_up",
            {
                "capture_id": capture_id,
                "source_page": source_page,
                "review_item_id": review_item_id,
                "llm_enhanced": bool(llm_data),
            },
        )
        return {
            "capture_id": capture_id,
            "source_page": source_page,
            "summary": summary,
            "claims": claims,
            "nodes": nodes,
            "edges": edges,
            "review_item_id": review_item_id,
        }

    def append_log(self, action: str, details: dict[str, Any]) -> None:
        self.ensure_structure()
        self.log_path.write_text(
            self.log_path.read_text(encoding="utf-8")
            + f"- {_now()} `{action}` {json.dumps(details, ensure_ascii=False, sort_keys=True)}\n",
            encoding="utf-8",
        )

    def create_note(self, title: str, content: str, collection: str = "notes", tags: list[str] | None = None) -> dict[str, Any]:
        """Save a confirmed note directly — bypasses review queue."""
        self.ensure_structure()
        filename = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{_slugify(title)}.md"
        path = (self.sources_path / filename).resolve()
        self._assert_inside_root(path)
        tags_list = tags or ["note"]
        meta = {
            "title": title,
            "summary": _summarize(content, 220),
            "collection": collection,
            "tags": ", ".join(tags_list),
            "created_at": _now(),
        }
        path.write_text(_compose_markdown(meta, content), encoding="utf-8")
        self.append_log("create_note", {"filename": filename, "title": title, "collection": collection})
        return self._source_item(path)

    def import_file(self, file_path: str, collection: str = "import", tags: list[str] | None = None, provider: Any = None) -> dict[str, Any]:
        """Read a local file from disk and ingest it as a knowledge source."""
        from pathlib import Path as _P
        import_path = _P(file_path).resolve()
        if not import_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        text = import_path.read_text(encoding="utf-8", errors="replace")
        title = import_path.stem.replace("_", " ").replace("-", " ").strip() or import_path.name
        payload = {
            "selected_text": text,
            "title": title,
            "collection": collection,
            "tags": tags or ["import"],
            "url": import_path.as_uri(),
        }
        return self.level_up(payload, provider=provider)

    @property
    def skills_path(self) -> Path:
        return self.root_path / "skills" / "skills.jsonl"

    def list_skills(self) -> list[dict[str, Any]]:
        self.ensure_structure()
        skills = _read_jsonl(self.skills_path)
        if not skills:
            self._seed_default_skills()
            skills = _read_jsonl(self.skills_path)
        return skills

    def create_skill(self, title: str, desc: str, system: str, user_template: str) -> dict[str, Any]:
        self.ensure_structure()
        skills = _read_jsonl(self.skills_path)
        existing_ids = {s.get("id", "") for s in skills}
        base_id = _slugify(title)
        skill_id = base_id
        counter = 1
        while skill_id in existing_ids:
            skill_id = f"{base_id}_{counter}"
            counter += 1
        skill: dict[str, Any] = {
            "id": skill_id,
            "title": title.strip(),
            "desc": desc.strip(),
            "system": system.strip(),
            "user_template": user_template.strip(),
            "created_at": _now(),
            "updated_at": _now(),
        }
        skills.append(skill)
        _write_jsonl(self.skills_path, skills)
        self.append_log("create_skill", {"id": skill_id, "title": title})
        return skill

    def update_skill(self, skill_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        skill_id = _safe_id(skill_id)
        skills = _read_jsonl(self.skills_path)
        for skill in skills:
            if skill.get("id") != skill_id:
                continue
            for key in ["title", "desc", "system", "user_template"]:
                if updates.get(key) is not None:
                    skill[key] = str(updates[key]).strip()
            skill["updated_at"] = _now()
            _write_jsonl(self.skills_path, skills)
            self.append_log("update_skill", {"id": skill_id})
            return skill
        raise FileNotFoundError("Skill not found.")

    def delete_skill(self, skill_id: str) -> None:
        skill_id = _safe_id(skill_id)
        skills = _read_jsonl(self.skills_path)
        next_skills = [s for s in skills if s.get("id") != skill_id]
        if len(next_skills) == len(skills):
            raise FileNotFoundError("Skill not found.")
        _write_jsonl(self.skills_path, next_skills)
        self.append_log("delete_skill", {"id": skill_id})

    def _seed_default_skills(self) -> None:
        now = _now()
        skills = [
            {
                "id": "deep_read",
                "title": "精读分析",
                "desc": "提取核心论点、关键概念、待验证问题，建立与已有知识的连接",
                "system": "你是学习教练，擅长结构化分析学习材料。",
                "user_template": (
                    "对以下材料进行精读分析（Karpathy exocortex 方法）。来源：{{title}}\n\n{{content}}\n\n"
                    "输出：\n1. 核心论点（1-3句）\n2. 关键概念（3-7个，含简短定义）\n"
                    "3. 多视角提问（定义/机制/应用/边界/历史，各2个）\n"
                    "4. 与已有知识的关系（支持/挑战/引出新问题）\n5. 待验证断言（2-4条）"
                ),
                "created_at": now, "updated_at": now,
            },
            {
                "id": "flashcard",
                "title": "生成闪卡",
                "desc": "从材料提取 Anki 风格问答对，用于主动回忆",
                "system": "你是学习专家，擅长设计高质量闪卡。",
                "user_template": (
                    "为以下材料生成 6-10 张闪卡（Anki 风格）。来源：{{title}}\n\n{{content}}\n\n"
                    "格式（每张一组）：\nQ: 问题\nA: 答案（简明，不超过2句）\n\n"
                    "要求：覆盖核心概念、边界条件、易错点；侧重理解而非死记硬背。"
                ),
                "created_at": now, "updated_at": now,
            },
            {
                "id": "question_map",
                "title": "提问地图",
                "desc": "从多个视角生成问题图谱，找出知识盲区",
                "system": "你是苏格拉底式教练，擅长用提问引导深度思考。",
                "user_template": (
                    "为以下材料生成结构化提问地图。来源：{{title}}\n\n{{content}}\n\n"
                    "按视角分组，各至少2个问题：\n"
                    "【定义视角】这个概念的本质是什么？\n【机制视角】它是怎么工作的？\n"
                    "【应用视角】什么场景用？什么场景不该用？\n"
                    "【边界视角】什么条件下会失效？\n【历史视角】怎么演化来的？"
                ),
                "created_at": now, "updated_at": now,
            },
            {
                "id": "synthesize",
                "title": "知识蒸馏",
                "desc": "提炼核心洞见，生成可跨领域迁移的心智模型",
                "system": "你是知识蒸馏专家，擅长提炼底层原理和心智模型。",
                "user_template": (
                    "对以下材料进行知识蒸馏，提炼可迁移的心智模型。来源：{{title}}\n\n{{content}}\n\n"
                    "输出：\n1. 一句话核心洞见\n2. 底层原理\n3. 3个可迁移场景\n4. 反例和边界\n5. 与其他经典模型的关联"
                ),
                "created_at": now, "updated_at": now,
            },
        ]
        _write_jsonl(self.skills_path, skills)

    def _write_source(self, capture_id: str, title: str, text: str, collection: str, tags: list[str], url: str) -> str:
        filename = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{_slugify(title)}.md"
        path = (self.sources_path / filename).resolve()
        self._assert_inside_root(path)
        meta = {
            "title": title,
            "summary": _summarize(text, 220),
            "collection": collection,
            "tags": ", ".join(tags),
            "created_at": _now(),
            "source_url": url,
            "capture_id": capture_id,
        }
        body = f"# {title}\n\n## 摘要\n\n{_summarize(text, 420)}\n\n## 原文\n\n{text}\n"
        path.write_text(_compose_markdown(meta, body), encoding="utf-8")
        return f"wiki/sources/{path.name}"

    def _source_item(self, path: Path) -> dict[str, Any]:
        self._assert_inside_root(path)
        meta, body = _frontmatter(path.read_text(encoding="utf-8"))
        source_url = str(meta.get("source_url") or meta.get("url") or "")
        return {
            "id": path.stem,
            "title": str(meta.get("title") or _first_heading(body) or path.stem),
            "filename": path.name,
            "collection": str(meta.get("collection") or ""),
            "tags": _normalize_list(meta.get("tags") or []),
            "created_at": str(meta.get("created_at") or meta.get("last_updated") or _mtime(path)),
            "source_domain": _domain(source_url),
            "summary": str(meta.get("summary") or _extract_summary(body) or _summarize(body, 220)),
        }

    def _source_path(self, source_id: str) -> Path:
        source_id = _safe_id(source_id)
        path = (self.sources_path / f"{source_id}.md").resolve()
        self._assert_inside_root(path)
        if not path.exists():
            raise FileNotFoundError("Source page not found.")
        return path

    def _review_summary(self, item: dict[str, Any], index: int) -> dict[str, Any]:
        item = dict(item)
        item.setdefault("id", f"review_{index}")
        item.setdefault("status", "pending")
        return {
            "id": item["id"],
            "source_title": item.get("source_title") or item.get("title") or item.get("source_page") or "",
            "summary": item.get("summary", ""),
            "claims_count": len(item.get("claims") or []),
            "nodes_count": len(item.get("nodes") or []),
            "edges_count": len(item.get("edges") or []),
            "status": item.get("status", "pending"),
            "created_at": item.get("created_at", ""),
        }

    def _find_review_item(self, review_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        review_id = _safe_id(review_id)
        items = []
        found: dict[str, Any] | None = None
        for index, item in enumerate(_read_jsonl(self.review_queue_path)):
            item = dict(item)
            item.setdefault("id", f"review_{index}")
            items.append(item)
            if item["id"] == review_id:
                found = item
        if found is None:
            raise FileNotFoundError("Review item not found.")
        return found, items

    def _append_unique(self, path: Path, records: list[dict[str, Any]], key: str) -> None:
        existing = _read_jsonl(path)
        seen = {str(item.get(key)) for item in existing if item.get(key)}
        for record in records:
            if not record.get(key) or str(record[key]) in seen:
                continue
            existing.append(record)
            seen.add(str(record[key]))
        _write_jsonl(path, existing)

    def _normalize_claim(self, item: dict[str, Any], index: int) -> dict[str, Any]:
        item = dict(item)
        item.setdefault("id", f"claim_{index}")
        item["text"] = str(item.get("text") or item.get("claim") or item.get("claim_text") or "")
        item["status"] = str(item.get("status") or "needs_review")
        if item["status"] not in VALID_CLAIM_STATUSES:
            item["status"] = "needs_review"
        item["confidence"] = float(item.get("confidence") or 0)
        item.setdefault("evidence", [])
        item.setdefault("source_page", item.get("source") or "")
        item.setdefault("created_at", "")
        return item

    def _normalize_node(self, item: dict[str, Any], index: int) -> dict[str, Any]:
        item = dict(item)
        item.setdefault("id", f"node_{index}")
        item.setdefault("type", "")
        item.setdefault("name", item.get("label") or item["id"])
        item["aliases"] = _normalize_list(item.get("aliases") or [])
        item.setdefault("source", "")
        return item

    def _normalize_edge(self, item: dict[str, Any], index: int) -> dict[str, Any]:
        item = dict(item)
        item["from"] = str(item.get("from") or item.get("from_node") or item.get("source_node") or "")
        item.setdefault("type", "")
        item["to"] = str(item.get("to") or item.get("to_node") or item.get("target_node") or "")
        item["confidence"] = float(item.get("confidence") or 0)
        item.setdefault("source", "")
        item.setdefault("id", _edge_id(item, index))
        return item

    def _assert_inside_root(self, path: Path) -> None:
        root = self.root_path.resolve()
        resolved = path.resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError("Knowledge OS path escapes root.")


def _safe_id(value: str) -> str:
    raw = value.strip()
    if not raw or "/" in raw or "\\" in raw or ".." in raw:
        raise ValueError("Invalid Knowledge OS id.")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", raw):
        raise ValueError("Invalid Knowledge OS id.")
    return raw


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
    return records


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records)
    path.write_text(body, encoding="utf-8")


def _frontmatter(markdown: str) -> tuple[dict[str, str], str]:
    if not markdown.startswith("---"):
        return {}, markdown
    parts = markdown.split("---", 2)
    if len(parts) < 3:
        return {}, markdown
    meta: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip("'\"")
    return meta, parts[2].strip()


def _compose_markdown(meta: dict[str, Any], body: str) -> str:
    lines = ["---"]
    for key, value in meta.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines).rstrip() + "\n\n" + body.strip() + "\n"


def _normalize_list(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_items = re.split(r"[,\n]+", value)
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = []
    return [str(item).strip() for item in raw_items if str(item).strip()]


def _first_heading(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.strip().startswith("# "):
            return line.strip()[2:].strip()
    return ""


def _extract_summary(markdown: str) -> str:
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        if line.strip() in {"## 摘要", "## Summary"}:
            block = []
            for next_line in lines[index + 1 :]:
                if next_line.strip().startswith("## "):
                    break
                if next_line.strip():
                    block.append(next_line.strip())
            return " ".join(block).strip()
    return ""


def _summarize(text: str, limit: int) -> str:
    cleaned = re.sub(r"^---.*?---", "", text, flags=re.S)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    return cleaned[:limit].rstrip() + ("..." if len(cleaned) > limit else "")


def _first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:80]
    return ""


def _first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[。.!?])\s+", text.strip(), maxsplit=1)
    return parts[0].strip()[:260] if parts and parts[0].strip() else ""


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._-")
    return slug[:60] if slug else f"source_{abs(hash(value)) % 1_000_000}"


def _domain(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    return parsed.netloc.lower()


def _mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _edge_id(item: dict[str, Any], index: int) -> str:
    raw = f"{item.get('from', '')}_{item.get('type', '')}_{item.get('to', '')}".strip("_")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("_")
    return safe[:120] if safe else f"edge_{index}"


from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.models.schemas import (
    CaptureRequest,
    CaptureResponse,
    FolderOpenResponse,
    GenerateRequest,
    GenerateResponse,
    KnowledgeOSClaimUpdateRequest,
    KnowledgeOSGraphEdgeUpdateRequest,
    KnowledgeOSGraphNodeUpdateRequest,
    KnowledgeOSSearchRequest,
    KnowledgeOSSourceUpdateRequest,
    LevelUpRequest,
    LevelUpResponse,
    ModelSettingsRequest,
    ModelSettingsResponse,
    PersonalSummaryTestResponse,
    PersonalWikiFileContent,
    PersonalWikiFileItem,
    PersonalWikiFileUpdateRequest,
    PromptLabCompareRequest,
    PromptLabCompareResponse,
    PromptLabTestRequest,
    PromptLabTestResponse,
    ProviderPreset,
)
from app.providers.presets import list_provider_presets
from app.services.knowledge_os_service import KnowledgeOSService
from app.services.prompt_agent import PromptAgent
from app.services.prompt_lab_service import PromptLabService
from app.services.settings_service import SettingsService


app = FastAPI(title="PromptAgent", version="0.6.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["tauri://localhost", "http://127.0.0.1:1420", "http://localhost:1420"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings_service = SettingsService()
knowledge_os = KnowledgeOSService()
prompt_agent = PromptAgent(settings_service=settings_service, knowledge_os_service=knowledge_os)
prompt_lab = PromptLabService(settings_service=settings_service)
latest_capture: CaptureResponse | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "prompt-agent-core"}


@app.post("/api/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest) -> GenerateResponse:
    try:
        return prompt_agent.generate(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/prompt-lab/test", response_model=PromptLabTestResponse)
def prompt_lab_test(request: PromptLabTestRequest) -> PromptLabTestResponse:
    try:
        return prompt_lab.test_prompt(request.prompt, request.test_input, request.model_override)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/prompt-lab/compare", response_model=PromptLabCompareResponse)
def prompt_lab_compare(request: PromptLabCompareRequest) -> PromptLabCompareResponse:
    try:
        return prompt_lab.compare_prompts(request.original_prompt, request.optimized_prompt, request.test_input)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/settings/model", response_model=ModelSettingsResponse)
def get_model_settings() -> ModelSettingsResponse:
    return settings_service.describe()


@app.post("/api/settings/model", response_model=ModelSettingsResponse)
def update_model_settings(request: ModelSettingsRequest) -> ModelSettingsResponse:
    return settings_service.update_model_settings(request)


@app.get("/api/settings/provider-presets", response_model=list[ProviderPreset])
def provider_presets() -> list[ProviderPreset]:
    return list_provider_presets()


@app.post("/api/capture", response_model=CaptureResponse)
def capture(request: CaptureRequest) -> CaptureResponse:
    global latest_capture
    latest_capture = CaptureResponse(**request.model_dump(), ok=True)
    return latest_capture


@app.get("/api/capture/latest", response_model=CaptureResponse | None)
def get_latest_capture() -> CaptureResponse | None:
    return latest_capture


@app.post("/api/level-up", response_model=LevelUpResponse)
def level_up(request: LevelUpRequest) -> LevelUpResponse:
    try:
        model, privacy = settings_service.get_model_settings()
        from app.providers.factory import build_provider
        provider = build_provider(model, privacy)
        result = knowledge_os.level_up(request.model_dump(), provider=provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return LevelUpResponse(level_up_result=result)


@app.get("/api/knowledge-os/sources")
def knowledge_os_sources(query: str = "", collection: str = "", tag: str = "") -> list[dict[str, object]]:
    return knowledge_os.list_sources(query=query, collection=collection, tag=tag)


@app.get("/api/knowledge-os/sources/{source_id}")
def knowledge_os_source(source_id: str) -> dict[str, object]:
    try:
        return knowledge_os.get_source(source_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/api/knowledge-os/sources/{source_id}")
def update_knowledge_os_source(source_id: str, request: KnowledgeOSSourceUpdateRequest) -> dict[str, object]:
    try:
        return knowledge_os.update_source(source_id, request.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/knowledge-os/sources/{source_id}")
def delete_knowledge_os_source(source_id: str) -> dict[str, bool]:
    try:
        knowledge_os.delete_source(source_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True}


@app.post("/api/knowledge-os/search")
def search_knowledge_os(request: KnowledgeOSSearchRequest) -> list[dict[str, str]]:
    return knowledge_os.search(request.query, request.collection, request.tag)


@app.post("/api/knowledge-os/open-folder", response_model=FolderOpenResponse)
def open_knowledge_os_folder() -> FolderOpenResponse:
    opened, message, path = knowledge_os.open_root_folder()
    return FolderOpenResponse(opened=opened, path=str(path), message=message)


@app.post("/api/knowledge-os/sources/{source_id}/open", response_model=FolderOpenResponse)
def open_knowledge_os_source(source_id: str) -> FolderOpenResponse:
    try:
        opened, message, path = knowledge_os.open_source_file(source_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FolderOpenResponse(opened=opened, path=str(path), message=message)


@app.get("/api/knowledge-os/claims")
def knowledge_os_claims(
    query: str = "",
    status: str = "",
    min_confidence: float | None = Query(default=None),
) -> list[dict[str, object]]:
    return knowledge_os.list_claims(query=query, status=status, min_confidence=min_confidence)


@app.put("/api/knowledge-os/claims/{claim_id}")
def update_knowledge_os_claim(claim_id: str, request: KnowledgeOSClaimUpdateRequest) -> dict[str, object]:
    try:
        return knowledge_os.update_claim(claim_id, request.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/knowledge-os/claims/{claim_id}")
def delete_knowledge_os_claim(claim_id: str) -> dict[str, bool]:
    try:
        knowledge_os.delete_claim(claim_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True}


@app.get("/api/level-up/review-queue")
def level_up_review_queue() -> list[dict[str, object]]:
    return knowledge_os.list_review_queue()


@app.get("/api/level-up/review/{review_id}")
def level_up_review_item(review_id: str) -> dict[str, object]:
    try:
        return knowledge_os.get_review_item(review_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/api/level-up/review/{review_id}")
def update_level_up_review_item(review_id: str, request: dict[str, object]) -> dict[str, object]:
    try:
        return knowledge_os.update_review_item(review_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/level-up/review/{review_id}/approve")
def approve_level_up_review_item(review_id: str) -> dict[str, object]:
    try:
        return knowledge_os.approve_review_item(review_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/level-up/review/{review_id}/reject")
def reject_level_up_review_item(review_id: str) -> dict[str, object]:
    try:
        return knowledge_os.reject_review_item(review_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/knowledge-os/graph/nodes")
def knowledge_os_graph_nodes(query: str = "") -> list[dict[str, object]]:
    return knowledge_os.list_nodes(query=query)


@app.get("/api/knowledge-os/graph/edges")
def knowledge_os_graph_edges(query: str = "") -> list[dict[str, object]]:
    return knowledge_os.list_edges(query=query)


@app.put("/api/knowledge-os/graph/nodes/{node_id}")
def update_knowledge_os_graph_node(node_id: str, request: KnowledgeOSGraphNodeUpdateRequest) -> dict[str, object]:
    try:
        return knowledge_os.update_node(node_id, request.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/api/knowledge-os/graph/edges/{edge_id}")
def update_knowledge_os_graph_edge(edge_id: str, request: KnowledgeOSGraphEdgeUpdateRequest) -> dict[str, object]:
    try:
        return knowledge_os.update_edge(edge_id, request.model_dump(exclude_unset=True, by_alias=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/knowledge-os/graph/nodes/{node_id}")
def delete_knowledge_os_graph_node(node_id: str) -> dict[str, bool]:
    try:
        knowledge_os.delete_node(node_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True}


@app.delete("/api/knowledge-os/graph/edges/{edge_id}")
def delete_knowledge_os_graph_edge(edge_id: str) -> dict[str, bool]:
    try:
        knowledge_os.delete_edge(edge_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True}


@app.post("/api/knowledge-os/graph/open-folder", response_model=FolderOpenResponse)
def open_knowledge_os_graph_folder() -> FolderOpenResponse:
    opened, message, path = knowledge_os.open_graph_folder()
    return FolderOpenResponse(opened=opened, path=str(path), message=message)


@app.get("/api/knowledge-os/personal/files", response_model=list[PersonalWikiFileItem])
def list_knowledge_os_personal_files() -> list[PersonalWikiFileItem]:
    return knowledge_os.personal_wiki.list_files()


@app.get("/api/knowledge-os/personal/files/{file_id}", response_model=PersonalWikiFileContent)
def get_knowledge_os_personal_file(file_id: str) -> PersonalWikiFileContent:
    try:
        return knowledge_os.personal_wiki.read_file(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/knowledge-os/personal/files/{file_id}", response_model=PersonalWikiFileContent)
def update_knowledge_os_personal_file(file_id: str, request: PersonalWikiFileUpdateRequest) -> PersonalWikiFileContent:
    try:
        return knowledge_os.personal_wiki.update_file(file_id, request.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/knowledge-os/personal/open-folder", response_model=FolderOpenResponse)
def open_knowledge_os_personal_folder() -> FolderOpenResponse:
    opened, message, path = knowledge_os.personal_wiki.open_folder()
    return FolderOpenResponse(opened=opened, path=str(path), message=message)


@app.post("/api/knowledge-os/personal/summary-test", response_model=PersonalSummaryTestResponse)
def knowledge_os_personal_summary_test() -> PersonalSummaryTestResponse:
    _, privacy = settings_service.get_model_settings()
    return PersonalSummaryTestResponse(**knowledge_os.personal_wiki.summary_test(privacy.personal_wiki_enabled))


@app.get("/api/knowledge-os/logs")
def knowledge_os_logs() -> dict[str, object]:
    return knowledge_os.logs()


@app.post("/api/knowledge-os/logs/open", response_model=FolderOpenResponse)
def open_knowledge_os_log_file() -> FolderOpenResponse:
    opened, message, path = knowledge_os.open_log_file()
    return FolderOpenResponse(opened=opened, path=str(path), message=message)


@app.post("/api/knowledge-os/notes")
def create_knowledge_os_note(request: dict[str, object]) -> dict[str, object]:
    title = str(request.get("title") or "").strip() or "未命名笔记"
    content = str(request.get("content") or "").strip()
    collection = str(request.get("collection") or "notes").strip()
    tags = list(request.get("tags") or ["note"])
    if not content:
        raise HTTPException(status_code=400, detail="content is required")
    return knowledge_os.create_note(title=title, content=content, collection=collection, tags=tags)


@app.post("/api/knowledge-os/import")
def import_knowledge_os_file(request: dict[str, object]) -> dict[str, object]:
    file_path = str(request.get("path") or "").strip()
    collection = str(request.get("collection") or "import").strip()
    tags = list(request.get("tags") or ["import"])
    if not file_path:
        raise HTTPException(status_code=400, detail="path is required")
    try:
        from app.providers.factory import build_provider
        model, privacy = settings_service.get_model_settings()
        provider = build_provider(model, privacy)
        return knowledge_os.import_file(file_path, collection=collection, tags=tags, provider=provider)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/llm/run")
def llm_run(request: dict[str, object]) -> dict[str, object]:
    """Direct LLM call — used by skill runner in Knowledge OS."""
    system = str(request.get("system") or "You are a helpful assistant.")
    user = str(request.get("user") or "")
    max_tokens = int(request.get("max_tokens") or 2000)
    if not user:
        raise HTTPException(status_code=400, detail="user message is required")
    try:
        from app.providers.factory import build_provider
        model, privacy = settings_service.get_model_settings()
        provider = build_provider(model, privacy)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        output = provider.generate(messages, {"temperature": 0.5, "max_tokens": max_tokens, "timeout": 60})
        return {"output": output}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=settings_service.sanitize_error(str(exc))) from exc


@app.post("/api/learning-plan/generate")
def generate_learning_plan(request: dict[str, object]) -> dict[str, object]:
    goal = str(request.get("goal") or "").strip()
    days = int(request.get("days") or 30)
    if not goal:
        raise HTTPException(status_code=400, detail="goal is required")
    try:
        from app.providers.factory import build_provider
        from app.providers.mock import MockProvider
        model, privacy = settings_service.get_model_settings()
        provider = build_provider(model, privacy)

        # Build context from personal wiki and recent sources
        personal_ctx = ""
        try:
            files = knowledge_os.personal_wiki.list_files()
            for f in files[:3]:
                fc = knowledge_os.personal_wiki.read_file(f.id)
                personal_ctx += f"\n\n### {f.filename}\n{fc.content[:600]}"
        except Exception:
            pass

        recent = knowledge_os.list_sources()[:8]
        sources_ctx = "\n".join(
            f"- 《{s['title']}》: {(s.get('summary') or '')[:100]}" for s in recent
        ) or "(知识库暂无内容)"

        if isinstance(provider, MockProvider):
            plan = (
                f"# {goal} — 学习计划（{days} 天）\n\n"
                f"## 目标概览\n\n用 {days} 天掌握：{goal}\n\n"
                "## 第 1 周：基础建立\n\n"
                "- [ ] 整理已有知识和资料\n"
                "- [ ] 每天 1 小时阅读 + 记笔记\n"
                "- [ ] 生成第一批闪卡（Level Up 工具）\n\n"
                f"## 第 2–{days // 7} 周：深入学习\n\n"
                "- [ ] 精读核心资料（精读分析技能）\n"
                "- [ ] 完成提问地图练习\n"
                "- [ ] 每周知识蒸馏 1 次\n\n"
                "## 里程碑\n\n"
                f"- 第 7 天：完成基础框架\n"
                f"- 第 {days // 2} 天：中期自测\n"
                f"- 第 {days} 天：最终验收\n\n"
                "> 配置模型 API 后可获得更个性化的计划。"
            )
        else:
            user_msg = (
                f"用户目标：{goal}\n学习周期：{days} 天\n\n"
                f"个人档案：{personal_ctx or '（暂无）'}\n\n"
                f"已有知识资料：\n{sources_ctx}\n\n"
                "请用中文生成一份结构化学习计划，包含：\n"
                "① 分阶段时间表（周/日粒度）\n"
                "② 每阶段具体任务和时长\n"
                "③ 如何利用知识库现有内容\n"
                "④ 间隔复习安排\n"
                "⑤ 里程碑和验收标准\n\n"
                "输出格式：Markdown，含复选框（- [ ]），层级清晰。"
            )
            messages = [
                {"role": "system", "content": "你是专业学习教练，擅长制定个性化学习计划。"},
                {"role": "user", "content": user_msg},
            ]
            plan = provider.generate(messages, {"temperature": 0.7, "max_tokens": 2000, "timeout": 60})
        return {"plan": plan}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=settings_service.sanitize_error(str(exc))) from exc


@app.get("/api/knowledge-os/skills")
def list_knowledge_os_skills() -> list[dict[str, object]]:
    return knowledge_os.list_skills()


@app.post("/api/knowledge-os/skills")
def create_knowledge_os_skill(request: dict[str, object]) -> dict[str, object]:
    title = str(request.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    return knowledge_os.create_skill(
        title=title,
        desc=str(request.get("desc") or "").strip(),
        system=str(request.get("system") or "").strip(),
        user_template=str(request.get("user_template") or "").strip(),
    )


@app.put("/api/knowledge-os/skills/{skill_id}")
def update_knowledge_os_skill(skill_id: str, request: dict[str, object]) -> dict[str, object]:
    try:
        return knowledge_os.update_skill(skill_id, dict(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/knowledge-os/skills/{skill_id}")
def delete_knowledge_os_skill(skill_id: str) -> dict[str, bool]:
    try:
        knowledge_os.delete_skill(skill_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True}


@app.get("/api/skills/level-up")
def level_up_skill() -> dict[str, object]:
    return {
        "id": "level_up_capture",
        "name": "Level Up",
        "description": "把选中文本沉淀为 Knowledge OS 的长期知识，并进入图谱审核队列。",
        "enabled": True,
        "default_collection": "level-up",
        "default_tags": ["level-up"],
        "writes": ["knowledge_os/wiki/sources", "knowledge_os/claims/claims.jsonl", "knowledge_os/graph/review_queue.jsonl"],
    }


@app.get("/api/extension/status")
def extension_status() -> dict[str, object]:
    return {
        "ok": True,
        "context_menu": ["Prompt", "Level Up"],
        "backend": f"http://{settings.host}:{settings.port}",
        "note": "浏览器扩展只是右键输入入口；桌面端是主要使用界面。",
    }


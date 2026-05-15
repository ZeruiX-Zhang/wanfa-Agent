from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProviderInfo(BaseModel):
    vendor: str = "mock"
    provider: str = "mock"
    active_provider: str = "mock"
    model: str = "mock-prompt-model"
    label: str = "本地模拟模型"


class SkillInfo(BaseModel):
    mode: str = "auto"
    mode_label: str = "自动选择"
    skill_policy_allows_personalization: bool = True
    skill_policy_allows_knowledge_os: bool = False


class PersonalWikiUsedFile(BaseModel):
    id: str
    filename: str
    title: str


class PersonalizationInfo(BaseModel):
    enabled: bool = True
    used: bool = False
    used_files: list[PersonalWikiUsedFile] = Field(default_factory=list)


class KnowledgeOSInfo(BaseModel):
    used: bool = False
    sources: list[dict[str, Any]] = Field(default_factory=list)
    claims: list[dict[str, Any]] = Field(default_factory=list)
    graph: list[dict[str, Any]] = Field(default_factory=list)


class ContextBudget(BaseModel):
    used_skill_tokens: int = 0
    used_memory_tokens: int = 0
    used_knowledge_tokens: int = 0
    used_graph_tokens: int = 0
    used_total_estimate: int = 0


class GenerateRequest(BaseModel):
    selected_text: str = Field(default="", min_length=1)
    user_goal: str = ""
    mode: str = "auto"
    user_id: str = "default"
    use_knowledge_os: bool = False
    model_override: str | None = None


class PromptVariant(BaseModel):
    name: str
    prompt: str


class GenerateResponse(BaseModel):
    final_prompt: str
    why_it_works: str
    variants: list[PromptVariant] = Field(default_factory=list)
    provider_info: ProviderInfo = Field(default_factory=ProviderInfo)
    skill_info: SkillInfo = Field(default_factory=SkillInfo)
    personalization_info: PersonalizationInfo = Field(default_factory=PersonalizationInfo)
    knowledge_os_info: KnowledgeOSInfo = Field(default_factory=KnowledgeOSInfo)
    context_budget: ContextBudget = Field(default_factory=ContextBudget)


class PromptLabTestRequest(BaseModel):
    prompt: str = Field(default="", min_length=1)
    test_input: str = ""
    model_override: str | None = None


class PromptLabTestResponse(BaseModel):
    ok: bool
    output: str
    provider_info: ProviderInfo
    token_budget: ContextBudget


class PromptLabComparisonScores(BaseModel):
    clarity: int = 0
    specificity: int = 0
    usefulness: int = 0


class PromptLabComparison(BaseModel):
    winner: Literal["original", "optimized", "tie"] = "optimized"
    reason: str = ""
    scores: PromptLabComparisonScores = Field(default_factory=PromptLabComparisonScores)


class PromptLabCompareRequest(BaseModel):
    original_prompt: str = Field(default="", min_length=1)
    optimized_prompt: str = Field(default="", min_length=1)
    test_input: str = ""


class PromptLabCompareResponse(BaseModel):
    ok: bool
    original_output: str
    optimized_output: str
    comparison: PromptLabComparison


class ModelSettingsRequest(BaseModel):
    vendor: str = "mock"
    provider: str = "mock"
    base_url: str = ""
    model: str = "mock-prompt-model"
    api_key: str | None = None
    api_key_env: str = "OPENAI_API_KEY"
    local_only: bool = True
    allow_cloud_model: bool = False
    redact_sensitive_info: bool = True
    personal_wiki_enabled: bool = True
    allow_cloud_personal_summary: bool = False
    allow_cloud_sensitive_personal: bool = False


class ModelSettingsResponse(BaseModel):
    vendor: str = "mock"
    provider: str = "mock"
    base_url: str = ""
    model: str = "mock-prompt-model"
    api_key_env: str = "OPENAI_API_KEY"
    has_api_key: bool = False
    local_only: bool = True
    allow_cloud_model: bool = False
    redact_sensitive_info: bool = True
    personal_wiki_enabled: bool = True
    allow_cloud_personal_summary: bool = False
    allow_cloud_sensitive_personal: bool = False
    active_provider: str = "mock"
    provider_label: str = "本地模拟模型"


class ProviderPreset(BaseModel):
    id: str
    label: str
    vendor: str
    provider: str
    base_url: str
    model: str
    api_key_env: str
    local_only: bool
    allow_cloud_model: bool


class CaptureRequest(BaseModel):
    selected_text: str = ""
    source: str = "desktop"
    action: Literal["prompt", "level_up"] = "prompt"
    title: str = ""
    url: str = ""


class CaptureResponse(BaseModel):
    ok: bool = True
    selected_text: str = ""
    source: str = "desktop"
    action: str = "prompt"
    title: str = ""
    url: str = ""


class LevelUpRequest(BaseModel):
    selected_text: str = Field(default="", min_length=1)
    title: str = ""
    source: str = "desktop"
    url: str = ""
    collection: str = "level-up"
    tags: list[str] = Field(default_factory=lambda: ["level-up"])


class LevelUpResult(BaseModel):
    capture_id: str
    source_page: str
    summary: str
    claims: list[dict[str, Any]] = Field(default_factory=list)
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    review_item_id: str


class LevelUpResponse(BaseModel):
    level_up_result: LevelUpResult


class KnowledgeOSSourceUpdateRequest(BaseModel):
    title: str | None = None
    summary: str | None = None
    tags: list[str] | None = None
    collection: str | None = None
    content: str | None = None


class KnowledgeOSSearchRequest(BaseModel):
    query: str = ""
    collection: str = ""
    tag: str = ""


class KnowledgeOSClaimUpdateRequest(BaseModel):
    text: str | None = None
    status: str | None = None
    confidence: float | None = None
    evidence: list[Any] | None = None
    source_page: str | None = None


class KnowledgeOSGraphNodeUpdateRequest(BaseModel):
    type: str | None = None
    name: str | None = None
    aliases: list[str] | None = None
    source: str | None = None


class KnowledgeOSGraphEdgeUpdateRequest(BaseModel):
    from_node: str | None = Field(default=None, alias="from")
    type: str | None = None
    to: str | None = None
    confidence: float | None = None
    source: str | None = None


class PersonalWikiFileItem(BaseModel):
    id: str
    filename: str
    title: str
    updated_at: str = ""


class PersonalWikiFileContent(PersonalWikiFileItem):
    content: str = ""


class PersonalWikiFileUpdateRequest(BaseModel):
    content: str = ""


class PersonalSummaryTestResponse(BaseModel):
    enabled: bool
    summary: str
    used_files: list[PersonalWikiFileItem] = Field(default_factory=list)


class FolderOpenResponse(BaseModel):
    opened: bool
    path: str
    message: str


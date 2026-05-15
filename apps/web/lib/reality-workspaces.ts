import type { Language } from "@/lib/preferences";

export type WorkspaceStatus = "ready" | "planned" | "adapter-next";

type Bilingual = { "zh-CN": string; en: string };

type RawWorkspaceConfig = {
  title: Bilingual;
  eyebrow: Bilingual;
  description: Bilingual;
  status: WorkspaceStatus;
  legacySources: Bilingual[];
  currentScope: Bilingual[];
  nextAdapters: Bilingual[];
  acceptance: Bilingual[];
};

export type WorkspaceConfig = {
  title: string;
  eyebrow: string;
  description: string;
  status: WorkspaceStatus;
  legacySources: string[];
  currentScope: string[];
  nextAdapters: string[];
  acceptance: string[];
};

const b = (zh: string, en: string): Bilingual => ({ "zh-CN": zh, en });

const rawWorkspaces = {
  dashboard: {
    title: b("总览", "Dashboard"),
    eyebrow: b("系统总览", "System overview"),
    description: b(
      "统一查看近期判断、知识增长、证据验证与被监督 Agent 工作状态。",
      "Unified operating view for recent decisions, knowledge growth, verification health, and supervised agent work.",
    ),
    status: "ready",
    legacySources: [
      b("sou 面板指标", "sou dashboard metrics"),
      b("work 追踪与评估摘要", "work trace and eval summaries"),
      b("prompt-agent 的知识 OS 状态", "prompt-agent Knowledge OS status"),
    ],
    currentScope: [
      b("Reality OS 静态壳", "Static Reality OS shell"),
      b("到各个主流程页面的导航", "Navigation to all main workspaces"),
      b("保留到历史工具的链接", "Legacy intelligence links preserved"),
    ],
    nextAdapters: [
      b("DecisionCase 摘要适配器", "DecisionCase summary adapter"),
      b("KnowledgeItem 增长适配器", "KnowledgeItem growth adapter"),
      b("AgentTask 追踪适配器", "AgentTask trace adapter"),
    ],
    acceptance: [
      b("没有后端时页面也能打开", "The route opens without a backend"),
      b("每张卡片说明当前接入状态", "Cards explain current integration state"),
      b("历史工具路径仍可达", "Legacy routes remain reachable"),
    ],
  },
  input: {
    title: b("现实输入", "Input"),
    eyebrow: b("现实输入工位", "Reality input desk"),
    description: b(
      "承接文本、图片、网页、文件、扩展捕获等现实输入的入口，统一进入澄清流程。",
      "Entry point for real-world text, image, webpage, file, and extension-captured context before clarification.",
    ),
    status: "planned",
    legacySources: [
      b("prompt-agent 浏览器捕获", "prompt-agent browser capture"),
      b("work 文档摄入", "work document ingestion"),
      b("sou 信息源与关注列表创建", "sou source and watchlist creation"),
    ],
    currentScope: [
      b("文本输入区布局", "Text input layout"),
      b("任务类型选择占位", "Task type selection placeholder"),
      b("文件 / 网页 / 图片 / 语音入口预留", "File, webpage, image, and voice intake slots reserved"),
    ],
    nextAdapters: [
      b("prompt-agent /api/capture", "prompt-agent /api/capture"),
      b("work 文档摄入", "work document ingest"),
      b("sou 信息源创建", "sou source creation"),
    ],
    acceptance: [
      b("页面展示所有预期输入通道", "The page shows the intended input channels"),
      b("不在此处执行任何上传写入", "No upload writes are performed"),
      b("扩展保持轻量输入入口", "Extension remains a light input path"),
    ],
  },
  decision: {
    title: b("判断备忘录", "Decision Workbench"),
    eyebrow: b("判断备忘录工位", "Judgment memo"),
    description: b(
      "围绕一个案例整理澄清后的问题、思维模型、证据、反论点、风险与建议。",
      "Case workspace for clarified problem, thinking models, evidence, counterarguments, risks, and recommendations.",
    ),
    status: "adapter-next",
    legacySources: [
      b("prompt-agent 的 decision_prompt", "prompt-agent decision_prompt"),
      b("sou 证据账本", "sou evidence ledger"),
      b("work 的 QA 计划与验证器", "work QA plan and verifier"),
    ],
    currentScope: [
      b("动态路由骨架", "Dynamic route shell"),
      b("展示案例 id", "Case id display"),
      b("备忘录各段预留位", "Memo sections reserved"),
    ],
    nextAdapters: [
      b("ClarifiedProblem 适配器", "ClarifiedProblem adapter"),
      b("RetrievalResult 适配器", "RetrievalResult adapter"),
      b("DecisionMemo 持久化", "DecisionMemo persistence"),
    ],
    acceptance: [
      b("支持 /decision/:id 路由", "The route supports /decision/:id"),
      b("占位 id 也能进入", "The shell is usable with a placeholder id"),
      b("没有来源的结论不当作已验证", "No claim is treated as verified without sources"),
    ],
  },
  knowledge: {
    title: b("知识库", "Knowledge"),
    eyebrow: b("统一知识工位", "Unified knowledge workbench"),
    description: b(
      "覆盖个人、行业、企业与学习四类知识，带来源、租户、可见性、置信与审核状态。",
      "Personal, industry, enterprise, and study knowledge with source, tenant, visibility, confidence, and review status.",
    ),
    status: "adapter-next",
    legacySources: [
      b("prompt-agent 知识 OS", "prompt-agent Knowledge OS"),
      b("study 的 llm-wiki", "study llm-wiki"),
      b("sou 信息源与证据", "sou sources and evidence"),
      b("work 工作区文档", "work workspace documents"),
    ],
    currentScope: [
      b("按知识域组织布局", "Knowledge domain layout"),
      b("审核队列策略可见", "Review queue policy visible"),
      b("索引边界已说明", "Index boundaries documented"),
    ],
    nextAdapters: [
      b("PromptKnowledgeOSAdapter", "PromptKnowledgeOSAdapter"),
      b("StudyWikiReadOnlyAdapter", "StudyWikiReadOnlyAdapter"),
      b("SouKnowledgeAdapter", "SouKnowledgeAdapter"),
      b("WorkDocumentAdapter", "WorkDocumentAdapter"),
    ],
    acceptance: [
      b("页面按知识域分栏", "The page separates knowledge domains"),
      b("study 原始文件保持只读", "Raw study files are marked read-only"),
      b("正式写入仅限待审核", "Formal writes are pending-review only"),
    ],
  },
  search: {
    title: b("检索", "Search"),
    eyebrow: b("检索工位", "Retrieval workbench"),
    description: b(
      "关键词、向量、混合检索跨作用域的知识，返回带引用与追踪链的结果。",
      "Keyword, vector, and hybrid retrieval across scoped knowledge sources with citations and retrieval trace.",
    ),
    status: "adapter-next",
    legacySources: [
      b("work 的混合 RAG", "work hybrid RAG"),
      b("sou 检索采集器", "sou search collectors"),
      b("prompt-agent 本地检索", "prompt-agent local search"),
    ],
    currentScope: [
      b("检索模式控件", "Search mode controls"),
      b("引用与追踪占位", "Citation and trace placeholders"),
      b("租户安全过滤策略说明", "Tenant-safe filter policy displayed"),
    ],
    nextAdapters: [
      b("work RAG 查询/调试", "work RAG query/debug"),
      b("sou 检索提供方", "sou search provider"),
      b("统一 RetrievalResult schema", "unified RetrievalResult schema"),
    ],
    acceptance: [
      b("区分关键词 / 向量 / 混合三种模式", "The page distinguishes keyword/vector/hybrid modes"),
      b("追踪作为一等输出", "Trace is visible as a first-class output"),
      b("不暗示跨租户检索", "No cross-tenant search is implied"),
    ],
  },
  verification: {
    title: b("证据验证", "Verification"),
    eyebrow: b("断言与证据", "Claim evidence review"),
    description: b(
      "拆解断言、绑定来源、标注置信与无法验证、呈现反证与过时信息检查。",
      "Claim decomposition, source binding, confidence, unverifiable markings, counterevidence, and stale information checks.",
    ),
    status: "adapter-next",
    legacySources: [
      b("work 验证器", "work verifier"),
      b("sou 的 EventClaim 与 EvidenceLedgerEntry", "sou EventClaim and EvidenceLedgerEntry"),
      b("prompt-agent 的 claims JSONL", "prompt-agent claims JSONL"),
    ],
    currentScope: [
      b("动态路由骨架", "Dynamic route shell"),
      b("断言状态列预留", "Claim status columns reserved"),
      b("证据策略可见", "Evidence policy visible"),
    ],
    nextAdapters: [
      b("Claim 适配器", "Claim adapter"),
      b("VerificationResult 适配器", "VerificationResult adapter"),
      b("过时源检查器", "stale source checker"),
    ],
    acceptance: [
      b("支持 /verification/:id", "The route supports /verification/:id"),
      b("无法验证状态显式标注", "Unverifiable state is explicit"),
      b("每条断言都要绑定来源", "Claims require source bindings"),
    ],
  },
  workflow: {
    title: b("工作流", "Workflow"),
    eyebrow: b("工作流图", "Workflow graph"),
    description: b(
      "以图的形式规划澄清 / 检索 / 推理 / 验证 / 监督 / 执行 / 复盘。",
      "Graph-based workflow planning for clarification, retrieval, reasoning, verification, supervision, execution, and reflection.",
    ),
    status: "adapter-next",
    legacySources: [
      b("work 的 workflow_core", "work workflow_core"),
      b("work 的工具注册表", "work tool registry"),
      b("work 的 QA 编排器", "work QA orchestrator"),
    ],
    currentScope: [
      b("工作流节点映射", "Workflow node map"),
      b("审批检查点", "Approval checkpoints"),
      b("失败处理位", "Failure handling slots"),
    ],
    nextAdapters: [
      b("工作流运行时适配器", "Workflow runtime adapter"),
      b("AgentTask 持久化", "AgentTask persistence"),
      b("ApprovalRequest 适配器", "ApprovalRequest adapter"),
    ],
    acceptance: [
      b("工作流形态可见", "The graph shape is visible"),
      b("人工审批有位置可放", "Human approval is represented"),
      b("不暴露自由多 Agent 执行", "No free-form multi-agent execution is exposed"),
    ],
  },
  supervisor: {
    title: b("Agent 监督", "Supervisor"),
    eyebrow: b("Agent 监督", "Agent supervision"),
    description: b(
      "展示执行 Agent 的计划 / 步骤 / 工具调用 / 审批 / 日志 / 差异 / 测试 / 追踪 / 风险控制。",
      "Plan, steps, tool calls, approvals, logs, diff review, tests, trace, and risk controls for execution agents.",
    ),
    status: "adapter-next",
    legacySources: [
      b("work 的护栏", "work guardrails"),
      b("work 的追踪存储", "work trace store"),
      b("work 的审批流", "work approval flow"),
      b("work 的工具注册表", "work tool registry"),
    ],
    currentScope: [
      b("监督控制台骨架", "Supervisor console shell"),
      b("风险策略摘要", "Risk policy summary"),
      b("工具网关边界说明", "Tool gateway boundaries"),
    ],
    nextAdapters: [
      b("ToolCallLog 适配器", "ToolCallLog adapter"),
      b("ApprovalRequest 适配器", "ApprovalRequest adapter"),
      b("Agent 追踪适配器", "Agent trace adapter"),
    ],
    acceptance: [
      b("工具执行显示为受控", "Tool execution is shown as gated"),
      b("高风险动作需要审批", "High-risk actions require approval"),
      b("日志与 diff 是一等输出", "Logs and diffs are first-class outputs"),
    ],
  },
  reflection: {
    title: b("复盘成长", "Reflection"),
    eyebrow: b("复盘与学习", "Learning and review"),
    description: b(
      "回顾结果、接收用户反馈、沉淀经验、待审核知识与个人学习路径更新。",
      "Outcome review, user feedback, lesson capture, pending knowledge writes, and personal learning path updates.",
    ),
    status: "planned",
    legacySources: [
      b("prompt-agent 的 Level Up", "prompt-agent Level Up"),
      b("prompt-agent 个人 wiki", "prompt-agent personal wiki"),
      b("study 学习工作流", "study learning workflow"),
    ],
    currentScope: [
      b("复盘记录布局", "Reflection record layout"),
      b("待审核策略", "Pending knowledge policy"),
      b("学习路径占位", "Learning path placeholders"),
    ],
    nextAdapters: [
      b("Level Up 审核队列", "Level Up review queue"),
      b("PersonalWikiService", "PersonalWikiService"),
      b("学习工作流索引", "Study workflow index"),
    ],
    acceptance: [
      b("知识写入默认待审核", "Knowledge writes are pending by default"),
      b("支持记录用户结果反馈", "User outcome feedback is modeled"),
      b("study 原始内容保持只读", "Study raw sources remain read-only"),
    ],
  },
  settings: {
    title: b("设置", "Settings"),
    eyebrow: b("配置与安全", "Configuration and safety"),
    description: b(
      "模型、API Key、知识源、插件通道、权限、租户隔离与安全默认值。",
      "Models, API keys, knowledge sources, plugin channels, permissions, tenant isolation, and safety defaults.",
    ),
    status: "ready",
    legacySources: [
      b("sou 设置", "sou settings"),
      b("prompt-agent 设置", "prompt-agent settings"),
      b("work 平台设置", "work platform settings"),
    ],
    currentScope: [
      b("API Key 仅保存在服务端", "Server-only API key policy"),
      b("Postgres 目标决策", "Postgres target decision"),
      b("工具安全默认值", "Tool safety defaults"),
    ],
    nextAdapters: [
      b("统一设置 API", "Unified settings API"),
      b("服务端 secret 存储", "server-side secret store"),
      b("租户权限编辑器", "tenant permission editor"),
    ],
    acceptance: [
      b("API Key 明确仅服务端保存", "API keys are described as server-only"),
      b("工具执行默认关闭", "Tool execution defaults to disabled"),
      b("租户隔离明确", "Tenant isolation is explicit"),
    ],
  },
} satisfies Record<string, RawWorkspaceConfig>;

type WorkspaceKeyInternal = keyof typeof rawWorkspaces;

function localizeBilingual(value: Bilingual, language: Language): string {
  return value[language] ?? value.en;
}

function localizeConfig(raw: RawWorkspaceConfig, language: Language): WorkspaceConfig {
  return {
    title: localizeBilingual(raw.title, language),
    eyebrow: localizeBilingual(raw.eyebrow, language),
    description: localizeBilingual(raw.description, language),
    status: raw.status,
    legacySources: raw.legacySources.map((item) => localizeBilingual(item, language)),
    currentScope: raw.currentScope.map((item) => localizeBilingual(item, language)),
    nextAdapters: raw.nextAdapters.map((item) => localizeBilingual(item, language)),
    acceptance: raw.acceptance.map((item) => localizeBilingual(item, language)),
  };
}

export function workspaceConfig(key: WorkspaceKeyInternal, language: Language): WorkspaceConfig {
  return localizeConfig(rawWorkspaces[key], language);
}

/**
 * Convenience proxy that keeps the old `workspaceConfigs.dashboard`-style API
 * working for server components that do not yet read the user's language.
 * It defaults to English because Next.js server-rendered fixtures sometimes
 * run before the preferences cookie is available; the client components that
 * actually render these configs re-localize through `workspaceConfig()`.
 */
export const workspaceConfigs = new Proxy({} as Record<WorkspaceKeyInternal, WorkspaceConfig>, {
  get(_target, property) {
    if (typeof property !== "string" || !(property in rawWorkspaces)) {
      return undefined;
    }
    return localizeConfig(rawWorkspaces[property as WorkspaceKeyInternal], "zh-CN");
  },
});

export type WorkspaceKey = WorkspaceKeyInternal;

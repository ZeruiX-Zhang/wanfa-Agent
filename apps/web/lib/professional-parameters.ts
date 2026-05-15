/**
 * Catalog of professional-mode parameters.
 *
 * Derived by first-principles from requirements.md / design.md, and from the
 * public design surface of top-tier agent frameworks (LangGraph, AutoGen,
 * CrewAI, Claude Code, Codex). Every parameter maps back to a concept already
 * defined in the spec so professional mode stays grounded and reproducible.
 *
 * The list is intentionally narrow. A knob makes this list only if it changes
 * a measurable outcome the user may want to trade off: correctness,
 * reproducibility, latency, cost, or safety.
 */

import type { Language } from "@/lib/preferences";

export type ParameterKind = "toggle" | "slider" | "select";

export type ParameterDefinition =
  | {
      id: string;
      kind: "toggle";
      section: ProfessionalSection;
      label: Record<Language, string>;
      description: Record<Language, string>;
      defaultValue: boolean;
      reference: string;
    }
  | {
      id: string;
      kind: "slider";
      section: ProfessionalSection;
      label: Record<Language, string>;
      description: Record<Language, string>;
      defaultValue: number;
      min: number;
      max: number;
      step: number;
      unit?: string;
      reference: string;
    }
  | {
      id: string;
      kind: "select";
      section: ProfessionalSection;
      label: Record<Language, string>;
      description: Record<Language, string>;
      defaultValue: string;
      options: Array<{ value: string; label: Record<Language, string> }>;
      reference: string;
    };

export type ProfessionalSection =
  | "reasoning"
  | "retrieval"
  | "context"
  | "quality"
  | "supervisor"
  | "model";

export const PROFESSIONAL_SECTIONS: ProfessionalSection[] = [
  "reasoning",
  "retrieval",
  "context",
  "quality",
  "supervisor",
  "model",
];

export const PROFESSIONAL_PARAMETERS: ParameterDefinition[] = [
  // ---- reasoning & planning ----
  {
    id: "thinking_models",
    kind: "select",
    section: "reasoning",
    label: {
      "zh-CN": "思维模型选择",
      en: "Thinking model strategy",
    },
    description: {
      "zh-CN":
        "auto：系统按问题自动匹配思维模型；assist：推荐一组让你确认；manual：完全由你指定。",
      en:
        "auto: system auto-matches models; assist: system suggests a set you confirm; manual: you pick the set yourself.",
    },
    defaultValue: "assist",
    options: [
      { value: "auto", label: { "zh-CN": "自动", en: "Auto" } },
      { value: "assist", label: { "zh-CN": "辅助", en: "Assist" } },
      { value: "manual", label: { "zh-CN": "手动", en: "Manual" } },
    ],
    reference: "requirements.md Req 5 AC2, design.md §5.1",
  },
  {
    id: "planner_depth",
    kind: "slider",
    section: "reasoning",
    label: { "zh-CN": "规划深度", en: "Planner depth" },
    description: {
      "zh-CN": "子问题最大层级。越大越细，越慢，越易卡壳。",
      en: "Max sub-question depth. Deeper = more thorough but slower and more error-prone.",
    },
    defaultValue: 2,
    min: 1,
    max: 5,
    step: 1,
    reference: "design.md §5.3 Goal_Decomposer",
  },
  {
    id: "reflection_depth",
    kind: "slider",
    section: "reasoning",
    label: { "zh-CN": "复盘深度", en: "Reflection depth" },
    description: {
      "zh-CN": "任务结束后的复盘轮数。深复盘更适合重要决策。",
      en: "Retrospective rounds after a task. Higher values suit high-stakes decisions.",
    },
    defaultValue: 1,
    min: 0,
    max: 3,
    step: 1,
    reference: "design.md §5.7 Reflection_Engine",
  },
  {
    id: "subagent_isolation",
    kind: "toggle",
    section: "reasoning",
    label: { "zh-CN": "子代理上下文隔离", en: "Subagent context isolation" },
    description: {
      "zh-CN": "开启后子代理拥有独立上下文，避免互相污染；关闭更快但更容易串味。",
      en: "Keep subagents in isolated contexts. Off = faster but risk of cross-task contamination.",
    },
    defaultValue: true,
    reference: "design.md §5 Subagent isolation",
  },

  // ---- retrieval & evidence ----
  {
    id: "retrieval_mode",
    kind: "select",
    section: "retrieval",
    label: { "zh-CN": "检索模式", en: "Retrieval mode" },
    description: {
      "zh-CN": "hybrid 默认启用所有检索器；bm25 / vector / graph 用于复现实验。",
      en: "hybrid enables every retriever; bm25/vector/graph isolate a single one for reproducible runs.",
    },
    defaultValue: "hybrid",
    options: [
      { value: "hybrid", label: { "zh-CN": "混合", en: "Hybrid" } },
      { value: "bm25", label: { "zh-CN": "BM25", en: "BM25" } },
      { value: "vector", label: { "zh-CN": "向量", en: "Vector" } },
      { value: "graph", label: { "zh-CN": "图", en: "Graph" } },
    ],
    reference: "design.md §5.2 Retrieval_Engine",
  },
  {
    id: "top_k",
    kind: "slider",
    section: "retrieval",
    label: { "zh-CN": "召回数量 top-k", en: "top-k per retriever" },
    description: {
      "zh-CN": "每个检索器返回的候选数。数值越大越全面，成本越高。",
      en: "Candidates each retriever returns. Higher = more recall, higher cost.",
    },
    defaultValue: 8,
    min: 1,
    max: 32,
    step: 1,
    reference: "design.md §5.2",
  },
  {
    id: "rerank",
    kind: "toggle",
    section: "retrieval",
    label: { "zh-CN": "启用重排", en: "Rerank candidates" },
    description: {
      "zh-CN": "关闭后按召回分数直接返回；关闭可复现，开启更准。",
      en: "Off = return candidates as-scored (reproducible). On = higher precision after rerank.",
    },
    defaultValue: true,
    reference: "design.md §5.2",
  },
  {
    id: "include_untrusted",
    kind: "toggle",
    section: "retrieval",
    label: { "zh-CN": "纳入不可信源", en: "Include untrusted sources" },
    description: {
      "zh-CN": "关闭：只用已审核源；开启：允许参考不可信源但仍标注。",
      en: "Off = trusted sources only. On = consult untrusted sources with explicit flags.",
    },
    defaultValue: false,
    reference: "design.md §5.5 Authority_Checker",
  },
  {
    id: "authority_check",
    kind: "toggle",
    section: "retrieval",
    label: { "zh-CN": "权威性校验", en: "Authority check" },
    description: {
      "zh-CN": "对每条关键 Claim 调用 Authority_Checker；关闭仅在需要时触发。",
      en: "Run Authority_Checker on every key Claim. Off = only when flagged by Quality_Gate.",
    },
    defaultValue: true,
    reference: "design.md §5.5",
  },

  // ---- context engineering ----
  {
    id: "context_budget_pct",
    kind: "slider",
    section: "context",
    label: { "zh-CN": "上下文预算占比", en: "Context budget share" },
    description: {
      "zh-CN":
        "Context_Engine 预留给证据的 token 占比（剩余给系统提示与计划）。",
      en: "Share of the token budget reserved for evidence (the rest goes to system prompt + plan).",
    },
    defaultValue: 0.7,
    min: 0.3,
    max: 0.9,
    step: 0.05,
    unit: "ratio",
    reference: "design.md §5.3 ContextBudgeter",
  },
  {
    id: "compression_level",
    kind: "select",
    section: "context",
    label: { "zh-CN": "压缩级别", en: "Compression level" },
    description: {
      "zh-CN": "证据落入上下文前的压缩力度。none 最保真，high 最省 token。",
      en: "How aggressively evidence is compressed. none = full fidelity, high = token-saving.",
    },
    defaultValue: "medium",
    options: [
      { value: "none", label: { "zh-CN": "不压缩", en: "None" } },
      { value: "low", label: { "zh-CN": "轻度", en: "Low" } },
      { value: "medium", label: { "zh-CN": "中等", en: "Medium" } },
      { value: "high", label: { "zh-CN": "高", en: "High" } },
    ],
    reference: "design.md §5.3 compression/decompression",
  },
  {
    id: "coverage_matrix",
    kind: "toggle",
    section: "context",
    label: { "zh-CN": "启用覆盖矩阵", en: "Build coverage matrix" },
    description: {
      "zh-CN": "复杂问题自动构建覆盖矩阵并写入 TraceEvent。",
      en: "Build the Coverage_Matrix for complex questions and attach it to the Trace_Event.",
    },
    defaultValue: true,
    reference: "design.md §5.3 CoverageMatrixBuilder",
  },

  // ---- quality gate ----
  {
    id: "quality_threshold",
    kind: "slider",
    section: "quality",
    label: { "zh-CN": "发布阈值", en: "Publication threshold" },
    description: {
      "zh-CN": "低于该分数的 Decision_Memo 强制标记 provisional。默认 60。",
      en: "Below this Quality_Score the memo is forced provisional. Default 60.",
    },
    defaultValue: 60,
    min: 40,
    max: 90,
    step: 5,
    reference: "requirements.md Req 5 AC9, design.md §5.4",
  },
  {
    id: "recovery_strategy",
    kind: "select",
    section: "quality",
    label: { "zh-CN": "低分恢复策略", en: "Low-score recovery" },
    description: {
      "zh-CN":
        "低于阈值时的恢复动作：expand_retrieval / decompress / subagent_review / stop。",
      en: "Action when Quality_Score dips below threshold.",
    },
    defaultValue: "expand_retrieval",
    options: [
      {
        value: "expand_retrieval",
        label: { "zh-CN": "扩大检索", en: "Expand retrieval" },
      },
      { value: "decompress", label: { "zh-CN": "解压证据", en: "Decompress evidence" } },
      { value: "subagent_review", label: { "zh-CN": "子代理复核", en: "Subagent review" } },
      { value: "stop", label: { "zh-CN": "停止并报告", en: "Stop and report" } },
    ],
    reference: "design.md §5.4",
  },
  {
    id: "uncertainty_surface",
    kind: "toggle",
    section: "quality",
    label: { "zh-CN": "显式披露不确定性", en: "Surface uncertainty" },
    description: {
      "zh-CN": "在备忘录顶部显示置信度与缺证据清单；关闭可保持 UI 更简洁。",
      en: "Show confidence band and missing-evidence list on every memo.",
    },
    defaultValue: true,
    reference: "requirements.md Req 10",
  },

  // ---- supervisor ----
  {
    id: "plan_drift_tolerance",
    kind: "slider",
    section: "supervisor",
    label: { "zh-CN": "计划漂移容忍度", en: "Plan drift tolerance" },
    description: {
      "zh-CN": "0 = 严格对齐 Execution_Plan，1 = 允许更广偏离。",
      en: "0 = strict plan-execution alignment, 1 = allow wide deviation.",
    },
    defaultValue: 0.15,
    min: 0,
    max: 1,
    step: 0.05,
    reference: "requirements.md Req 7 AC2",
  },
  {
    id: "auto_approve_low_risk",
    kind: "toggle",
    section: "supervisor",
    label: { "zh-CN": "自动批准低风险步骤", en: "Auto-approve low-risk steps" },
    description: {
      "zh-CN": "只读工具等低风险步骤不再人工审批；高风险仍必须审批。",
      en: "Read-only and low-risk steps skip human approval; destructive steps still require it.",
    },
    defaultValue: false,
    reference: "requirements.md Req 7 AC3",
  },
  {
    id: "audit_verbosity",
    kind: "select",
    section: "supervisor",
    label: { "zh-CN": "审计记录详细度", en: "Audit verbosity" },
    description: {
      "zh-CN": "standard：必要字段；detailed：含输入输出摘要；forensic：完整 diff，体积最大。",
      en: "standard = required fields; detailed = with I/O summaries; forensic = full diffs, heaviest.",
    },
    defaultValue: "standard",
    options: [
      { value: "standard", label: { "zh-CN": "标准", en: "Standard" } },
      { value: "detailed", label: { "zh-CN": "详细", en: "Detailed" } },
      { value: "forensic", label: { "zh-CN": "取证级", en: "Forensic" } },
    ],
    reference: "requirements.md Req 7 AC4 / Req 11",
  },

  // ---- model & budget ----
  {
    id: "temperature",
    kind: "slider",
    section: "model",
    label: { "zh-CN": "温度", en: "Temperature" },
    description: {
      "zh-CN": "0 = 稳定可复现，1 = 多样性更强。默认 0.2 偏稳。",
      en: "0 = deterministic / reproducible, 1 = more diverse. Default 0.2 favours stability.",
    },
    defaultValue: 0.2,
    min: 0,
    max: 1,
    step: 0.05,
    reference: "design.md §5 Model_Gateway",
  },
  {
    id: "max_tokens",
    kind: "slider",
    section: "model",
    label: { "zh-CN": "最大 token", en: "Max tokens" },
    description: {
      "zh-CN": "单次回复 token 上限。",
      en: "Per-response token cap.",
    },
    defaultValue: 1200,
    min: 256,
    max: 4096,
    step: 128,
    reference: "design.md §5 Model_Gateway",
  },
  {
    id: "seed",
    kind: "slider",
    section: "model",
    label: { "zh-CN": "随机种子", en: "Seed" },
    description: {
      "zh-CN": "固定种子保证可复现。设为 0 表示不固定。",
      en: "Fixed seed keeps runs reproducible. 0 = unseeded.",
    },
    defaultValue: 0,
    min: 0,
    max: 999999,
    step: 1,
    reference: "design.md §6 Correctness / PBT",
  },
];

export type ProfessionalParameterValues = Record<string, string | number | boolean>;

export function defaultProfessionalValues(): ProfessionalParameterValues {
  const values: ProfessionalParameterValues = {};
  for (const parameter of PROFESSIONAL_PARAMETERS) {
    values[parameter.id] = parameter.defaultValue;
  }
  return values;
}

export function parametersBySection(section: ProfessionalSection): ParameterDefinition[] {
  return PROFESSIONAL_PARAMETERS.filter((parameter) => parameter.section === section);
}

export const SIMPLE_MODE_AUTOMATION: Array<{ id: string; label: Record<Language, string> }> = [
  {
    id: "memory_profile",
    label: {
      "zh-CN": "依据记忆库自动套用你的偏好、风格与历史决策。",
      en: "Auto-applies your preferences, voice, and past decisions from the memory store.",
    },
  },
  {
    id: "expert_defaults",
    label: {
      "zh-CN": "默认采用顶级领域专家的思维模型与检索策略。",
      en: "Runs the workflow with top-expert defaults for thinking models and retrieval.",
    },
  },
  {
    id: "auto_clarify",
    label: {
      "zh-CN": "问题模糊时自动追问关键澄清点，避免跑偏。",
      en: "Automatically asks targeted clarifying questions when the goal is under-specified.",
    },
  },
  {
    id: "evidence_first",
    label: {
      "zh-CN": "强制证据优先：缺证据直接标记，不靠模型脑补。",
      en: "Evidence-first: missing evidence is flagged, never hallucinated.",
    },
  },
  {
    id: "safety_rails",
    label: {
      "zh-CN": "破坏性工具、无权限来源、可疑改写一律走审批。",
      en: "Destructive tools, unauthorised sources, and silent rewrites always require approval.",
    },
  },
];

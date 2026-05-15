"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Key, Loader2, Plus, Trash2, Zap } from "lucide-react";
import { useState } from "react";

import { usePreferences } from "@/components/preferences-provider";
import { Badge, Button, Input, Panel, Select } from "@/components/ui";
import { v2, type ModelSlotConfig } from "@/lib/api-v2";
import { cn } from "@/lib/utils";

const SLOT_LABELS: Record<string, Record<string, string>> = {
  generator: { "zh-CN": "生成模型（主力）", en: "Generator (Primary)" },
  verifier: { "zh-CN": "验证模型（独立审查）", en: "Verifier (Independent Review)" },
  classifier: { "zh-CN": "分类模型（问题路由）", en: "Classifier (Question Routing)" },
  embedder: { "zh-CN": "嵌入模型（向量检索）", en: "Embedder (Vector Search)" },
};

const SLOT_DESCRIPTIONS: Record<string, Record<string, string>> = {
  generator: {
    "zh-CN": "用于生成回答、诊断分析、思维模型推理。建议选择能力最强的模型。",
    en: "Used for answer generation, diagnosis, and thinking model reasoning. Pick your strongest model.",
  },
  verifier: {
    "zh-CN": "独立验证生成结果的真实性和目标符合度。必须和生成模型不同。",
    en: "Independently verifies truthfulness and goal fitness. Must differ from generator.",
  },
  classifier: {
    "zh-CN": "对问题进行语义分类，选择最佳思维模型。可选，不配则用关键词匹配。",
    en: "Semantic classification for thinking model selection. Optional — falls back to keyword matching.",
  },
  embedder: {
    "zh-CN": "生成文本向量用于语义检索。可选，不配则用 TF-IDF。",
    en: "Generates text embeddings for semantic search. Optional — falls back to TF-IDF.",
  },
};

export function ModelConfigPanel() {
  const { preferences } = usePreferences();
  const language = preferences.language;
  const queryClient = useQueryClient();

  const providersQuery = useQuery({
    queryKey: ["model-providers"],
    queryFn: () => v2.modelProviders(),
  });

  const configsQuery = useQuery({
    queryKey: ["model-configs"],
    queryFn: () => v2.modelConfigs(),
  });

  const providers = providersQuery.data?.providers ?? [];
  const configs = configsQuery.data?.slots ?? [];
  const availableSlots = configsQuery.data?.available_slots ?? ["generator", "verifier", "classifier", "embedder"];

  const [editingSlot, setEditingSlot] = useState<string | null>(null);

  return (
    <Panel>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Key className="h-4 w-4 text-accent" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-foreground">
              {language === "zh-CN" ? "模型 API 配置" : "Model API Configuration"}
            </h2>
          </div>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
            {language === "zh-CN"
              ? "连接任意 OpenAI 兼容的模型 API。支持 OpenAI、Anthropic、Gemini、DeepSeek、Groq、Mistral、Ollama 等。"
              : "Connect any OpenAI-compatible model API. Supports OpenAI, Anthropic, Gemini, DeepSeek, Groq, Mistral, Ollama, and more."}
          </p>
        </div>
      </div>

      <div className="mt-5 grid gap-4">
        {availableSlots.map((slot) => {
          const existing = configs.find((c) => c.slot === slot);
          const isEditing = editingSlot === slot;
          return (
            <SlotCard
              key={slot}
              slot={slot}
              config={existing}
              providers={providers}
              language={language}
              isEditing={isEditing}
              onEdit={() => setEditingSlot(isEditing ? null : slot)}
              onSaved={() => {
                setEditingSlot(null);
                queryClient.invalidateQueries({ queryKey: ["model-configs"] });
              }}
            />
          );
        })}
      </div>
    </Panel>
  );
}

function SlotCard({
  slot,
  config,
  providers,
  language,
  isEditing,
  onEdit,
  onSaved,
}: {
  slot: string;
  config: ModelSlotConfig | undefined;
  providers: Array<{ id: string; label: string; base_url_hint: string; models_hint?: string }>;
  language: "zh-CN" | "en";
  isEditing: boolean;
  onEdit: () => void;
  onSaved: () => void;
}) {
  const label = SLOT_LABELS[slot]?.[language] ?? slot;
  const description = SLOT_DESCRIPTIONS[slot]?.[language] ?? "";

  return (
    <div className={cn(
      "rounded-panel border p-4 transition",
      config?.api_key_configured
        ? "border-success/30 bg-success/5"
        : "border-border bg-panel",
    )}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-foreground">{label}</span>
            {config?.api_key_configured ? (
              <Badge className="border-success/40 bg-success/10 text-success">
                <Check className="mr-1 h-3 w-3" />
                {config.provider_id} / {config.model_name}
              </Badge>
            ) : (
              <Badge className="border-border bg-panel-muted text-muted">
                {language === "zh-CN" ? "未配置" : "Not configured"}
              </Badge>
            )}
          </div>
          <p className="mt-1 text-xs text-muted">{description}</p>
        </div>
        <Button variant="ghost" onClick={onEdit}>
          {isEditing
            ? (language === "zh-CN" ? "取消" : "Cancel")
            : config?.api_key_configured
              ? (language === "zh-CN" ? "修改" : "Edit")
              : (language === "zh-CN" ? "配置" : "Configure")}
        </Button>
      </div>

      {isEditing ? (
        <SlotForm
          slot={slot}
          config={config}
          providers={providers}
          language={language}
          onSaved={onSaved}
        />
      ) : null}
    </div>
  );
}

function SlotForm({
  slot,
  config,
  providers,
  language,
  onSaved,
}: {
  slot: string;
  config: ModelSlotConfig | undefined;
  providers: Array<{ id: string; label: string; base_url_hint: string; models_hint?: string }>;
  language: "zh-CN" | "en";
  onSaved: () => void;
}) {
  const [providerId, setProviderId] = useState(config?.provider_id ?? "openai");
  const [baseUrl, setBaseUrl] = useState(config?.base_url ?? "");
  const [apiKey, setApiKey] = useState("");
  const [modelName, setModelName] = useState(config?.model_name ?? "");

  const selectedProvider = providers.find((p) => p.id === providerId);

  // Auto-fill base_url when provider changes
  const handleProviderChange = (newId: string) => {
    setProviderId(newId);
    const p = providers.find((x) => x.id === newId);
    if (p?.base_url_hint && !baseUrl) {
      setBaseUrl(p.base_url_hint);
    }
  };

  const saveMutation = useMutation({
    mutationFn: () =>
      v2.saveModelConfig({
        slot,
        provider_id: providerId,
        base_url: baseUrl || selectedProvider?.base_url_hint || "",
        api_key: apiKey,
        model_name: modelName,
        enabled: true,
      }),
    onSuccess: () => onSaved(),
  });

  const testMutation = useMutation({
    mutationFn: () => v2.testModelConfig(slot),
  });

  return (
    <div className="mt-4 space-y-3 border-t border-border pt-4">
      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <label className="text-[11px] font-semibold uppercase tracking-widest text-muted">
            {language === "zh-CN" ? "模型厂商" : "Provider"}
          </label>
          <Select className="mt-1" value={providerId} onChange={(e) => handleProviderChange(e.target.value)}>
            {providers.map((p) => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </Select>
        </div>
        <div>
          <label className="text-[11px] font-semibold uppercase tracking-widest text-muted">
            {language === "zh-CN" ? "模型名称" : "Model Name"}
          </label>
          <Input
            className="mt-1"
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
            placeholder={(selectedProvider as any)?.models_hint || "gpt-4.1 / claude-sonnet-4 / deepseek-v4-pro"}
          />
        </div>
      </div>
      <div>
        <label className="text-[11px] font-semibold uppercase tracking-widest text-muted">
          API Key
        </label>
        <Input
          className="mt-1"
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={config?.api_key_configured ? (language === "zh-CN" ? "已配置，留空则不修改" : "Already set — leave blank to keep") : "sk-..."}
        />
      </div>
      <div>
        <label className="text-[11px] font-semibold uppercase tracking-widest text-muted">
          API {language === "zh-CN" ? "地址" : "Base URL"}
        </label>
        <Input
          className="mt-1"
          value={baseUrl || selectedProvider?.base_url_hint || ""}
          onChange={(e) => setBaseUrl(e.target.value)}
          placeholder="https://api.openai.com/v1"
        />
      </div>

      <div className="flex items-center gap-2 pt-2">
        <Button
          onClick={() => saveMutation.mutate()}
          disabled={!modelName || saveMutation.isPending}
        >
          {saveMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Check className="h-4 w-4" />
          )}
          {language === "zh-CN" ? "保存" : "Save"}
        </Button>
        {config?.api_key_configured ? (
          <Button
            variant="secondary"
            onClick={() => testMutation.mutate()}
            disabled={testMutation.isPending}
          >
            {testMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Zap className="h-4 w-4" />
            )}
            {language === "zh-CN" ? "测试连接" : "Test Connection"}
          </Button>
        ) : null}
      </div>

      {saveMutation.isError ? (
        <div className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
          {(saveMutation.error as Error)?.message ?? "Save failed"}
        </div>
      ) : null}

      {testMutation.data ? (
        <div className={cn(
          "rounded-md border px-3 py-2 text-sm",
          testMutation.data.ok
            ? "border-success/30 bg-success/10 text-success"
            : "border-danger/30 bg-danger/10 text-danger",
        )}>
          {testMutation.data.ok
            ? `✓ ${language === "zh-CN" ? "连接成功" : "Connected"}: ${testMutation.data.response}`
            : `✗ ${testMutation.data.error}`}
        </div>
      ) : null}
    </div>
  );
}

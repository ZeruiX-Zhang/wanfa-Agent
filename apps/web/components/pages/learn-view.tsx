"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Check, ClipboardCheck, Loader2, Sparkles } from "lucide-react";
import { useState } from "react";

import { usePreferences } from "@/components/preferences-provider";
import { Badge, Button, Input, Panel, Select, Textarea } from "@/components/ui";
import { v2, type Experiment, type LearningReview } from "@/lib/api-v2";
import { cn } from "@/lib/utils";

const ROOT_CAUSES = ["fact_wrong", "model_wrong", "execution_wrong", "unknown"] as const;

export function LearnView() {
  const { preferences, t } = usePreferences();
  const queryClient = useQueryClient();

  const planQuery = useQuery({
    queryKey: ["v2", "learn-plan", preferences.language],
    queryFn: () => v2.learnPlan({ language: preferences.language, limit: 5 }),
  });

  const experimentsQuery = useQuery({
    queryKey: ["v2", "experiments"],
    queryFn: () => v2.listExperiments(10),
  });

  const reviewsQuery = useQuery({
    queryKey: ["v2", "reviews"],
    queryFn: () => v2.listReviews(10),
  });

  const [activeExperiment, setActiveExperiment] = useState<Experiment | null>(null);
  const [review, setReview] = useState({
    actual_result: "",
    gap: "",
    root_cause: "unknown" as (typeof ROOT_CAUSES)[number],
    signal_for_next_time: "",
    knowledge_card_title: "",
    knowledge_card_body: "",
  });

  const reviewMutation = useMutation({
    mutationFn: () => {
      if (!activeExperiment) throw new Error("no experiment");
      return v2.createReview({
        experiment_id: activeExperiment.id,
        original_judgment: activeExperiment.hypothesis,
        actual_result: review.actual_result,
        gap: review.gap,
        root_cause: review.root_cause,
        signal_for_next_time: review.signal_for_next_time,
        knowledge_card_title: review.knowledge_card_title,
        knowledge_card_body: review.knowledge_card_body,
      });
    },
    onSuccess: async () => {
      if (activeExperiment) {
        await v2.updateExperiment(activeExperiment.id, {
          status: "succeeded",
          actual_result: review.actual_result,
        });
      }
      queryClient.invalidateQueries({ queryKey: ["v2"] });
      setActiveExperiment(null);
      setReview({
        actual_result: "",
        gap: "",
        root_cause: "unknown",
        signal_for_next_time: "",
        knowledge_card_title: "",
        knowledge_card_body: "",
      });
    },
  });

  const plan = planQuery.data?.items ?? [];
  const experiments = experimentsQuery.data?.items ?? [];
  const reviews = reviewsQuery.data?.items ?? [];

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 border-b border-border pb-5">
        <div className="text-xs font-semibold uppercase tracking-widest text-muted">Reality OS</div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">{t("learn.title")}</h1>
        <p className="max-w-3xl text-sm leading-6 text-muted">{t("learn.subtitle")}</p>
      </header>

      <section>
        <div className="mb-3 flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-accent" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-foreground">
            {preferences.language === "zh-CN" ? "我的知识盲区" : "My knowledge gaps"}
          </h2>
        </div>
        {plan.length === 0 ? (
          <Panel className="text-sm text-muted">{t("learn.empty")}</Panel>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {plan.map((p) => (
              <Panel key={p.concept_id}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-sm font-semibold text-foreground">{p.label}</div>
                    <div className="mt-1 text-xs text-muted">
                      {t("learn.row.item_count").replace("{count}", String(p.item_count))} ·{" "}
                      {t("learn.row.retrieved").replace("{count}", String(p.retrieved_count))}
                    </div>
                  </div>
                  <Badge
                    className={cn(
                      p.gap_level === "no_knowledge" && "border-danger/40 bg-danger/10 text-danger",
                      p.gap_level === "shallow" && "border-warning/40 bg-warning/10 text-warning",
                      p.gap_level === "consolidate" && "border-accent/40 bg-accent-soft text-foreground",
                    )}
                  >
                    {t(`learn.gap.${p.gap_level}`)}
                  </Badge>
                </div>
                <p className="mt-3 text-sm leading-6 text-foreground/80">{p.recommendation}</p>
              </Panel>
            ))}
          </div>
        )}
      </section>

      <section>
        <div className="mb-3 flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-accent" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-foreground">
            {preferences.language === "zh-CN" ? "待复盘的实验" : "Experiments to review"}
          </h2>
        </div>
        {experiments.length === 0 ? (
          <Panel className="text-sm text-muted">
            {preferences.language === "zh-CN"
              ? "暂无实验；在 提问 页面给出诊断后，会有建议的最小实验自动出现在这里。"
              : "No experiments yet. Run a diagnose on the Ask page and they will appear here."}
          </Panel>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {experiments.map((e) => (
              <Panel
                key={e.id}
                className={cn(activeExperiment?.id === e.id && "border-accent/60 shadow-lg")}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-sm font-semibold text-foreground">{e.hypothesis}</div>
                    <div className="mt-1 text-xs text-muted">{e.experiment}</div>
                  </div>
                  <Badge
                    className={cn(
                      e.status === "succeeded" && "border-success/40 bg-success/10 text-success",
                      e.status === "failed" && "border-danger/40 bg-danger/10 text-danger",
                      e.status === "running" && "border-accent/40 bg-accent-soft text-foreground",
                    )}
                  >
                    {e.status}
                  </Badge>
                </div>
                <div className="mt-3 flex gap-2">
                  <Button
                    variant={activeExperiment?.id === e.id ? "primary" : "secondary"}
                    onClick={() =>
                      setActiveExperiment((current) => (current?.id === e.id ? null : e))
                    }
                  >
                    <ClipboardCheck className="h-4 w-4" aria-hidden="true" />
                    {preferences.language === "zh-CN" ? "复盘" : "Review"}
                  </Button>
                </div>
              </Panel>
            ))}
          </div>
        )}
      </section>

      {activeExperiment ? (
        <Panel className="border-accent/40">
          <h2 className="text-sm font-semibold text-foreground">
            {preferences.language === "zh-CN" ? "复盘：" : "Review: "}
            {activeExperiment.hypothesis}
          </h2>

          <div className="mt-4 grid gap-3">
            <LabeledTextarea
              label={preferences.language === "zh-CN" ? "实际结果" : "Actual result"}
              value={review.actual_result}
              onChange={(v) => setReview({ ...review, actual_result: v })}
            />
            <LabeledTextarea
              label={preferences.language === "zh-CN" ? "判断与现实的差异" : "Gap between judgment and reality"}
              value={review.gap}
              onChange={(v) => setReview({ ...review, gap: v })}
            />
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-widest text-muted">
                {preferences.language === "zh-CN" ? "根因是什么" : "Root cause"}
              </label>
              <Select
                className="mt-1"
                value={review.root_cause}
                onChange={(e) => setReview({ ...review, root_cause: e.target.value as (typeof ROOT_CAUSES)[number] })}
              >
                {ROOT_CAUSES.map((cause) => (
                  <option key={cause} value={cause}>
                    {cause}
                  </option>
                ))}
              </Select>
            </div>
            <LabeledInput
              label={preferences.language === "zh-CN" ? "下次遇到类似问题先看什么" : "Signal to check next time"}
              value={review.signal_for_next_time}
              onChange={(v) => setReview({ ...review, signal_for_next_time: v })}
            />
            <LabeledInput
              label={preferences.language === "zh-CN" ? "沉淀的知识卡标题" : "Knowledge card title"}
              value={review.knowledge_card_title}
              onChange={(v) => setReview({ ...review, knowledge_card_title: v })}
            />
            <LabeledTextarea
              label={preferences.language === "zh-CN" ? "知识卡正文（会自动进入知识库）" : "Knowledge card body (auto-absorbed)"}
              value={review.knowledge_card_body}
              onChange={(v) => setReview({ ...review, knowledge_card_body: v })}
            />
          </div>

          <div className="mt-4 flex items-center gap-2">
            <Button
              onClick={() => reviewMutation.mutate()}
              disabled={reviewMutation.isPending || !review.actual_result.trim()}
            >
              {reviewMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Check className="h-4 w-4" aria-hidden="true" />
              )}
              {preferences.language === "zh-CN" ? "保存复盘" : "Save review"}
            </Button>
            <Button variant="ghost" onClick={() => setActiveExperiment(null)}>
              {t("common.cancel")}
            </Button>
          </div>
        </Panel>
      ) : null}

      <section>
        <div className="mb-3 flex items-center gap-2">
          <ClipboardCheck className="h-4 w-4 text-accent" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-foreground">
            {preferences.language === "zh-CN" ? "已完成复盘" : "Completed reviews"}
          </h2>
        </div>
        {reviews.length === 0 ? (
          <Panel className="text-sm text-muted">
            {preferences.language === "zh-CN" ? "还没有复盘记录。" : "No reviews yet."}
          </Panel>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {reviews.map((r) => (
              <ReviewCard key={r.id} review={r} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function LabeledInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <label className="text-[11px] font-semibold uppercase tracking-widest text-muted">{label}</label>
      <Input className="mt-1" value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  );
}

function LabeledTextarea({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <label className="text-[11px] font-semibold uppercase tracking-widest text-muted">{label}</label>
      <Textarea className="mt-1" value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  );
}

function ReviewCard({ review }: { review: LearningReview }) {
  return (
    <Panel>
      <div className="text-sm font-semibold text-foreground">{review.knowledge_card_title || review.gap}</div>
      <div className="mt-1 text-xs text-muted">{review.original_judgment}</div>
      <p className="mt-2 text-sm text-foreground/80">{review.actual_result}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
        <Badge className="text-[10px]">{review.root_cause}</Badge>
      </div>
    </Panel>
  );
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, Sparkles, Target, Trophy } from "lucide-react";
import Link from "next/link";
import type { FormEvent } from "react";
import { useState } from "react";
import { ErrorState, LoadingState } from "@/components/data-state";
import { MetricCard, StatusBadge } from "@/components/insight-ui";
import { PageHeader } from "@/components/page-header";
import { Badge, Button, Input, Panel, Table, Td, Textarea, Th } from "@/components/ui";
import { api } from "@/lib/api";
import { reviewRecommendation } from "@/lib/insights";
import { fmtDate, pct } from "@/lib/utils";

export default function AIProductReviewsPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ product_name: "", official_url: "", competitors: "", target_users: "" });
  const { data, isLoading, error } = useQuery({
    queryKey: ["product-reviews"],
    queryFn: () => api.productReviews({ limit: 100 }),
  });
  const create = useMutation({
    mutationFn: () =>
      api.createProductReview({
        product_name: form.product_name,
        official_url: form.official_url || undefined,
        competitors: form.competitors
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        target_users: form.target_users
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      }),
    onSuccess: () => {
      setForm({ product_name: "", official_url: "", competitors: "", target_users: "" });
      queryClient.invalidateQueries({ queryKey: ["product-reviews"] });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate();
  }

  const reviews = data?.items ?? [];
  const completed = reviews.filter((review) => review.status === "completed").length;
  const competitors = reviews.reduce((sum, review) => sum + review.competitors.length, 0);
  const strongRecommendations = reviews.filter((review) => review.confidence >= 0.75).length;

  return (
    <>
      <PageHeader
        title="AI Product Reviews"
        description="Competitive AI product review workflow with target users, competitor matrix, recommendation, confidence, and evidence drill-down."
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={Sparkles} label="Reviews" value={data?.total ?? 0} detail={`${completed} completed review(s)`} />
        <MetricCard icon={Trophy} label="Strong Signals" value={strongRecommendations} detail="Confidence at or above 75%" />
        <MetricCard icon={Target} label="Competitors" value={competitors} detail="Competitor entries tracked across reviews" />
        <MetricCard label="Evidence" value="detail" detail="Open each review to inspect source count and evidence snippets" />
      </div>

      <Panel className="mt-4">
        <form className="grid gap-3 lg:grid-cols-4" onSubmit={submit}>
          <Input
            required
            placeholder="Product name"
            value={form.product_name}
            onChange={(event) => setForm({ ...form, product_name: event.target.value })}
          />
          <Input
            placeholder="Official URL"
            value={form.official_url}
            onChange={(event) => setForm({ ...form, official_url: event.target.value })}
          />
          <Input
            placeholder="Competitors, comma-separated"
            value={form.competitors}
            onChange={(event) => setForm({ ...form, competitors: event.target.value })}
          />
          <Button disabled={create.isPending} type="submit">
            <Search className="h-4 w-4" aria-hidden="true" />
            Run Review
          </Button>
          <Textarea
            className="lg:col-span-4"
            placeholder="Target users, comma-separated"
            value={form.target_users}
            onChange={(event) => setForm({ ...form, target_users: event.target.value })}
          />
        </form>
      </Panel>

      {isLoading ? <LoadingState label="Loading product reviews" /> : null}
      {error ? <ErrorState error={error} /> : null}
      {data ? (
        <Panel className="mt-4 overflow-x-auto">
          {reviews.length === 0 ? (
            <div className="text-sm text-muted">No product reviews yet.</div>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Product</Th>
                  <Th>Recommendation</Th>
                  <Th>Confidence</Th>
                  <Th>Competitors</Th>
                  <Th>Target Users</Th>
                  <Th>Status</Th>
                  <Th>Created</Th>
                </tr>
              </thead>
              <tbody>
                {reviews.map((review) => (
                  <tr key={review.id}>
                    <Td>
                      <Link className="font-medium hover:text-accent" href={`/ai-product-reviews/${review.id}`}>
                        {review.product_name}
                      </Link>
                      {review.official_url ? <div className="mt-1 text-xs text-muted">{review.official_url}</div> : null}
                    </Td>
                    <Td>
                      <Badge>{reviewRecommendation(review)}</Badge>
                    </Td>
                    <Td>{pct(review.confidence)}</Td>
                    <Td>{review.competitors.join(", ") || "none"}</Td>
                    <Td>{review.target_users.join(", ") || "not specified"}</Td>
                    <Td>
                      <StatusBadge status={review.status} />
                    </Td>
                    <Td>{fmtDate(review.created_at)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Panel>
      ) : null}
    </>
  );
}

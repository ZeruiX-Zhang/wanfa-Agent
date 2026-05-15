"use client";

import { useQueries } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Event, EventDetail } from "@/lib/types";

function fromEvent(event: Event): EventDetail {
  return {
    ...event,
    claims: [],
    evidence: [],
  };
}

export function useEventDetails(events: Event[] | undefined, limit = 12) {
  const selected = (events ?? []).slice(0, limit);
  const queries = useQueries({
    queries: selected.map((event) => ({
      queryKey: ["event", event.id],
      queryFn: () => api.event(event.id),
      staleTime: 30_000,
    })),
  });

  const details = selected.map((event, index) => queries[index]?.data ?? fromEvent(event));
  const isFetching = queries.some((query) => query.isFetching);
  const error = queries.find((query) => query.error)?.error ?? null;

  return { details, isFetching, error };
}

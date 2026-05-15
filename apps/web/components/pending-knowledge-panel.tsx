"use client";

import { useState } from "react";
import { PendingKnowledgeWrites } from "@/components/reality-adapter-ui";
import type { PendingKnowledgeWrite } from "@/lib/reality-adapter-data";

export function PendingKnowledgePanel({ writes }: { writes: PendingKnowledgeWrite[] }) {
  const [items, setItems] = useState(writes);
  return (
    <PendingKnowledgeWrites
      writes={items}
      onUndo={(id) => {
        setItems((current) =>
          current.map((item) =>
            item.id === id ? { ...item, status: "undo_requested", undoAvailable: false } : item,
          ),
        );
      }}
    />
  );
}


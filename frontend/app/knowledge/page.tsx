"use client";

import { KnowledgePanel } from "@/components/KnowledgePanel";

export default function KnowledgePage() {
  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-emerald-400">Knowledge Assistant</h1>
      <p className="text-slate-400">
        Query internal documents. Results include citations to source chunks.
      </p>
      <KnowledgePanel />
    </div>
  );
}

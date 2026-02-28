"use client";

import { ChatPanel } from "@/components/ChatPanel";

export default function AssistantPage() {
  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-emerald-400">AI Analyst Assistant</h1>
      <p className="text-slate-400">
        Ask questions about forecasts, scenarios, and historical data. Answers are
        grounded in real data only.
      </p>
      <ChatPanel />
    </div>
  );
}

"use client";

import { AssistantShell } from "@/components/assistants/AssistantShell";

export default function KnowledgeAssistantPage() {
  return (
    <AssistantShell
      assistantType="knowledge"
      title="Knowledge Assistant"
      description="Factual answers from internal reports — products, categories, trends."
    />
  );
}

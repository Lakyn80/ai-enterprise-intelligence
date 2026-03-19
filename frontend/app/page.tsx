"use client";

import { useLocale } from "@/lib/i18n/LocaleContext";
import { getT } from "@/lib/i18n/translations";

export default function Home() {
  const { locale } = useLocale();
  const t = getT(locale).home;

  const cards = [
    { href: "/forecast", title: t.cardForecast, desc: t.cardForecastDesc },
    { href: "/assistants/analyst", title: t.cardAnalyst, desc: t.cardAnalystDesc },
    { href: "/assistants/knowledge", title: t.cardKnowledge, desc: t.cardKnowledgeDesc },
    { href: "/data", title: t.cardData, desc: t.cardDataDesc },
  ];

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold text-emerald-400">{t.title}</h1>
      <p className="max-w-xl text-slate-400">{t.desc}</p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((c) => (
          <a
            key={c.href}
            href={c.href}
            className="rounded-lg border border-slate-700 bg-slate-800/50 p-6 transition hover:border-emerald-500/50"
          >
            <h2 className="font-semibold text-white">{c.title}</h2>
            <p className="mt-2 text-sm text-slate-400">{c.desc}</p>
          </a>
        ))}
      </div>
    </div>
  );
}

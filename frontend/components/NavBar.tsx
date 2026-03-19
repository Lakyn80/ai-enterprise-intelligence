"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale } from "@/lib/i18n/LocaleContext";
import { getT, type Locale } from "@/lib/i18n/translations";

const LOCALES: { value: Locale; label: string }[] = [
  { value: "en", label: "EN" },
  { value: "cs", label: "CS" },
  { value: "sk", label: "SK" },
  { value: "ru", label: "RU" },
];

export function NavBar() {
  const { locale, setLocale } = useLocale();
  const t = getT(locale);
  const pathname = usePathname();

  const navLinks = [
    { href: "/forecast", label: t.nav.forecast },
    { href: "/data", label: t.nav.data },
    { href: "/assistants/knowledge", label: t.nav.knowledge },
    { href: "/assistants/analyst", label: t.nav.analyst },
  ];

  return (
    <nav className="border-b border-slate-800 bg-slate-900/50 px-6 py-3">
      <div className="mx-auto flex max-w-6xl items-center gap-1">
        <Link href="/" className="mr-4 text-lg font-semibold text-emerald-400 shrink-0">
          {t.nav.brand}
        </Link>

        <div className="flex items-center gap-1 flex-1">
          {navLinks.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded px-3 py-1.5 text-sm transition-colors ${
                pathname.startsWith(l.href)
                  ? "bg-slate-700 text-white"
                  : "text-slate-400 hover:bg-slate-800 hover:text-white"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </div>

        {/* Language switcher */}
        <div className="flex items-center gap-1 ml-2">
          {LOCALES.map((l) => (
            <button
              key={l.value}
              onClick={() => setLocale(l.value)}
              className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
                locale === l.value
                  ? "bg-emerald-600 text-white"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>

        <Link
          href="/admin"
          className="ml-3 text-sm text-slate-500 hover:text-slate-300"
        >
          {t.nav.admin}
        </Link>
      </div>
    </nav>
  );
}

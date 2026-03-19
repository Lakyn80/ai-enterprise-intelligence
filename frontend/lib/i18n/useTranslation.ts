"use client";

// Re-export for components that don't need the full context
export type { Locale } from "./translations";
export { getT } from "./translations";
export { useLocale } from "./LocaleContext";

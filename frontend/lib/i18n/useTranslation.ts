"use client";

import { useState } from "react";
import { type Locale, getTranslations } from "./translations";

export function useTranslation(defaultLocale: Locale = "en") {
  const [locale, setLocale] = useState<Locale>(defaultLocale);
  const tr = getTranslations(locale);
  return { locale, setLocale, tr };
}

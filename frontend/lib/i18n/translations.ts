export type Locale = "en" | "cs" | "sk" | "ru";

const t = {
  en: {
    presetQuestions: "Preset questions",
    customQuestion: "Ask anything...",
    ask: "Ask",
    asking: "Asking...",
    cachedBadge: "cached",
    citations: "Sources",
    usedTools: "Tools used",
    errorPrefix: "Error",
    noAnswer: "No answer returned.",
    knowledgeTitle: "Knowledge Assistant",
    knowledgeDesc: "Factual answers from internal reports — products, categories, trends.",
    analystTitle: "AI Analyst Assistant",
    analystDesc: "Data-driven analysis using live forecasting tools and business intelligence.",
    locale: "Language",
  },
  cs: {
    presetQuestions: "Připravené otázky",
    customQuestion: "Zeptejte se na cokoliv...",
    ask: "Zeptat se",
    asking: "Hledám odpověď...",
    cachedBadge: "z cache",
    citations: "Zdroje",
    usedTools: "Použité nástroje",
    errorPrefix: "Chyba",
    noAnswer: "Odpověď nebyla vrácena.",
    knowledgeTitle: "Znalostní asistent",
    knowledgeDesc: "Faktické odpovědi z interních reportů — produkty, kategorie, trendy.",
    analystTitle: "AI analytický asistent",
    analystDesc: "Datová analýza s využitím nástrojů pro predikci a business intelligence.",
    locale: "Jazyk",
  },
  sk: {
    presetQuestions: "Pripravené otázky",
    customQuestion: "Spýtajte sa na čokoľvek...",
    ask: "Opýtať sa",
    asking: "Hľadám odpoveď...",
    cachedBadge: "z cache",
    citations: "Zdroje",
    usedTools: "Použité nástroje",
    errorPrefix: "Chyba",
    noAnswer: "Odpoveď nebola vrátená.",
    knowledgeTitle: "Znalostný asistent",
    knowledgeDesc: "Faktické odpovede z interných reportov — produkty, kategórie, trendy.",
    analystTitle: "AI analytický asistent",
    analystDesc: "Dátová analýza s využitím nástrojov pre predikciu a business intelligence.",
    locale: "Jazyk",
  },
  ru: {
    presetQuestions: "Готовые вопросы",
    customQuestion: "Спросите что угодно...",
    ask: "Спросить",
    asking: "Ищу ответ...",
    cachedBadge: "из кэша",
    citations: "Источники",
    usedTools: "Использованные инструменты",
    errorPrefix: "Ошибка",
    noAnswer: "Ответ не получен.",
    knowledgeTitle: "Ассистент знаний",
    knowledgeDesc: "Фактические ответы из внутренних отчётов — продукты, категории, тренды.",
    analystTitle: "ИИ-аналитический ассистент",
    analystDesc: "Анализ данных с использованием инструментов прогнозирования и бизнес-аналитики.",
    locale: "Язык",
  },
} as const;

export type TranslationKey = keyof typeof t.en;

export function getTranslations(locale: Locale) {
  return t[locale] ?? t.en;
}

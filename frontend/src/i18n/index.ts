import en from "./locales/en"
import zhCN from "./locales/zh-CN"
import zhTW from "./locales/zh-TW"
import es from "./locales/es"
import fr from "./locales/fr"

export type Locale = "en" | "zh-CN" | "zh-TW" | "es" | "fr"

export const locales: Locale[] = ["en", "zh-CN", "zh-TW", "es", "fr"]

const translations = { en, "zh-CN": zhCN, "zh-TW": zhTW, es, fr }

export function getTranslations(locale: Locale) {
  return translations[locale]
}

export function getDefaultLocale(): Locale {
  if (typeof window === "undefined") return "en"
  const stored = localStorage.getItem("quotepilot_locale") as Locale | null
  if (stored && locales.includes(stored)) return stored
  return "en"
}

export function setStoredLocale(locale: Locale) {
  if (typeof window !== "undefined") {
    localStorage.setItem("quotepilot_locale", locale)
  }
}

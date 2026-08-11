"use client"

import { useT } from "@/i18n/I18nProvider"
import { locales, type Locale } from "@/i18n/index"
import { Globe } from "lucide-react"
import { useState, useRef, useEffect } from "react"

const FLAGS: Record<Locale, string> = {
  en: "🇺🇸",
  "zh-CN": "🇨🇳",
  "zh-TW": "🇹🇼",
  es: "🇪🇸",
  fr: "🇫🇷",
}

export default function LanguageSwitcher() {
  const { locale, setLocale, t } = useT()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [])

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
        title={t.language.switch}
      >
        <Globe className="w-3.5 h-3.5" />
        <span>{FLAGS[locale]}</span>
        <span className="hidden sm:inline">{t.language[locale]}</span>
      </button>

      {open && (
        <div className="absolute bottom-full left-0 mb-1 w-40 bg-white border border-gray-200 rounded-lg shadow-lg z-50 py-1">
          <p className="px-3 py-1.5 text-xs text-gray-400 font-medium uppercase tracking-wider">
            {t.language.switch}
          </p>
          {locales.map((loc) => (
            <button
              key={loc}
              onClick={() => {
                setLocale(loc as Locale)
                setOpen(false)
              }}
              className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 hover:bg-gray-50 transition-colors ${
                locale === loc ? "text-brand-600 font-medium bg-brand-50" : "text-gray-700"
              }`}
            >
              <span className="text-base">{FLAGS[loc]}</span>
              <span>{t.language[loc]}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

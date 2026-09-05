"use client"

import { useState } from "react"
import { Menu, X, LogOut, LogIn } from "lucide-react"
import type { LucideIcon } from "lucide-react"
import LanguageSwitcher from "@/components/LanguageSwitcher"
import { useT } from "@/i18n/I18nProvider"
import BrandLogo from "@/components/BrandLogo"

export interface NavItem {
  key: string
  label: string
  icon: LucideIcon
}

interface DashboardShellProps {
  nav: NavItem[]
  active: string
  onNavigate: (key: string) => void
  userEmail?: string | null
  onSignOut: () => void
  guestMode?: boolean
  onSignIn?: () => void
  children: React.ReactNode
}

export default function DashboardShell({
  nav,
  active,
  onNavigate,
  userEmail,
  onSignOut,
  guestMode,
  onSignIn,
  children,
}: DashboardShellProps) {
  const { t } = useT()
  const [open, setOpen] = useState(false)

  const navigate = (key: string) => {
    onNavigate(key)
    setOpen(false)
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 bg-white border-r border-slate-200 flex flex-col transition-transform duration-200 ease-in-out lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="h-16 flex items-center gap-2.5 px-4 border-b border-slate-200 flex-shrink-0">
          <BrandLogo className="w-36 flex-1 min-w-0" />
          <div className="hidden lg:block flex-shrink-0">
            <LanguageSwitcher />
          </div>
          <button
            onClick={() => setOpen(false)}
            className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg lg:hidden flex-shrink-0"
            aria-label="Close menu"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {nav.map((item) => (
            <button
              key={item.key}
              onClick={() => navigate(item.key)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-150 ${
                active === item.key
                  ? "bg-brand-50 text-brand-700"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              }`}
            >
              <item.icon className="w-5 h-5 flex-shrink-0" />
              <span className="truncate">{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="p-3 border-t border-slate-200 space-y-2 flex-shrink-0">
          {guestMode ? (
            <button
              onClick={onSignIn}
              className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-white bg-brand-600 hover:bg-brand-700 transition-colors duration-150"
            >
              <LogIn className="w-5 h-5" />
              {t.auth.signIn}
            </button>
          ) : (
            <>
              <div className="flex items-center gap-2.5 px-2 py-1.5">
                <div className="w-8 h-8 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-xs font-semibold uppercase flex-shrink-0">
                  {(userEmail?.[0] || "?").toUpperCase()}
                </div>
                <p className="text-sm font-medium text-slate-700 truncate">{userEmail}</p>
              </div>
              <button
                onClick={onSignOut}
                className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors duration-150"
              >
                <LogOut className="w-5 h-5" />
                {t.common.signOut}
              </button>
            </>
          )}
        </div>
      </aside>

      {open && (
        <div
          className="fixed inset-0 bg-black/40 z-30 lg:hidden"
          onClick={() => setOpen(false)}
          aria-hidden
        />
      )}

      <div className="lg:pl-64">
        {/* Mobile topbar */}
        <header className="sticky top-0 z-20 h-14 bg-white border-b border-slate-200 flex items-center gap-3 px-4 lg:hidden">
          <button
            onClick={() => setOpen(true)}
            className="p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <BrandLogo className="w-28" />
          </div>
          <div className="ml-auto">
            <LanguageSwitcher />
          </div>
        </header>

        <main className="p-4 md:p-6 lg:p-8">
          <div className="mx-auto max-w-[1400px]">{children}</div>
        </main>
      </div>
    </div>
  )
}

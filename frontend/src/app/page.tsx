"use client"

import { useState } from "react"
import { Package, MessageSquareText, FileText, TrendingUp } from "lucide-react"
import { getDashboardStats } from "@/lib/store"
import type { DashboardStats } from "@/types"
import { useT } from "@/i18n/I18nProvider"

export default function DashboardPage() {
  const { t } = useT()
  const [stats] = useState<DashboardStats>(() => getDashboardStats())

  const cards = [
    {
      label: t.dashboard.products,
      value: stats.total_products,
      icon: Package,
      color: "text-brand-600 bg-brand-100",
    },
    {
      label: t.dashboard.todayInquiries,
      value: stats.today_inquiries,
      icon: MessageSquareText,
      color: "text-blue-600 bg-blue-100",
    },
    {
      label: t.dashboard.totalInquiries,
      value: stats.total_inquiries,
      icon: TrendingUp,
      color: "text-green-600 bg-green-100",
    },
    {
      label: t.dashboard.quotesGenerated,
      value: stats.total_quotes,
      icon: FileText,
      color: "text-purple-600 bg-purple-100",
    },
  ]

  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900">{t.dashboard.title}</h2>
        <p className="mt-1 text-sm text-gray-500">
          {t.dashboard.subtitle}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {cards.map((card) => (
          <div key={card.label} className="card p-5">
            <div className="flex items-center gap-4">
              <div className={`w-11 h-11 rounded-lg flex items-center justify-center ${card.color}`}>
                <card.icon className="w-5 h-5" />
              </div>
              <div>
                <p className="text-sm text-gray-500">{card.label}</p>
                <p className="text-2xl font-bold text-gray-900">{card.value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {Object.keys(stats.categories).length > 0 && (
        <div className="card p-5">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            {t.dashboard.productsByCategory}
          </h3>
          <div className="space-y-3">
            {Object.entries(stats.categories).map(([cat, count]) => (
              <div key={cat} className="flex items-center justify-between">
                <span className="text-sm text-gray-600 capitalize">
                  {cat.replace(/_/g, " ")}
                </span>
                <div className="flex items-center gap-3">
                  <div className="w-40 h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-brand-500 rounded-full"
                      style={{
                        width: `${stats.total_products > 0 ? ((count / stats.total_products) * 100).toFixed(0) : 0}%`,
                      }}
                    />
                  </div>
                  <span className="text-sm font-medium text-gray-900 w-8 text-right">
                    {count}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

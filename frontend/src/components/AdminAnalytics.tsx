"use client"

import { useEffect, useState } from "react"
import { Activity, BarChart3, Inbox, Users } from "lucide-react"
import { adminGetTrends } from "@/lib/api-client"
import type { AdminTrendDay } from "@/lib/api-client"

type Metric = Exclude<keyof AdminTrendDay, "date">
type Series = { key: Metric; label: string; color: string }

function TrendChart({ title, data, series }: { title: string; data: AdminTrendDay[]; series: Series[] }) {
  const width = 760
  const height = 240
  const left = 38
  const top = 16
  const right = 12
  const bottom = 32
  const plotWidth = width - left - right
  const plotHeight = height - top - bottom
  const maximum = Math.max(1, ...data.flatMap(day => series.map(item => day[item.key])))
  const scaleMax = Math.max(1, Math.ceil(maximum / 4) * 4)
  const x = (index: number) => left + (index * plotWidth) / Math.max(1, data.length - 1)
  const y = (value: number) => top + plotHeight * (1 - value / scaleMax)
  const labelStep = Math.max(1, Math.ceil(data.length / 6))

  return (
    <section className="card p-5 min-w-0">
      <h2 className="font-semibold text-slate-900">{title}</h2>
      <div className="flex flex-wrap gap-x-5 gap-y-2 mt-3 text-xs text-slate-600">
        {series.map(item => <span key={item.key} className="inline-flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }} />
          {item.label} · {data.reduce((sum, day) => sum + day[item.key], 0).toLocaleString()}
        </span>)}
      </div>
      <div className="mt-4 overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title}，按 UTC 日期展示每日趋势`} className="w-full min-w-[460px] h-auto">
          {[0, 1, 2, 3, 4].map(index => {
            const value = (scaleMax * (4 - index)) / 4
            const lineY = y(value)
            return <g key={index}>
              <line x1={left} x2={width - right} y1={lineY} y2={lineY} stroke="#e2e8f0" />
              <text x={left - 7} y={lineY + 4} textAnchor="end" fontSize="11" fill="#64748b">{Number.isInteger(value) ? value : value.toFixed(1)}</text>
            </g>
          })}
          {data.map((day, index) => index % labelStep === 0 || index === data.length - 1 ?
            <text key={day.date} x={x(index)} y={height - 5} textAnchor="middle" fontSize="11" fill="#64748b">{day.date.slice(5)}</text> : null)}
          {series.map(item => <g key={item.key}>
            <polyline fill="none" stroke={item.color} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round"
              points={data.map((day, index) => `${x(index)},${y(day[item.key])}`).join(" ")} />
            {data.map((day, index) => <circle key={day.date} cx={x(index)} cy={y(day[item.key])} r="4"
              fill={item.color} stroke="white" strokeWidth="1.5">
              <title>{`${day.date} ${item.label}: ${day[item.key]}`}</title>
            </circle>)}
          </g>)}
        </svg>
      </div>
    </section>
  )
}

export default function AdminAnalytics() {
  const [range, setRange] = useState<7 | 30 | 90>(30)
  const [days, setDays] = useState<AdminTrendDay[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(false)
    adminGetTrends(range).then(result => {
      if (active) setDays(result.days)
    }).catch(() => {
      if (active) setError(true)
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [range])

  const totals = {
    views: days.reduce((sum, day) => sum + day.buyer_views + day.seller_views + day.admin_views, 0),
    analyses: days.reduce((sum, day) => sum + day.analyses, 0),
    sent: days.reduce((sum, day) => sum + day.sent_inquiries, 0),
    accounts: days.reduce((sum, day) => sum + day.new_buyers + day.new_sellers, 0),
  }

  return <>
    <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">数据分析</h1>
        <p className="mt-1 text-sm text-slate-500">各网页端访问、询盘与新增账号 · 按 UTC 日期统计</p>
      </div>
      <div className="flex gap-1 rounded-lg border border-slate-200 bg-white p-1" aria-label="统计时间范围">
        {([7, 30, 90] as const).map(value => <button key={value} type="button" onClick={() => setRange(value)}
          aria-pressed={range === value}
          className={`rounded-md px-3 py-1.5 text-sm ${range === value ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-50"}`}>
          {value} 天
        </button>)}
      </div>
    </header>
    {loading ? <div className="card p-8 text-sm text-slate-500" role="status">正在加载统计数据…</div>
      : error ? <div className="card p-8 text-sm text-red-700" role="alert">统计数据加载失败，请切换时间范围后重试。</div>
      : <>
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-5">
          {[
            { label: "页面浏览", value: totals.views, icon: BarChart3 },
            { label: "询盘分析", value: totals.analyses, icon: Activity },
            { label: "发送卖家", value: totals.sent, icon: Inbox },
            { label: "新增账号", value: totals.accounts, icon: Users },
          ].map(item => <div key={item.label} className="card p-4">
            <div className="flex items-center gap-2 text-sm text-slate-500"><item.icon className="w-4 h-4" />{item.label}</div>
            <p className="mt-2 text-2xl font-semibold text-slate-900">{item.value.toLocaleString()}</p>
          </div>)}
        </div>
        <div className="grid gap-5">
          <TrendChart title="各端页面浏览量" data={days} series={[
            { key: "buyer_views", label: "买家端", color: "#2563eb" },
            { key: "seller_views", label: "卖家端", color: "#059669" },
            { key: "admin_views", label: "管理端", color: "#d97706" },
          ]} />
          <TrendChart title="询盘趋势" data={days} series={[
            { key: "analyses", label: "询盘分析", color: "#7c3aed" },
            { key: "sent_inquiries", label: "发送卖家", color: "#e11d48" },
          ]} />
          <TrendChart title="新增账号" data={days} series={[
            { key: "new_buyers", label: "买家", color: "#2563eb" },
            { key: "new_sellers", label: "卖家", color: "#059669" },
          ]} />
        </div>
        <p className="mt-4 text-xs leading-5 text-slate-500">页面浏览量从本功能上线后开始记录：进入买家首页或已登录的卖家、管理工作台各计一次，不代表独立访客；询盘分析、发送卖家和新增账号使用已有记录。</p>
      </>}
  </>
}

import type { LucideIcon } from "lucide-react"

interface StatCardProps {
  label: string
  value: number
  icon: LucideIcon
}

export default function StatCard({ label, value, icon: Icon }: StatCardProps) {
  return (
    <div className="card p-5">
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-slate-100 text-slate-500 flex items-center justify-center">
          <Icon className="w-4 h-4" />
        </div>
        <p className="text-sm text-slate-500 capitalize">{label}</p>
      </div>
      <p className="mt-3 text-2xl font-semibold tracking-tight text-slate-900">{value}</p>
    </div>
  )
}

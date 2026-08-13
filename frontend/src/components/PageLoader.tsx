import { Zap } from "lucide-react"

export default function PageLoader() {
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-brand-600 text-white flex items-center justify-center">
          <Zap className="w-5 h-5" />
        </div>
        <div className="w-24 h-2 rounded-full bg-slate-200 animate-pulse" />
      </div>
    </div>
  )
}

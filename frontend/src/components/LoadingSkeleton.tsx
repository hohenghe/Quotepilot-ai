export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />
}

export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="card overflow-hidden">
      <div className="divide-y divide-slate-100">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="flex items-center gap-4 px-4 py-4">
            <Skeleton className="w-4 h-4 flex-shrink-0" />
            {Array.from({ length: cols }).map((_, c) => (
              <Skeleton
                key={c}
                className={`h-4 ${c === 0 ? "w-2/5" : "w-24"}`}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

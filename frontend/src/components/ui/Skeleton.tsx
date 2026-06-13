interface SkeletonProps {
  className?: string
}

export function Skeleton({ className = '' }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse rounded-xl bg-slate-200 dark:bg-slate-700 ${className}`}
    />
  )
}

export function SkeletonCard({ lines = 2 }: { lines?: number }) {
  return (
    <div className="rounded-2xl border border-slate-200/60 bg-white/80 p-6 dark:border-slate-700/60 dark:bg-slate-900/80">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-3">
          <Skeleton className="h-5 w-1/3" />
          {lines > 1 && <Skeleton className="h-4 w-2/3" />}
        </div>
        <Skeleton className="h-9 w-20" />
      </div>
    </div>
  )
}

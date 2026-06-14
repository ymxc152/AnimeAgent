import { Card } from './Card'

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

interface SkeletonCardProps {
  lines?: number
  variant?: 'list-item' | 'stat' | 'compact'
}

export function SkeletonCard({ lines = 2, variant = 'list-item' }: SkeletonCardProps) {
  const padding = variant === 'compact' ? 'sm' : 'md'

  return (
    <Card padding={padding}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-3">
          <Skeleton className="h-5 w-1/3" />
          {lines > 1 && <Skeleton className="h-4 w-2/3" />}
        </div>
        <Skeleton className="h-9 w-20" />
      </div>
    </Card>
  )
}

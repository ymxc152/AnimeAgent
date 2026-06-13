interface LoadingProps {
  message?: string
}

export function Loading({ message }: LoadingProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16">
      <div className="relative h-10 w-10">
        <div className="absolute inset-0 rounded-full border-2 border-slate-200 dark:border-slate-700" />
        <div className="absolute inset-0 rounded-full border-2 border-indigo-600 border-t-transparent animate-spin dark:border-indigo-400" />
      </div>
      {message && <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">{message}</p>}
    </div>
  )
}

import { forwardRef, type InputHTMLAttributes } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = '', ...props }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
            {label}
          </label>
        )}
        <input
          ref={ref}
          className={`
            w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5
            text-sm text-slate-900 placeholder:text-slate-400
            transition-colors duration-200
            focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20
            dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500
            dark:focus:border-indigo-400 dark:focus:ring-indigo-400/20
            disabled:cursor-not-allowed disabled:opacity-60
            ${error ? 'border-rose-500 focus:border-rose-500 focus:ring-rose-500/20' : ''}
            ${className}
          `}
          {...props}
        />
        {error && <p className="mt-1 text-xs text-rose-500">{error}</p>}
      </div>
    )
  }
)

Input.displayName = 'Input'

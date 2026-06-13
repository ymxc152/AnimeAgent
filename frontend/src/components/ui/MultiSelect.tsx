import { useState, useRef, useEffect } from 'react'
import { Check, ChevronDown, X } from 'lucide-react'

interface Option {
  value: string
  label: string
}

interface MultiSelectProps {
  label?: string
  options: Option[]
  value: string[]
  onChange: (value: string[]) => void
  placeholder?: string
}

export function MultiSelect({ label, options, value, onChange, placeholder }: MultiSelectProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  function toggle(optionValue: string) {
    if (value.includes(optionValue)) {
      onChange(value.filter((v) => v !== optionValue))
    } else {
      onChange([...value, optionValue])
    }
  }

  function clear() {
    onChange([])
  }

  const selectedLabels = value
    .map((v) => options.find((o) => o.value === v)?.label)
    .filter(Boolean)

  return (
    <div ref={ref} className="relative">
      {label && (
        <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
          {label}
        </label>
      )}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm transition-colors hover:border-slate-300 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
      >
        <span className="truncate">
          {selectedLabels.length > 0 ? selectedLabels.join(', ') : placeholder}
        </span>
        <div className="flex items-center gap-1">
          {value.length > 0 && (
            <span
              onClick={(e) => {
                e.stopPropagation()
                clear()
              }}
              className="rounded-full p-0.5 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <X className="h-3.5 w-3.5 text-slate-400" />
            </span>
          )}
          <ChevronDown className={`h-4 w-4 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
        </div>
      </button>

      {open && (
        <div className="absolute z-10 mt-1 w-full rounded-xl border border-slate-200 bg-white p-1 shadow-lg dark:border-slate-700 dark:bg-slate-900">
          {options.map((option) => {
            const isSelected = value.includes(option.value)
            return (
              <div
                key={option.value}
                onClick={() => toggle(option.value)}
                className={`flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors ${
                  isSelected
                    ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/30 dark:text-indigo-300'
                    : 'text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-slate-800'
                }`}
              >
                {option.label}
                {isSelected && <Check className="h-4 w-4" />}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

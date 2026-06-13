import { useEffect, useRef } from 'react'

/**
 * Poll a callback at a fixed interval while the document is visible.
 * Polling pauses when the tab is hidden to avoid unnecessary requests.
 */
export function usePolling(
  callback: () => void | Promise<void>,
  intervalMs: number,
  enabled = true
) {
  const savedCallback = useRef(callback)

  useEffect(() => {
    savedCallback.current = callback
  }, [callback])

  useEffect(() => {
    if (!enabled || intervalMs <= 0) return

    let timerId: number | undefined

    const tick = () => {
      if (document.visibilityState === 'hidden') return
      void savedCallback.current()
    }

    timerId = window.setInterval(tick, intervalMs)

    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        void savedCallback.current()
      }
    }

    document.addEventListener('visibilitychange', handleVisibility)

    return () => {
      if (timerId !== undefined) window.clearInterval(timerId)
      document.removeEventListener('visibilitychange', handleVisibility)
    }
  }, [intervalMs, enabled])
}

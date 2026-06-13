import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import { I18nProvider } from './i18n/I18nContext'
import { ToastProvider } from './context/ToastProvider'

vi.mock('./api/client', () => ({
  getStats: vi.fn().mockResolvedValue({
    subscriptions: { total: 1, ongoing: 1, completed: 0 },
    episodes: { pending: 2, completed: 0, failed: 0 },
  }),
  getToolsHealth: vi.fn().mockResolvedValue({
    anilist: { healthy: true, detail: 'ok' },
  }),
  listSubscriptions: vi.fn().mockResolvedValue([]),
  listRSSSources: vi.fn().mockResolvedValue([]),
  listEpisodes: vi.fn().mockResolvedValue([]),
  discoverySeason: vi.fn().mockResolvedValue([]),
  listLogs: vi.fn().mockResolvedValue([]),
}))

function renderWithI18n(ui: React.ReactNode) {
  return render(
    <I18nProvider>
      <ToastProvider>{ui}</ToastProvider>
    </I18nProvider>
  )
}

describe('App routing', () => {
  it('renders dashboard by default', async () => {
    renderWithI18n(<App />)
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
  })

  it('renders navigation links', async () => {
    renderWithI18n(<App />)
    expect(await screen.findAllByText('Subscriptions')).toHaveLength(2)
    expect(await screen.findAllByText('Episodes')).toHaveLength(2)
    expect(await screen.findAllByText('Discovery')).toHaveLength(2)
    expect(await screen.findAllByText('RSS Sources')).toHaveLength(2)
    expect(await screen.findAllByText('Logs')).toHaveLength(2)
  })
})

import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'

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

describe('App routing', () => {
  it('renders dashboard by default', async () => {
    render(<App />)
    expect(await screen.findByText('Dashboard')).toBeInTheDocument()
  })

  it('renders navigation links', () => {
    render(<App />)
    expect(screen.getByText('Subscriptions')).toBeInTheDocument()
    expect(screen.getByText('Episodes')).toBeInTheDocument()
    expect(screen.getByText('Discovery')).toBeInTheDocument()
    expect(screen.getByText('RSS Sources')).toBeInTheDocument()
    expect(screen.getByText('Logs')).toBeInTheDocument()
  })
})

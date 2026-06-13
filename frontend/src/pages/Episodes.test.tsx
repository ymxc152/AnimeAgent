import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { Episodes } from './Episodes'
import { I18nProvider } from '../i18n/I18nContext'
import { ToastProvider } from '../context/ToastProvider'

vi.mock('../api/client', () => ({
  listEpisodes: vi.fn().mockResolvedValue([]),
  listSubscriptions: vi.fn().mockResolvedValue([]),
  getEpisodeDetail: vi.fn().mockResolvedValue({}),
  retryEpisode: vi.fn().mockResolvedValue({}),
  submitHumanInput: vi.fn().mockResolvedValue({}),
}))

function renderEpisodes(initialEntries: string[]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <I18nProvider>
        <ToastProvider>
          <Episodes />
        </ToastProvider>
      </I18nProvider>
    </MemoryRouter>
  )
}

describe('Episodes', () => {
  it('reads status filter from URL', async () => {
    renderEpisodes(['/?status=failed'])
    // The MultiSelect should display the translated "failed" label
    expect(await screen.findByText(/Download Failed/i)).toBeInTheDocument()
  })
})

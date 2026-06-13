import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { RSSSources } from './RSSSources'
import { I18nProvider } from '../i18n/I18nContext'
import { ToastProvider } from '../context/ToastProvider'

vi.mock('../api/client', () => ({
  listRSSSources: vi.fn().mockResolvedValue([]),
  createRSSSource: vi.fn().mockResolvedValue({}),
  updateRSSSource: vi.fn().mockResolvedValue({}),
  deleteRSSSource: vi.fn().mockResolvedValue(undefined),
}))

function renderRssSources() {
  return render(
    <I18nProvider>
      <ToastProvider>
        <RSSSources />
      </ToastProvider>
    </I18nProvider>
  )
}

describe('RSSSources', () => {
  it('renders header and add button', async () => {
    renderRssSources()
    expect(await screen.findByRole('heading', { name: /RSS Sources/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Add/i })).toBeInTheDocument()
  })

  it('opens add source modal', async () => {
    renderRssSources()
    fireEvent.click(await screen.findByRole('button', { name: /Add/i }))
    expect(await screen.findByPlaceholderText(/e\.g\. Nyaa 1080p/i)).toBeInTheDocument()
  })
})

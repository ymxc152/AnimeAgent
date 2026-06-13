import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Discovery } from './Discovery'
import { I18nProvider } from '../i18n/I18nContext'
import { ToastProvider } from '../context/ToastProvider'

vi.mock('../api/client', () => ({
  discoverySeason: vi.fn().mockResolvedValue([]),
  listSubscriptions: vi.fn().mockResolvedValue([]),
  discoverySubscribe: vi.fn().mockResolvedValue({}),
  listAutoSubscribeRules: vi.fn().mockResolvedValue([]),
  createAutoSubscribeRule: vi.fn().mockResolvedValue({}),
  updateAutoSubscribeRule: vi.fn().mockResolvedValue({}),
  deleteAutoSubscribeRule: vi.fn().mockResolvedValue(undefined),
}))

function renderDiscovery() {
  return render(
    <I18nProvider>
      <ToastProvider>
        <Discovery />
      </ToastProvider>
    </I18nProvider>
  )
}

describe('Discovery', () => {
  it('renders search input and rules button', async () => {
    renderDiscovery()
    expect(await screen.findByPlaceholderText(/Search Chinese/i)).toBeInTheDocument()
    expect(screen.getByText(/Auto-subscribe Rules/i)).toBeInTheDocument()
  })

  it('opens the auto-subscribe rules form', async () => {
    renderDiscovery()
    fireEvent.click(screen.getByText(/Auto-subscribe Rules/i))
    expect(await screen.findByPlaceholderText(/Rule Name/i)).toBeInTheDocument()
  })
})

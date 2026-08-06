import { describe, expect, it } from 'vitest'
import { sanitizeTelemetryEvent } from './telemetry'

describe('sanitizeTelemetryEvent', () => {
  it('removes authentication codes, query parameters and fragments', () => {
    expect(sanitizeTelemetryEvent({
      type: 'pageview' as const,
      url: 'https://artha.test/?code=private-code#access_token=private-token'
    })).toEqual({
      type: 'pageview',
      url: 'https://artha.test/'
    })
  })

  it('preserves the route needed for aggregate performance reporting', () => {
    expect(sanitizeTelemetryEvent({
      type: 'vital' as const,
      url: 'https://artha.test/assistant?conversation=private'
    })).toEqual({
      type: 'vital',
      url: 'https://artha.test/assistant'
    })
  })

  it('drops malformed event URLs', () => {
    expect(sanitizeTelemetryEvent({ type: 'pageview' as const, url: 'http://[' })).toBeNull()
  })
})

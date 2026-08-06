export function sanitizeTelemetryEvent<T extends { url: string }>(event: T): T | null {
  try {
    const url = new URL(event.url, window.location.origin)
    url.search = ''
    url.hash = ''
    return { ...event, url: url.toString() }
  } catch {
    return null
  }
}

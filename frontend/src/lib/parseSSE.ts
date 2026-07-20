export interface SSEEvent {
  event: string
  data: any
}

export async function* parseSSE(response: Response): AsyncGenerator<SSEEvent> {
  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let idx: number
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)

      const lines = frame.split('\n')
      const event = lines.find(l => l.startsWith('event: '))?.slice(7) || 'message'
      const dataLine = lines.find(l => l.startsWith('data: '))?.slice(6) || '{}'
      try {
        yield { event, data: JSON.parse(dataLine) }
      } catch {
        yield { event, data: { raw: dataLine } }
      }
    }
  }
}

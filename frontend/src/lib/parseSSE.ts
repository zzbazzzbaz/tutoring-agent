export interface SSEEvent {
  event: string
  data: any
}

/**
 * 解析 SSE 流。后端帧格式：event: <name>\ndata: <json>\n\n
 */
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

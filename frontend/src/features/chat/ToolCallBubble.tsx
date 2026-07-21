import { Search } from 'lucide-react'
import type { ChatEvent, ToolEventData } from '@/types/message'

export default function ToolCallBubble({ message }: { message: ChatEvent }) {
  const data = message.data as ToolEventData
  if (data?.tool_name === 'search_knowledge') {
    const query = (data.tool_input as Record<string, unknown>)?.query as string ?? ''
    return (
      <div className="flex justify-center">
        <div className="flex items-center gap-1.5 rounded-lg border bg-muted/50 px-3 py-1.5 text-xs text-muted-foreground">
          <Search className="size-3" />
          <span>搜索知识库: {query}</span>
        </div>
      </div>
    )
  }
  return null
}

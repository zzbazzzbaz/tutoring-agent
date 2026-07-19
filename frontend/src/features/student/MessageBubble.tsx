import { useState } from 'react'
import { toast } from 'sonner'
import MarkdownRenderer from '@/features/shared/MarkdownRenderer'
import { cn } from '@/lib/cn'
import { formatRelativeTime } from '@/lib/formatDate'
import { Copy } from 'lucide-react'

interface Props {
  role: 'user' | 'agent'
  content: string
  createdAt: string
  streaming?: boolean
}

export default function MessageBubble({ role, content, createdAt, streaming }: Props) {
  const [copied, setCopied] = useState(false)
  const isUser = role === 'user'

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content)
    setCopied(true)
    toast.success('已复制')
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className={cn('flex group', isUser ? 'justify-end' : 'justify-start')}>
      <div className={cn('max-w-[85%] space-y-1', isUser && 'items-end')}>
        <div className={cn('text-xs text-muted-foreground', isUser && 'text-right')}>
          {isUser ? '我' : 'Agent'} · {formatRelativeTime(createdAt)}
        </div>
        <div
          className={cn(
            'relative rounded-lg p-3',
            isUser ? 'bg-primary text-primary-foreground' : 'bg-muted',
          )}
        >
          {isUser ? (
            <div className="whitespace-pre-wrap break-words">{content}</div>
          ) : (
            <MarkdownRenderer content={content} />
          )}
          {streaming && <span className="ml-0.5 animate-pulse">▋</span>}
          {!streaming && (
            <button
              onClick={handleCopy}
              className="absolute right-1 top-1 opacity-0 transition-opacity group-hover:opacity-100"
              title="复制"
            >
              <Copy className="h-3.5 w-3.5" />
            </button>
          )}
          {copied && (
            <span className="absolute -bottom-5 right-0 text-xs text-muted-foreground">
              已复制
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

import { useState } from 'react'
import { Check, Copy, User } from 'lucide-react'
import { cn } from '@/lib/cn'
import MarkdownRenderer from '@/features/shared/MarkdownRenderer'
import type { MessageOut } from '@/types/message'

export default function MessageBubble({ message }: { message: MessageOut }) {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className={cn('flex gap-3 group', isUser && 'flex-row-reverse')}>
      <div className={cn(
        'flex size-8 shrink-0 items-center justify-center rounded-full',
        isUser ? 'bg-primary text-primary-foreground' : 'bg-muted'
      )}>
        <User className="size-4" />
      </div>
      <div className={cn('flex-1', isUser && 'flex flex-col items-end')}>
        <div
          className={cn(
            'inline-block max-w-[85%] rounded-lg px-3 py-2',
            isUser ? 'bg-primary text-primary-foreground' : 'bg-muted'
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap text-sm">{message.content}</p>
          ) : (
            <div className="text-sm">
              <MarkdownRenderer content={message.content} />
            </div>
          )}
        </div>
        {!isUser && (
          <button
            onClick={handleCopy}
            className="mt-1 flex items-center gap-1 text-xs text-muted-foreground opacity-0 group-hover:opacity-100"
          >
            {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        )}
      </div>
    </div>
  )
}

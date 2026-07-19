import { useState, useRef, useEffect } from 'react'
import { useChatStore } from '@/stores/chat'
import { Button } from '@/components/ui/button'
import { Send } from 'lucide-react'

const MAX_CHARS = 2000

export default function ChatInput() {
  const [content, setContent] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const streamStatus = useChatStore(s => s.streamStatus)
  const sendMessage = useChatStore(s => s.sendMessage)

  const disabled = streamStatus === 'streaming' || streamStatus === 'quiz_interrupted'
  const placeholder =
    streamStatus === 'quiz_interrupted'
      ? '请先答题或跳过当前题目'
      : streamStatus === 'streaming'
        ? '生成中...'
        : '输入消息，Enter 发送'

  const handleSubmit = async () => {
    const trimmed = content.trim()
    if (!trimmed || disabled) return
    setContent('')
    await sendMessage(trimmed)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px'
  }, [content])

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={content}
          onChange={e => setContent(e.target.value.slice(0, MAX_CHARS))}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none rounded-md border bg-background p-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
        />
        <Button onClick={handleSubmit} disabled={disabled || !content.trim()} size="icon">
          <Send className="h-4 w-4" />
        </Button>
      </div>
      <div className="mt-1 text-right text-xs text-muted-foreground">
        {content.length}/{MAX_CHARS}
        {streamStatus === 'streaming' && ' · 生成中...'}
      </div>
    </div>
  )
}

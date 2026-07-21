import { useState, useRef, useEffect } from 'react'
import { Send } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

interface ChatInputProps {
  onSend: (content: string) => void
  disabled: boolean
  placeholder?: string
  hint?: string
}

export default function ChatInput({ onSend, disabled, placeholder, hint }: ChatInputProps) {
  const { t } = useTranslation()
  const [value, setValue] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (ref.current) {
      ref.current.style.height = 'auto'
      ref.current.style.height = `${ref.current.scrollHeight}px`
    }
  }, [value])

  const handleSend = () => {
    if (!value.trim() || disabled) return
    onSend(value.trim())
    setValue('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="border-t p-3">
      {hint && (
        <p className="mb-1.5 text-xs text-muted-foreground">{hint}</p>
      )}
      <div className="flex items-end gap-2">
        <Textarea
          ref={ref}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder || t('chat.inputPlaceholder')}
          disabled={disabled}
          className="min-h-[40px] max-h-32 resize-none"
          rows={1}
        />
        <Button onClick={handleSend} disabled={disabled || !value.trim()} size="icon">
          <Send className="size-4" />
        </Button>
      </div>
    </div>
  )
}

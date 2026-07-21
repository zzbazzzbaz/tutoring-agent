import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import MarkdownRenderer from '@/features/shared/MarkdownRenderer'
import type { ChatEvent, QuizEventData } from '@/types/message'

interface QuizCardProps {
  quiz: ChatEvent
  status: 'pending' | 'answered' | 'skipped'
  userAnswer?: string | null
  onSubmit: (answer: string) => void
  onSkip: () => void
}

export default function QuizCard({ quiz, status, userAnswer, onSubmit, onSkip }: QuizCardProps) {
  const { t } = useTranslation()
  const data = quiz.data as QuizEventData
  const qType = data.q_type
  const options = data.options ?? []
  const [selected, setSelected] = useState<string[]>([])
  const [shortAnswer, setShortAnswer] = useState('')
  const locked = status !== 'pending'

  const handleSubmit = () => {
    if (qType === 'single') {
      if (selected.length === 1) onSubmit(selected[0])
    } else if (qType === 'multi') {
      if (selected.length > 0) onSubmit(selected.join(','))
    } else {
      if (shortAnswer.trim()) onSubmit(shortAnswer.trim())
    }
  }

  const toggleOption = (idx: string) => {
    setSelected(prev =>
      prev.includes(idx)
        ? prev.filter(i => i !== idx)
        : qType === 'single'
          ? [idx]
          : [...prev, idx]
    )
  }

  const questionId = quiz.id
  const optionIdx = (i: number) => String.fromCharCode(65 + i)

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-3 flex items-center gap-2">
        <Badge variant="secondary">
          {qType === 'single' ? t('chat.quiz.single') : qType === 'multi' ? t('chat.quiz.multi') : t('chat.quiz.short')}
        </Badge>
        <span className="text-xs text-muted-foreground">{t('chat.quiz.topic')}: {data.topic}</span>
        {locked && (
          <Badge variant="outline" className="ml-auto">
            {status === 'skipped' ? t('chat.quiz.skip') : t('chat.quiz.submit')}
          </Badge>
        )}
      </div>

      <div className="mb-4 text-sm">
        <MarkdownRenderer content={data.stem} />
      </div>

      {qType === 'single' && (
        <RadioGroup
          value={selected[0] ?? ''}
          onValueChange={(v: string) => setSelected([v])}
          disabled={locked}
        >
          {options.map((opt: string, i: number) => (
            <div key={i} className="flex items-center gap-2">
              <RadioGroupItem value={optionIdx(i)} id={`q-${questionId}-${i}`} />
              <Label htmlFor={`q-${questionId}-${i}`}>{opt}</Label>
            </div>
          ))}
        </RadioGroup>
      )}

      {qType === 'multi' && (
        <div className="space-y-2">
          {options.map((opt: string, i: number) => (
            <div key={i} className="flex items-center gap-2">
              <Checkbox
                checked={selected.includes(optionIdx(i))}
                onCheckedChange={() => toggleOption(optionIdx(i))}
                disabled={locked}
              />
              <Label>{opt}</Label>
            </div>
          ))}
        </div>
      )}

      {qType === 'short' && (
        <Input
          value={shortAnswer}
          onChange={e => setShortAnswer(e.target.value)}
          disabled={locked}
          placeholder={t('chat.quiz.short')}
        />
      )}

      {locked && userAnswer && (
        <div className="mt-4 border-t pt-3 text-sm">
          <span className="font-medium">{t('chat.quiz.yourAnswer')}:</span> {userAnswer}
        </div>
      )}

      {!locked && (
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={onSkip}>
            {t('chat.quiz.skip')}
          </Button>
          <Button onClick={handleSubmit}>
            {t('chat.quiz.submit')}
          </Button>
        </div>
      )}
    </div>
  )
}

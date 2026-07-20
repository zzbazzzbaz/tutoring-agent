import { useState } from 'react'
import type { QuestionOut, QuizInterruptData } from '@/types/question'
import { useChatStore } from '@/stores/chat'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Checkbox } from '@/components/ui/checkbox'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/cn'

interface Props {
  question?: QuestionOut
  pending?: QuizInterruptData
}

export default function QuizCard({ question, pending }: Props) {
  const streamStatus = useChatStore(s => s.streamStatus)
  const submitQuiz = useChatStore(s => s.submitQuiz)

  const data = pending || question
  const isPending = !!pending && streamStatus === 'quiz_interrupted'
  const isLocked = !isPending || streamStatus !== 'quiz_interrupted'

  const qType = data?.q_type
  const options = data?.options
  const stem = data?.stem

  const [selected, setSelected] = useState<string>('')
  const [multiSelected, setMultiSelected] = useState<string[]>([])
  const [shortAnswer, setShortAnswer] = useState('')

  if (!data) return null

  const handleMultiChange = (v: string) => {
    setMultiSelected(prev =>
      prev.includes(v) ? prev.filter(x => x !== v) : [...prev, v],
    )
  }

  const handleSubmit = async () => {
    let answer = ''
    if (qType === 'single') answer = selected
    else if (qType === 'multi') answer = multiSelected.sort().join(',')
    else if (qType === 'short') answer = shortAnswer
    await submitQuiz('answer', answer)
  }

  const handleSkip = async () => {
    await submitQuiz('skip')
  }

  return (
    <div className="rounded-lg border p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">
            {qType === 'single' ? '单选题' : qType === 'multi' ? '多选题' : '简答题'}
          </span>
          {(question?.topic || pending?.topic) && (
            <Badge variant="outline" className="text-xs">
              {question?.topic || pending?.topic}
            </Badge>
          )}
        </div>
        {isPending && <Badge variant="outline">作答中</Badge>}
      </div>

      <div className="mb-3 text-sm">{stem}</div>

      {options && qType === 'single' && (
        <RadioGroup
          value={question?.user_answer || selected}
          onValueChange={setSelected}
          disabled={isLocked}
          className="space-y-2"
        >
          {options.map((opt, i) => {
            const letter = String.fromCharCode(65 + i)
            const isUserAnswer = question?.user_answer === opt
            const isCorrectAnswer = question?.answer?.includes(opt)
            return (
              <div
                key={i}
                className={cn(
                  'flex items-center gap-2 rounded-md p-2',
                  isLocked && isUserAnswer && 'bg-yellow-100 dark:bg-yellow-900/30',
                  isLocked && isCorrectAnswer && 'bg-green-100 dark:bg-green-900/30',
                )}
              >
                <RadioGroupItem value={opt} id={`q-${i}`} disabled={isLocked} />
                <label htmlFor={`q-${i}`} className="text-sm">
                  <span className="font-medium">{letter}.</span> {opt}
                </label>
              </div>
            )
          })}
        </RadioGroup>
      )}

      {options && qType === 'multi' && (
        <div className="space-y-2">
          {options.map((opt, i) => {
            const letter = String.fromCharCode(65 + i)
            const userAns = question?.user_answer?.split(',') || []
            const isUserAnswer = userAns.includes(opt)
            const isCorrectAnswer = question?.answer?.split(',').includes(opt)
            const checked = isLocked ? isUserAnswer : multiSelected.includes(opt)
            return (
              <div
                key={i}
                className={cn(
                  'flex items-center gap-2 rounded-md p-2',
                  isLocked && isUserAnswer && 'bg-yellow-100 dark:bg-yellow-900/30',
                  isLocked && isCorrectAnswer && 'bg-green-100 dark:bg-green-900/30',
                )}
              >
                <Checkbox
                  checked={checked}
                  onCheckedChange={() => handleMultiChange(opt)}
                  disabled={isLocked}
                />
                <span className="text-sm">
                  <span className="font-medium">{letter}.</span> {opt}
                </span>
              </div>
            )
          })}
        </div>
      )}

      {qType === 'short' && (
        <Textarea
          value={question?.user_answer || shortAnswer}
          onChange={e => setShortAnswer(e.target.value)}
          disabled={isLocked}
          placeholder="输入你的答案..."
          className="min-h-24"
        />
      )}

      {isLocked && question && question.status !== 'pending' && (
        <div className="mt-3 space-y-1 border-t pt-3 text-sm">
          {question.user_answer && (
            <div>
              <span className="text-muted-foreground">你的答案：</span>
              {question.user_answer}
            </div>
          )}
          <div>
            <span className="text-muted-foreground">正确答案：</span>
            {question.answer}
          </div>
          {question.analysis && (
            <div>
              <span className="text-muted-foreground">解析：</span>
              {question.analysis}
            </div>
          )}
        </div>
      )}

      {isPending && !isLocked && (
        <div className="mt-3 flex justify-between">
          <Button variant="ghost" size="sm" onClick={handleSkip}>
            跳过
          </Button>
          <Button
            size="sm"
            onClick={handleSubmit}
            disabled={
              (qType === 'single' && !selected) ||
              (qType === 'multi' && multiSelected.length === 0) ||
              (qType === 'short' && !shortAnswer.trim())
            }
          >
            提交
          </Button>
        </div>
      )}
    </div>
  )
}

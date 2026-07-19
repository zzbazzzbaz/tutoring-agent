import type { QuestionOut } from '@/types/question'

interface Props {
  question: QuestionOut
  locked?: boolean
}

export default function QuizCard({ question }: Props) {
  return (
    <div className="rounded-lg border p-3">
      <div className="text-sm text-muted-foreground">题目卡片（待 Task 9 实现）</div>
      <div className="mt-2 text-sm">{question.stem}</div>
    </div>
  )
}

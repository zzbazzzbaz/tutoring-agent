interface Props {
  role: 'user' | 'agent'
  content: string
  createdAt: string
  streaming?: boolean
}

export default function MessageBubble({ role, content, streaming }: Props) {
  return (
    <div className={`flex ${role === 'user' ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-lg p-3 ${
          role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'
        }`}
      >
        <div className="whitespace-pre-wrap">
          {content}
          {streaming && '▋'}
        </div>
      </div>
    </div>
  )
}

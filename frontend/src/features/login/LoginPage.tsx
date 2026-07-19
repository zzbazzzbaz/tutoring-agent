import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore, type Role } from '@/stores/auth'
import { mockLogin } from '@/api/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'

export default function LoginPage() {
  const navigate = useNavigate()
  const login = useAuthStore(s => s.login)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('student')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username.trim()) return
    setLoading(true)
    try {
      await mockLogin(username, password, role)
      login(username.trim(), role)
      navigate(role === 'teacher' ? '/teacher/knowledge-base' : '/student/sessions')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/50">
      <div className="w-full max-w-sm rounded-lg border bg-card p-6 shadow-sm">
        <h1 className="mb-6 text-center text-2xl font-bold">教学 Agent 登录</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="username">用户名</Label>
            <Input
              id="username"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="任意用户名"
              autoComplete="username"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">密码</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="任意密码"
              autoComplete="current-password"
            />
          </div>
          <div className="space-y-2">
            <Label>角色</Label>
            <RadioGroup
              value={role}
              onValueChange={v => setRole(v as Role)}
              className="flex gap-6"
            >
              <div className="flex items-center gap-2">
                <RadioGroupItem value="student" id="r-student" />
                <Label htmlFor="r-student">学生</Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="teacher" id="r-teacher" />
                <Label htmlFor="r-teacher">教师</Label>
              </div>
            </RadioGroup>
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? '登录中...' : '登录'}
          </Button>
        </form>
      </div>
    </div>
  )
}

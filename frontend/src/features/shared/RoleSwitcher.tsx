import { useNavigate } from 'react-router-dom'
import { useAuthStore, type Role } from '@/stores/auth'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

export default function RoleSwitcher() {
  const navigate = useNavigate()
  const role = useAuthStore(s => s.role)
  const username = useAuthStore(s => s.username)
  const login = useAuthStore(s => s.login)
  const isAuthenticated = useAuthStore(s => s.isAuthenticated)

  if (!import.meta.env.DEV || !isAuthenticated) return null

  const handleChange = (newRole: Role) => {
    if (!username) return
    login(username, newRole)
    navigate(newRole === 'teacher' ? '/teacher/knowledge-base' : '/student/sessions')
  }

  return (
    <Select value={role || 'student'} onValueChange={v => handleChange(v as Role)}>
      <SelectTrigger className="w-24">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="student">学生</SelectItem>
        <SelectItem value="teacher">教师</SelectItem>
      </SelectContent>
    </Select>
  )
}

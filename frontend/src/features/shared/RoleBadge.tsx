import { useAuthStore } from '@/stores/auth'
import { Badge } from '@/components/ui/badge'

export default function RoleBadge() {
  const role = useAuthStore(s => s.role)
  if (!role) return null
  return (
    <Badge variant={role === 'teacher' ? 'default' : 'secondary'}>
      {role === 'teacher' ? '教师' : '学生'}
    </Badge>
  )
}

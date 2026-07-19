import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import RoleBadge from '@/features/shared/RoleBadge'
import RoleSwitcher from '@/features/shared/RoleSwitcher'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

const TABS = [
  { value: '/teacher/knowledge-base', label: '知识库' },
  { value: '/teacher/knowledge-graph', label: '知识图谱' },
  { value: '/teacher/projects', label: '项目配置' },
]

export default function TeacherLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const username = useAuthStore(s => s.username)
  const logout = useAuthStore(s => s.logout)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen w-screen flex-col">
      <header className="flex h-12 items-center justify-between border-b px-4">
        <div className="flex items-center gap-3">
          <span className="font-bold">教学 Agent</span>
          <RoleBadge />
          <RoleSwitcher />
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>{username}</span>
          <Button variant="ghost" size="sm" onClick={handleLogout}>
            退出
          </Button>
        </div>
      </header>
      <div className="border-b px-4">
        <Tabs value={location.pathname}>
          <TabsList>
            {TABS.map(t => (
              <TabsTrigger key={t.value} value={t.value} onClick={() => navigate(t.value)}>
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}

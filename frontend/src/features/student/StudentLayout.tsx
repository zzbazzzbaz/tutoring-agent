import { Outlet, useNavigate } from 'react-router-dom'
import SessionList from './SessionList'
import RoleBadge from '@/features/shared/RoleBadge'
import RoleSwitcher from '@/features/shared/RoleSwitcher'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'

export default function StudentLayout() {
  const navigate = useNavigate()
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
          <Button variant="ghost" size="sm" onClick={handleLogout}>退出</Button>
        </div>
      </header>
      <div className="flex flex-1 overflow-hidden">
        <aside className="w-72 shrink-0 border-r">
          <SessionList />
        </aside>
        <main className="flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

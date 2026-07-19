import { HashRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { Toaster } from 'sonner'
import { useAuthStore } from '@/stores/auth'
import LoginPage from '@/features/login/LoginPage'
import StudentLayout from '@/features/student/StudentLayout'
import SessionDetail from '@/features/student/SessionDetail'

function RequireAuth() {
  const isAuthenticated = useAuthStore(s => s.isAuthenticated)
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <Outlet />
}

function RoleRoute({ role }: { role: 'student' | 'teacher' }) {
  const currentRole = useAuthStore(s => s.role)
  if (currentRole !== role) {
    return (
      <Navigate
        to={currentRole === 'teacher' ? '/teacher/knowledge-base' : '/student/sessions'}
        replace
      />
    )
  }
  return <Outlet />
}

function TeacherPlaceholder() {
  return <div className="p-8 text-xl">教师端（待实现）</div>
}

function NotFound() {
  return <div className="p-8 text-xl">404</div>
}

export default function AppRouter() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route element={<RoleRoute role="student" />}>
            <Route path="/student" element={<StudentLayout />}>
              <Route index element={<Navigate to="/student/sessions" replace />} />
              <Route
                path="sessions"
                element={<div className="p-8 text-muted-foreground">请从左侧选择一个会话</div>}
              />
              <Route path="sessions/:id" element={<SessionDetail />} />
            </Route>
          </Route>
          <Route element={<RoleRoute role="teacher" />}>
            <Route path="/teacher" element={<Navigate to="/teacher/knowledge-base" replace />} />
            <Route path="/teacher/knowledge-base" element={<TeacherPlaceholder />} />
            <Route path="/teacher/knowledge-graph" element={<TeacherPlaceholder />} />
            <Route path="/teacher/projects" element={<TeacherPlaceholder />} />
            <Route path="/teacher/projects/new" element={<TeacherPlaceholder />} />
            <Route path="/teacher/projects/:id/edit" element={<TeacherPlaceholder />} />
          </Route>
        </Route>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
      <Toaster position="bottom-center" closeButton richColors />
    </HashRouter>
  )
}

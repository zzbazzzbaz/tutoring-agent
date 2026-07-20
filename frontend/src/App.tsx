import { useTranslation } from 'react-i18next'
import { Toaster } from 'sonner'
import { GraduationCap, MessageSquare, Users, FolderOpen } from 'lucide-react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { TooltipProvider } from '@/components/ui/tooltip'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import { useTheme } from '@/hooks/useTheme'
import SettingsMenu from '@/features/shared/SettingsMenu'
import ChatTab from '@/features/chat/ChatTab'
import StudentsTab from '@/features/students/StudentsTab'
import ProjectsTab from '@/features/projects/ProjectsTab'

export default function App() {
  const { t } = useTranslation()
  const user = useAuthStore(s => s.user)
  const activeTab = useSettingsStore(s => s.activeTab)
  const setActiveTab = useSettingsStore(s => s.setActiveTab)
  useTheme()

  const isTeacher = user?.role === 'teacher'

  return (
    <TooltipProvider>
      <div className="flex h-screen flex-col">
        <header className="flex items-center justify-between border-b px-4 py-2">
          <div className="flex items-center gap-2">
            <GraduationCap className="size-6" />
            <span className="font-bold">{t('common.appName')}</span>
          </div>
          <SettingsMenu />
        </header>
        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 overflow-hidden">
          <TabsList className="mx-4 mt-2">
            <TabsTrigger value="chat" className="gap-1">
              <MessageSquare className="size-4" />
              {t('chat.title')}
            </TabsTrigger>
            {isTeacher && (
              <TabsTrigger value="students" className="gap-1">
                <Users className="size-4" />
                {t('students.title')}
              </TabsTrigger>
            )}
            <TabsTrigger value="projects" className="gap-1">
              <FolderOpen className="size-4" />
              {t('projects.title')}
            </TabsTrigger>
          </TabsList>
          <TabsContent value="chat" className="mt-0 h-[calc(100vh-7rem)]" style={{ display: activeTab !== 'chat' ? 'none' : undefined }}>
            <ChatTab />
          </TabsContent>
          {isTeacher && (
            <TabsContent value="students" className="mt-0 h-[calc(100vh-7rem)]" style={{ display: activeTab !== 'students' ? 'none' : undefined }}>
              <StudentsTab />
            </TabsContent>
          )}
          <TabsContent value="projects" className="mt-0 h-[calc(100vh-7rem)]" style={{ display: activeTab !== 'projects' ? 'none' : undefined }}>
            <ProjectsTab />
          </TabsContent>
        </Tabs>
      </div>
      <Toaster richColors position="top-right" />
    </TooltipProvider>
  )
}

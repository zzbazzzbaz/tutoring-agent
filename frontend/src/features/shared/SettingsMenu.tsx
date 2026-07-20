import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Settings, LogOut, Moon, Sun, Monitor, KeyRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import { useChatStore } from '@/stores/chat'
import { authApi } from '@/api/auth'

export default function SettingsMenu() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const logout = useAuthStore(s => s.logout)
  const user = useAuthStore(s => s.user)
  const theme = useSettingsStore(s => s.theme)
  const setTheme = useSettingsStore(s => s.setTheme)
  const language = useSettingsStore(s => s.language)
  const setLanguage = useSettingsStore(s => s.setLanguage)
  const clearCurrent = useChatStore(s => s.clearCurrent)

  const [pwDialogOpen, setPwDialogOpen] = useState(false)
  const [oldPw, setOldPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [changing, setChanging] = useState(false)

  const handleLogout = async () => {
    try {
      await authApi.logout()
    } catch {
      // ignore
    }
    logout()
    clearCurrent()
    navigate('/login')
  }

  const handleChangePassword = async () => {
    setChanging(true)
    try {
      await authApi.changePassword(oldPw, newPw)
      setPwDialogOpen(false)
      setOldPw('')
      setNewPw('')
    } catch {
      // toast handled by interceptor
    } finally {
      setChanging(false)
    }
  }

  const themeIcons = {
    light: <Sun className="size-4" />,
    dark: <Moon className="size-4" />,
    system: <Monitor className="size-4" />,
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon">
            <Settings className="size-5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <div className="px-2 py-1.5 text-sm font-medium">
            {user?.name} ({user?.username})
          </div>
          <DropdownMenuSeparator />
          <div className="px-2 py-1.5">
            <Label className="text-xs text-muted-foreground">{t('settings.theme')}</Label>
            <div className="mt-1 flex gap-1">
              {(['light', 'dark', 'system'] as const).map(th => (
                <Button
                  key={th}
                  variant={theme === th ? 'default' : 'outline'}
                  size="sm"
                  className="flex-1"
                  onClick={() => setTheme(th)}
                >
                  {themeIcons[th]}
                </Button>
              ))}
            </div>
          </div>
          <DropdownMenuSeparator />
          <div className="px-2 py-1.5">
            <Label className="text-xs text-muted-foreground">{t('settings.language')}</Label>
            <div className="mt-1 flex gap-1">
              <Button
                variant={language === 'zh' ? 'default' : 'outline'}
                size="sm"
                className="flex-1"
                onClick={() => setLanguage('zh')}
              >
                中文
              </Button>
              <Button
                variant={language === 'en' ? 'default' : 'outline'}
                size="sm"
                className="flex-1"
                onClick={() => setLanguage('en')}
              >
                English
              </Button>
            </div>
          </div>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => setPwDialogOpen(true)}>
            <KeyRound className="mr-2 size-4" />
            {t('settings.changePassword')}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={handleLogout} className="text-destructive">
            <LogOut className="mr-2 size-4" />
            {t('settings.logout')}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={pwDialogOpen} onOpenChange={setPwDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('settings.changePassword')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="old-pw">{t('settings.oldPassword')}</Label>
              <Input
                id="old-pw"
                type="password"
                value={oldPw}
                onChange={e => setOldPw(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-pw">{t('settings.newPassword')}</Label>
              <Input
                id="new-pw"
                type="password"
                value={newPw}
                onChange={e => setNewPw(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPwDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={handleChangePassword} disabled={changing || !oldPw || !newPw}>
              {t('common.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

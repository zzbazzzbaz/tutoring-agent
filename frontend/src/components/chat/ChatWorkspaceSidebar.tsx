"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  FolderOpen,
  GraduationCap,
  Loader2,
  LogOut,
  MoreHorizontal,
  MessageCircle,
  PanelLeftClose,
  Pencil,
  Settings,
  Trash2,
  UserCircle,
} from "lucide-react";
import { useQueryState } from "nuqs";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { useAuth } from "@/components/auth/AuthProvider";
import { ProfileDialog } from "@/components/chat/ProfileDialog";
import { useSessions } from "@/components/chat/SessionProvider";
import { avatarUrl, cn } from "@/lib/utils";
import type { Session, UserRole } from "@/lib/types";
import { toast } from "sonner";

function sessionTitle(session: Session) {
  if (session.title) return session.title;
  if (session.mode === "free") return "自由学习";
  if (session.mode === "case_design") return "案例设计";
  return session.project_name || "案例模式";
}

export function ChatWorkspaceSidebar({
  role,
  onNewSession: _onNewSession,
  onCollapse,
  mobileOpen = false,
  onMobileOpenChange,
}: {
  role: UserRole;
  onNewSession: () => void;
  onCollapse?: () => void;
  mobileOpen?: boolean;
  onMobileOpenChange?: (open: boolean) => void;
}) {
  const { user, logout } = useAuth();
  const {
    sessions,
    sessionsLoading,
    refreshSessions,
    updateSession,
    deleteSession,
  } = useSessions();
  const [sessionId, setSessionId] = useQueryState("session");
  const [profileOpen, setProfileOpen] = useState(false);
  const [confirmDeleteSession, setConfirmDeleteSession] = useState<Session | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);

  const manageHref =
    role === "teacher"
      ? "/teacher/manage/projects"
      : "/student/manage/projects";
  const manageLabel = role === "teacher" ? "管理中心" : "案例中心";

  async function handleRenameSession(session: Session) {
    const nextTitle = prompt("请输入新的会话标题", sessionTitle(session));
    if (nextTitle === null) return;
    try {
      await updateSession(session.id, nextTitle.trim() || null);
      toast.success("会话已重命名");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "重命名失败");
    }
  }

  async function handleDeleteSession() {
    if (!confirmDeleteSession) return;
    setDeleting(true);
    try {
      await deleteSession(confirmDeleteSession.id);
      if (sessionId === confirmDeleteSession.id) setSessionId(null);
      toast.success("会话已删除");
      setConfirmDeleteSession(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "删除失败");
    } finally {
      setDeleting(false);
    }
  }

  // 原“新建对话”功能：弹出 NewSessionModal 让用户选择会话类型（由父组件 onNewSession 触发）。
  // 现已被注释（下方 handleNewSession 不再调用 _onNewSession），保留 prop 以便后续恢复：
  //   onClick={() => _onNewSession()}
  // 当前改为与顶部“基础心理学教学 Agent”按钮行为一致：清空 session 参数，回到空白起始页 /chat。
  const handleNewSession = () => {
    setSessionId(null);
    onMobileOpenChange?.(false);
  };

  const content = (
    <div className="flex h-full w-full flex-col bg-[#0b2139]">
      <div className="px-4 pt-4 pb-3">
        <div className="flex items-center justify-between gap-3">
          <button
            className="hover:text-white flex min-w-0 cursor-pointer items-center gap-2 rounded-lg text-left transition-colors"
            onClick={() => {
              setSessionId(null);
              onMobileOpenChange?.(false);
            }}
          >
            <span className="bg-gradient-to-br from-[#2d59df] to-[#2249c4] text-white flex size-8 shrink-0 items-center justify-center rounded-xl shadow-sm shadow-blue-900/30">
              <GraduationCap className="size-4" />
            </span>
            <span className="[font-family:'Songti_SC','STSong','SimSun','Noto_Serif_SC',serif] truncate text-sm font-semibold text-white">
              基础心理学教学Agent
            </span>
          </button>

          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="text-gray-400 hover:text-white size-8 cursor-pointer rounded-lg"
              onClick={() => {
                onCollapse?.();
                onMobileOpenChange?.(false);
              }}
              title="收起侧边栏"
            >
              <PanelLeftClose className="size-4" />
            </Button>
          </div>
        </div>

        <div className="mt-5 space-y-1">
          <button
            className="text-gray-300 flex w-full cursor-pointer items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors hover:bg-white/10"
            onClick={handleNewSession}
          >
            <MessageCircle className="text-gray-400 size-4" />
            新建对话
          </button>
          <button
            className="text-gray-300 flex w-full cursor-pointer items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors hover:bg-white/10"
            onClick={() => setProfileOpen(true)}
          >
            <UserCircle className="text-gray-400 size-4" />
            个人中心
          </button>
          <Button
            asChild
            variant="ghost"
            className="flex h-auto w-full cursor-pointer justify-start gap-3 rounded-xl px-3 py-2 text-sm font-normal text-gray-300 transition-colors hover:bg-white/10 hover:text-white"
          >
            <Link
              href={
                sessionId ? `${manageHref}?session=${sessionId}` : manageHref
              }
              onClick={() => onMobileOpenChange?.(false)}
            >
              {role === "teacher" ? (
                <Settings className="text-gray-400 size-4" />
              ) : (
                <FolderOpen className="text-gray-400 size-4" />
              )}
              {manageLabel}
            </Link>
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-2">
        <p className="text-gray-400 px-3 pt-3 pb-2 text-xs font-medium">
          历史对话
        </p>
        {sessionsLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 8 }).map((_, index) => (
              <Skeleton
                key={index}
                className="h-10 w-full rounded-xl"
              />
            ))}
          </div>
        ) : sessions.length === 0 ? (
          <p className="text-muted-foreground p-3 text-sm">暂无历史对话</p>
        ) : (
          <div className="space-y-1">
            {sessions.map((session) => {
              const active = sessionId === session.id;

              return (
                <div
                  key={session.id}
                  className={cn(
                    "group flex items-center rounded-xl hover:bg-white/5",
                    active && "bg-[#2d59df] text-white font-medium shadow-sm ring-1 ring-[#2d59df]",
                  )}
                >
                  <button
                    className="flex min-w-0 flex-1 cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-left text-sm"
                    onClick={() => {
                      setSessionId(session.id);
                      onMobileOpenChange?.(false);
                    }}
                  >
                    <MessageCircle className="size-4 shrink-0 text-white" />
                    <span className="block min-w-0 truncate text-white">
                      {sessionTitle(session)}
                    </span>
                  </button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="mr-1 size-7 shrink-0 cursor-pointer text-gray-300 opacity-0 group-hover:opacity-100 hover:text-white data-[state=open]:opacity-100"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <MoreHorizontal className="size-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={() => handleRenameSession(session)}
                      >
                        <Pencil className="size-4" />
                        重命名
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive focus:text-destructive"
                        onClick={() => setConfirmDeleteSession(session)}
                      >
                        <Trash2 className="size-4" />
                        删除
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              );
            })}
          </div>
        )}
      </div>
      <div className="border-t border-white/10 px-3 py-3">
        <div className="flex items-center justify-between gap-2">
          <button
            className="hover:text-white flex min-w-0 cursor-pointer items-center gap-2 rounded-xl px-1 py-1 text-left transition-colors"
            onClick={() => setProfileOpen(true)}
          >
            <Avatar className="size-8">
              <AvatarImage
                src={avatarUrl(user?.avatar_url)}
                alt={user?.name}
              />
              <AvatarFallback className="text-xs">
                {user?.name?.charAt(0)}
              </AvatarFallback>
            </Avatar>
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium text-white">
                {user?.name}
              </span>
              <span className="text-gray-400 block truncate text-xs">
                {user?.username}
              </span>
            </span>
          </button>
          <Button
            variant="ghost"
            size="icon"
            onClick={logout}
            className="text-muted-foreground hover:text-destructive size-8 shrink-0 cursor-pointer rounded-lg"
            title="退出登录"
          >
            <LogOut className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <aside className="bg-[#0b2139] backdrop-blur-sm hidden h-screen w-[280px] shrink-0 border-r border-white/10 lg:block">
        {content}
      </aside>
      <Sheet
        open={mobileOpen}
        onOpenChange={onMobileOpenChange}
      >
        <SheetContent
          side="left"
          className="w-[280px] p-0 lg:hidden"
        >
          {content}
        </SheetContent>
      </Sheet>
      <ProfileDialog
        open={profileOpen}
        onOpenChange={setProfileOpen}
      />
      <Dialog
        open={confirmDeleteSession !== null}
        onOpenChange={(open) => {
          if (!open && !deleting) setConfirmDeleteSession(null);
        }}
      >
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>删除会话</DialogTitle>
            <DialogDescription>
              确定删除「{confirmDeleteSession ? sessionTitle(confirmDeleteSession) : ""}」吗？删除后不可恢复。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setConfirmDeleteSession(null)}
              disabled={deleting}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteSession}
              disabled={deleting}
            >
              {deleting ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  删除中...
                </>
              ) : (
                "删除"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

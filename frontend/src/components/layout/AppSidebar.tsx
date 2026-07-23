"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquare, FolderOpen, Users, LogOut } from "lucide-react";
import { useAuth } from "@/components/auth/AuthProvider";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { UserRole } from "@/lib/types";

interface NavItem {
  label: string;
  href: string;
  icon: typeof MessageSquare;
}

const STUDENT_NAV: NavItem[] = [
  { label: "对话", href: "/student/chat", icon: MessageSquare },
  { label: "项目", href: "/student/projects", icon: FolderOpen },
];

const TEACHER_NAV: NavItem[] = [
  { label: "对话", href: "/teacher/chat", icon: MessageSquare },
  { label: "项目", href: "/teacher/projects", icon: FolderOpen },
  { label: "学生", href: "/teacher/students", icon: Users },
];

export function AppSidebar({ role }: { role: UserRole }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const navItems = role === "teacher" ? TEACHER_NAV : STUDENT_NAV;

  return (
    <aside className="flex h-screen w-60 flex-col border-r bg-background">
      <div className="flex h-14 items-center border-b px-4">
        <span className="text-lg font-bold">教学 Agent</span>
      </div>
      <nav className="flex-1 space-y-1 p-2">
        {navItems.map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <item.icon className="size-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t p-3">
        <div className="mb-2 px-2 text-sm">
          <p className="font-medium">{user?.name}</p>
          <p className="text-xs text-muted-foreground">{user?.username}</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={logout}
          className="w-full justify-start"
        >
          <LogOut className="mr-2 size-4" />
          退出登录
        </Button>
      </div>
    </aside>
  );
}

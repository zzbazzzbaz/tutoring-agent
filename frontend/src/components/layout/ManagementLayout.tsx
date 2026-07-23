"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { ArrowLeft, Database, FolderOpen, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { UserRole } from "@/lib/types";

export function ManagementLayout({
  role,
  children,
}: {
  role: UserRole;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const session = searchParams.get("session");
  const chatHref = session
    ? `/${role}/chat?session=${session}`
    : `/${role}/chat`;
  const items =
    role === "teacher"
      ? [
          {
            label: "项目",
            href: "/teacher/manage/projects",
            icon: FolderOpen,
          },
          {
            label: "学生",
            href: "/teacher/manage/students",
            icon: Users,
          },
          {
            label: "知识库",
            href: "/teacher/manage/knowledge",
            icon: Database,
          },
        ]
      : [
          {
            label: "项目",
            href: "/student/manage/projects",
            icon: FolderOpen,
          },
        ];

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      <header className="flex h-14 shrink-0 items-center justify-between border-b px-4">
        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" size="sm">
            <Link href={chatHref}>
              <ArrowLeft className="mr-2 size-4" />
              返回对话
            </Link>
          </Button>
          <h1 className="text-base font-semibold">
            {role === "teacher" ? "管理中心" : "项目中心"}
          </h1>
        </div>
        <nav className="flex gap-2">
          {items.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Button
                key={item.href}
                asChild
                variant={active ? "secondary" : "ghost"}
                size="sm"
              >
                <Link href={item.href} className={cn("gap-2")}>
                  <item.icon className="size-4" />
                  {item.label}
                </Link>
              </Button>
            );
          })}
        </nav>
      </header>
      <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}

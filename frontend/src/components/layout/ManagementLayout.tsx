"use client";

import Link from "next/link";
import { Suspense } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { ArrowLeft, Database, FolderOpen, Users,BarChart3 } from "lucide-react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { UserRole } from "@/lib/types";

function BackToChatButton({ role }: { role: UserRole }) {
  const searchParams = useSearchParams();
  const session = searchParams.get("session");
  const chatHref = session
    ? `/${role}/chat?session=${session}`
    : `/${role}/chat`;
  return (
    <Button
      asChild
      variant="ghost"
      size="sm"
      className="text-ink/70 hover:bg-ink/10 hover:text-ink"
    >
      <Link href={chatHref}>
        <ArrowLeft className="mr-2 size-4" />
        返回对话
      </Link>
    </Button>
  );
}

export function ManagementLayout({
  role,
  children,
}: {
  role: UserRole;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const items =
    role === "teacher"
      ? [
          {
            label: "统计分析",
            href: "/teacher/manage/analytics",
            icon: BarChart3,
          },
          {
            label: "项目",
            href: "/teacher/manage/projects",
            icon: FolderOpen,
          },
          /* {
            label: "学生",
            href: "/teacher/manage/students",
            icon: Users,
          }, */
          { label: "班级",
            href: "/teacher/manage/classes", 
            icon: Users },
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
    <div className="flex h-screen flex-col overflow-hidden bg-[#efece3] dark:bg-[#091611]">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-ink/10 px-4 print:hidden">
        <div className="flex items-center gap-3">
          <Suspense fallback={
            <Button
              variant="ghost"
              size="sm"
              className="text-ink/70 hover:bg-ink/10 hover:text-ink"
            >
              <ArrowLeft className="mr-2 size-4" />
              返回对话
            </Button>
          }>
            <BackToChatButton role={role} />
          </Suspense>
          <h1 className="[font-family:'Songti_SC','STSong','SimSun','Noto_Serif_SC',serif] text-base font-semibold tracking-[0.04em] text-ink">
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
                className={cn(
                  "gap-2 transition-[opacity,transform] duration-150 hover:opacity-80 active:scale-[0.97]",
                  active
                    ? "bg-gradient-to-r from-[#0b3d31] to-[#064e3b] text-emerald-50 shadow-sm hover:from-[#0b3d31] hover:to-[#064e3b]"
                    : "text-ink/70 hover:bg-ink/10 hover:text-ink",
                )}
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
      <main className="min-h-0 flex-1 overflow-y-auto bg-[#efece3] dark:bg-[#091611]">
        <motion.div
          key={pathname}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
        >
          {children}
        </motion.div>
      </main>
    </div>
  );
}

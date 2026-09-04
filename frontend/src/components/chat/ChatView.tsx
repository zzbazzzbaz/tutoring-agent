"use client";

import { useState, useEffect } from "react";
import { useQueryState } from "nuqs";
import { motion, AnimatePresence } from "framer-motion";
import { StreamProvider } from "./StreamProvider";
import { SessionProvider } from "./SessionProvider";
import { ArtifactProvider } from "./thread/artifact";
import { Thread } from "./thread";
import { NewSessionModal } from "./NewSessionModal";
import { ChatWorkspaceSidebar } from "./ChatWorkspaceSidebar";
import { Button } from "@/components/ui/button";
import { PanelLeftOpen } from "lucide-react";

export function ChatView({
  role,
  readOnly = false,
}: {
  role: "student" | "teacher";
  readOnly?: boolean;
}) {
  return (
    <SessionProvider>
      <ChatShell role={role} readOnly={readOnly} />
    </SessionProvider>
  );
}

function ChatShell({
  role,
  readOnly,
}: {
  role: "student" | "teacher";
  readOnly: boolean;
}) {
  const [modalOpen, setModalOpen] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [projectPreselect, setProjectPreselect] = useState<
    string | undefined
  >(undefined);
  const [_sessionId, setSessionId] = useQueryState("session");
  const [projectParam, setProjectParam] = useQueryState("project");

  useEffect(() => {
    if (projectParam) {
      setProjectPreselect(projectParam);
      setModalOpen(true);
      setProjectParam(null);
    }
  }, [projectParam, setProjectParam]);

  return (
    <div className="flex h-screen overflow-hidden bg-white dark:bg-[#0f172a]">
      {/* 桌面端侧边栏：始终挂载，translateX 滑入滑出 */}
      {!readOnly && (
        <motion.aside
          className="fixed left-0 top-0 z-30 hidden h-screen w-[280px] lg:block"
          animate={{ x: sidebarCollapsed ? -280 : 0 }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
          style={{ willChange: "transform" }}
          aria-hidden={sidebarCollapsed}
        >
          <ChatWorkspaceSidebar
            role={role}
            onNewSession={() => {
              setProjectPreselect(undefined);
              setModalOpen(true);
            }}
            onCollapse={() => setSidebarCollapsed(true)}
            mobileOpen={mobileSidebarOpen}
            onMobileOpenChange={setMobileSidebarOpen}
          />
        </motion.aside>
      )}

      {/* 展开按钮：侧边栏收起时淡入 */}
      <AnimatePresence>
        {!readOnly && sidebarCollapsed && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed left-3 top-3 z-30 hidden lg:block"
          >
            <Button
              variant="ghost"
              size="icon"
              className="size-9 rounded-xl bg-paper-card/90 shadow-sm backdrop-blur-sm border border-ink/8 hover:bg-paper"
              onClick={() => setSidebarCollapsed(false)}
              title="展开侧边栏"
            >
              <PanelLeftOpen className="size-4" />
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
      <div className="min-w-0 flex-1">
        <StreamProvider readOnly={readOnly}>
          <ArtifactProvider>
            <Thread
              onOpenSessions={() => {
                setSidebarCollapsed(false);
                setMobileSidebarOpen(true);
              }}
            />
          </ArtifactProvider>
        </StreamProvider>
      </div>
      <NewSessionModal
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setProjectPreselect(undefined);
        }}
        onCreated={(id) => setSessionId(id)}
        preselectProjectId={projectPreselect}
      />
    </div>
  );
}

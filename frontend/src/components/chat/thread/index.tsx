import { v4 as uuidv4 } from "uuid";
import { ReactNode, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useStreamContext } from "@/components/chat/StreamProvider";
import { useSessions } from "@/components/chat/SessionProvider";
import { useState, FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Checkpoint, Message } from "@langchain/langgraph-sdk";
import { AssistantMessage, AssistantMessageLoading } from "./messages/ai";
import { HumanMessage } from "./messages/human";
import {
  DO_NOT_RENDER_ID_PREFIX,
  ensureToolCallsHaveResponses,
} from "@/lib/ensure-tool-responses";
import {
  ArrowDown,
  LoaderCircle,
  PanelRightClose,
  XIcon,
  Plus,
} from "lucide-react";
import { useQueryState, parseAsBoolean } from "nuqs";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import { toast } from "sonner";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { projectsApi } from "@/lib/api/projects";
import type { Project } from "@/lib/types";
import { LearningMainlinePanel } from "@/components/chat/LearningMainlinePanel";
import { useFileUpload } from "@/hooks/use-file-upload";
import { ContentBlocksPreview } from "./ContentBlocksPreview";
import {
  useArtifactOpen,
  ArtifactContent,
  ArtifactTitle,
  useArtifactContext,
} from "./artifact";

function StickyToBottomContent(props: {
  content: ReactNode;
  footer?: ReactNode;
  className?: string;
  contentClassName?: string;
}) {
  const context = useStickToBottomContext();
  return (
    <div
      ref={context.scrollRef}
      style={{ width: "100%", height: "100%" }}
      className={props.className}
    >
      <div
        ref={context.contentRef}
        className={props.contentClassName}
      >
        {props.content}
      </div>

      {props.footer}
    </div>
  );
}

function ScrollToBottom(props: { className?: string }) {
  const { isAtBottom, scrollToBottom } = useStickToBottomContext();

  if (isAtBottom) return null;
  return (
    <Button
      variant="outline"
      className={props.className}
      onClick={() => scrollToBottom()}
    >
      <ArrowDown className="h-4 w-4" />
      <span>滚动到底部</span>
    </Button>
  );
}

export function Thread({
  onOpenSessions,
}: {
  onOpenSessions?: () => void;
} = {}) {
  const [artifactContext, setArtifactContext] = useArtifactContext();
  const [artifactOpen, closeArtifact] = useArtifactOpen();

  const [threadId, _setThreadId] = useQueryState("session");
  const [hideToolCalls, setHideToolCalls] = useQueryState(
    "hideToolCalls",
    parseAsBoolean.withDefault(true),
  );
  const [input, setInput] = useState("");
  // 无会话时首次发送：先创建会话，threadId 就绪后再提交消息
  const [pendingSubmit, setPendingSubmit] = useState<{
    message: Message;
    context?: Record<string, unknown>;
  } | null>(null);
  // 新建对话时的会话类型（自由学习 / 案例模式）与所选案例
  const [sessionMode, setSessionMode] = useState<"free" | "project">("free");
  const [selectedProject, setSelectedProject] = useState<string>("");
  const [projects, setProjects] = useState<Project[]>([]);

  const { createSession } = useSessions();
  const { sessions } = useSessions();
  const currentSession = sessions.find((s) => s.id === threadId);
  const currentProjectId =
    currentSession?.mode === "project" ? currentSession.project_id : undefined;
  const currentSessionId =
    currentSession?.mode === "project" ? currentSession.id : undefined;

  // 切到案例模式时拉取已发布案例
  useEffect(() => {
    if (sessionMode === "project" && projects.length === 0) {
      projectsApi
        .list("published", 1, 100)
        .then((data) => setProjects(data.items))
        .catch(console.error);
    }
  }, [sessionMode, projects.length]);
  const renderToolCallsToggle = false; // 隐藏工具调用开关已注释；恢复时改为 true 或删除条件包裹
  const {
    contentBlocks,
    setContentBlocks,
    handleFileUpload,
    dropRef,
    removeBlock,
    resetBlocks: _resetBlocks,
    dragOver,
    handlePaste,
  } = useFileUpload();
  const [firstTokenReceived, setFirstTokenReceived] = useState(false);
  const isLargeScreen = useMediaQuery("(min-width: 1024px)");

  const stream = useStreamContext();
  const messages = stream.messages;
  const isLoading = stream.isLoading;

  const lastError = useRef<string | undefined>(undefined);

  const setThreadId = (id: string | null) => {
    _setThreadId(id);

    // close artifact and reset artifact context
    closeArtifact();
    setArtifactContext({});
  };

  useEffect(() => {
    if (!stream.error) {
      lastError.current = undefined;
      return;
    }
    try {
      const message = (stream.error as any).message;
      if (!message || lastError.current === message) {
        // Message has already been logged. do not modify ref, return early.
        return;
      }

      // Message is defined, and it has not been logged yet. Save it, and send the error
      lastError.current = message;
      toast.error("An error occurred. Please try again.", {
        description: (
          <p>
            <strong>Error:</strong> <code>{message}</code>
          </p>
        ),
        richColors: true,
        closeButton: true,
      });
    } catch {
      // no-op
    }
  }, [stream.error]);

  // TODO: this should be part of the useStream hook
  const prevMessageLength = useRef(0);
  useEffect(() => {
    if (
      messages.length !== prevMessageLength.current &&
      messages?.length &&
      messages[messages.length - 1].type === "ai"
    ) {
      setFirstTokenReceived(true);
    }

    prevMessageLength.current = messages.length;
  }, [messages]);

  const performSubmit = (
    newHumanMessage: Message,
    context?: Record<string, unknown>,
  ) => {
    const toolMessages = ensureToolCallsHaveResponses(stream.messages);

    stream.submit(
      { messages: [...toolMessages, newHumanMessage], context },
      {
        streamMode: ["values"],
        streamSubgraphs: true,
        streamResumable: true,
        optimisticValues: (prev) => ({
          ...prev,
          context,
          messages: [
            ...(prev.messages ?? []),
            ...toolMessages,
            newHumanMessage,
          ],
        }),
      },
    );
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if ((input.trim().length === 0 && contentBlocks.length === 0) || isLoading)
      return;
    setFirstTokenReceived(false);

    const newHumanMessage: Message = {
      id: uuidv4(),
      type: "human",
      content: [
        ...(input.trim().length > 0 ? [{ type: "text", text: input }] : []),
        ...contentBlocks,
      ] as Message["content"],
    };

    const context =
      Object.keys(artifactContext).length > 0 ? artifactContext : undefined;

    if (!threadId) {
      // 保持现状：新建对话弹窗仍然可用；但直接输入并发送时按所选类型创建会话
      if (sessionMode === "project" && !selectedProject) {
        toast.error("请先选择一个案例");
        return;
      }
      try {
        const session = await createSession(
          sessionMode,
          sessionMode === "project" ? selectedProject : undefined,
        );
        setInput("");
        setContentBlocks([]);
        setThreadId(session.id);
        setPendingSubmit({ message: newHumanMessage, context });
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : "创建会话失败，请重试",
        );
      }
      return;
    }

    performSubmit(newHumanMessage, context);
    setInput("");
    setContentBlocks([]);
  };

  // 无会话场景：等待 threadId（URL 参数）就绪后再提交消息，确保发往新创建会话
  useEffect(() => {
    if (pendingSubmit && threadId) {
      performSubmit(pendingSubmit.message, pendingSubmit.context);
      setPendingSubmit(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId, pendingSubmit]);

  const handleRegenerate = (
    parentCheckpoint: Checkpoint | null | undefined,
  ) => {
    // Do this so the loading state is correct
    prevMessageLength.current = prevMessageLength.current - 1;
    setFirstTokenReceived(false);
    stream.submit(undefined, {
      checkpoint: parentCheckpoint,
      streamMode: ["values"],
      streamSubgraphs: true,
      streamResumable: true,
    });
  };

  const chatStarted = !!threadId || !!messages.length;
  const hasNoAIOrToolMessages = !messages.find(
    (m) => m.type === "ai" || m.type === "tool",
  );
  const showMainline =
    !!currentProjectId && !!currentSessionId && !artifactOpen;

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#efece3] dark:bg-[#091611]">
      <div
        className={cn(
          "grid w-full grid-cols-[1fr_0fr] transition-[grid-template-columns] duration-500",
          artifactOpen && "grid-cols-[3fr_2fr]",
          !artifactOpen && showMainline && "grid-cols-[1fr_minmax(300px,400px)]",
        )}
      >
        <motion.div
          className={cn(
            "relative flex min-w-0 flex-1 flex-col overflow-hidden",
            !chatStarted && "grid-rows-[1fr]",
          )}
          layout={isLargeScreen}
          animate={{ width: "100%" }}
          transition={
            isLargeScreen
              ? { type: "spring", stiffness: 300, damping: 30 }
              : { duration: 0 }
          }
        >
          {!chatStarted && (
            <div className="absolute top-0 left-0 z-10 flex w-full items-center justify-between gap-3 p-2 pl-4">
              <div>
                <Button
                  className="hover:bg-paper/80 lg:hidden"
                  variant="ghost"
                  onClick={onOpenSessions}
                >
                  <PanelRightClose className="size-5 text-ink/50" />
                </Button>
              </div>
            </div>
          )}
          {chatStarted && (
            <div className="relative z-10 flex items-center p-2">
              <Button
                className="hover:bg-paper/80 lg:hidden"
                variant="ghost"
                onClick={onOpenSessions}
              >
                <PanelRightClose className="size-5 text-ink/50" />
              </Button>
            </div>
          )}

          <StickToBottom className="relative flex-1 overflow-hidden">
            <StickyToBottomContent
              className={cn(
                "absolute inset-0 overflow-y-scroll px-4 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-ink/15 [&::-webkit-scrollbar-track]:bg-transparent",
                !chatStarted && "mt-[25vh] flex flex-col items-stretch",
                chatStarted && "grid grid-rows-[1fr_auto]",
              )}
              contentClassName="pt-8 pb-16 max-w-4xl mx-auto flex flex-col gap-6 w-full"
              content={
                <>
                  {messages
                    .filter((m) => !m.id?.startsWith(DO_NOT_RENDER_ID_PREFIX))
                    .map((message, index) =>
                      message.type === "human" ? (
                        <HumanMessage
                          key={message.id || `${message.type}-${index}`}
                          message={message}
                          isLoading={isLoading}
                        />
                      ) : (
                        <AssistantMessage
                          key={message.id || `${message.type}-${index}`}
                          message={message}
                          isLoading={isLoading}
                          handleRegenerate={handleRegenerate}
                        />
                      ),
                    )}
                  {/* Special rendering case where there are no AI/tool messages, but there is an interrupt.
                    We need to render it outside of the messages list, since there are no messages to render */}
                  {hasNoAIOrToolMessages && !!stream.interrupt && (
                    <AssistantMessage
                      key="interrupt-msg"
                      message={undefined}
                      isLoading={isLoading}
                      handleRegenerate={handleRegenerate}
                    />
                  )}
                  {isLoading && !firstTokenReceived && (
                    <AssistantMessageLoading />
                  )}
                </>
              }
              footer={
                <div className="sticky bottom-0 flex flex-col items-center gap-8 bg-gradient-to-t from-[#efece3] via-[#efece3]/95 to-[#efece3]/0 backdrop-blur-sm dark:from-[#0a1410] dark:via-[#0a1410]/95 dark:to-[#0a1410]/0">
                  {!chatStarted && (
                    <div className="flex items-center gap-3">
                      <h1 className="[font-family:'Songti_SC','STSong','SimSun','Noto_Serif_SC',serif] text-2xl font-semibold tracking-[0.04em] text-ink">
                        有什么我能帮你的吗？
                      </h1>
                    </div>
                  )}

                  {!chatStarted && (
                    <div className="flex flex-col items-center gap-4">
                      {/* 新建对话类型切换：滑动切换（仿 deepseek） */}
                      <div className="relative flex items-center gap-1 rounded-full bg-ink/[0.06] p-1 text-sm font-medium backdrop-blur-sm">
                        {(["free", "project"] as const).map((mode) => {
                          const active = sessionMode === mode;
                          return (
                            <button
                              key={mode}
                              type="button"
                              onClick={() => setSessionMode(mode)}
                              className={cn(
                                "relative rounded-full px-5 py-1.5 transition-colors",
                                active
                                  ? "text-ink"
                                  : "text-ink/40 hover:text-ink/60",
                              )}
                            >
                              {active && (
                                <motion.span
                                  layoutId="chat-mode-tab"
                                  className="absolute inset-0 rounded-full bg-paper-card shadow-sm ring-1 ring-ink/8"
                                  transition={{
                                    type: "spring",
                                    stiffness: 300,
                                    damping: 30,
                                  }}
                                />
                              )}
                              <span className="relative z-10">
                                {mode === "free" ? "自由学习" : "案例模式"}
                              </span>
                            </button>
                          );
                        })}
                      </div>

                      {/* 案例模式下选择案例 */}
                      {sessionMode === "project" && (
                        <Select
                          value={selectedProject}
                          onValueChange={setSelectedProject}
                        >
                          <SelectTrigger className="w-[320px]">
                            <SelectValue placeholder="请选择案例" />
                          </SelectTrigger>
                          <SelectContent>
                            {projects.length === 0 ? (
                              <div className="text-muted-foreground px-3 py-2 text-sm">
                                暂无已发布案例
                              </div>
                            ) : (
                              projects.map((p) => (
                                <SelectItem
                                  key={p.id}
                                  value={p.id}
                                >
                                  {p.name}
                                </SelectItem>
                              ))
                            )}
                          </SelectContent>
                        </Select>
                      )}
                    </div>
                  )}

                  <ScrollToBottom className="animate-in fade-in-0 zoom-in-95 absolute bottom-full left-1/2 mb-4 -translate-x-1/2" />

                  <div
                    ref={dropRef}
                    className={cn(
                      "relative z-10 mx-auto mb-8 w-full max-w-4xl rounded-2xl shadow-[0_2px_6px_rgba(6,39,31,0.06),0_8px_24px_-8px_rgba(6,39,31,0.12)] transition-[border-color] bg-paper-card border border-ink/8",
                      dragOver
                        ? "border-brand/40 border-2 border-dotted"
                        : "",
                    )}
                  >
                    <form
                      onSubmit={handleSubmit}
                      className="mx-auto grid max-w-4xl grid-rows-[1fr_auto] gap-2"
                    >
                      <ContentBlocksPreview
                        blocks={contentBlocks}
                        onRemove={removeBlock}
                      />
                      <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onPaste={handlePaste}
                        onKeyDown={(e) => {
                          if (
                            e.key === "Enter" &&
                            !e.shiftKey &&
                            !e.metaKey &&
                            !e.nativeEvent.isComposing
                          ) {
                            e.preventDefault();
                            const el = e.target as HTMLElement | undefined;
                            const form = el?.closest("form");
                            form?.requestSubmit();
                          }
                        }}
                        placeholder="输入消息..."
                        className="field-sizing-content resize-none border-none bg-transparent p-3.5 pb-0 shadow-none ring-0 outline-none focus:ring-0 focus:outline-none"
                      />

                      <div className="flex items-center gap-6 p-2 pt-4">
                        <div>
                          {/* 隐藏工具调用开关已注释；恢复时删除条件包裹即可 */}
                          {renderToolCallsToggle && (
                            <div className="flex items-center space-x-2">
                              <Switch
                                id="render-tool-calls"
                                checked={hideToolCalls ?? true}
                                onCheckedChange={setHideToolCalls}
                              />
                              <Label
                                htmlFor="render-tool-calls"
                                className="text-sm text-gray-600"
                              >
                                隐藏工具调用
                              </Label>
                            </div>
                          )}
                        </div>
                        {/* 上传 PDF 或图片功能 - 本期暂不需要，后续版本恢复
                          <Label
                            htmlFor="file-input"
                            className="flex cursor-pointer items-center gap-2"
                          >
                            <Plus className="size-5 text-gray-600" />
                            <span className="text-sm text-gray-600">
                              上传 PDF 或图片
                            </span>
                          </Label>
                          <input
                            id="file-input"
                            type="file"
                            onChange={handleFileUpload}
                            multiple
                            accept="image/jpeg,image/png,image/gif,image/webp,application/pdf"
                            className="hidden"
                          />
                          */}
                        {stream.isLoading ? (
                          <Button
                            key="stop"
                            onClick={() => stream.stop()}
                            className="ml-auto bg-paper-card border border-ink/10 text-ink/60 hover:bg-paper hover:text-ink/80 shadow-sm"
                          >
                            <LoaderCircle className="h-4 w-4 animate-spin" />
                            取消
                          </Button>
                        ) : (
                          <Button
                            type="submit"
                            className="ml-auto bg-gradient-to-r from-[#0b3d31] to-[#064e3b] text-emerald-50 hover:from-[#0a362b] hover:to-[#054333] shadow-lg shadow-emerald-900/20 rounded-xl px-5 font-medium"
                            disabled={
                              isLoading ||
                              (!input.trim() && contentBlocks.length === 0)
                            }
                          >
                            发送
                          </Button>
                        )}
                      </div>
                    </form>
                  </div>
                </div>
              }
            />
          </StickToBottom>
        </motion.div>
        <div className="relative flex flex-col border-l border-ink/8 bg-paper-card/60 backdrop-blur-sm">
          {artifactOpen ? (
            <div className="absolute inset-0 flex min-w-[30vw] flex-col">
              <div className="grid grid-cols-[1fr_auto] border-b border-ink/8 p-4">
                <ArtifactTitle className="truncate overflow-hidden" />
                <button
                  onClick={closeArtifact}
                  className="cursor-pointer"
                >
                  <XIcon className="size-5" />
                </button>
              </div>
              <ArtifactContent className="relative flex-grow" />
            </div>
          ) : showMainline && currentProjectId && currentSessionId ? (
            <div className="h-full overflow-y-auto p-4 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-ink/15 [&::-webkit-scrollbar-track]:bg-transparent">
              <LearningMainlinePanel
                projectId={currentProjectId}
                sessionId={currentSessionId}
              />
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

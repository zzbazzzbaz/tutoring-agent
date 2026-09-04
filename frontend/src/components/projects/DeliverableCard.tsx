"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, ChevronDown, ChevronUp, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import { MarkdownText } from "@/components/chat/thread/markdown-text";

export function DeliverableCard({
  stageTitle,
  deliverableTitle,
  content,
  done,
  defaultExpanded = false,
}: {
  stageTitle: string;
  deliverableTitle: string | null;
  content: string;
  done: boolean;
  defaultExpanded?: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div
      className={cn(
        "border-ink/10 bg-paper-card overflow-hidden rounded-lg border",
        done && "border-blue-500/20",
      )}
    >
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="hover:bg-paper flex w-full cursor-pointer items-center gap-2 px-4 py-2.5 text-left transition-colors"
      >
        <FileText
          className={cn(
            "size-4 shrink-0",
            done ? "text-blue-600" : "text-ink/35",
          )}
        />
        <span className="text-ink flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="truncate text-sm font-medium">
            {stageTitle}
            {deliverableTitle && (
              <span className="text-muted-foreground font-normal">
                {" "}
                「{deliverableTitle}」
              </span>
            )}
          </span>
          {!expanded && (
            <span className="text-muted-foreground truncate text-xs">
              {content}
            </span>
          )}
        </span>
        <span
          className={cn(
            "shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium",
            done
              ? "bg-blue-500/10 text-blue-600"
              : "bg-amber-500/10 text-amber-600",
          )}
        >
          {done ? "已达标" : "待完成"}
        </span>
        {expanded ? (
          <ChevronUp className="text-muted-foreground size-4 shrink-0" />
        ) : (
          <ChevronDown className="text-muted-foreground size-4 shrink-0" />
        )}
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="border-ink/10 text-ink border-t px-4 py-3">
              <div className="flex items-start gap-2">
                {done && (
                  <Check className="text-blue-600 mt-1 size-4 shrink-0" />
                )}
                <div className="min-w-0 flex-1">
                  <MarkdownText>{content}</MarkdownText>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

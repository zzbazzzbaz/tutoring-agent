import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useStreamContext } from "@/components/chat/StreamProvider";

type QuizInterrupt = {
  question_id: string;
  topic: string;
  q_type: "single" | "multi" | "short";
  stem: string;
  options: string[] | null;
};

function isQuizInterrupt(value: unknown): value is QuizInterrupt {
  if (!value || Array.isArray(value) || typeof value !== "object") return false;
  const quiz = value as Partial<QuizInterrupt>;
  return (
    typeof quiz.question_id === "string" &&
    typeof quiz.stem === "string" &&
    ["single", "multi", "short"].includes(quiz.q_type ?? "")
  );
}

function QuizInterruptView({ interrupt }: { interrupt: QuizInterrupt }) {
  const thread = useStreamContext();
  const [selected, setSelected] = useState<string[]>([]);
  const [shortAnswer, setShortAnswer] = useState("");
  const answer =
    interrupt.q_type === "short" ? shortAnswer.trim() : selected.join(", ");

  const resume = (action: "answer" | "skip") => {
    thread.submit(
      {},
      {
        command: {
          resume: { action, answer: action === "answer" ? answer : "" },
        },
        streamMode: ["values"],
        streamSubgraphs: true,
        streamResumable: true,
      },
    );
  };

  const chooseOption = (option: string) => {
    if (interrupt.q_type === "single") {
      setSelected([option]);
      return;
    }
    setSelected((current) =>
      current.includes(option)
        ? current.filter((item) => item !== option)
        : [...current, option],
    );
  };

  return (
    <div className="overflow-hidden rounded-lg border border-ink/10 bg-paper-card">
      <div className="border-b border-ink/10 bg-paper px-4 py-3">
        <p className="text-xs font-medium text-muted-foreground">{interrupt.topic}</p>
        <h3 className="mt-1 font-medium text-ink">{interrupt.stem}</h3>
      </div>
      <div className="space-y-3 p-4">
        {interrupt.q_type === "short" ? (
          <Input
            aria-label="Quiz answer"
            value={shortAnswer}
            onChange={(event) => setShortAnswer(event.target.value)}
          />
        ) : (
          <div className="grid gap-2">
            {(interrupt.options ?? []).map((option) => (
              <button
                key={option}
                type="button"
                aria-pressed={selected.includes(option)}
                className={cn(
                  "rounded-md border px-3 py-2 text-left text-sm transition-colors",
                  selected.includes(option)
                    ? "border-[#0b3d31] bg-[#0b3d31] text-emerald-50"
                    : "border-ink/10 hover:bg-paper",
                )}
                onClick={() => chooseOption(option)}
              >
                {option}
              </button>
            ))}
          </div>
        )}
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={thread.isLoading}
            onClick={() => resume("skip")}
          >
            跳过
          </Button>
          <Button
            type="button"
            disabled={!answer || thread.isLoading}
            onClick={() => resume("answer")}
          >
            提交答案
          </Button>
        </div>
      </div>
    </div>
  );
}

function isComplexValue(value: any): boolean {
  return Array.isArray(value) || (typeof value === "object" && value !== null);
}

function isUrl(value: any): boolean {
  if (typeof value !== "string") return false;
  try {
    new URL(value);
    return value.startsWith("http://") || value.startsWith("https://");
  } catch {
    return false;
  }
}

function renderInterruptStateItem(value: any): React.ReactNode {
  if (isComplexValue(value)) {
    return (
      <code className="rounded bg-paper px-2 py-1 font-mono text-sm">
        {JSON.stringify(value, null, 2)}
      </code>
    );
  } else if (isUrl(value)) {
    return (
      <a
        href={value}
        target="_blank"
        rel="noopener noreferrer"
        className="break-all text-brand underline hover:text-brand-dark"
      >
        {value}
      </a>
    );
  } else {
    return String(value);
  }
}

export function GenericInterruptView({
  interrupt,
}: {
  interrupt: Record<string, any> | Record<string, any>[];
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (isQuizInterrupt(interrupt)) {
    return <QuizInterruptView interrupt={interrupt} />;
  }

  const contentStr = JSON.stringify(interrupt, null, 2);
  const contentLines = contentStr.split("\n");
  const shouldTruncate = contentLines.length > 4 || contentStr.length > 500;

  // Function to truncate long string values (but preserve URLs)
  const truncateValue = (value: any): any => {
    if (typeof value === "string" && value.length > 100) {
      // Don't truncate URLs so they remain clickable
      if (isUrl(value)) {
        return value;
      }
      return value.substring(0, 100) + "...";
    }

    if (Array.isArray(value) && !isExpanded) {
      return value.slice(0, 2).map(truncateValue);
    }

    if (isComplexValue(value) && !isExpanded) {
      const strValue = JSON.stringify(value, null, 2);
      if (strValue.length > 100) {
        // Return plain text for truncated content instead of a JSON object
        return `Truncated ${strValue.length} characters...`;
      }
    }

    return value;
  };

  // Process entries based on expanded state
  const processEntries = () => {
    if (Array.isArray(interrupt)) {
      return isExpanded ? interrupt : interrupt.slice(0, 5);
    } else {
      const entries = Object.entries(interrupt);
      if (!isExpanded && shouldTruncate) {
        // When collapsed, process each value to potentially truncate it
        return entries.map(([key, value]) => [key, truncateValue(value)]);
      }
      return entries;
    }
  };

  const displayEntries = processEntries();

  return (
    <div className="overflow-hidden rounded-lg border border-ink/10">
      <div className="border-b border-ink/10 bg-paper px-4 py-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-medium text-ink">Human Interrupt</h3>
        </div>
      </div>
      <motion.div
        className="min-w-full overflow-hidden bg-paper"
        initial={false}
        animate={{ height: "auto" }}
        transition={{ duration: 0.25, ease: "easeOut" }}
      >
        <div className="p-3">
          <AnimatePresence
            mode="wait"
            initial={false}
          >
            <motion.div
              key={isExpanded ? "expanded" : "collapsed"}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.2 }}
              style={{
                maxHeight: isExpanded ? "none" : "500px",
                overflow: "auto",
              }}
            >
              <table className="min-w-full divide-y divide-gray-200">
                <tbody className="divide-y divide-gray-200">
                  {displayEntries.map((item, argIdx) => {
                    const [key, value] = Array.isArray(interrupt)
                      ? [argIdx.toString(), item]
                      : (item as [string, any]);
                    return (
                      <tr key={argIdx}>
                        <td className="px-4 py-2 text-sm font-medium whitespace-nowrap text-ink">
                          {key}
                        </td>
                        <td className="px-4 py-2 text-sm text-muted-foreground">
                          {renderInterruptStateItem(value)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </motion.div>
          </AnimatePresence>
        </div>
        {(shouldTruncate ||
          (Array.isArray(interrupt) && interrupt.length > 5)) && (
          <motion.button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex w-full cursor-pointer items-center justify-center border-t-[1px] border-ink/10 py-2 text-ink/50 transition-[background-color,color] duration-200 ease-in-out hover:bg-paper/80 hover:text-ink/80"
            initial={{ scale: 1 }}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            {isExpanded ? <ChevronUp /> : <ChevronDown />}
          </motion.button>
        )}
      </motion.div>
    </div>
  );
}

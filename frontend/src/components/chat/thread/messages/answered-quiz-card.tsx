import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { isOptionSelected, type QuizType } from "@/lib/quiz";

export type AnsweredQuizCardProps = {
  topic: string;
  qType: QuizType;
  stem: string;
  options: string[] | null;
  studentAnswer: string | null;
  skipped: boolean;
};

export function AnsweredQuizCard({
  topic,
  qType,
  stem,
  options,
  studentAnswer,
  skipped,
}: AnsweredQuizCardProps) {
  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
      <div className="border-b border-gray-200 bg-gray-50 px-4 py-3">
        <p className="text-xs font-medium text-gray-500">{topic}</p>
        <h3 className="mt-1 font-medium text-gray-900">{stem}</h3>
      </div>
      <div className="space-y-3 p-4">
        {qType === "short" ? (
          <div className="rounded-md bg-gray-50 px-3 py-2 text-sm text-gray-900">
            <span className="font-medium text-gray-500">你的回答：</span>
            {studentAnswer}
          </div>
        ) : (
          <div className="grid gap-2">
            {(options ?? []).map((option) => {
              const selected =
                !skipped &&
                !!studentAnswer &&
                isOptionSelected(option, studentAnswer);
              return (
                <div
                  key={option}
                  aria-selected={selected}
                  className={cn(
                    "flex items-center justify-between rounded-md border px-3 py-2 text-left text-sm",
                    selected
                      ? "border-gray-900 bg-gray-900 text-white"
                      : "border-gray-200",
                  )}
                >
                  <span>{option}</span>
                  {selected && <Check className="size-4 shrink-0" />}
                </div>
              );
            })}
          </div>
        )}
        {skipped && (
          <p className="text-xs text-gray-500">已跳过</p>
        )}
      </div>
    </div>
  );
}

import { Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { isOptionSelected, type QuizType } from "@/lib/quiz";

export type AnsweredQuizCardProps = {
  topic: string;
  qType: QuizType;
  stem: string;
  options: string[] | null;
  studentAnswer: string | null;
  skipped: boolean;
  correctAnswer: string;
};

export function AnsweredQuizCard({
  topic,
  qType,
  stem,
  options,
  studentAnswer,
  skipped,
  correctAnswer,
}: AnsweredQuizCardProps) {
  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
      <div className="border-b border-gray-200 bg-gray-50 px-4 py-3">
        <p className="text-xs font-medium text-gray-500">{topic}</p>
        <h3 className="mt-1 font-medium text-gray-900">{stem}</h3>
      </div>
      <div className="space-y-3 p-4">
        {qType === "short" ? (
          <>
            <div className="rounded-md bg-gray-50 px-3 py-2 text-sm text-gray-900">
              <span className="font-medium text-gray-500">你的回答：</span>
              {studentAnswer}
            </div>
            {correctAnswer && (
              <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-gray-900">
                <span className="font-medium text-emerald-700">参考答案：</span>
                {correctAnswer}
              </div>
            )}
          </>
        ) : (
          <div className="grid gap-2">
            {(options ?? []).map((option) => {
              const selected =
                !skipped &&
                !!studentAnswer &&
                isOptionSelected(option, studentAnswer);
              const isCorrect =
                correctAnswer.trim() !== "" &&
                isOptionSelected(option, correctAnswer);
              const isWrong = selected && !isCorrect;
              return (
                <div
                  key={option}
                  aria-selected={selected}
                  className={cn(
                    "flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-sm",
                    selected && isCorrect
                      ? "border-emerald-500 bg-emerald-100 text-emerald-900"
                      : isCorrect
                        ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                        : isWrong
                          ? "border-red-300 bg-red-50 text-red-900"
                          : "border-gray-200",
                  )}
                >
                  <span>{option}</span>
                  <span className="flex shrink-0 items-center gap-2">
                    {isCorrect && (
                      <span className="text-xs font-medium text-emerald-600">
                        正确答案
                      </span>
                    )}
                    {selected && isCorrect && <Check className="size-4" />}
                    {isWrong && (
                      <>
                        <span className="text-xs font-medium text-red-600">
                          我的选择
                        </span>
                        <X className="size-4" />
                      </>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
        )}
        {skipped && <p className="text-xs text-gray-500">已跳过</p>}
      </div>
    </div>
  );
}

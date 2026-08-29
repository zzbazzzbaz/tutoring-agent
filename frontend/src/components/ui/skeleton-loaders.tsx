import { Skeleton } from "@/components/ui/skeleton";

/**
 * 表格骨架屏：模拟 N 行 M 列的表格加载态
 * columns: 每列宽度比例（如 ["1fr", "2fr", "1fr"]）
 */
export function SkeletonTable({
  rows = 5,
  columns = ["1fr", "1fr", "1fr"],
  className,
}: {
  rows?: number;
  columns?: string[];
  className?: string;
}) {
  return (
    <div
      className={`overflow-hidden rounded-md border border-ink/10 bg-paper-card ${className ?? ""}`}
    >
      <table className="w-full text-sm">
        <thead className="bg-paper">
          <tr>
            {columns.map((_, i) => (
              <th key={i} className="px-4 py-2.5 text-left font-medium">
                <Skeleton className="h-4 w-16 bg-ink/5" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, rowIdx) => (
            <tr
              key={rowIdx}
              className="border-t border-ink/10"
            >
              {columns.map((_, colIdx) => (
                <td key={colIdx} className="px-4 py-3">
                  <Skeleton
                    className="h-4 bg-ink/5"
                    style={{
                      width: `${50 + ((rowIdx * 7 + colIdx * 13) % 40)}%`,
                    }}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * 卡片骨架屏：模拟详情页/表单页加载态
 */
export function SkeletonCard({
  lines = 4,
  className,
}: {
  lines?: number;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-ink/10 bg-paper-card p-6 ${className ?? ""}`}
    >
      <Skeleton className="mb-4 h-6 w-32 bg-ink/5" />
      <div className="space-y-3">
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton
            key={i}
            className="h-4 bg-ink/5"
            style={{
              width: `${60 + ((i * 11) % 35)}%`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

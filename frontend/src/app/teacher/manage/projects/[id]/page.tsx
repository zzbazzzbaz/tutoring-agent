"use client";

import { use } from "react";
import { ProjectDetail } from "@/components/projects/ProjectDetail";

export default function TeacherManageProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return (
    <div className="h-full overflow-y-auto">
      <ProjectDetail id={id} basePath="/teacher/manage" />
    </div>
  );
}

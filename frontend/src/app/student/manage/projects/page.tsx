"use client";

import { ProjectList } from "@/components/projects/ProjectList";

export default function StudentManageProjectsPage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="border-b px-4 py-3">
        <h1 className="text-xl font-bold">项目列表</h1>
      </div>
      <ProjectList basePath="/student/manage" publishedOnly />
    </div>
  );
}

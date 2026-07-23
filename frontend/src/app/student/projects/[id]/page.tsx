"use client";

import { use } from "react";
import { ProjectDetail } from "@/components/projects/ProjectDetail";

export default function StudentProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <ProjectDetail id={id} basePath="/student" readOnly />;
}

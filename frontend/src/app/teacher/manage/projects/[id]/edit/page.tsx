"use client";

import { use } from "react";
import { ProjectFormPage } from "@/components/projects/ProjectFormPage";

export default function TeacherManageProjectEditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <ProjectFormPage projectId={id} />;
}

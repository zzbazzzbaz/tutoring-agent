"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, FileDown, Save, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { analyticsApi } from "@/lib/api/analytics";
import { classesApi } from "@/lib/api/classes";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import type { ClassInfo, ScoringResultResponse } from "@/lib/types";

function scoreColor(score: number) {
  if (score >= 80) return "text-green-600";
  if (score >= 60) return "text-blue-600";
  return "text-red-600";
}

export default function TeacherScoringPage() {
  const [classes, setClasses] = useState<ClassInfo[]>([]);
  const [selectedClassId, setSelectedClassId] = useState("");
  const [since, setSince] = useState("");
  const [prompt, setPrompt] = useState("");
  const [isDefault, setIsDefault] = useState(true);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<ScoringResultResponse | null>(null);
  const [loadingResult, setLoadingResult] = useState(false);

  useEffect(() => {
    classesApi
      .list(undefined, "active", undefined, 1, 100)
      .then((data) =>
        setClasses((data.items || []).filter((c) => c.status === "active")),
      )
      .catch(() => setClasses([]));
    analyticsApi
      .getScoringPrompt()
      .then((data) => {
        setPrompt(data.prompt);
        setIsDefault(data.is_default);
      })
      .catch(() => toast.error("加载评分提示词失败"));
  }, []);

  useEffect(() => {
    if (!selectedClassId) {
      setResult(null);
      return;
    }
    setLoadingResult(true);
    analyticsApi
      .getScoring(selectedClassId)
      .then(setResult)
      .catch(() => setResult(null))
      .finally(() => setLoadingResult(false));
  }, [selectedClassId]);

  async function handleSavePrompt() {
    if (!prompt.trim()) {
      toast.error("提示词不能为空");
      return;
    }
    setSaving(true);
    try {
      const data = await analyticsApi.saveScoringPrompt(prompt);
      setPrompt(data.prompt);
      setIsDefault(data.is_default);
      toast.success("提示词已保存");
    } catch (err: any) {
      toast.error(err?.message || "保存失败，请重试");
    } finally {
      setSaving(false);
    }
  }

  async function handleGenerate() {
    if (!selectedClassId) {
      toast.error("请先选择班级");
      return;
    }
    setGenerating(true);
    try {
      const data = await analyticsApi.generateScoring(
        selectedClassId,
        since || undefined,
      );
      setResult(data);
      if (data.items.length === 0) {
        toast.info("该班级暂无学生");
      } else {
        toast.success(`已生成 ${data.items.length} 名学生的平时分`);
      }
    } catch (err: any) {
      toast.error(err?.message || "生成失败，请重试");
    } finally {
      setGenerating(false);
    }
  }

  async function handleExport() {
    if (!selectedClassId || !result?.items.length) return;
    try {
      await analyticsApi.exportScoring(selectedClassId);
    } catch {
      toast.error("导出失败，请重试");
    }
  }

  return (
    <div className="h-full space-y-6 overflow-y-auto p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <Button
            asChild
            variant="ghost"
            size="sm"
          >
            <Link href="/teacher/manage/analytics">
              <ArrowLeft className="size-4" />
            </Link>
          </Button>
          <h1 className="text-xl font-bold">平时分</h1>
          <Select
            value={selectedClassId}
            onValueChange={setSelectedClassId}
          >
            <SelectTrigger className="w-[220px]">
              <SelectValue placeholder="选择班级" />
            </SelectTrigger>
            <SelectContent>
              {classes.map((c) => (
                <SelectItem
                  key={c.id}
                  value={c.id}
                >
                  {c.grade} {c.classname}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            type="date"
            value={since}
            onChange={(e) => setSince(e.target.value)}
            className="w-[170px]"
          />
          <Button
            onClick={handleGenerate}
            disabled={!selectedClassId || generating}
          >
            <Sparkles className="mr-2 size-4" />
            {generating ? "AI 评分中，约需 30~60 秒…" : "生成平时分"}
          </Button>
        </div>
        <Button
          variant="outline"
          onClick={handleExport}
          disabled={!result || result.items.length === 0}
        >
          <FileDown className="mr-2 size-4" />
          导出 Word
        </Button>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">评分提示词</CardTitle>
          <span className="text-muted-foreground text-xs">
            {isDefault ? "当前为系统默认模板" : "已自定义"}
          </span>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            className="min-h-[220px]"
            placeholder="请输入评分标准…"
          />
          <div className="flex justify-end">
            <Button
              onClick={handleSavePrompt}
              disabled={saving || !prompt.trim()}
            >
              <Save className="mr-2 size-4" />
              {saving ? "保存中…" : "保存提示词"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">
            评分结果
            {result && result.items.length > 0
              ? `（${result.items.length} 人）`
              : ""}
          </CardTitle>
          {result?.generated_at ? (
            <span className="text-muted-foreground text-xs">
              生成时间：
              {new Date(result.generated_at).toLocaleString("zh-CN")}
            </span>
          ) : null}
        </CardHeader>
        <CardContent>
          {loadingResult ? (
            <div className="text-muted-foreground py-10 text-center text-sm">
              加载中…
            </div>
          ) : !selectedClassId ? (
            <div className="text-muted-foreground py-10 text-center text-sm">
              请选择班级
            </div>
          ) : result && result.items.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16">排名</TableHead>
                  <TableHead>姓名</TableHead>
                  <TableHead>学号</TableHead>
                  <TableHead className="w-20">分数</TableHead>
                  <TableHead>理由</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {result.items.map((item, index) => (
                  <TableRow key={item.student_id}>
                    <TableCell>{index + 1}</TableCell>
                    <TableCell className="font-medium">{item.name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {item.username}
                    </TableCell>
                    <TableCell
                      className={`font-semibold ${scoreColor(item.score)}`}
                    >
                      {item.score}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {item.reason || "-"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-muted-foreground py-10 text-center text-sm">
              尚未生成平时分
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

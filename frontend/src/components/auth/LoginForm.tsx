"use client";

import { useState } from "react";
import { useAuth } from "./AuthProvider";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { toast } from "sonner";
import { BrainCircuit, Sparkles } from "lucide-react";

export function LoginForm() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await login(username, password);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "登录失败，请重试";
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen">
      {/* Left panel — brand & atmosphere */}
      <div className="relative hidden w-[44%] overflow-hidden bg-gradient-to-br from-[#1a4a4a] via-[#2F6868] to-[#1d5555] lg:flex">
        {/* Dot grid pattern — neural network / mind map feel */}
        <svg
          className="absolute inset-0 size-full opacity-[0.12]"
          aria-hidden="true"
        >
          <defs>
            <pattern
              id="dot-grid"
              width="28"
              height="28"
              patternUnits="userSpaceOnUse"
            >
              <circle cx="2" cy="2" r="1.2" fill="white" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#dot-grid)" />
        </svg>

        {/* Soft radial glows */}
        <div className="absolute top-[-20%] left-[-10%] size-[500px] rounded-full bg-white/[0.06] blur-3xl" />
        <div className="absolute right-[-15%] bottom-[-10%] size-[400px] rounded-full bg-white/[0.04] blur-3xl" />

        {/* Content */}
        <div className="relative z-10 flex flex-1 flex-col items-center justify-center px-12 text-white">
          <div className="login-brand-animate flex flex-col items-center text-center">
            <div className="mb-8 flex size-20 items-center justify-center rounded-2xl bg-white/10 shadow-lg backdrop-blur-sm ring-1 ring-white/20">
              <BrainCircuit className="size-10 text-white/90" strokeWidth={1.5} />
            </div>
            <h1 className="mb-4 text-3xl font-semibold tracking-tight">
              心理学教学 Agent
            </h1>
            <p className="max-w-xs text-sm leading-relaxed text-white/60">
              基于苏格拉底式教学法的智能辅导系统，引导思考而非给予答案
            </p>
          </div>
        </div>
      </div>

      {/* Right panel — login form */}
      <div className="flex flex-1 items-center justify-center bg-background px-6 py-12">
        <div className="w-full max-w-[360px] space-y-10 login-form-animate">
          {/* Mobile-only brand header */}
          <div className="flex flex-col items-center gap-3 text-center lg:hidden">
            <div className="flex size-14 items-center justify-center rounded-xl bg-[#2F6868]/10 ring-1 ring-[#2F6868]/20">
              <BrainCircuit className="size-7 text-[#2F6868]" strokeWidth={1.5} />
            </div>
            <h1 className="text-xl font-semibold tracking-tight text-foreground">
              心理学教学 Agent
            </h1>
          </div>

          {/* Form header */}
          <div className="space-y-2">
            <h2 className="text-2xl font-semibold tracking-tight text-foreground">
              欢迎回来
            </h2>
            <p className="text-sm text-muted-foreground">
              登录以继续使用教学平台
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label
                htmlFor="username"
                className="text-sm font-medium text-foreground/80"
              >
                用户名
              </Label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                placeholder="请输入用户名"
                className="login-input flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-base shadow-xs transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:border-[#2F6868]/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2F6868]/15 disabled:cursor-not-allowed disabled:opacity-50 md:text-sm"
              />
            </div>

            <div className="space-y-2">
              <Label
                htmlFor="password"
                className="text-sm font-medium text-foreground/80"
              >
                密码
              </Label>
              <PasswordInput
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="请输入密码"
                className="login-input"
              />
            </div>

            <Button
              type="submit"
              disabled={loading}
              size="lg"
              className="login-button relative w-full rounded-lg bg-[#2F6868] text-base font-medium shadow-md transition-all hover:bg-[#265858] hover:shadow-lg active:scale-[0.985] focus-visible:ring-[#2F6868]/30"
            >
              {loading ? (
                <span className="inline-flex items-center gap-2">
                  <span className="size-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  登录中...
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5">
                  登录
                  <Sparkles className="size-3.5 opacity-70" />
                </span>
              )}
            </Button>
          </form>

          {/* Footer hint */}
          <p className="text-center text-xs text-muted-foreground/60">
            仅限已授权的师生用户登录
          </p>
        </div>
      </div>
    </div>
  );
}

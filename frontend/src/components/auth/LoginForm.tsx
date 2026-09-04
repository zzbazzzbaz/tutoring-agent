"use client";

import { useState, useRef, useCallback } from "react";
import { useAuth } from "./AuthProvider";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { toast } from "sonner";
import {
  BrainCircuit,
  ArrowRight,
  AlertCircle,
  GraduationCap,
  BookOpen,
  Lightbulb,
  Feather,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { z } from "zod";

/* ══════════════════════════════════════════════════════════════════════════════
 * LoginForm — 心理学教学 Agent 登录页（重构版 ·「深夜墨卷 × 素笺」）
 *
 * 美学方向：Scholarly Ink 书斋美学
 *   左「墨卷」 — 深夜墨绿书卷，衬线宋体标题，思考波纹，点阵纹理
 *   右「素笺」 — 暖纸色信笺卡片，学术表单语言，纸感层叠阴影
 *
 * 设计理念：
 *   心理学课堂的"纸本 + 深夜思考"。墨卷端传达智性与静谧，
 *   素笺端传递专注与书写感。既不同于通用科技登录页，
 *   也契合"引导思考，而非给予答案"的教学主张。
 * ══════════════════════════════════════════════════════════════════════════════ */

/* ──────────────────────────────────────────────────────────────────────────────
 * 动画预设 — 物理弹簧 + 渐入渐出（延续既有规范）
 * ────────────────────────────────────────────────────────────────────────────── */
const spring = {
  enter: { type: "spring" as const, damping: 28, stiffness: 260 },
  fast: { type: "spring" as const, damping: 30, stiffness: 300 },
  gentle: { type: "spring" as const, damping: 35, stiffness: 200 },
};

const stagger = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.08, delayChildren: 0.1 },
  },
};

const fadeUp = {
  hidden: { opacity: 0, y: 14, filter: "blur(4px)" },
  visible: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: spring.enter,
  },
};

const fadeIn = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.6 } },
};

/* ──────────────────────────────────────────────────────────────────────────────
 * 「星尘」光点 — 墨卷中的静谧微光，象征思绪浮动
 * ────────────────────────────────────────────────────────────────────────────── */
const PARTICLES = Array.from({ length: 12 }, (_, i) => ({
  id: i,
  x: 6 + ((i * 37 + 13) % 88),
  y: 8 + ((i * 53 + 7) % 84),
  size: 1.5 + ((i * 3) % 3),
  duration: 9 + ((i * 2) % 7),
  delay: (i * 1.1) % 4,
}));

/* ──────────────────────────────────────────────────────────────────────────────
 * 表单验证 — zod schema 实时校验（保持既有规则）
 * ────────────────────────────────────────────────────────────────────────────── */
const usernameSchema = z
  .string()
  .min(1, "请输入用户名")
  .min(2, "用户名至少 2 个字符");

const passwordSchema = z
  .string()
  .min(1, "请输入密码")
  .min(6, "密码至少 6 个字符");

type FieldError = string | null;

function validateField(
  field: "username" | "password",
  value: string,
): FieldError {
  const result =
    field === "username"
      ? usernameSchema.safeParse(value)
      : passwordSchema.safeParse(value);
  return result.success ? null : result.error.issues[0]?.message ?? "输入有误";
}

/* ══════════════════════════════════════════════════════════════════════════════
 * 子组件
 * ══════════════════════════════════════════════════════════════════════════════ */

/* ──────────────────────────────────────────────────────────────────────────────
 * FieldErrorMessage — 内联字段错误提示（保持无障碍）
 * ────────────────────────────────────────────────────────────────────────────── */
function FieldErrorMessage({
  id,
  error,
  show,
}: {
  id: string;
  error: FieldError;
  show: boolean;
}) {
  return (
    <AnimatePresence>
      {show && error && (
        <motion.p
          id={id}
          role="alert"
          initial={{ opacity: 0, height: 0, y: -4 }}
          animate={{ opacity: 1, height: "auto", y: 0 }}
          exit={{ opacity: 0, height: 0, y: -4 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="flex items-center gap-1.5 pt-1 text-xs text-destructive/80"
        >
          <AlertCircle className="size-3.5 shrink-0" />
          <span>{error}</span>
        </motion.p>
      )}
    </AnimatePresence>
  );
}

/* ──────────────────────────────────────────────────────────────────────────────
 * FormInput — 可复用表单字段包装
 * 素笺式：聚焦时底部浮现一缕翡翠"蘸墨痕"
 * ────────────────────────────────────────────────────────────────────────────── */
function FormInput({
  id,
  label,
  error,
  show,
  focused,
  children,
}: {
  id: string;
  label: string;
  error: FieldError;
  show: boolean;
  focused: boolean;
  children: React.ReactNode;
}) {
  return (
    <motion.div variants={fadeUp} className="space-y-1.5">
      <Label
        htmlFor={id}
        className="text-[13px] font-medium tracking-wide text-ink/70"
      >
        {label}
      </Label>
      <div className="relative">
        {children}
        {/* 墨痕扫描线 — 聚焦时的书写暗示 */}
        <motion.div
          className="absolute right-0 -bottom-px left-0 h-px rounded-full bg-gradient-to-r from-transparent via-blue-600 to-transparent"
          initial={false}
          animate={{
            opacity: focused ? 1 : 0,
            scaleX: focused ? 1 : 0,
          }}
          transition={spring.fast}
        />
      </div>
      <FieldErrorMessage id={`${id}-error`} error={error} show={show} />
    </motion.div>
  );
}

/* ──────────────────────────────────────────────────────────────────────────────
 * FocusableInput — 原生 input + 聚焦交互（素笺字段风格）
 * ────────────────────────────────────────────────────────────────────────────── */
function FocusableInput({
  error,
  show,
  focused,
  onFocus,
  onBlur,
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & {
  error: FieldError;
  show: boolean;
  focused: boolean;
}) {
  return (
    <input
      onFocus={onFocus}
      onBlur={onBlur}
      aria-invalid={!!error && show}
      aria-describedby={error && show ? `${props.id}-error` : undefined}
      className={cn(
        "flex h-11 w-full rounded-lg border bg-paper/50 px-3.5 py-2.5 text-base text-ink shadow-sm transition-[background-color,border-color,box-shadow] duration-200 ease-out file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-ink/25 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm",
        focused
          ? "border-blue-600/30 bg-white ring-[3px] ring-blue-600/10 dark:bg-paper-card"
          : error && show
            ? "border-destructive/50 ring-[3px] ring-destructive/8"
            : "border-ink/10 hover:border-ink/20",
        className,
      )}
      {...props}
    />
  );
}

/* ──────────────────────────────────────────────────────────────────────────────
 * FocusablePasswordInput — PasswordInput + 聚焦交互
 * ────────────────────────────────────────────────────────────────────────────── */
function FocusablePasswordInput({
  error,
  show,
  focused,
  onFocus,
  onBlur,
  ...props
}: React.ComponentProps<typeof PasswordInput> & {
  error: FieldError;
  show: boolean;
  focused: boolean;
}) {
  return (
    <PasswordInput
      onFocus={onFocus}
      onBlur={onBlur}
      aria-invalid={!!error && show}
      aria-describedby={error && show ? `${props.id}-error` : undefined}
      className={cn(
        "h-11 bg-paper/50 text-ink transition-[background-color,border-color,box-shadow] duration-200 ease-out",
        focused
          ? "border-blue-600/30 bg-white !ring-[3px] !ring-blue-600/10 dark:bg-paper-card"
          : error && show
            ? "!border-destructive/50 !ring-[3px] !ring-destructive/8"
            : "border-ink/10 hover:border-ink/20",
      )}
      {...props}
    />
  );
}

/* ──────────────────────────────────────────────────────────────────────────────
 * InkBrand — 左「墨卷」品牌面板
 *
 * 【记忆点】一条徐徐流动的"思考波纹" SVG，位于标题之下；
 *          点阵纹理 + 星尘微光 + 衬线宋体排字，营造深夜书斋的静谧智性。
 * ────────────────────────────────────────────────────────────────────────────── */
function InkBrand() {
  return (
    <div className="relative hidden w-[46%] overflow-hidden lg:flex">
      {/* 深蓝渐变底 */}
      <div className="absolute inset-0 bg-gradient-to-br from-[#1e40af] to-[#143a7a]" />

      {/* 装饰光斑 — 供毛玻璃透出柔和色彩 */}
      <div className="pointer-events-none absolute inset-0" aria-hidden="true">
        <motion.div
          className="absolute -top-24 -left-16 size-96 rounded-full bg-blue-400/40 blur-3xl"
          animate={{ opacity: [0.5, 0.85, 0.5] }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute -right-24 bottom-0 size-[26rem] rounded-full bg-indigo-400/30 blur-3xl"
          animate={{ opacity: [0.4, 0.75, 0.4] }}
          transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute top-1/3 left-1/2 size-72 rounded-full bg-cyan-300/25 blur-3xl"
          animate={{ opacity: [0.3, 0.6, 0.3] }}
          transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>

      {/* 点阵纹理 — 谜样网格 */}
      <svg
        className="absolute inset-0 size-full opacity-[0.07]"
        aria-hidden="true"
      >
        <defs>
          <pattern
            id="dot-grid-ink"
            width="30"
            height="30"
            patternUnits="userSpaceOnUse"
          >
            <circle cx="2" cy="2" r="1" fill="#e3edfd" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#dot-grid-ink)" />
      </svg>

      {/* 星尘微光 */}
      <div className="absolute inset-0" aria-hidden="true">
        {PARTICLES.map((p) => (
          <motion.div
            key={p.id}
            className="absolute rounded-full bg-blue-100/30"
            style={{
              left: `${p.x}%`,
              top: `${p.y}%`,
              width: p.size,
              height: p.size,
            }}
            animate={{
              y: [0, -16, 0, 10, 0],
              x: [0, 6, -5, 3, 0],
              opacity: [0.08, 0.3, 0.14, 0.24, 0.08],
            }}
            transition={{
              duration: p.duration,
              repeat: Infinity,
              delay: p.delay,
              ease: "easeInOut",
            }}
          />
        ))}
      </div>

      {/* 微弱呼吸光 */}
      <motion.div
        className="absolute top-[-12%] left-[-6%] size-[420px] rounded-full bg-blue-400/[0.06] blur-3xl"
        animate={{
          scale: [1, 1.08, 1],
          opacity: [0.4, 0.7, 0.4],
        }}
        transition={{ duration: 9, repeat: Infinity, ease: "easeInOut" }}
      />

      <motion.div
        className="relative z-10 m-8 flex flex-1 flex-col justify-between gap-8 overflow-hidden rounded-3xl border border-white/20 bg-white/10 px-10 py-12 shadow-2xl shadow-blue-950/40 backdrop-blur-xl"
        initial="hidden"
        animate="visible"
        variants={stagger}
      >
        {/* 顶部 · 标识与刊头 */}
        <motion.div variants={fadeUp} className="flex items-center gap-3">
          <div className="flex size-11 items-center justify-center rounded-xl border border-blue-300/20 bg-blue-300/5 backdrop-blur-sm">
            <BrainCircuit
              className="size-6 text-blue-200/90"
              strokeWidth={1.4}
            />
          </div>
          <div className="leading-tight">
            <p className="text-[13px] font-semibold tracking-[0.3em] text-blue-100/90 uppercase">
              Psych · Tutor
            </p>
            <p className="text-[11px] tracking-[0.18em] text-blue-200/40">
              基础心理学教学代理
            </p>
          </div>
        </motion.div>

        {/* 中央 · 书卷标题 */}
        <motion.div
          variants={stagger}
          className="my-auto w-full max-w-[400px]"
        >
          <motion.div variants={fadeUp} className="mb-6 flex items-center gap-3">
            <span className="h-px w-10 bg-blue-300/30" />
            <span className="text-[11px] uppercase tracking-[0.35em] text-blue-200/45">
              The Study Series
            </span>
          </motion.div>

          <motion.h1
            variants={fadeUp}
            className="[font-family:'Songti_SC','STSong','SimSun','Noto_Serif_SC',serif] text-[42px] font-semibold leading-[1.25] tracking-[0.04em] text-white"
          >
            以思考
            <br />
            照亮学习的路
          </motion.h1>

          <motion.p
            variants={fadeUp}
            className="mt-6 font-serif text-[13px] italic tracking-[0.08em] text-blue-100/40"
          >
            Thought · Reflection · Growth
          </motion.p>

          {/* 【记忆点】思考波纹 — 徐徐流动的波形 */}
          <motion.div variants={fadeUp} className="mt-10">
            <svg
              viewBox="0 0 440 64"
              className="h-14 w-full max-w-[420px]"
              fill="none"
              aria-hidden="true"
            >
              <defs>
                <linearGradient
                  id="wave-ink"
                  x1="0"
                  y1="0"
                  x2="1"
                  y2="0"
                >
                  <stop offset="0%" stopColor="#60a5fa" stopOpacity="0" />
                  <stop offset="25%" stopColor="#93c5fd" stopOpacity="0.9" />
                  <stop offset="75%" stopColor="#60a5fa" stopOpacity="0.7" />
                  <stop offset="100%" stopColor="#bfdbfe" stopOpacity="0" />
                </linearGradient>
              </defs>
              <motion.path
                d="M0,32 C30,8 60,56 90,32 S150,8 180,32 S240,56 270,32 S330,8 360,32 S420,56 440,32"
                stroke="url(#wave-ink)"
                strokeWidth="1.5"
                strokeLinecap="round"
                animate={{
                  opacity: [0.35, 0.9, 0.35],
                  pathLength: [0.4, 1, 0.4],
                }}
                transition={{
                  duration: 6,
                  repeat: Infinity,
                  ease: "easeInOut",
                }}
              />
            </svg>
            <p className="mt-3 text-[11px] tracking-[0.2em] text-blue-200/30">
              引导思考，而非给予答案
            </p>
          </motion.div>
        </motion.div>

        {/* 底部 · 教学注脚 */}
        <motion.div
          variants={fadeUp}
          className="flex items-center justify-between"
        >
          <p className="text-[11px] tracking-[0.12em] text-blue-200/35">
            © 2026 心理学教学 Agent
          </p>
          <div className="flex items-center gap-2 text-[11px] tracking-[0.12em] text-blue-200/35">
            <span className="relative flex size-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400/60" />
              <span className="relative inline-flex size-1.5 rounded-full bg-blue-400" />
            </span>
            在线课堂
          </div>
        </motion.div>
      </motion.div>
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────────────────────
 * MobileFeatures — 移动端三项特色（素笺语感）
 * ────────────────────────────────────────────────────────────────────────────── */
function MobileFeatures() {
  const features = [
    {
      icon: Feather,
      title: "启发式教学",
      desc: "提问引导思考",
    },
    {
      icon: BookOpen,
      title: "知识检索",
      desc: "AI 精准图谱",
    },
    {
      icon: GraduationCap,
      title: "个性化学习",
      desc: "契合个人节奏",
    },
  ];

  return (
    <motion.div
      variants={stagger}
      className="mt-8 grid grid-cols-3 gap-2.5 lg:hidden"
    >
      {features.map((f) => (
        <motion.div
          key={f.title}
          variants={fadeUp}
          className="flex flex-col items-center gap-1.5 rounded-xl border border-blue-800/15 bg-paper/70 px-2 py-3.5 text-center"
        >
          <f.icon className="size-4 text-blue-800/70" strokeWidth={1.5} />
          <p className="text-[12px] font-medium text-ink/80">{f.title}</p>
          <p className="text-[10px] text-ink/40">{f.desc}</p>
        </motion.div>
      ))}
    </motion.div>
  );
}

/* ──────────────────────────────────────────────────────────────────────────────
 * SubmitButton — 登录提交按钮（墨卷色填充 + Shimmer）
 * ────────────────────────────────────────────────────────────────────────────── */
function SubmitButton({ loading }: { loading: boolean }) {
  return (
    <motion.div variants={fadeUp} className="pt-1">
      <Button
        type="submit"
        disabled={loading}
        size="lg"
        variant="brand"
        className="login-button group relative w-full overflow-hidden rounded-lg bg-gradient-to-r from-[#2d59df] to-[#2249c4] text-[15px] font-medium text-blue-50 shadow-lg shadow-blue-900/20 transition-[box-shadow] duration-200 hover:shadow-[0_8px_28px_-8px_rgba(34,73,196,0.5)]"
        asChild
      >
        <motion.button
          whileHover={loading ? undefined : { scale: 1.008 }}
          whileTap={loading ? undefined : { scale: 0.985 }}
          transition={spring.fast}
        >
          {/* Shimmer 光扫 */}
          <span className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-blue-200/15 to-transparent transition-transform duration-500 ease-out group-hover:translate-x-full" />

          <AnimatePresence mode="wait">
            {loading ? (
              <motion.span
                key="loading"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={spring.fast}
                className="inline-flex items-center gap-2"
              >
                <motion.span
                  className="size-4 rounded-full border-2 border-blue-200/30 border-t-blue-100"
                  animate={{ rotate: 360 }}
                  transition={{
                    duration: 0.8,
                    repeat: Infinity,
                    ease: "linear",
                  }}
                />
                <span>登录中…</span>
              </motion.span>
            ) : (
              <motion.span
                key="idle"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={spring.fast}
                className="inline-flex items-center gap-1.5"
              >
                <span>开始学习</span>
                <motion.span
                  className="inline-flex"
                  animate={{ x: [0, 3, 0] }}
                  transition={{
                    duration: 2,
                    repeat: Infinity,
                    ease: "easeInOut",
                  }}
                >
                  <ArrowRight className="size-4 opacity-70" />
                </motion.span>
              </motion.span>
            )}
          </AnimatePresence>
        </motion.button>
      </Button>
    </motion.div>
  );
}

/* ══════════════════════════════════════════════════════════════════════════════
 * LoginForm — 主组件
 * 状态管理 / 验证策略：与先前版本一致，仅外观重构
 * ══════════════════════════════════════════════════════════════════════════════ */
export function LoginForm() {
  const { login } = useAuth();

  /* ── form state ── */
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  /* ── validation state ── */
  const [errors, setErrors] = useState<{
    username: FieldError;
    password: FieldError;
  }>({ username: null, password: null });
  const [touched, setTouched] = useState<{
    username: boolean;
    password: boolean;
  }>({ username: false, password: false });
  const [submitAttempted, setSubmitAttempted] = useState(false);

  /* ── UI state ── */
  const [loading, setLoading] = useState(false);
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const submitRef = useRef(false);

  /* ── derived ── */
  const showUsernameError = touched.username || submitAttempted;
  const showPasswordError = touched.password || submitAttempted;

  /* ── 实时验证（保持既有逻辑） ── */
  const validateAndSetError = useCallback(
    (field: "username" | "password", value: string) => {
      const error = validateField(field, value);
      setErrors((prev) => ({ ...prev, [field]: error }));
      return error;
    },
    [],
  );

  const handleBlur = useCallback(
    (field: "username" | "password", value: string) => {
      setTouched((prev) => ({ ...prev, [field]: true }));
      validateAndSetError(field, value);
    },
    [validateAndSetError],
  );

  const handleUsernameChange = useCallback(
    (value: string) => {
      setUsername(value);
      if (showUsernameError) {
        validateAndSetError("username", value);
      }
    },
    [showUsernameError, validateAndSetError],
  );

  const handlePasswordChange = useCallback(
    (value: string) => {
      setPassword(value);
      if (showPasswordError) {
        validateAndSetError("password", value);
      }
    },
    [showPasswordError, validateAndSetError],
  );

  /* ── 提交处理 — 防抖 + 全字段校验（保持既有逻辑） ── */
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitRef.current) return;

    const usernameError = validateAndSetError("username", username);
    const passwordError = validateAndSetError("password", password);
    setTouched({ username: true, password: true });
    setSubmitAttempted(true);

    if (usernameError || passwordError) return;

    submitRef.current = true;
    setLoading(true);
    try {
      await login(username, password);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "登录时遇到问题，请检查网络后重试";
      toast.error(message, {
        duration: 5000,
        description: "如果问题持续存在，请联系老师或管理员",
      });
    } finally {
      setLoading(false);
      submitRef.current = false;
    }
  }

  return (
    <div className="flex min-h-dvh overflow-x-clip bg-[#f0f2f5] dark:bg-[#0f172a]">
      {/* ═══════ 左「墨卷」— 品牌与氛围 ═══════ */}
      <InkBrand />

      {/* ═══════ 右「素笺」— 登录表单 ═══════ */}
      <div className="relative flex flex-1 items-center justify-center overflow-hidden px-6 py-12">
        {/* 纸面肌理 */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute inset-0 opacity-[0.5] [background-image:radial-gradient(rgba(15,23,42,0.05)_1px,transparent_1px)] [background-size:22px_22px]" />
          <motion.div
            className="absolute -top-24 -right-24 size-80 rounded-full bg-blue-800/5 blur-3xl"
            animate={{ opacity: [0.3, 0.6, 0.3] }}
            transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
          />
        </div>

        <motion.div
          className="relative w-full max-w-[400px]"
          initial="hidden"
          animate="visible"
          variants={stagger}
        >
          {/* ── 移动端品牌头 ── */}
          <motion.div
            variants={fadeIn}
            className="mb-8 flex flex-col items-center gap-3 text-center lg:hidden"
          >
            <div className="flex size-14 items-center justify-center rounded-2xl border border-blue-800/15 bg-gradient-to-br from-[#2d59df] to-[#2249c4] shadow-lg shadow-blue-900/20">
              <BrainCircuit className="size-7 text-blue-50" strokeWidth={1.5} />
            </div>
            <h1 className="[font-family:'Songti_SC','STSong','SimSun','Noto_Serif_SC',serif] text-xl font-semibold tracking-[0.08em] text-ink">
              心理学教学 Agent
            </h1>
          </motion.div>

          {/* ── 「素笺」信笺卡片 ── */}
          <motion.div
            variants={fadeUp}
            className="relative rounded-2xl border border-ink/8 bg-paper-card px-8 py-9 shadow-[0_2px_6px_rgba(15,23,42,0.06),0_18px_44px_-18px_rgba(15,23,42,0.28)]"
          >
            {/* 笺头细线 */}
            <div className="pointer-events-none absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-blue-700/30 to-transparent" />

            {/* 笺首 */}
            <motion.div variants={fadeUp} className="mb-7">
              <h2 className="[font-family:'Songti_SC','STSong','SimSun','Noto_Serif_SC',serif] text-[26px] font-semibold tracking-[0.06em] text-ink">
                欢迎回来
              </h2>
              <p className="mt-1.5 text-[13px] tracking-wide text-ink/45">
                登录以继续你的学习之旅
              </p>
            </motion.div>

            {/* 移动端特色 */}
            <MobileFeatures />

            {/* ── 表单 ── */}
            <motion.form
              onSubmit={handleSubmit}
              noValidate
              className="mt-7 space-y-5"
              variants={stagger}
            >
              <FormInput
                id="username"
                label="用户名"
                error={errors.username}
                show={showUsernameError}
                focused={focusedField === "username"}
              >
                <FocusableInput
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => handleUsernameChange(e.target.value)}
                  error={errors.username}
                  show={showUsernameError}
                  focused={focusedField === "username"}
                  onFocus={() => setFocusedField("username")}
                  onBlur={() => {
                    setFocusedField(null);
                    handleBlur("username", username);
                  }}
                  required
                  autoFocus
                  autoComplete="username"
                  placeholder="请输入用户名"
                />
              </FormInput>

              <FormInput
                id="password"
                label="密码"
                error={errors.password}
                show={showPasswordError}
                focused={focusedField === "password"}
              >
                <FocusablePasswordInput
                  id="password"
                  value={password}
                  onChange={(e) => handlePasswordChange(e.target.value)}
                  error={errors.password}
                  show={showPasswordError}
                  focused={focusedField === "password"}
                  onFocus={() => setFocusedField("password")}
                  onBlur={() => {
                    setFocusedField(null);
                    handleBlur("password", password);
                  }}
                  required
                  autoComplete="current-password"
                  placeholder="请输入密码"
                />
              </FormInput>

              <SubmitButton loading={loading} />
            </motion.form>

            {/* 笺尾 · 访问说明 */}
            <motion.p
              variants={fadeIn}
              className="mt-6 text-center text-[11px] tracking-[0.15em] text-ink/30"
            >
              仅限已授权的师生用户登录
            </motion.p>
          </motion.div>
        </motion.div>
      </div>
    </div>
  );
}
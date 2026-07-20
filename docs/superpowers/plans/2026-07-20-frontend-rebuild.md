# Frontend Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new React 19 + TypeScript frontend in `frontend/` with Tab-based SPA, Bearer token auth, chat with SSE streaming, student management, and projects CRUD.

**Architecture:** Tab-based SPA (Radix Tabs, not router sub-routes). HashRouter only for login vs. app guard. Three Zustand stores (auth, chat, settings) with persist. axios for HTTP with Bearer token interceptor, fetch for SSE. shadcn/ui + Tailwind CSS v4. i18next (zh/en). Dark mode via CSS variables.

**Tech Stack:** React 19, TypeScript ~6.0, Vite 8, Bun, Tailwind CSS v4, shadcn/ui (new-york/zinc), Zustand 5, axios, i18next, react-markdown, KaTeX, lucide-react, sonner.

## Global Constraints

- Package manager: **Bun** (`bun install`, `bun run dev`, `bun run build`)
- Indentation: 2 spaces, single quotes (enforced by @stylistic ESLint)
- Path alias: `@/*` -> `./src/*` (tsconfig paths + vite resolve.alias)
- No frontend unit tests; verification = `bun run lint && bun run typecheck && bun run build`
- Backend API base: `http://localhost:8000` (dev proxy via vite.config.ts)
- Auth: `Authorization: Bearer <token>` header (NOT X-User-Id)
- Backend seed accounts: teacher1/teacher123, student1/student123, student2/student123
- shadcn/ui config: style=new-york, baseColor=zinc, cssVariables=true, iconLibrary=lucide
- Reference source for LightRAG webui patterns: `docs/_chat/LightRAG/lightrag_webui/`
- Reference source for existing prototype chat logic: `docs/_chat/frontend/`

---

## File Structure

```
frontend/
├── package.json
├── bun.lock
├── vite.config.ts
├── tsconfig.json
├── tsconfig.node.json
├── tailwind.config.js
├── eslint.config.js
├── prettier.config.json
├── components.json
├── index.html
├── .env.development
└── src/
    ├── main.tsx                    # Entry: ReactDOM render + i18n init
    ├── App.tsx                     # AppShell: Header + Tabs + SettingsMenu
    ├── AppRouter.tsx               # HashRouter + RequireAuth
    ├── index.css                   # Tailwind + shadcn CSS variables + dark mode
    ├── i18n.ts                     # i18next init (zh/en)
    ├── vite-env.d.ts
    ├── api/
    │   ├── client.ts               # axios instance + Bearer token + 401 redirect
    │   ├── auth.ts                 # login / logout / me / changePassword
    │   ├── sessions.ts             # CRUD + messages + questions
    │   ├── chat.ts                 # SSE: streamMessage + resumeQuiz
    │   ├── projects.ts             # CRUD
    │   └── users.ts                # listStudents / listTeachers / import / reset / delete
    ├── stores/
    │   ├── auth.ts                 # token + user (persist)
    │   ├── chat.ts                 # SSE state machine (sessions, items, streamStatus)
    │   └── settings.ts             # theme + language + activeTab (persist)
    ├── features/
    │   ├── login/
    │   │   └── LoginPage.tsx
    │   ├── chat/
    │   │   ├── ChatTab.tsx         # Two-pane: SessionList + ChatView
    │   │   ├── SessionList.tsx
    │   │   ├── NewSessionDialog.tsx
    │   │   ├── ChatView.tsx        # Message stream + input
    │   │   ├── MessageBubble.tsx   # Markdown render + copy
    │   │   ├── QuizCard.tsx        # Quiz interrupt card
    │   │   └── ChatInput.tsx       # Input + send button
    │   ├── students/
    │   │   └── StudentsTab.tsx     # List + import + reset + delete
    │   ├── projects/
    │   │   ├── ProjectsTab.tsx     # List (student read-only, teacher CRUD)
    │   │   └── ProjectEditor.tsx   # Markdown editor + preview
    │   └── shared/
    │       ├── MarkdownRenderer.tsx
    │       └── SettingsMenu.tsx     # Theme / language / change password / logout
    ├── components/
    │   └── ui/                     # shadcn/ui components (added via CLI)
    ├── hooks/
    │   ├── useTheme.ts             # light/dark/system + OS preference
    │   └── useDebounce.ts
    ├── lib/
    │   ├── cn.ts                   # clsx + tailwind-merge
    │   ├── utils.ts                # createSelectors wrapper
    │   ├── formatDate.ts           # formatRelativeTime + formatDateTime
    │   └── parseSSE.ts             # SSE stream parser (async generator)
    ├── locales/
    │   ├── zh.json
    │   └── en.json
    └── types/
        ├── session.ts
        ├── message.ts
        ├── question.ts
        ├── project.ts
        ├── chat.ts
        └── user.ts
```

---

### Task 1: Project Scaffold + Configs + Dependencies

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/eslint.config.js`
- Create: `frontend/prettier.config.json`
- Create: `frontend/components.json`
- Create: `frontend/index.html`
- Create: `frontend/.env.development`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx` (placeholder)
- Create: `frontend/src/index.css`
- Create: `frontend/src/vite-env.d.ts`

**Interfaces:**
- Produces: A buildable Vite project with all dependencies installed.

- [ ] **Step 1: Create package.json**

```json
{
  "name": "teaching-agent-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "lint": "eslint .",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@radix-ui/react-alert-dialog": "^1.1.19",
    "@radix-ui/react-dialog": "^1.1.19",
    "@radix-ui/react-dropdown-menu": "^2.1.20",
    "@radix-ui/react-label": "^2.1.11",
    "@radix-ui/react-scroll-area": "^1.2.14",
    "@radix-ui/react-select": "^2.3.3",
    "@radix-ui/react-separator": "^1.1.11",
    "@radix-ui/react-slot": "^1.3.0",
    "@radix-ui/react-tabs": "^1.1.17",
    "@radix-ui/react-tooltip": "^1.2.12",
    "axios": "^1.18.1",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "i18next": "^26.0.0",
    "katex": "^0.17.0",
    "lucide-react": "^1.24.0",
    "react": "^19.2.7",
    "react-dom": "^19.2.7",
    "react-i18next": "^17.0.0",
    "react-markdown": "^10.1.0",
    "react-router-dom": "^7.18.1",
    "rehype-katex": "^7.0.1",
    "rehype-raw": "^7.0.0",
    "remark-gfm": "^4.0.1",
    "remark-math": "^6.0.0",
    "sonner": "^2.0.7",
    "tailwind-merge": "^3.6.0",
    "tailwind-scrollbar": "^4.0.2",
    "zustand": "^5.0.14"
  },
  "devDependencies": {
    "@eslint/js": "^9.19.0",
    "@stylistic/eslint-plugin": "^5.10.0",
    "@tailwindcss/typography": "^0.5.20",
    "@tailwindcss/vite": "^4.3.2",
    "@types/katex": "^0.16.8",
    "@types/node": "^25.9.5",
    "@types/react": "^19.2.17",
    "@types/react-dom": "^19.2.3",
    "@vitejs/plugin-react": "^6.0.3",
    "eslint": "^9.19.0",
    "eslint-config-prettier": "^10.1.8",
    "eslint-plugin-react": "^7.37.5",
    "eslint-plugin-react-hooks": "^7.1.1",
    "eslint-plugin-react-refresh": "^0.5.3",
    "globals": "^17.7.0",
    "prettier": "^3.9.5",
    "prettier-plugin-tailwindcss": "^0.8.0",
    "tailwindcss": "^4.3.2",
    "tailwindcss-animate": "^1.0.7",
    "typescript": "~6.0.3",
    "typescript-eslint": "^8.63.0",
    "vite": "^8.1.4"
  }
}
```

- [ ] **Step 2: Create vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import path from 'path'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/health': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/users': 'http://localhost:8000',
      '/projects': 'http://localhost:8000',
      '/sessions': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
    },
  },
})
```

- [ ] **Step 3: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src", "vite.config.ts"]
}
```

- [ ] **Step 4: Create tsconfig.node.json**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 5: Create tailwind.config.js**

Copy from `docs/_chat/LightRAG/lightrag_webui/tailwind.config.js` verbatim (same shadcn/ui theme + typography config).

- [ ] **Step 6: Create eslint.config.js**

```javascript
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import stylistic from '@stylistic/eslint-plugin'
import tseslint from 'typescript-eslint'
import prettier from 'eslint-config-prettier'
import react from 'eslint-plugin-react'

export default tseslint.config(
  { ignores: ['dist'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended, prettier],
    files: ['**/*.{ts,tsx,js,jsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    settings: { react: { version: '19.0' } },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      '@stylistic': stylistic,
      react,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      ...react.configs.recommended.rules,
      ...react.configs['jsx-runtime'].rules,
      '@stylistic/indent': ['error', 2],
      '@stylistic/quotes': ['error', 'single'],
      '@typescript-eslint/no-explicit-any': ['off'],
    },
  },
)
```

- [ ] **Step 7: Create prettier.config.json**

```json
{
  "plugins": ["prettier-plugin-tailwindcss"],
  "semi": false,
  "singleQuote": true,
  "tabWidth": 2,
  "trailingComma": "all"
}
```

- [ ] **Step 8: Create components.json (shadcn/ui config)**

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "config": "",
    "css": "src/index.css",
    "baseColor": "zinc",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/cn",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  },
  "iconLibrary": "lucide"
}
```

- [ ] **Step 9: Create index.html**

```html
<!doctype html>
<html lang="zh">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>教学 Agent</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 10: Create .env.development**

```
VITE_API_BASE=
```

- [ ] **Step 11: Create src/index.css**

Copy from `docs/_chat/LightRAG/lightrag_webui/src/index.css` verbatim (same CSS variables, dark mode, scrollbar, KaTeX styles). Remove the Mermaid v11 section (`.mermaidTooltip`).

- [ ] **Step 12: Create src/vite-env.d.ts**

```typescript
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
```

- [ ] **Step 13: Create src/main.tsx**

```typescript
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import AppRouter from './AppRouter'
import './index.css'
import './i18n'
import 'katex/dist/katex.min.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HashRouter>
      <AppRouter />
    </HashRouter>
  </StrictMode>,
)
```

- [ ] **Step 14: Create src/App.tsx (placeholder)**

```typescript
export default function App() {
  return <div>Teaching Agent</div>
}
```

- [ ] **Step 15: Create src/AppRouter.tsx (placeholder)**

```typescript
export default function AppRouter() {
  return <div>Teaching Agent</div>
}
```

- [ ] **Step 16: Run bun install**

```bash
cd frontend && bun install
```

Expected: `bun.lock` created, node_modules populated.

- [ ] **Step 17: Verify build**

```bash
cd frontend && bun run build
```

Expected: Build succeeds, `dist/` created.

- [ ] **Step 18: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold project with Vite + React + Tailwind + shadcn/ui"
```

---

### Task 2: shadcn/ui Base Components + Lib Utilities + Types

**Files:**
- Create: `frontend/src/lib/cn.ts`
- Create: `frontend/src/lib/utils.ts`
- Create: `frontend/src/lib/formatDate.ts`
- Create: `frontend/src/lib/parseSSE.ts`
- Create: `frontend/src/hooks/useDebounce.ts`
- Create: `frontend/src/types/session.ts`
- Create: `frontend/src/types/message.ts`
- Create: `frontend/src/types/question.ts`
- Create: `frontend/src/types/project.ts`
- Create: `frontend/src/types/chat.ts`
- Create: `frontend/src/types/user.ts`
- Create: `frontend/src/components/ui/*.tsx` (via shadcn CLI)

**Interfaces:**
- Produces: `cn()` helper, `createSelectors` wrapper, `parseSSE()` async generator, all TypeScript types, shadcn/ui base components.

- [ ] **Step 1: Add shadcn/ui components via CLI**

```bash
cd frontend && bunx --bun shadcn@latest add button input textarea label card badge tabs scroll-area dialog alert-dialog dropdown-menu select separator tooltip separator
```

Expected: `src/components/ui/*.tsx` files created.

Note: If the shadcn CLI prompts for `utils` alias, point it to `@/lib/cn`. If it fails, manually copy the component files from `docs/_chat/LightRAG/lightrag_webui/src/components/ui/` and fix imports to use `@/lib/cn` instead of `@/lib/utils`.

- [ ] **Step 2: Create src/lib/cn.ts**

```typescript
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

- [ ] **Step 3: Create src/lib/utils.ts (createSelectors)**

```typescript
import { StoreApi, UseBoundStore } from 'zustand'

type WithSelectors<S> = S extends { getState: () => infer T }
  ? S & { use: { [K in keyof T]: () => T[K] } }
  : never

export const createSelectors = <S extends UseBoundStore<StoreApi<object>>>(_store: S) => {
  const store = _store as WithSelectors<typeof _store>
  store.use = {}
  for (const k of Object.keys(store.getState())) {
    ;(store.use as any)[k] = () => store((s) => s[k as keyof typeof s])
  }
  return store
}
```

- [ ] **Step 4: Create src/lib/formatDate.ts**

```typescript
export function formatRelativeTime(iso: string): string {
  const now = Date.now()
  const then = new Date(iso).getTime()
  const diff = now - then
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (seconds < 60) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  if (hours < 24) return `${hours} 小时前`
  if (days < 30) return `${days} 天前`
  return formatDateTime(iso)
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
```

- [ ] **Step 5: Create src/lib/parseSSE.ts**

```typescript
export interface SSEEvent {
  event: string
  data: any
}

export async function* parseSSE(response: Response): AsyncGenerator<SSEEvent> {
  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let idx: number
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)

      const lines = frame.split('\n')
      const event = lines.find(l => l.startsWith('event: '))?.slice(7) || 'message'
      const dataLine = lines.find(l => l.startsWith('data: '))?.slice(6) || '{}'
      try {
        yield { event, data: JSON.parse(dataLine) }
      } catch {
        yield { event, data: { raw: dataLine } }
      }
    }
  }
}
```

- [ ] **Step 6: Create src/hooks/useDebounce.ts**

```typescript
import { useEffect, useState } from 'react'

export function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}
```

- [ ] **Step 7: Create src/types/user.ts**

```typescript
export interface UserOut {
  id: string
  username: string
  role: 'student' | 'teacher'
  name: string
  created_at: string
}

export interface LoginResponse {
  token: string
  user: {
    id: string
    username: string
    role: 'student' | 'teacher'
    name: string
  }
}
```

- [ ] **Step 8: Create src/types/session.ts**

```typescript
export interface SessionOut {
  id: string
  user_id: string
  mode: 'free' | 'project'
  project_id: string | null
  project_name: string | null
  title: string | null
  status: 'active' | 'ended'
  last_active_at: string
  created_at: string
}

export interface SessionCreate {
  mode: 'free' | 'project'
  project_id?: string
}
```

- [ ] **Step 9: Create src/types/message.ts**

```typescript
export interface MessageOut {
  id: string
  session_id: string
  role: 'user' | 'agent'
  content: string
  created_at: string
}
```

- [ ] **Step 10: Create src/types/question.ts**

```typescript
export interface QuestionOut {
  id: string
  session_id: string
  topic: string
  q_type: 'single' | 'multi' | 'short'
  stem: string
  options: string[] | null
  answer: string
  analysis: string | null
  status: 'pending' | 'answered' | 'skipped'
  user_answer: string | null
  created_at: string
  answered_at: string | null
}

export interface QuizInterruptData {
  question_id: string
  topic: string
  q_type: 'single' | 'multi' | 'short'
  stem: string
  options: string[] | null
}
```

- [ ] **Step 11: Create src/types/project.ts**

```typescript
export interface ProjectOut {
  id: string
  name: string
  background_md: string
  status: 'draft' | 'published'
  created_at: string
  updated_at: string
}

export interface ProjectCreate {
  name: string
  background_md: string
  status?: 'draft' | 'published'
}

export interface ProjectUpdate {
  name?: string
  background_md?: string
  status?: 'draft' | 'published'
}
```

- [ ] **Step 12: Create src/types/chat.ts**

```typescript
import type { MessageOut } from './message'
import type { QuestionOut, QuizInterruptData } from './question'

export type StreamStatus = 'idle' | 'streaming' | 'quiz_interrupted' | 'error'

export type SSEEvent =
  | { event: 'text'; data: { content: string } }
  | { event: 'quiz_interrupt'; data: QuizInterruptData }
  | { event: 'done'; data: Record<string, never> }
  | { event: 'error'; data: { message: string; code: string } }

export type ChatItem =
  | { type: 'message'; data: MessageOut }
  | { type: 'quiz'; data: QuestionOut }
  | { type: 'streaming'; data: { content: string } }
```

- [ ] **Step 13: Verify lint + typecheck + build**

```bash
cd frontend && bun run lint && bun run typecheck && bun run build
```

Expected: All pass. Fix any import path issues in shadcn/ui components (they should import from `@/lib/cn`, not `@/lib/utils`).

- [ ] **Step 14: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): add shadcn/ui components, lib utils, and TypeScript types"
```

---

### Task 3: API Layer + Stores + i18n + Theme

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/auth.ts`
- Create: `frontend/src/api/sessions.ts`
- Create: `frontend/src/api/chat.ts`
- Create: `frontend/src/api/projects.ts`
- Create: `frontend/src/api/users.ts`
- Create: `frontend/src/stores/auth.ts`
- Create: `frontend/src/stores/settings.ts`
- Create: `frontend/src/stores/chat.ts`
- Create: `frontend/src/i18n.ts`
- Create: `frontend/src/locales/zh.json`
- Create: `frontend/src/locales/en.json`
- Create: `frontend/src/hooks/useTheme.ts`

**Interfaces:**
- Consumes: Types from Task 2 (`@/types/*`), `parseSSE` from `@/lib/parseSSE`, `createSelectors` from `@/lib/utils`
- Produces: `useAuthStore`, `useChatStore`, `useSettingsStore` (all with `.use` selectors), API functions, i18n instance, `useTheme` hook.

- [ ] **Step 1: Create src/api/client.ts**

```typescript
import axios from 'axios'
import { toast } from 'sonner'
import { useAuthStore } from '@/stores/auth'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '',
  timeout: 30000,
})

apiClient.interceptors.request.use(config => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.hash = '#/login'
    }
    const detail = err.response?.data?.detail?.error
    if (detail) {
      toast.error(detail.message)
    } else if (err.response) {
      toast.error(`HTTP ${err.response.status}`)
    } else {
      toast.error(err.message || '网络错误')
    }
    return Promise.reject(err)
  },
)

export function getAuthToken(): string | null {
  return useAuthStore.getState().token
}
```

- [ ] **Step 2: Create src/stores/auth.ts**

```typescript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { createSelectors } from '@/lib/utils'

interface User {
  id: string
  username: string
  role: 'student' | 'teacher'
  name: string
}

interface AuthState {
  token: string | null
  user: User | null
  login: (token: string, user: User) => void
  logout: () => void
}

const useAuthStore = create<AuthState>()(
  persist(
    set => ({
      token: null,
      user: null,
      login: (token, user) => set({ token, user }),
      logout: () => set({ token: null, user: null }),
    }),
    { name: 'tutoring-auth' },
  ),
)

export const useAuth = createSelectors(useAuthStore)
export { useAuthStore }
```

- [ ] **Step 3: Create src/stores/settings.ts**

```typescript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { createSelectors } from '@/lib/utils'

type Theme = 'light' | 'dark' | 'system'
type Language = 'zh' | 'en'

interface SettingsState {
  theme: Theme
  language: Language
  activeTab: string
  setTheme: (theme: Theme) => void
  setLanguage: (language: Language) => void
  setActiveTab: (tab: string) => void
}

const useSettingsStore = create<SettingsState>()(
  persist(
    set => ({
      theme: 'system',
      language: 'zh',
      activeTab: 'chat',
      setTheme: theme => set({ theme }),
      setLanguage: language => set({ language }),
      setActiveTab: activeTab => set({ activeTab }),
    }),
    { name: 'tutoring-settings' },
  ),
)

export const useSettings = createSelectors(useSettingsStore)
export { useSettingsStore }
```

- [ ] **Step 4: Create src/api/auth.ts**

```typescript
import { apiClient } from './client'
import type { LoginResponse } from '@/types/user'

export const authApi = {
  login: async (username: string, password: string) => {
    const { data } = await apiClient.post<LoginResponse>('/auth/login', {
      username,
      password,
    })
    return data
  },
  logout: async () => {
    await apiClient.post('/auth/logout')
  },
  me: async () => {
    const { data } = await apiClient.get('/auth/me')
    return data
  },
  changePassword: async (oldPassword: string, newPassword: string) => {
    await apiClient.post('/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
    })
  },
}
```

- [ ] **Step 5: Create src/api/sessions.ts**

```typescript
import { apiClient } from './client'
import type { SessionOut, SessionCreate } from '@/types/session'
import type { MessageOut } from '@/types/message'
import type { QuestionOut } from '@/types/question'

export const sessionsApi = {
  list: async (params?: { status?: string; mode?: string; limit?: number; offset?: number }) => {
    const { data } = await apiClient.get<SessionOut[]>('/sessions', { params })
    return data
  },
  get: async (id: string) => {
    const { data } = await apiClient.get<SessionOut>(`/sessions/${id}`)
    return data
  },
  create: async (body: SessionCreate) => {
    const { data } = await apiClient.post<SessionOut>('/sessions', body)
    return data
  },
  delete: async (id: string) => {
    await apiClient.delete(`/sessions/${id}`)
  },
  listMessages: async (id: string, params?: { limit?: number; offset?: number }) => {
    const { data } = await apiClient.get<MessageOut[]>(`/sessions/${id}/messages`, { params })
    return data
  },
  listQuestions: async (id: string, params?: { status?: string }) => {
    const { data } = await apiClient.get<QuestionOut[]>(`/sessions/${id}/questions`, { params })
    return data
  },
}
```

- [ ] **Step 6: Create src/api/chat.ts**

```typescript
import { getAuthToken } from './client'
import { parseSSE, type SSEEvent } from '@/lib/parseSSE'

const API_BASE = import.meta.env.VITE_API_BASE || ''

export async function* streamMessage(
  sessionId: string,
  content: string,
  signal?: AbortSignal,
): AsyncGenerator<SSEEvent> {
  const token = getAuthToken()
  const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ content }),
    signal,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  yield* parseSSE(res)
}

export async function* resumeQuiz(
  sessionId: string,
  action: 'answer' | 'skip',
  answer: string | null,
  signal?: AbortSignal,
): AsyncGenerator<SSEEvent> {
  const token = getAuthToken()
  const body: Record<string, unknown> = { action }
  if (action === 'answer' && answer !== null) {
    body.answer = answer
  }
  const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}/quiz/resume`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  yield* parseSSE(res)
}
```

- [ ] **Step 7: Create src/api/projects.ts**

```typescript
import { apiClient } from './client'
import type { ProjectOut, ProjectCreate, ProjectUpdate } from '@/types/project'

export const projectsApi = {
  list: async (statusFilter?: string) => {
    const { data } = await apiClient.get<ProjectOut[]>('/projects', {
      params: statusFilter ? { status_filter: statusFilter } : undefined,
    })
    return data
  },
  get: async (id: string) => {
    const { data } = await apiClient.get<ProjectOut>(`/projects/${id}`)
    return data
  },
  create: async (body: ProjectCreate) => {
    const { data } = await apiClient.post<ProjectOut>('/projects', body)
    return data
  },
  update: async (id: string, body: ProjectUpdate) => {
    const { data } = await apiClient.patch<ProjectOut>(`/projects/${id}`, body)
    return data
  },
  delete: async (id: string) => {
    await apiClient.delete(`/projects/${id}`)
  },
}
```

- [ ] **Step 8: Create src/api/users.ts**

```typescript
import { apiClient } from './client'
import type { UserOut } from '@/types/user'

export interface ImportResult {
  total: number
  created: number
  skipped: number
  errors: string[]
}

export const usersApi = {
  listStudents: async () => {
    const { data } = await apiClient.get<UserOut[]>('/users/students')
    return data
  },
  listTeachers: async () => {
    const { data } = await apiClient.get<UserOut[]>('/users/teachers')
    return data
  },
  deleteUser: async (id: string) => {
    await apiClient.delete(`/users/${id}`)
  },
  resetPassword: async (id: string) => {
    const { data } = await apiClient.post<{ message: string }>(`/users/${id}/reset-password`)
    return data
  },
  importStudents: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await apiClient.post<ImportResult>('/users/students/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },
}
```

- [ ] **Step 9: Create src/stores/chat.ts**

This is the SSE state machine. Reference: `docs/_chat/frontend/src/stores/chat.ts` (adapt auth from X-User-Id to Bearer token, add sessions list).

```typescript
import { create } from 'zustand'
import { toast } from 'sonner'
import { sessionsApi } from '@/api/sessions'
import { streamMessage, resumeQuiz } from '@/api/chat'
import { createSelectors } from '@/lib/utils'
import type { SessionOut } from '@/types/session'
import type { QuestionOut, QuizInterruptData } from '@/types/question'
import type { ChatItem, StreamStatus } from '@/types/chat'

interface ChatState {
  sessions: SessionOut[]
  currentSession: SessionOut | null
  items: ChatItem[]
  streamStatus: StreamStatus
  pendingQuiz: QuizInterruptData | null
  streamingContent: string
  lastError: { message: string; code: string } | null
  currentAbort: AbortController | null
  loadingSession: boolean
  loadingSessions: boolean

  loadSessions: () => Promise<void>
  selectSession: (id: string) => Promise<void>
  sendMessage: (content: string) => Promise<void>
  submitQuiz: (action: 'answer' | 'skip', answer?: string) => Promise<void>
  resetStream: () => void
  clearCurrent: () => void
}

const useChatStore = create<ChatState>((set, get) => ({
  sessions: [],
  currentSession: null,
  items: [],
  streamStatus: 'idle',
  pendingQuiz: null,
  streamingContent: '',
  lastError: null,
  currentAbort: null,
  loadingSession: false,
  loadingSessions: false,

  loadSessions: async () => {
    set({ loadingSessions: true })
    try {
      const sessions = await sessionsApi.list({ limit: 50 })
      set({ sessions })
    } finally {
      set({ loadingSessions: false })
    }
  },

  selectSession: async id => {
    set({ loadingSession: true, streamStatus: 'idle', pendingQuiz: null, streamingContent: '', lastError: null })
    try {
      const [session, messages, questions] = await Promise.all([
        sessionsApi.get(id),
        sessionsApi.listMessages(id),
        sessionsApi.listQuestions(id),
      ])
      const items: ChatItem[] = [
        ...messages.map(m => ({ type: 'message' as const, data: m })),
        ...questions.map(q => ({ type: 'quiz' as const, data: q })),
      ].sort((a, b) => +new Date(a.data.created_at) - +new Date(b.data.created_at))
      set({ currentSession: session, items })
    } finally {
      set({ loadingSession: false })
    }
  },

  sendMessage: async content => {
    const { currentSession } = get()
    if (!currentSession) return
    if (get().streamStatus === 'streaming' || get().streamStatus === 'quiz_interrupted') return

    const userMsg = {
      type: 'message' as const,
      data: {
        id: crypto.randomUUID(),
        session_id: currentSession.id,
        role: 'user' as const,
        content,
        created_at: new Date().toISOString(),
      },
    }
    set(state => ({
      items: [...state.items, userMsg],
      streamStatus: 'streaming' as const,
      streamingContent: '',
      lastError: null,
    }))

    const ac = new AbortController()
    set({ currentAbort: ac })

    try {
      for await (const ev of streamMessage(currentSession.id, content, ac.signal)) {
        switch (ev.event) {
          case 'text':
            set(state => ({
              streamingContent: state.streamingContent + ev.data.content,
            }))
            break
          case 'quiz_interrupt':
            set({ pendingQuiz: ev.data, streamStatus: 'quiz_interrupted' })
            break
          case 'done':
            if (get().streamStatus === 'streaming') {
              const agentMsg = {
                type: 'message' as const,
                data: {
                  id: crypto.randomUUID(),
                  session_id: currentSession.id,
                  role: 'agent' as const,
                  content: get().streamingContent,
                  created_at: new Date().toISOString(),
                },
              }
              set(state => ({
                items: [...state.items, agentMsg],
                streamStatus: 'idle' as const,
                streamingContent: '',
              }))
            } else if (get().streamStatus === 'quiz_interrupted') {
              set({ streamingContent: '' })
            }
            break
          case 'error':
            set({ streamStatus: 'error', lastError: ev.data })
            toast.error(ev.data.message)
            set(state => ({ items: state.items.filter(it => it !== userMsg) }))
            break
        }
      }
      if (get().streamStatus === 'streaming') {
        set({ streamStatus: 'error', lastError: { message: '连接中断', code: 'STREAM_CLOSED' } })
        toast.error('连接中断')
        set(state => ({ items: state.items.filter(it => it !== userMsg) }))
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        set({ streamStatus: 'error', lastError: { message: String(e), code: 'NETWORK' } })
        toast.error('网络错误')
        set(state => ({ items: state.items.filter(it => it !== userMsg) }))
      }
    } finally {
      set({ currentAbort: null })
    }
  },

  submitQuiz: async (action, answer) => {
    const { currentSession, pendingQuiz, currentAbort } = get()
    if (!currentSession || !pendingQuiz) return

    set({ streamStatus: 'streaming', streamingContent: '' })

    try {
      for await (const ev of resumeQuiz(currentSession.id, action, answer ?? null, currentAbort?.signal)) {
        switch (ev.event) {
          case 'text':
            set(state => ({ streamingContent: state.streamingContent + ev.data.content }))
            break
          case 'quiz_interrupt':
            set({ pendingQuiz: ev.data, streamStatus: 'quiz_interrupted' })
            break
          case 'done':
            if (get().streamStatus === 'streaming') {
              const question: QuestionOut = {
                ...pendingQuiz,
                id: pendingQuiz.question_id,
                session_id: currentSession.id,
                answer: '',
                analysis: null,
                status: action === 'skip' ? 'skipped' : 'answered',
                user_answer: action === 'skip' ? null : (answer ?? null),
                created_at: new Date().toISOString(),
                answered_at: new Date().toISOString(),
              }
              const qItem = { type: 'quiz' as const, data: question }
              const agentMsg = {
                type: 'message' as const,
                data: {
                  id: crypto.randomUUID(),
                  session_id: currentSession.id,
                  role: 'agent' as const,
                  content: get().streamingContent,
                  created_at: new Date().toISOString(),
                },
              }
              set(state => ({
                items: [...state.items, qItem, agentMsg],
                pendingQuiz: null,
                streamStatus: 'idle' as const,
                streamingContent: '',
              }))
            } else if (get().streamStatus === 'quiz_interrupted') {
              set({ streamingContent: '' })
            }
            break
          case 'error':
            set({ streamStatus: 'quiz_interrupted', lastError: ev.data })
            toast.error(ev.data.message)
            break
        }
      }
      if (get().streamStatus === 'streaming') {
        set({ streamStatus: 'quiz_interrupted', lastError: { message: '连接中断', code: 'STREAM_CLOSED' } })
        toast.error('连接中断，请重新答题')
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        set({ streamStatus: 'quiz_interrupted', lastError: { message: String(e), code: 'NETWORK' } })
        toast.error('网络错误，请重新答题')
      }
    } finally {
      set({ currentAbort: null })
    }
  },

  resetStream: () => {
    const ac = get().currentAbort
    if (ac) ac.abort()
    set({
      streamStatus: 'idle',
      streamingContent: '',
      pendingQuiz: null,
      lastError: null,
      currentAbort: null,
    })
  },

  clearCurrent: () => {
    get().resetStream()
    set({ currentSession: null, items: [], loadingSession: false })
  },
}))

export const useChat = createSelectors(useChatStore)
```

- [ ] **Step 10: Create src/locales/zh.json**

```json
{
  "common": {
    "appName": "教学 Agent",
    "loading": "加载中...",
    "empty": "暂无数据",
    "delete": "删除",
    "cancel": "取消",
    "confirm": "确认",
    "save": "保存",
    "back": "返回",
    "search": "搜索"
  },
  "login": {
    "title": "教学 Agent 登录",
    "username": "用户名",
    "password": "密码",
    "submit": "登录",
    "loading": "登录中..."
  },
  "chat": {
    "title": "聊天",
    "newSession": "新建会话",
    "freeMode": "自由学习",
    "projectMode": "项目学习",
    "selectProject": "选择项目",
    "noSession": "请选择或创建一个会话",
    "inputPlaceholder": "输入消息...",
    "send": "发送",
    "sessionEnded": "会话已结束",
    "connectionLost": "连接中断",
    "retry": "重试",
    "quiz": {
      "topic": "知识点",
      "single": "单选题",
      "multi": "多选题",
      "short": "简答题",
      "submit": "提交答案",
      "skip": "跳过",
      "correct": "回答正确",
      "wrong": "回答错误",
      "yourAnswer": "你的答案",
      "correctAnswer": "正确答案",
      "analysis": "解析",
      "answered": "已作答",
      "skipped": "已跳过",
      "pending": "待作答"
    }
  },
  "students": {
    "title": "学生管理",
    "import": "导入 Excel",
    "resetPassword": "重置密码",
    "resetConfirm": "确定将密码重置为 123456？",
    "deleteConfirm": "确定删除该学生账号？",
    "username": "学号",
    "name": "姓名",
    "createdAt": "创建时间",
    "actions": "操作",
    "importResult": "导入完成：共 {{total}} 行，新增 {{created}}，跳过 {{skipped}}"
  },
  "projects": {
    "title": "项目",
    "new": "新建项目",
    "name": "项目名称",
    "status": "状态",
    "draft": "草稿",
    "published": "已发布",
    "updatedAt": "更新时间",
    "actions": "操作",
    "edit": "编辑",
    "background": "项目背景",
    "preview": "预览",
    "publish": "发布",
    "unpublish": "取消发布"
  },
  "settings": {
    "title": "设置",
    "theme": "主题",
    "light": "浅色",
    "dark": "深色",
    "system": "跟随系统",
    "language": "语言",
    "changePassword": "修改密码",
    "oldPassword": "旧密码",
    "newPassword": "新密码",
    "logout": "退出登录"
  }
}
```

- [ ] **Step 11: Create src/locales/en.json**

Same structure as zh.json but with English values:

```json
{
  "common": {
    "appName": "Teaching Agent",
    "loading": "Loading...",
    "empty": "No data",
    "delete": "Delete",
    "cancel": "Cancel",
    "confirm": "Confirm",
    "save": "Save",
    "back": "Back",
    "search": "Search"
  },
  "login": {
    "title": "Teaching Agent Login",
    "username": "Username",
    "password": "Password",
    "submit": "Login",
    "loading": "Logging in..."
  },
  "chat": {
    "title": "Chat",
    "newSession": "New Session",
    "freeMode": "Free Study",
    "projectMode": "Project Study",
    "selectProject": "Select Project",
    "noSession": "Select or create a session",
    "inputPlaceholder": "Type a message...",
    "send": "Send",
    "sessionEnded": "Session ended",
    "connectionLost": "Connection lost",
    "retry": "Retry",
    "quiz": {
      "topic": "Topic",
      "single": "Single Choice",
      "multi": "Multiple Choice",
      "short": "Short Answer",
      "submit": "Submit",
      "skip": "Skip",
      "correct": "Correct",
      "wrong": "Incorrect",
      "yourAnswer": "Your Answer",
      "correctAnswer": "Correct Answer",
      "analysis": "Analysis",
      "answered": "Answered",
      "skipped": "Skipped",
      "pending": "Pending"
    }
  },
  "students": {
    "title": "Student Management",
    "import": "Import Excel",
    "resetPassword": "Reset Password",
    "resetConfirm": "Reset password to 123456?",
    "deleteConfirm": "Delete this student account?",
    "username": "Student ID",
    "name": "Name",
    "createdAt": "Created",
    "actions": "Actions",
    "importResult": "Import complete: {{total}} total, {{created}} created, {{skipped}} skipped"
  },
  "projects": {
    "title": "Projects",
    "new": "New Project",
    "name": "Name",
    "status": "Status",
    "draft": "Draft",
    "published": "Published",
    "updatedAt": "Updated",
    "actions": "Actions",
    "edit": "Edit",
    "background": "Background",
    "preview": "Preview",
    "publish": "Publish",
    "unpublish": "Unpublish"
  },
  "settings": {
    "title": "Settings",
    "theme": "Theme",
    "light": "Light",
    "dark": "Dark",
    "system": "System",
    "language": "Language",
    "changePassword": "Change Password",
    "oldPassword": "Old Password",
    "newPassword": "New Password",
    "logout": "Logout"
  }
}
```

- [ ] **Step 12: Create src/i18n.ts**

```typescript
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { useSettingsStore } from '@/stores/settings'
import zh from './locales/zh.json'
import en from './locales/en.json'

const getStoredLanguage = () => {
  try {
    const settingsString = localStorage.getItem('tutoring-settings')
    if (settingsString) {
      const settings = JSON.parse(settingsString)
      return settings.state?.language || 'zh'
    }
  } catch {
    // ignore
  }
  return 'zh'
}

i18n.use(initReactI18next).init({
  resources: {
    zh: { translation: zh },
    en: { translation: en },
  },
  lng: getStoredLanguage(),
  fallbackLng: 'zh',
  interpolation: { escapeValue: false },
})

useSettingsStore.subscribe(state => {
  if (i18n.language !== state.language) {
    i18n.changeLanguage(state.language)
  }
})

export default i18n
```

- [ ] **Step 13: Create src/hooks/useTheme.ts**

```typescript
import { useEffect } from 'react'
import { useSettingsStore } from '@/stores/settings'

export function useTheme() {
  const theme = useSettingsStore(s => s.theme)

  useEffect(() => {
    const root = document.documentElement
    const applyTheme = (isDark: boolean) => {
      root.classList.toggle('dark', isDark)
    }

    if (theme === 'system') {
      const mq = window.matchMedia('(prefers-color-scheme: dark)')
      applyTheme(mq.matches)
      const handler = (e: MediaQueryListEvent) => applyTheme(e.matches)
      mq.addEventListener('change', handler)
      return () => mq.removeEventListener('change', handler)
    } else {
      applyTheme(theme === 'dark')
    }
  }, [theme])
}
```

- [ ] **Step 14: Verify lint + typecheck + build**

```bash
cd frontend && bun run lint && bun run typecheck && bun run build
```

Expected: All pass. Fix any import issues.

- [ ] **Step 15: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): add API layer, Zustand stores, i18n, and theme hook"
```

---

### Task 4: Login Page + App Shell + Settings Menu

**Files:**
- Create: `frontend/src/features/login/LoginPage.tsx`
- Create: `frontend/src/features/shared/SettingsMenu.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/AppRouter.tsx`

**Interfaces:**
- Consumes: `useAuthStore`, `useSettingsStore`, `useChatStore`, `authApi`, `useTheme` hook, i18n
- Produces: Working login flow, Tab-based app shell with header and settings menu.

- [ ] **Step 1: Create src/features/login/LoginPage.tsx**

```typescript
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export default function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const login = useAuthStore(s => s.login)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password) return
    setLoading(true)
    try {
      const { token, user } = await authApi.login(username.trim(), password)
      login(token, user)
      navigate('/')
    } catch {
      // toast handled by axios interceptor
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/50">
      <div className="w-full max-w-sm rounded-lg border bg-card p-6 shadow-sm">
        <h1 className="mb-6 text-center text-2xl font-bold">{t('login.title')}</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="username">{t('login.username')}</Label>
            <Input
              id="username"
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoComplete="username"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">{t('login.password')}</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? t('login.loading') : t('login.submit')}
          </Button>
        </form>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create src/features/shared/SettingsMenu.tsx**

```typescript
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Settings, LogOut, Moon, Sun, Monitor, KeyRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import { useChatStore } from '@/stores/chat'
import { authApi } from '@/api/auth'

export default function SettingsMenu() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const logout = useAuthStore(s => s.logout)
  const user = useAuthStore(s => s.user)
  const theme = useSettingsStore(s => s.theme)
  const setTheme = useSettingsStore(s => s.setTheme)
  const language = useSettingsStore(s => s.language)
  const setLanguage = useSettingsStore(s => s.setLanguage)
  const clearCurrent = useChatStore(s => s.clearCurrent)

  const [pwDialogOpen, setPwDialogOpen] = useState(false)
  const [oldPw, setOldPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [changing, setChanging] = useState(false)

  const handleLogout = async () => {
    try {
      await authApi.logout()
    } catch {
      // ignore
    }
    logout()
    clearCurrent()
    navigate('/login')
  }

  const handleChangePassword = async () => {
    setChanging(true)
    try {
      await authApi.changePassword(oldPw, newPw)
      setPwDialogOpen(false)
      setOldPw('')
      setNewPw('')
    } catch {
      // toast handled by interceptor
    } finally {
      setChanging(false)
    }
  }

  const themeIcons = {
    light: <Sun className="size-4" />,
    dark: <Moon className="size-4" />,
    system: <Monitor className="size-4" />,
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon">
            <Settings className="size-5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <div className="px-2 py-1.5 text-sm font-medium">
            {user?.name} ({user?.username})
          </div>
          <DropdownMenuSeparator />
          <div className="px-2 py-1.5">
            <Label className="text-xs text-muted-foreground">{t('settings.theme')}</Label>
            <div className="mt-1 flex gap-1">
              {(['light', 'dark', 'system'] as const).map(th => (
                <Button
                  key={th}
                  variant={theme === th ? 'default' : 'outline'}
                  size="sm"
                  className="flex-1"
                  onClick={() => setTheme(th)}
                >
                  {themeIcons[th]}
                </Button>
              ))}
            </div>
          </div>
          <DropdownMenuSeparator />
          <div className="px-2 py-1.5">
            <Label className="text-xs text-muted-foreground">{t('settings.language')}</Label>
            <div className="mt-1 flex gap-1">
              <Button
                variant={language === 'zh' ? 'default' : 'outline'}
                size="sm"
                className="flex-1"
                onClick={() => setLanguage('zh')}
              >
                中文
              </Button>
              <Button
                variant={language === 'en' ? 'default' : 'outline'}
                size="sm"
                className="flex-1"
                onClick={() => setLanguage('en')}
              >
                English
              </Button>
            </div>
          </div>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => setPwDialogOpen(true)}>
            <KeyRound className="mr-2 size-4" />
            {t('settings.changePassword')}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={handleLogout} className="text-destructive">
            <LogOut className="mr-2 size-4" />
            {t('settings.logout')}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={pwDialogOpen} onOpenChange={setPwDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('settings.changePassword')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="old-pw">{t('settings.oldPassword')}</Label>
              <Input
                id="old-pw"
                type="password"
                value={oldPw}
                onChange={e => setOldPw(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-pw">{t('settings.newPassword')}</Label>
              <Input
                id="new-pw"
                type="password"
                value={newPw}
                onChange={e => setNewPw(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPwDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={handleChangePassword} disabled={changing || !oldPw || !newPw}>
              {t('common.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
```

- [ ] **Step 3: Rewrite src/App.tsx (AppShell with Tabs)**

```typescript
import { useTranslation } from 'react-i18next'
import { GraduationCap, MessageSquare, Users, FolderOpen } from 'lucide-react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import { useTheme } from '@/hooks/useTheme'
import SettingsMenu from '@/features/shared/SettingsMenu'
import ChatTab from '@/features/chat/ChatTab'
import StudentsTab from '@/features/students/StudentsTab'
import ProjectsTab from '@/features/projects/ProjectsTab'

export default function App() {
  const { t } = useTranslation()
  const user = useAuthStore(s => s.user)
  const activeTab = useSettingsStore(s => s.activeTab)
  const setActiveTab = useSettingsStore(s => s.setActiveTab)
  useTheme()

  const isTeacher = user?.role === 'teacher'

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b px-4 py-2">
        <div className="flex items-center gap-2">
          <GraduationCap className="size-6" />
          <span className="font-bold">{t('common.appName')}</span>
        </div>
        <SettingsMenu />
      </header>
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 overflow-hidden">
        <TabsList className="mx-4 mt-2">
          <TabsTrigger value="chat" className="gap-1">
            <MessageSquare className="size-4" />
            {t('chat.title')}
          </TabsTrigger>
          {isTeacher && (
            <TabsTrigger value="students" className="gap-1">
              <Users className="size-4" />
              {t('students.title')}
            </TabsTrigger>
          )}
          <TabsTrigger value="projects" className="gap-1">
            <FolderOpen className="size-4" />
            {t('projects.title')}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="chat" className="mt-0 h-[calc(100vh-7rem)]" style={{ display: activeTab !== 'chat' ? 'none' : undefined }}>
          <ChatTab />
        </TabsContent>
        {isTeacher && (
          <TabsContent value="students" className="mt-0 h-[calc(100vh-7rem)]" style={{ display: activeTab !== 'students' ? 'none' : undefined }}>
            <StudentsTab />
          </TabsContent>
        )}
        <TabsContent value="projects" className="mt-0 h-[calc(100vh-7rem)]" style={{ display: activeTab !== 'projects' ? 'none' : undefined }}>
          <ProjectsTab />
          </TabsContent>
      </Tabs>
    </div>
  )
}
```

Note: The `style={{ display: ... }}` pattern keeps all tabs mounted (no unmount on switch) so chat SSE state persists. Radix TabsContent normally unmounts inactive tabs; this override forces them to stay in DOM.

- [ ] **Step 4: Rewrite src/AppRouter.tsx (Route guard)**

```typescript
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth'
import LoginPage from '@/features/login/LoginPage'
import App from './App'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = useAuthStore(s => s.token)
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <RequireAuth>
            <App />
          </RequireAuth>
        }
      />
    </Routes>
  )
}
```

- [ ] **Step 5: Create placeholder feature components**

Create minimal placeholders so the build passes:

`src/features/chat/ChatTab.tsx`:
```typescript
export default function ChatTab() {
  return <div className="p-4">Chat (TODO)</div>
}
```

`src/features/students/StudentsTab.tsx`:
```typescript
export default function StudentsTab() {
  return <div className="p-4">Students (TODO)</div>
}
```

`src/features/projects/ProjectsTab.tsx`:
```typescript
export default function ProjectsTab() {
  return <div className="p-4">Projects (TODO)</div>
}
```

- [ ] **Step 6: Verify lint + typecheck + build**

```bash
cd frontend && bun run lint && bun run typecheck && bun run build
```

Expected: All pass.

- [ ] **Step 7: Manual test - login flow**

Start backend (port 8000) and frontend dev server:
```bash
cd frontend && bun run dev
```

Open browser to `http://localhost:5173`, login with `teacher1` / `teacher123`. Verify:
- Login succeeds, redirects to app
- Header shows app name + settings gear
- Tabs: Chat | Students | Projects (teacher sees all 3)
- Settings menu: theme toggle, language toggle, change password dialog, logout
- Logout returns to login page

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): login page, app shell with tabs, settings menu"
```

---

### Task 5: Chat Module - Session List + New Session Dialog

**Files:**
- Create: `frontend/src/features/chat/ChatTab.tsx`
- Create: `frontend/src/features/chat/SessionList.tsx`
- Create: `frontend/src/features/chat/NewSessionDialog.tsx`

**Interfaces:**
- Consumes: `useChatStore` (sessions, loadSessions, selectSession, currentSession), `sessionsApi`
- Produces: Working session list with create/select/delete.

- [ ] **Step 1: Create src/features/chat/NewSessionDialog.tsx**

```typescript
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { sessionsApi } from '@/api/sessions'
import { useChatStore } from '@/stores/chat'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ProjectOut } from '@/types/project'
import type { SessionOut } from '@/types/session'

export default function NewSessionDialog() {
  const { t } = useTranslation()
  const loadSessions = useChatStore(s => s.loadSessions)
  const selectSession = useChatStore(s => s.selectSession)
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<'free' | 'project'>('free')
  const [projects, setProjects] = useState<ProjectOut[]>([])
  const [selectedProject, setSelectedProject] = useState<string>('')

  useEffect(() => {
    if (open && mode === 'project') {
      import('@/api/projects').then(({ projectsApi }) => {
        projectsApi.list('published').then(setProjects)
      })
    }
  }, [open, mode])

  const handleCreate = async () => {
    const session = await sessionsApi.create({
      mode,
      ...(mode === 'project' && selectedProject ? { project_id: selectedProject } : {}),
    })
    await loadSessions()
    await selectSession(session.id)
    setOpen(false)
    setMode('free')
    setSelectedProject('')
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="w-full">
          {t('chat.newSession')}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('chat.newSession')}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="flex gap-2">
            <Button
              variant={mode === 'free' ? 'default' : 'outline'}
              className="flex-1"
              onClick={() => setMode('free')}
            >
              {t('chat.freeMode')}
            </Button>
            <Button
              variant={mode === 'project' ? 'default' : 'outline'}
              className="flex-1"
              onClick={() => setMode('project')}
            >
              {t('chat.projectMode')}
            </Button>
          </div>
          {mode === 'project' && (
            <div className="space-y-2">
              <Label>{t('chat.selectProject')}</Label>
              <Select value={selectedProject} onValueChange={setSelectedProject}>
                <SelectTrigger>
                  <SelectValue placeholder={t('chat.selectProject')} />
                </SelectTrigger>
                <SelectContent>
                  {projects.map(p => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <Button onClick={handleCreate} className="w-full">
            {t('common.confirm')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 2: Create src/features/chat/SessionList.tsx**

```typescript
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Trash2 } from 'lucide-react'
import { useChatStore } from '@/stores/chat'
import { sessionsApi } from '@/api/sessions'
import { formatRelativeTime } from '@/lib/formatDate'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import NewSessionDialog from './NewSessionDialog'

export default function SessionList() {
  const { t } = useTranslation()
  const sessions = useChatStore(s => s.sessions)
  const loadingSessions = useChatStore(s => s.loadingSessions)
  const loadSessions = useChatStore(s => s.loadSessions)
  const selectSession = useChatStore(s => s.selectSession)
  const currentSession = useChatStore(s => s.currentSession)

  useEffect(() => {
    loadSessions()
  }, [loadSessions])

  const handleDelete = async (id: string) => {
    await sessionsApi.delete(id)
    await loadSessions()
    if (currentSession?.id === id) {
      useChatStore.getState().clearCurrent()
    }
  }

  return (
    <div className="flex h-full flex-col border-r">
      <div className="p-2">
        <NewSessionDialog />
      </div>
      <ScrollArea className="flex-1">
        {loadingSessions && <div className="p-3 text-sm text-muted-foreground">{t('common.loading')}</div>}
        {!loadingSessions && sessions.length === 0 && (
          <div className="p-3 text-sm text-muted-foreground">{t('common.empty')}</div>
        )}
        <div className="space-y-1 p-2">
          {sessions.map(s => (
            <div
              key={s.id}
              className={`group flex items-center gap-2 rounded-md p-2 text-sm hover:bg-accent cursor-pointer ${
                currentSession?.id === s.id ? 'bg-accent' : ''
              }`}
              onClick={() => selectSession(s.id)}
            >
              <div className="flex-1 overflow-hidden">
                <div className="flex items-center gap-2">
                  <span className="truncate font-medium">
                    {s.title || s.project_name || t('chat.newSession')}
                  </span>
                  <Badge variant="outline" className="shrink-0 text-xs">
                    {s.mode === 'project' ? t('chat.projectMode') : t('chat.freeMode')}
                  </Badge>
                </div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {formatRelativeTime(s.last_active_at)}
                </div>
              </div>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-7 opacity-0 group-hover:opacity-100"
                    onClick={e => e.stopPropagation()}
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>{t('common.delete')}</AlertDialogTitle>
                    <AlertDialogDescription>
                      {t('common.confirm')}?
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                    <AlertDialogAction onClick={() => handleDelete(s.id)}>
                      {t('common.delete')}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
```

- [ ] **Step 3: Create src/features/chat/ChatTab.tsx**

```typescript
import { useTranslation } from 'react-i18next'
import { useChatStore } from '@/stores/chat'
import SessionList from './SessionList'
import ChatView from './ChatView'

export default function ChatTab() {
  const { t } = useTranslation()
  const currentSession = useChatStore(s => s.currentSession)

  return (
    <div className="flex h-full">
      <div className="w-72 shrink-0">
        <SessionList />
      </div>
      <div className="flex-1">
        {currentSession ? (
          <ChatView />
        ) : (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            {t('chat.noSession')}
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Create placeholder ChatView.tsx**

```typescript
export default function ChatView() {
  return <div className="p-4">Chat View (TODO)</div>
}
```

- [ ] **Step 5: Verify lint + typecheck + build**

```bash
cd frontend && bun run lint && bun run typecheck && bun run build
```

- [ ] **Step 6: Manual test**

```bash
cd frontend && bun run dev
```

Login as student1/student123. Verify:
- Chat tab shows session list on left
- "New Session" button opens dialog
- Can create free mode session
- Session appears in list, click to select

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): chat session list with create/select/delete"
```

---

### Task 6: Chat Module - Message View + SSE + Markdown + Quiz

**Files:**
- Create: `frontend/src/features/chat/ChatView.tsx`
- Create: `frontend/src/features/chat/MessageBubble.tsx`
- Create: `frontend/src/features/chat/ChatInput.tsx`
- Create: `frontend/src/features/chat/QuizCard.tsx`
- Create: `frontend/src/features/shared/MarkdownRenderer.tsx`

**Interfaces:**
- Consumes: `useChatStore` (items, streamStatus, streamingContent, pendingQuiz, sendMessage, submitQuiz, currentSession), `MarkdownRenderer`
- Produces: Full chat experience with SSE streaming, quiz interrupts, markdown rendering.

- [ ] **Step 1: Create src/features/shared/MarkdownRenderer.tsx**

```typescript
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import rehypeRaw from 'rehype-raw'

export default function MarkdownRenderer({ content }: { content: string }) {
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none break-words">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeRaw, rehypeKatex]}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
```

- [ ] **Step 2: Create src/features/chat/MessageBubble.tsx**

```typescript
import { useState } from 'react'
import { Check, Copy, User } from 'lucide-react'
import { cn } from '@/lib/cn'
import MarkdownRenderer from '@/features/shared/MarkdownRenderer'
import type { MessageOut } from '@/types/message'

export default function MessageBubble({ message }: { message: MessageOut }) {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className={cn('flex gap-3 group', isUser && 'flex-row-reverse')}>
      <div className={cn(
        'flex size-8 shrink-0 items-center justify-center rounded-full',
        isUser ? 'bg-primary text-primary-foreground' : 'bg-muted'
      )}>
        <User className="size-4" />
      </div>
      <div className={cn('flex-1', isUser && 'flex flex-col items-end')}>
        <div
          className={cn(
            'inline-block max-w-[85%] rounded-lg px-3 py-2',
            isUser ? 'bg-primary text-primary-foreground' : 'bg-muted'
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap text-sm">{message.content}</p>
          ) : (
            <div className="text-sm">
              <MarkdownRenderer content={message.content} />
            </div>
          )}
        </div>
        {!isUser && (
          <button
            onClick={handleCopy}
            className="mt-1 flex items-center gap-1 text-xs text-muted-foreground opacity-0 group-hover:opacity-100"
          >
            {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create src/features/chat/QuizCard.tsx**

```typescript
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CheckCircle2, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import MarkdownRenderer from '@/features/shared/MarkdownRenderer'
import type { QuestionOut, QuizInterruptData } from '@/types/question'

interface QuizCardProps {
  quiz: QuizInterruptData | QuestionOut
  status: 'pending' | 'answered' | 'skipped'
  userAnswer?: string | null
  correctAnswer?: string
  analysis?: string | null
  onSubmit: (answer: string) => void
  onSkip: () => void
}

export default function QuizCard({ quiz, status, userAnswer, correctAnswer, analysis, onSubmit, onSkip }: QuizCardProps) {
  const { t } = useTranslation()
  const qType = quiz.q_type
  const options = quiz.options ?? []
  const [selected, setSelected] = useState<string[]>([])
  const [shortAnswer, setShortAnswer] = useState('')
  const locked = status !== 'pending'

  const handleSubmit = () => {
    if (qType === 'single') {
      if (selected.length === 1) onSubmit(selected[0])
    } else if (qType === 'multi') {
      if (selected.length > 0) onSubmit(selected.join(','))
    } else {
      if (shortAnswer.trim()) onSubmit(shortAnswer.trim())
    }
  }

  const toggleOption = (idx: string) => {
    setSelected(prev =>
      prev.includes(idx)
        ? prev.filter(i => i !== idx)
        : qType === 'single'
          ? [idx]
          : [...prev, idx]
    )
  }

  const isCorrect = status === 'answered' && userAnswer === correctAnswer
  const questionId = 'question_id' in quiz ? quiz.question_id : (quiz as QuestionOut).id
  const optionIdx = (i: number) => String.fromCharCode(65 + i) // A, B, C...

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-3 flex items-center gap-2">
        <Badge variant="secondary">
          {qType === 'single' ? t('chat.quiz.single') : qType === 'multi' ? t('chat.quiz.multi') : t('chat.quiz.short')}
        </Badge>
        <span className="text-xs text-muted-foreground">{t('chat.quiz.topic')}: {quiz.topic}</span>
        {locked && (
          <Badge variant={isCorrect ? 'default' : 'destructive'} className="ml-auto">
            {isCorrect ? <CheckCircle2 className="mr-1 size-3" /> : <XCircle className="mr-1 size-3" />}
            {isCorrect ? t('chat.quiz.correct') : t('chat.quiz.wrong')}
          </Badge>
        )}
      </div>

      <div className="mb-4 text-sm">
        <MarkdownRenderer content={quiz.stem} />
      </div>

      {qType === 'single' && (
        <RadioGroup
          value={selected[0] ?? ''}
          onValueChange={v => setSelected([v])}
          disabled={locked}
        >
          {options.map((opt, i) => (
            <div key={i} className="flex items-center gap-2">
              <RadioGroupItem value={optionIdx(i)} id={`q-${questionId}-${i}`} />
              <Label htmlFor={`q-${questionId}-${i}`}>{opt}</Label>
            </div>
          ))}
        </RadioGroup>
      )}

      {qType === 'multi' && (
        <div className="space-y-2">
          {options.map((opt, i) => (
            <div key={i} className="flex items-center gap-2">
              <Checkbox
                checked={selected.includes(optionIdx(i))}
                onCheckedChange={() => toggleOption(optionIdx(i))}
                disabled={locked}
              />
              <Label>{opt}</Label>
            </div>
          ))}
        </div>
      )}

      {qType === 'short' && (
        <Input
          value={shortAnswer}
          onChange={e => setShortAnswer(e.target.value)}
          disabled={locked}
          placeholder={t('chat.quiz.short')}
        />
      )}

      {locked && (
        <div className="mt-4 space-y-2 border-t pt-3">
          {userAnswer && (
            <div className="text-sm">
              <span className="font-medium">{t('chat.quiz.yourAnswer')}:</span> {userAnswer}
            </div>
          )}
          {correctAnswer && (
            <div className="text-sm">
              <span className="font-medium">{t('chat.quiz.correctAnswer')}:</span> {correctAnswer}
            </div>
          )}
          {analysis && (
            <div className="text-sm">
              <div className="font-medium">{t('chat.quiz.analysis')}:</div>
              <MarkdownRenderer content={analysis} />
            </div>
          )}
        </div>
      )}

      {!locked && (
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={onSkip}>
            {t('chat.quiz.skip')}
          </Button>
          <Button onClick={handleSubmit}>
            {t('chat.quiz.submit')}
          </Button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Add Checkbox and RadioGroup shadcn components (if not already added)**

```bash
cd frontend && bunx --bun shadcn@latest add checkbox radio-group
```

- [ ] **Step 5: Create src/features/chat/ChatInput.tsx**

```typescript
import { useState, useRef, useEffect } from 'react'
import { Send } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

interface ChatInputProps {
  onSend: (content: string) => void
  disabled: boolean
  placeholder?: string
}

export default function ChatInput({ onSend, disabled, placeholder }: ChatInputProps) {
  const { t } = useTranslation()
  const [value, setValue] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (ref.current) {
      ref.current.style.height = 'auto'
      ref.current.style.height = `${ref.current.scrollHeight}px`
    }
  }, [value])

  const handleSend = () => {
    if (!value.trim() || disabled) return
    onSend(value.trim())
    setValue('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex items-end gap-2 border-t p-3">
      <Textarea
        ref={ref}
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder || t('chat.inputPlaceholder')}
        disabled={disabled}
        className="min-h-[40px] max-h-32 resize-none"
        rows={1}
      />
      <Button onClick={handleSend} disabled={disabled || !value.trim()} size="icon">
        <Send className="size-4" />
      </Button>
    </div>
  )
}
```

- [ ] **Step 6: Create src/features/chat/ChatView.tsx**

```typescript
import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useChatStore } from '@/stores/chat'
import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'
import QuizCard from './QuizCard'
import MarkdownRenderer from '@/features/shared/MarkdownRenderer'

export default function ChatView() {
  const { t } = useTranslation()
  const currentSession = useChatStore(s => s.currentSession)
  const items = useChatStore(s => s.items)
  const streamStatus = useChatStore(s => s.streamStatus)
  const streamingContent = useChatStore(s => s.streamingContent)
  const pendingQuiz = useChatStore(s => s.pendingQuiz)
  const sendMessage = useChatStore(s => s.sendMessage)
  const submitQuiz = useChatStore(s => s.submitQuiz)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [items, streamingContent])

  const inputDisabled = streamStatus === 'streaming' || streamStatus === 'quiz_interrupted'
  const sessionEnded = currentSession?.status === 'ended'

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {items.map((item, idx) => {
          if (item.type === 'message') {
            return <MessageBubble key={idx} message={item.data} />
          } else if (item.type === 'quiz') {
            const q = item.data
            return (
              <QuizCard
                key={idx}
                quiz={q}
                status={q.status}
                userAnswer={q.user_answer}
                correctAnswer={q.answer}
                analysis={q.analysis}
                onSubmit={() => {}}
                onSkip={() => {}}
              />
            )
          }
          return null
        })}
        {streamStatus === 'streaming' && streamingContent && (
          <div className="flex gap-3">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted">
              <span className="text-xs">AI</span>
            </div>
            <div className="flex-1 text-sm">
              <MarkdownRenderer content={streamingContent} />
            </div>
          </div>
        )}
        {streamStatus === 'quiz_interrupted' && pendingQuiz && (
          <QuizCard
            quiz={pendingQuiz}
            status="pending"
            onSubmit={answer => submitQuiz('answer', answer)}
            onSkip={() => submitQuiz('skip')}
          />
        )}
      </div>
      <ChatInput
        onSend={sendMessage}
        disabled={inputDisabled || sessionEnded}
        placeholder={sessionEnded ? t('chat.sessionEnded') : undefined}
      />
    </div>
  )
}
```

- [ ] **Step 7: Verify lint + typecheck + build**

```bash
cd frontend && bun run lint && bun run typecheck && bun run build
```

- [ ] **Step 8: Manual test - full chat flow**

```bash
cd frontend && bun run dev
```

Login as student1/student123. Verify:
- Create a free session
- Type a message, press Enter to send
- See streaming response appear token by token
- If quiz interrupt appears, answer it
- Quiz card locks after answer, shows correct/incorrect + analysis
- Can continue chatting after quiz

- [ ] **Step 9: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): chat view with SSE streaming, quiz cards, markdown rendering"
```

---

### Task 7: Students Management Tab

**Files:**
- Create: `frontend/src/features/students/StudentsTab.tsx`

**Interfaces:**
- Consumes: `usersApi` (listStudents, importStudents, resetPassword, deleteUser)
- Produces: Full student management UI for teachers.

- [ ] **Step 1: Create src/features/students/StudentsTab.tsx**

```typescript
import { useEffect, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Upload, RotateCcw, Trash2 } from 'lucide-react'
import { usersApi, type ImportResult } from '@/api/users'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { toast } from 'sonner'
import { formatDateTime } from '@/lib/formatDate'
import type { UserOut } from '@/types/user'

export default function StudentsTab() {
  const { t } = useTranslation()
  const [students, setStudents] = useState<UserOut[]>([])
  const [loading, setLoading] = useState(true)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [search, setSearch] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await usersApi.listStudents()
      setStudents(data)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const result = await usersApi.importStudents(file)
      setImportResult(result)
      await load()
    } catch {
      // toast handled by interceptor
    }
    e.target.value = ''
  }

  const handleReset = async (id: string) => {
    await usersApi.resetPassword(id)
    toast.success(t('students.resetPassword') + ': 123456')
  }

  const handleDelete = async (id: string) => {
    await usersApi.deleteUser(id)
    await load()
    toast.success(t('common.delete'))
  }

  const filtered = students.filter(
    s => s.username.includes(search) || s.name.includes(search)
  )

  return (
    <div className="flex h-full flex-col p-4">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-bold">{t('students.title')}</h2>
        <div className="flex items-center gap-2">
          <Input
            placeholder={t('common.search')}
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-48"
          />
          <Button variant="outline" onClick={() => document.getElementById('import-file')?.click()}>
            <Upload className="mr-2 size-4" />
            {t('students.import')}
          </Button>
          <input
            id="import-file"
            type="file"
            accept=".xlsx,.xls"
            className="hidden"
            onChange={handleImport}
          />
        </div>
      </div>
      <ScrollArea className="flex-1">
        {loading ? (
          <div className="text-sm text-muted-foreground">{t('common.loading')}</div>
        ) : filtered.length === 0 ? (
          <div className="text-sm text-muted-foreground">{t('common.empty')}</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('students.username')}</TableHead>
                <TableHead>{t('students.name')}</TableHead>
                <TableHead>{t('students.createdAt')}</TableHead>
                <TableHead className="text-right">{t('students.actions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map(s => (
                <TableRow key={s.id}>
                  <TableCell className="font-mono">{s.username}</TableCell>
                  <TableCell>{s.name}</TableCell>
                  <TableCell className="text-muted-foreground">{formatDateTime(s.created_at)}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button variant="ghost" size="icon" className="size-8">
                            <RotateCcw className="size-3.5" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>{t('students.resetPassword')}</AlertDialogTitle>
                            <AlertDialogDescription>
                              {t('students.resetConfirm')}
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                            <AlertDialogAction onClick={() => handleReset(s.id)}>
                              {t('common.confirm')}
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button variant="ghost" size="icon" className="size-8 text-destructive">
                            <Trash2 className="size-3.5" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>{t('common.delete')}</AlertDialogTitle>
                            <AlertDialogDescription>
                              {t('students.deleteConfirm')}
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                            <AlertDialogAction onClick={() => handleDelete(s.id)}>
                              {t('common.delete')}
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </ScrollArea>

      <Dialog open={!!importResult} onOpenChange={() => setImportResult(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('students.import')}</DialogTitle>
          </DialogHeader>
          {importResult && (
            <div className="space-y-2 text-sm">
              <p>{t('students.importResult', {
                total: importResult.total,
                created: importResult.created,
                skipped: importResult.skipped,
              })}</p>
              {importResult.errors.length > 0 && (
                <div className="text-destructive">
                  {importResult.errors.map((e, i) => (
                    <p key={i}>{e}</p>
                  ))}
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setImportResult(null)}>{t('common.confirm')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
```

- [ ] **Step 2: Add Table shadcn component (if not already added)**

```bash
cd frontend && bunx --bun shadcn@latest add table
```

- [ ] **Step 3: Verify lint + typecheck + build**

```bash
cd frontend && bun run lint && bun run typecheck && bun run build
```

- [ ] **Step 4: Manual test**

Login as teacher1/teacher123. Verify:
- Students tab visible (teacher only)
- Student list loads
- Import Excel button opens file picker
- Reset password button shows confirmation dialog
- Delete button shows confirmation dialog
- Search filters by username or name

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): student management tab with list, import, reset, delete"
```

---

### Task 8: Projects Tab + Editor

**Files:**
- Create: `frontend/src/features/projects/ProjectsTab.tsx`
- Create: `frontend/src/features/projects/ProjectEditor.tsx`

**Interfaces:**
- Consumes: `projectsApi`, `useAuthStore` (role check), `MarkdownRenderer`
- Produces: Projects list (student read-only, teacher CRUD) + editor.

- [ ] **Step 1: Create src/features/projects/ProjectsTab.tsx**

```typescript
import { useEffect, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, Pencil, Trash2, Eye } from 'lucide-react'
import { projectsApi } from '@/api/projects'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { formatDateTime } from '@/lib/formatDate'
import { toast } from 'sonner'
import type { ProjectOut } from '@/types/project'
import ProjectEditor from './ProjectEditor'

export default function ProjectsTab() {
  const { t } = useTranslation()
  const user = useAuthStore(s => s.user)
  const isTeacher = user?.role === 'teacher'
  const [projects, setProjects] = useState<ProjectOut[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [editingId, setEditingId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await projectsApi.list(statusFilter === 'all' ? undefined : statusFilter)
      setProjects(data)
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => {
    load()
  }, [load])

  const handleDelete = async (id: string) => {
    await projectsApi.delete(id)
    await load()
    toast.success(t('common.delete'))
  }

  if (editingId) {
    return <ProjectEditor projectId={editingId} onBack={() => { setEditingId(null); load() }} />
  }

  return (
    <div className="flex h-full flex-col p-4">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-bold">{t('projects.title')}</h2>
        {isTeacher && (
          <Button onClick={() => setEditingId('new')}>
            <Plus className="mr-2 size-4" />
            {t('projects.new')}
          </Button>
        )}
      </div>
      <div className="mb-4">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('common.search')}</SelectItem>
            <SelectItem value="draft">{t('projects.draft')}</SelectItem>
            <SelectItem value="published">{t('projects.published')}</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <ScrollArea className="flex-1">
        {loading ? (
          <div className="text-sm text-muted-foreground">{t('common.loading')}</div>
        ) : projects.length === 0 ? (
          <div className="text-sm text-muted-foreground">{t('common.empty')}</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('projects.name')}</TableHead>
                <TableHead>{t('projects.status')}</TableHead>
                <TableHead>{t('projects.updatedAt')}</TableHead>
                {isTeacher && <TableHead className="text-right">{t('projects.actions')}</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {projects.map(p => (
                <TableRow key={p.id}>
                  <TableCell className="font-medium">{p.name}</TableCell>
                  <TableCell>
                    <Badge variant={p.status === 'published' ? 'default' : 'secondary'}>
                      {p.status === 'published' ? t('projects.published') : t('projects.draft')}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatDateTime(p.updated_at)}</TableCell>
                  {isTeacher && (
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" className="size-8" onClick={() => setEditingId(p.id)}>
                          <Pencil className="size-3.5" />
                        </Button>
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button variant="ghost" size="icon" className="size-8 text-destructive">
                              <Trash2 className="size-3.5" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>{t('common.delete')}</AlertDialogTitle>
                              <AlertDialogDescription>{t('common.confirm')}?</AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                              <AlertDialogAction onClick={() => handleDelete(p.id)}>
                                {t('common.delete')}
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </ScrollArea>
    </div>
  )
}
```

- [ ] **Step 2: Create src/features/projects/ProjectEditor.tsx**

```typescript
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, Save } from 'lucide-react'
import { projectsApi } from '@/api/projects'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import MarkdownRenderer from '@/features/shared/MarkdownRenderer'
import { toast } from 'sonner'
import type { ProjectOut } from '@/types/project'

interface ProjectEditorProps {
  projectId: string // 'new' or UUID
  onBack: () => void
}

export default function ProjectEditor({ projectId, onBack }: ProjectEditorProps) {
  const { t } = useTranslation()
  const [name, setName] = useState('')
  const [backgroundMd, setBackgroundMd] = useState('')
  const [status, setStatus] = useState<'draft' | 'published'>('draft')
  const [loading, setLoading] = useState(projectId !== 'new')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (projectId !== 'new') {
      setLoading(true)
      projectsApi.get(projectId).then((p: ProjectOut) => {
        setName(p.name)
        setBackgroundMd(p.background_md)
        setStatus(p.status)
      }).finally(() => setLoading(false))
    }
  }, [projectId])

  const handleSave = async () => {
    if (!name.trim() || !backgroundMd.trim()) return
    setSaving(true)
    try {
      if (projectId === 'new') {
        await projectsApi.create({ name: name.trim(), background_md: backgroundMd, status })
      } else {
        await projectsApi.update(projectId, { name: name.trim(), background_md: backgroundMd, status })
      }
      toast.success(t('common.save'))
      onBack()
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="p-4 text-muted-foreground">{t('common.loading')}</div>

  return (
    <div className="flex h-full flex-col p-4">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={onBack}>
            <ArrowLeft className="size-4" />
          </Button>
          <h2 className="text-lg font-bold">
            {projectId === 'new' ? t('projects.new') : t('projects.edit')}
          </h2>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => setStatus(s => s === 'draft' ? 'published' : 'draft')}
          >
            {status === 'published' ? t('projects.unpublish') : t('projects.publish')}
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            <Save className="mr-2 size-4" />
            {t('common.save')}
          </Button>
        </div>
      </div>
      <div className="mb-4">
        <Label htmlFor="project-name">{t('projects.name')}</Label>
        <Input
          id="project-name"
          value={name}
          onChange={e => setName(e.target.value)}
          className="mt-1"
        />
      </div>
      <div className="grid flex-1 grid-cols-2 gap-4 overflow-hidden">
        <div className="flex flex-col">
          <Label>{t('projects.background')}</Label>
          <Textarea
            value={backgroundMd}
            onChange={e => setBackgroundMd(e.target.value)}
            className="mt-1 flex-1 resize-none font-mono text-sm"
            placeholder="Markdown..."
          />
        </div>
        <div className="flex flex-col">
          <Label>{t('projects.preview')}</Label>
          <ScrollArea className="mt-1 flex-1 rounded-md border p-3">
            <MarkdownRenderer content={backgroundMd || '*预览为空*'} />
          </ScrollArea>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Verify lint + typecheck + build**

```bash
cd frontend && bun run lint && bun run typecheck && bun run build
```

- [ ] **Step 4: Manual test**

Login as teacher1/teacher123. Verify:
- Projects tab shows list
- "New Project" button opens editor
- Markdown editor with live preview
- Save creates project, returns to list
- Edit existing project
- Publish/unpublish toggle
- Delete project with confirmation

Login as student1/student123. Verify:
- Projects tab shows list (read-only, no action column)
- No "New Project" button

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): projects tab with CRUD editor and markdown preview"
```

---

### Task 9: Final Polish + Verify Full Flow

**Files:**
- Modify: `frontend/src/App.tsx` (fix TabsContent display logic if needed)
- Verify all imports, fix any remaining issues

- [ ] **Step 1: Verify full build**

```bash
cd frontend && bun run lint && bun run typecheck && bun run build
```

- [ ] **Step 2: Full manual test - student flow**

```
1. Login as student1/student123
2. Chat tab: create session, send message, see streaming response
3. If quiz appears, answer it
4. Switch to Projects tab, verify read-only list
5. Switch back to Chat tab, verify session state preserved
6. Open Settings menu, toggle dark mode
7. Toggle language to English, verify UI text changes
8. Change password
9. Logout
```

- [ ] **Step 3: Full manual test - teacher flow**

```
1. Login as teacher1/teacher123
2. Chat tab: create session, send message (teacher can test)
3. Switch to Students tab:
   - View student list
   - Import Excel (create test .xlsx with columns: 学号, 姓名, 密码)
   - Reset password for a student
   - Delete a student
4. Switch to Projects tab:
   - Create new project with markdown background
   - Edit project
   - Publish/unpublish
   - Delete project
5. Switch between tabs, verify state preserved
6. Toggle theme and language
7. Logout
```

- [ ] **Step 4: Fix any issues found**

Fix any bugs, type errors, or UX issues discovered during testing.

- [ ] **Step 5: Final commit**

```bash
git add frontend/
git commit -m "feat(frontend): final polish and full flow verification"
```

---

## Spec Coverage Check

| Spec Section | Task |
|---|---|
| Tech Stack (Bun, React 19, Vite, Tailwind v4, shadcn/ui) | Task 1 |
| Zustand stores (auth, chat, settings) | Task 3 |
| API Layer (axios + Bearer token, SSE fetch) | Task 3 |
| Auth Flow (login, logout, 401 redirect, change password) | Task 3 + Task 4 |
| Tab-based SPA (Chat/Students/Projects) | Task 4 |
| Chat Module (session list, SSE, quiz, markdown) | Task 5 + Task 6 |
| Student Management (list, import, reset, delete) | Task 7 |
| Projects Module (CRUD, markdown editor) | Task 8 |
| i18n (zh/en) | Task 3 |
| Dark Mode (light/dark/system) | Task 3 + Task 4 |
| Settings Menu | Task 4 |
| Types | Task 2 |

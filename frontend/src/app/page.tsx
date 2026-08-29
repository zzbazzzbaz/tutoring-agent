// [调试模式] 路由拦截已临时禁用，见 docs/route-guard-debug.md
// 恢复方法：改回 redirect("/login")
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/teacher/chat");
}

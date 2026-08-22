import { NextResponse, type NextRequest } from "next/server";

// [调试模式] 路由拦截已临时禁用，见 docs/route-guard-debug.md
// 恢复方法：取消下方注释即可
export function middleware(request: NextRequest) {
  return NextResponse.next();
  //
  // const { pathname } = request.nextUrl;
  //
  // if (pathname === "/login") {
  //   const authCookie = request.cookies.get("tutoring_auth")?.value;
  //   const roleCookie = request.cookies.get("tutoring_role")?.value;
  //   if (authCookie === "1" && roleCookie) {
  //     const home =
  //       roleCookie === "teacher" ? "/teacher/chat" : "/student/chat";
  //     return NextResponse.redirect(new URL(home, request.url));
  //   }
  //   return NextResponse.next();
  // }
  //
  // const authCookie = request.cookies.get("tutoring_auth")?.value;
  // const roleCookie = request.cookies.get("tutoring_role")?.value;
  //
  // if (authCookie !== "1") {
  //   return NextResponse.redirect(new URL("/login", request.url));
  // }
  //
  // if (pathname.startsWith("/student") && roleCookie !== "student") {
  //   return NextResponse.redirect(new URL("/teacher/chat", request.url));
  // }
  // if (pathname.startsWith("/teacher") && roleCookie !== "teacher") {
  //   return NextResponse.redirect(new URL("/student/chat", request.url));
  // }
  //
  // return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};

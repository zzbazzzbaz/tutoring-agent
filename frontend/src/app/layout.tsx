import type { Metadata } from "next";
import "./globals.css";
import React from "react";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { Providers } from "@/components/providers/Providers";

export const metadata: Metadata = {
  title: "基础心理学教学Agent",
  description: "智能教学助手平台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body>
        <NuqsAdapter>
          <Providers>{children}</Providers>
        </NuqsAdapter>
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import { Inter } from "next/font/google";
import ErrorBoundary from "@/components/ErrorBoundary";
import NavBar from "@/components/NavBar";
import DemoModeBanner from "@/components/DemoModeBanner";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Flowforge — Workflow Console",
  description:
    "Orchestration console for the async workflow engine: trigger workflows, visualize DAGs, inspect runs, retry dead letters, and manage schedules.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body
        className={`${inter.variable} bg-gray-50 text-gray-900 antialiased`}
      >
        <NavBar />
        <DemoModeBanner />
        <main className="min-h-[calc(100vh-3.5rem)]">
          <ErrorBoundary>{children}</ErrorBoundary>
        </main>
      </body>
    </html>
  );
}

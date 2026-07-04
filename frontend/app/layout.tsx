import type { Metadata } from "next";
import "./globals.css";
import Providers from "./providers";
import { NavBar } from "@/components/nav";

export const metadata: Metadata = {
  title: "Versos Ops Console",
  description: "Human-in-the-loop console for the triage, index-hygiene and pipeline-healer agents",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full">
        <Providers>
          <NavBar />
          <main className="app-grid-bg min-h-[calc(100vh-57px)]">
            <div className="mx-auto max-w-6xl px-6 py-8">{children}</div>
          </main>
        </Providers>
      </body>
    </html>
  );
}

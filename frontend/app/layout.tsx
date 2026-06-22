import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "Versos Ops Console",
  description: "Human-in-the-loop console for the triage agent and its autonomy gate",
};

const NAV = [
  { href: "/", label: "Copilot" },
  { href: "/review", label: "Review queue" },
  { href: "/policy", label: "Policy & metrics" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full bg-zinc-50 text-zinc-900">
        <Providers>
          <header className="border-b border-zinc-200 bg-white">
            <nav className="mx-auto flex max-w-5xl items-center gap-6 px-6 py-3">
              <span className="font-semibold">Versos Ops</span>
              <div className="flex gap-4 text-sm text-zinc-600">
                {NAV.map((n) => (
                  <Link key={n.href} href={n.href} className="hover:text-zinc-900">
                    {n.label}
                  </Link>
                ))}
              </div>
            </nav>
          </header>
          <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}

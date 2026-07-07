"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "./theme-toggle";

// Internal ops surfaces.
const MAIN = [
  { href: "/", label: "Dashboard" },
  { href: "/copilot", label: "Copilot" },
  { href: "/review", label: "Support Requests" },
  { href: "/index", label: "Index Hygiene" },
  { href: "/pipeline", label: "Pipeline" },
  { href: "/policy", label: "Policy & Metrics" },
  { href: "/settings", label: "Settings" },
];
// Client-facing / demo surfaces, grouped.
const CLIENTS = [
  { href: "/submit", label: "Submit Request" },
  { href: "/simulation", label: "Simulation" },
];

const itemBase = "rounded-lg px-3 py-1.5 transition-colors";
const activeCls = "bg-accent text-accent-foreground font-medium";
const idleCls = "text-muted-foreground hover:bg-muted hover:text-foreground";

export function NavBar() {
  const path = usePathname();
  const [openClients, setOpenClients] = useState(false);
  const isActive = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));
  const clientsActive = CLIENTS.some((c) => isActive(c.href));

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-card/80 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-3">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <span className="grid h-6 w-6 place-items-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
            V
          </span>
          Versos Ops
        </Link>
        <div className="flex flex-1 flex-wrap items-center gap-1 text-sm">
          {MAIN.map((n) => (
            <Link key={n.href} href={n.href} className={cn(itemBase, isActive(n.href) ? activeCls : idleCls)}>
              {n.label}
            </Link>
          ))}

          {/* Clients dropdown */}
          <div className="relative" onMouseLeave={() => setOpenClients(false)}>
            <button
              onClick={() => setOpenClients((o) => !o)}
              className={cn(itemBase, "inline-flex items-center gap-1", clientsActive ? activeCls : idleCls)}
            >
              Clients <span className="text-xs">▾</span>
            </button>
            {openClients && (
              <div className="absolute left-0 top-full z-30 mt-1 min-w-[11rem] rounded-lg border border-border bg-card p-1 shadow-lg">
                {CLIENTS.map((c) => (
                  <Link
                    key={c.href}
                    href={c.href}
                    onClick={() => setOpenClients(false)}
                    className={cn(
                      "block rounded-md px-3 py-1.5",
                      isActive(c.href) ? activeCls : idleCls,
                    )}
                  >
                    {c.label}
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
        <ThemeToggle />
      </nav>
    </header>
  );
}

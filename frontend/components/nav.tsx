"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "./theme-toggle";

type Item = { href: string; label: string };

// Flat items + grouped dropdowns, in display order.
const DASHBOARD: Item = { href: "/", label: "Dashboard" };
const SUPPORT_TRIAGE: Item[] = [
  { href: "/copilot", label: "Copilot" },
  { href: "/review", label: "Support Requests" },
];
const OPS: Item[] = [
  { href: "/index-hygiene", label: "Index Hygiene" },
  { href: "/pipeline", label: "Pipeline" },
  { href: "/policy", label: "Policy & Metrics" },
  { href: "/settings", label: "Settings" },
];
const CLIENTS: Item[] = [
  { href: "/submit", label: "Submit Request" },
  { href: "/simulation", label: "Simulation" },
];

const itemBase = "rounded-lg px-3 py-1.5 transition-colors";
const activeCls = "bg-accent text-accent-foreground font-medium";
const idleCls = "text-muted-foreground hover:bg-muted hover:text-foreground";

function isActive(path: string, href: string) {
  return href === "/" ? path === "/" : path.startsWith(href);
}

function NavLink({ item, path }: { item: Item; path: string }) {
  return (
    <Link href={item.href} className={cn(itemBase, isActive(path, item.href) ? activeCls : idleCls)}>
      {item.label}
    </Link>
  );
}

function NavGroup({ label, items, path }: { label: string; items: Item[]; path: string }) {
  const [open, setOpen] = useState(false);
  const groupActive = items.some((i) => isActive(path, i.href));
  return (
    <div className="relative" onMouseLeave={() => setOpen(false)}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={cn(itemBase, "inline-flex items-center gap-1", groupActive ? activeCls : idleCls)}
      >
        {label} <span className="text-xs">▾</span>
      </button>
      {open && (
        <div className="absolute left-0 top-full z-30 mt-1 min-w-[11rem] rounded-lg border border-border bg-card p-1 shadow-lg">
          {items.map((i) => (
            <Link
              key={i.href}
              href={i.href}
              onClick={() => setOpen(false)}
              className={cn("block rounded-md px-3 py-1.5", isActive(path, i.href) ? activeCls : idleCls)}
            >
              {i.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export function NavBar() {
  const path = usePathname();
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
          <NavLink item={DASHBOARD} path={path} />
          <NavGroup label="Support Triage" items={SUPPORT_TRIAGE} path={path} />
          {OPS.map((i) => (
            <NavLink key={i.href} item={i} path={path} />
          ))}
          <NavGroup label="Clients" items={CLIENTS} path={path} />
        </div>
        <ThemeToggle />
      </nav>
    </header>
  );
}

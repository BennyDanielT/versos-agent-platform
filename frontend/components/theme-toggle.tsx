"use client";

import { useEffect, useState } from "react";

// Light/dark toggle. Defaults to the OS preference, then persists an explicit choice in
// localStorage and toggles the `.dark` class on <html> (the class our tokens key off).
export function ThemeToggle() {
  const [dark, setDark] = useState<boolean | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem("theme");
    const isDark = stored ? stored === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.classList.toggle("dark", isDark);
    // One-time client init: localStorage/matchMedia only exist in the browser, so this
    // must read after mount. This is the intended use of setState-in-effect here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDark(isDark);
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  }

  return (
    <button
      onClick={toggle}
      aria-label="Toggle theme"
      className="rounded-lg border border-border bg-card px-2 py-1 text-sm hover:bg-muted"
    >
      {dark ? "☀️" : "🌙"}
    </button>
  );
}

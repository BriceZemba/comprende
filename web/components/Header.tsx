"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { LANGS, useI18n } from "@/lib/i18n";

type Theme = "light" | "dark";

function currentTheme(): Theme {
  const set = document.documentElement.dataset.theme;
  if (set === "light" || set === "dark") return set;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function ThemeToggle() {
  const { t } = useI18n();
  const [theme, setTheme] = useState<Theme | null>(null); // unknown until mounted: the server cannot see the choice
  useEffect(() => { setTheme(currentTheme()); }, []);
  const flip = () => {
    const next: Theme = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch { /* not persisted */ }
    setTheme(next);
  };
  const label = theme === "dark" ? t.theme.toLight : t.theme.toDark;
  return (
    <button type="button" onClick={flip} aria-label={label} title={label}
      className="grid h-9 w-9 shrink-0 place-items-center rounded-full border border-line bg-card text-ink hover:border-accent">
      {theme === "dark" ? (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
          <circle cx="12" cy="12" r="4.5" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
      ) : (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" aria-hidden>
          <path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11Z" />
        </svg>
      )}
    </button>
  );
}

function LangSwitch() {
  const { t, lang, setLang } = useI18n();
  return (
    <div role="group" aria-label={t.langLabel} className="flex shrink-0 rounded-full border border-line bg-card p-0.5 text-xs font-medium">
      {LANGS.map((l) => (
        <button key={l} type="button" onClick={() => setLang(l)} aria-pressed={lang === l} lang={l}
          className={`rounded-full px-2.5 py-1.5 uppercase transition ${lang === l ? "bg-ink text-paper" : "text-muted hover:text-ink"}`}>
          {l}
        </button>
      ))}
    </div>
  );
}

export default function Header({ onLogo, nav }: { onLogo?: () => void; nav?: ReactNode }) {
  const logo = <span className="font-display text-2xl">comprende</span>;
  return (
    <header className="flex items-center justify-between gap-3 py-6">
      {onLogo ? <button type="button" onClick={onLogo}>{logo}</button> : <Link href="/">{logo}</Link>}
      <div className="flex items-center gap-3 sm:gap-5">
        {nav && <nav className="hidden gap-5 whitespace-nowrap text-sm text-muted sm:flex">{nav}</nav>}
        <ThemeToggle />
        <LangSwitch />
      </div>
    </header>
  );
}

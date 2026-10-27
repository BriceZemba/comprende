"use client";

import { useEffect, useRef, useState } from "react";
import { useI18n } from "@/lib/i18n";

interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>;
}

type Mode = "prompt" | "ios" | "menu";

// "Install the app", in the header on every page. Chrome and Edge give us an install prompt; iPhone Safari
// and other phone browsers never do, so there the button explains the two taps instead. Hidden once the app
// runs installed, and on desktop browsers that cannot install it. An icon on the phone is what brings a
// learner back to their list.
export default function InstallApp() {
  const { t } = useI18n();
  const [event, setEvent] = useState<InstallPromptEvent | null>(null);
  const [mode, setMode] = useState<Mode | null>(null);
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const installed = window.matchMedia("(display-mode: standalone)").matches
      || (navigator as Navigator & { standalone?: boolean }).standalone === true;
    if (installed) return;
    const ua = navigator.userAgent;
    const ios = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    if (ios) setMode("ios");
    else if (/Android|Mobi/i.test(ua)) setMode("menu");
    const keep = (e: Event) => { e.preventDefault(); setEvent(e as InstallPromptEvent); setMode("prompt"); };
    const done = () => { setEvent(null); setMode(null); setOpen(false); };
    addEventListener("beforeinstallprompt", keep);
    addEventListener("appinstalled", done);
    return () => { removeEventListener("beforeinstallprompt", keep); removeEventListener("appinstalled", done); };
  }, []);

  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    addEventListener("pointerdown", away);
    addEventListener("keydown", esc);
    return () => { removeEventListener("pointerdown", away); removeEventListener("keydown", esc); };
  }, [open]);

  if (!mode) return null;
  const click = async () => {
    if (mode === "prompt" && event) {
      await event.prompt();
      setEvent(null); setMode(null);
    } else setOpen((o) => !o);
  };

  return (
    <div ref={box} className="relative">
      <button type="button" onClick={click} aria-label={t.install.label} title={t.install.label}
        aria-expanded={mode === "prompt" ? undefined : open}
        className="flex h-9 shrink-0 items-center gap-1.5 rounded-full border border-accent bg-card px-2.5 text-sm font-medium text-accent hover:bg-accent hover:text-accent-ink sm:px-3.5">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M12 3v12M7 10l5 5 5-5M5 21h14" />
        </svg>
        <span className="hidden sm:inline">{t.install.button}</span>
      </button>
      {open && (
        <div role="dialog" aria-label={t.install.label}
          className="rise absolute right-0 top-full z-30 mt-2 w-72 rounded-2xl border border-line bg-card p-4 text-sm shadow-xl">
          <p className="font-medium">{t.install.label}</p>
          <p className="mt-2 text-muted">{mode === "ios" ? t.install.ios : t.install.menu}</p>
          <button type="button" onClick={() => setOpen(false)} className="mt-3 text-accent underline">{t.install.close}</button>
        </div>
      )}
    </div>
  );
}

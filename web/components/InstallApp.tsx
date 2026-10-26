"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";

interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>;
}

// "Add to home screen", offered only when the browser says the app can be installed (Chrome, Edge,
// Android). An icon on the phone is what brings a learner back to their list.
export default function InstallApp() {
  const { t } = useI18n();
  const [event, setEvent] = useState<InstallPromptEvent | null>(null);
  useEffect(() => {
    const keep = (e: Event) => { e.preventDefault(); setEvent(e as InstallPromptEvent); };
    addEventListener("beforeinstallprompt", keep);
    return () => removeEventListener("beforeinstallprompt", keep);
  }, []);
  if (!event) return null;
  return (
    <button type="button" onClick={async () => { await event.prompt(); setEvent(null); }}
      className="rounded-full border border-accent px-4 py-2 text-sm text-accent hover:bg-accent hover:text-accent-ink">
      {t.list.install}
    </button>
  );
}

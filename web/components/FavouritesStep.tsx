"use client";

import { useEffect, useRef, useState } from "react";
import { searchEntities, type SearchHit } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export interface Favourite {
  id: string | null; // Qloo entity id when picked from search; null when typed freely
  name: string;
  kind?: string;
}

const EXAMPLES = ["Breaking Bad", "Bad Bunny", "The Legend of Zelda", "Taylor Swift", "Harry Potter", "Stranger Things"];

export default function FavouritesStep({ value, onChange, onNext }: {
  value: Favourite[];
  onChange: (f: Favourite[]) => void;
  onNext: () => void;
}) {
  const { t } = useI18n();
  const KIND_LABEL = t.fav.kinds;
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [open, setOpen] = useState(false);
  const [searchDown, setSearchDown] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) { setHits([]); return; }
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      searchEntities(q, ctrl.signal)
        .then((r) => { setHits(r); setSearchDown(false); setOpen(true); })
        .catch((e) => { if (e.name !== "AbortError") setSearchDown(true); });
    }, 250);
    return () => { clearTimeout(t); ctrl.abort(); };
  }, [query]);

  const add = (f: Favourite) => {
    if (value.length >= 8 || value.some((v) => v.name.toLowerCase() === f.name.toLowerCase())) return;
    onChange([...value, f]);
    setQuery(""); setHits([]); setOpen(false);
    inputRef.current?.focus();
  };

  return (
    <section className="rise">
      <p className="text-sm font-medium uppercase tracking-wider text-accent">{t.fav.step}</p>
      <h2 className="font-display mt-1 text-3xl sm:text-4xl">{t.fav.title}</h2>
      <p className="mt-2 max-w-xl text-muted">
        {t.fav.lead}
      </p>

      <div className="relative mt-6 max-w-xl">
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => hits.length && setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && query.trim()) {
              e.preventDefault();
              add(hits[0] ? { id: hits[0].id, name: hits[0].name, kind: hits[0].kind } : { id: null, name: query.trim() });
            }
          }}
          placeholder={t.fav.placeholder}
          aria-label={t.fav.searchAria}
          className="w-full rounded-2xl border border-line bg-card px-5 py-4 text-lg shadow-sm outline-none focus:border-accent"
        />
        {open && hits.length > 0 && (
          <ul className="absolute z-10 mt-2 w-full overflow-hidden rounded-2xl border border-line bg-card shadow-lg" role="listbox">
            {hits.map((h) => (
              <li key={h.id}>
                <button
                  type="button"
                  onClick={() => add({ id: h.id, name: h.name, kind: h.kind })}
                  className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left hover:bg-paper"
                >
                  <span className="flex min-w-0 items-center gap-3">
                    <span className="h-10 w-10 shrink-0 overflow-hidden rounded-lg bg-line">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      {h.image ? <img src={h.image} alt="" className="h-full w-full object-cover" loading="lazy" /> : null}
                    </span>
                    <span className="truncate">{h.name}{h.year ? <span className="text-muted"> · {h.year}</span> : null}</span>
                  </span>
                  <span className="shrink-0 rounded-full bg-paper px-2 py-0.5 text-xs text-muted">{KIND_LABEL[h.kind] ?? h.kind}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {searchDown && query.trim().length >= 2 && (
          <p className="mt-2 text-sm text-muted">{t.fav.searchDown}</p>
        )}
      </div>

      {value.length > 0 && (
        <ul className="mt-5 flex flex-wrap gap-2" aria-label={t.fav.yours}>
          {value.map((f) => (
            <li key={f.name} className="rise flex items-center gap-2 rounded-full bg-ink px-4 py-2 text-paper">
              <span>{f.name}</span>
              {f.kind && <span className="text-xs opacity-70">{KIND_LABEL[f.kind] ?? f.kind}</span>}
              <button type="button" aria-label={t.fav.remove(f.name)} onClick={() => onChange(value.filter((v) => v !== f))}
                className="ml-1 opacity-70 hover:opacity-100">×</button>
            </li>
          ))}
        </ul>
      )}

      {value.length < 8 && (
        <div className="mt-5 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted">{value.length === 0 ? t.fav.startWith : t.fav.moreIdeas}</span>
          {EXAMPLES.filter((e) => !value.some((v) => v.name.toLowerCase() === e.toLowerCase())).map((e) => (
            <button key={e} type="button" onClick={() => add({ id: null, name: e })}
              className="rounded-full border border-line bg-card px-3 py-1.5 hover:border-accent">{e}</button>
          ))}
        </div>
      )}

      <button
        type="button"
        disabled={value.length === 0}
        onClick={onNext}
        className="mt-8 rounded-full bg-accent px-7 py-3.5 text-lg font-medium text-accent-ink shadow-sm transition enabled:hover:brightness-110 disabled:opacity-40"
      >
        {t.fav.next}
      </button>
    </section>
  );
}

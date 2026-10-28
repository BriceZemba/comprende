"""Check the live app the way a judge uses it; exit 1 with the reasons if anything is broken.

    python backend/scripts/healthcheck.py [https://comprende.vercel.app]

Standard library only, so it runs anywhere (the scheduled GitHub workflow runs it every 6 hours).
Checks: the API is up with the real Qloo key (never the development fake), the recorded example loads,
"Can you watch it without subtitles?" finds Money Heist, and one live search streams to a result with picks.
"""
import json
import sys
import time
import urllib.parse
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://comprende.vercel.app").rstrip("/")
HEADERS = {"User-Agent": "comprende-healthcheck"}


def get(path: str, timeout: float = 30) -> dict:
    req = urllib.request.Request(BASE + path, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def live_search() -> tuple[dict | None, list[dict], float]:
    body = json.dumps({"favourites_text": "Breaking Bad, Bad Bunny, The Legend of Zelda", "vocab_size": 3000}).encode()
    req = urllib.request.Request(BASE + "/api/recommend", data=body, method="POST",
                                 headers={**HEADERS, "Content-Type": "application/json"})
    t0, events = time.monotonic(), []
    with urllib.request.urlopen(req, timeout=150) as r:
        for raw in r:
            line = raw.decode("utf-8").strip()
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    result = next((e["result"] for e in events if e.get("type") == "result"), None)
    return result, events, time.monotonic() - t0


def main() -> int:
    problems: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"{'ok  ' if ok else 'FAIL'} {name}{': ' + detail if detail else ''}", flush=True)
        if not ok:
            problems.append(f"{name}: {detail}")

    try:
        h = get("/api/health")
        check("health", h.get("qloo_key") is True and h.get("fake_qloo") is False and h.get("measured_titles", 0) >= 1400,
              f"qloo_key={h.get('qloo_key')} fake_qloo={h.get('fake_qloo')} titles={h.get('measured_titles')} model={h.get('model')}")
    except Exception as e:  # noqa: BLE001 — report every kind of failure
        check("health", False, repr(e))
    try:
        ex = get("/api/example")
        check("recorded example", any(e["event"].get("type") == "result" for e in ex.get("events", [])),
              f"recorded {ex.get('recorded_at')}")
    except Exception as e:  # noqa: BLE001
        check("recorded example", False, repr(e))
    try:
        t = get("/api/title?q=" + urllib.parse.quote("money heist"))
        names = [x.get("title_es") for x in t.get("titles", [])]
        check("subtitles lookup", "La casa de papel" in names, ", ".join(n or "?" for n in names[:3]))
    except Exception as e:  # noqa: BLE001
        check("subtitles lookup", False, repr(e))
    try:
        result, events, secs = live_search()
        errors = [e.get("text") for e in events if e.get("type") == "error"]
        picks = sum(len(v) for v in (result or {}).get("buckets", {}).values())
        check("live search", result is not None and not errors and picks > 0 and not result.get("qloo_unavailable"),
              f"{secs:.0f} s, mode={result and result.get('mode')}, picks={picks}, errors={errors}, "
              f"qloo_errors={result and result.get('qloo_errors')}")
    except Exception as e:  # noqa: BLE001
        check("live search", False, repr(e))

    if problems:
        print("\nBROKEN:\n- " + "\n- ".join(problems))
        return 1
    print("\nall good")
    return 0


if __name__ == "__main__":
    sys.exit(main())

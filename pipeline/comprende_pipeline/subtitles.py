"""Parse OPUS OpenSubtitles XML into tokenised sentences."""
import xml.etree.ElementTree as ET


def parse_opus_xml(raw: bytes) -> tuple[list[list[str]], dict]:
    """Return (sentences as word lists, metadata) from one OPUS subtitle file."""
    root = ET.fromstring(raw)
    sentences = []
    for s in root.iter("s"):
        words = [w.text for w in s.iter("w") if w.text and w.text.strip()]
        if words:
            sentences.append(words)
    meta = {}
    source = root.find("meta/source")
    if source is not None:
        for key in ("year", "duration", "genre", "country"):
            el = source.find(key)
            if el is not None and el.text and el.text != "N/A":
                meta[key] = el.text
    sub = root.find("meta/subtitle")
    if sub is not None:
        el = sub.find("confidence")
        if el is not None and el.text:
            meta["confidence"] = float(el.text)
    return sentences, meta

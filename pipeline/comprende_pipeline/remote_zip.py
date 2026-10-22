"""Read single members of a large remote ZIP with HTTP range requests.

The OPUS Spanish subtitle archive is 18 GB. We only need a few thousand of its
357k files, so we read the central directory once and then fetch each member
by byte range instead of downloading the archive.
"""
import io
import pickle
import struct
import zipfile
import zlib
from collections import defaultdict
from pathlib import Path

import requests

from .config import USER_AGENT


class _RangeFile(io.RawIOBase):
    def __init__(self, url: str, session: requests.Session):
        self.url, self.session, self.pos = url, session, 0
        self.size = int(session.head(url).headers["content-length"])

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        base = {0: 0, 1: self.pos, 2: self.size}[whence]
        self.pos = base + offset
        return self.pos

    def readinto(self, buffer):
        if self.pos >= self.size or len(buffer) == 0:
            return 0
        end = min(self.pos + len(buffer), self.size) - 1
        data = self.session.get(self.url, headers={"Range": f"bytes={self.pos}-{end}"}).content
        buffer[: len(data)] = data
        self.pos += len(data)
        return len(data)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def load_index(url: str, cache_file: Path) -> list[tuple[str, int, int]]:
    """Return (member name, local header offset, compressed size) for every member."""
    if cache_file.exists():
        return pickle.loads(cache_file.read_bytes())
    raw = _RangeFile(url, _session())
    with zipfile.ZipFile(io.BufferedReader(raw, buffer_size=1 << 20)) as z:
        index = [(i.filename, i.header_offset, i.compress_size) for i in z.infolist()]
    cache_file.write_bytes(pickle.dumps(index))
    return index


def members_by_imdb(index: list[tuple[str, int, int]]) -> dict[str, list[tuple[str, int, int]]]:
    """Group subtitle files by IMDb id. Paths look like OpenSubtitles/xml/es/<year>/<imdb>/<id>.xml."""
    groups: dict[str, list[tuple[str, int, int]]] = defaultdict(list)
    for name, offset, size in index:
        parts = name.split("/")
        if len(parts) == 6 and parts[-1].endswith(".xml"):
            groups[f"tt{int(parts[4]):07d}"].append((name, offset, size))
    return dict(groups)


def fetch_member(url: str, offset: int, compress_size: int, session: requests.Session | None = None) -> bytes:
    """Fetch and decompress one member given its local header offset."""
    session = session or _session()
    # Local header is 30 bytes + file name + extra field; over-fetch to avoid a second request.
    head = 30 + 1024
    blob = session.get(
        url, headers={"Range": f"bytes={offset}-{offset + head + compress_size}"}, timeout=(10, 60)
    ).content
    if blob[:4] != b"PK\x03\x04":
        raise ValueError(f"no local file header at offset {offset}")
    method = struct.unpack("<H", blob[8:10])[0]
    name_len, extra_len = struct.unpack("<HH", blob[26:30])
    start = 30 + name_len + extra_len
    data = blob[start : start + compress_size]
    if len(data) < compress_size:
        raise ValueError("short read")
    if method == 0:
        return data
    if method == 8:
        return zlib.decompress(data, -15)
    raise ValueError(f"unsupported compression method {method}")

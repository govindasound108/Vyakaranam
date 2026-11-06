#!/usr/bin/env python3
"""Allinea la VERSION di sw.js al numero di versione dell'app (window.VR_N in index.html).
Da lanciare prima di ogni pubblicazione:  python3 tools/sync-sw-version.py"""
import re, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
html = (root / "index.html").read_text(encoding="utf-8")
n = re.search(r"VR_N\s*=\s*(\d+)", html).group(1)
sw = root / "sw.js"
s = sw.read_text(encoding="utf-8")
s2 = re.sub(r'const VERSION = "vyakaranam-v\d+";', f'const VERSION = "vyakaranam-v{n}";', s)
sw.write_text(s2, encoding="utf-8")
print("sw.js -> vyakaranam-v" + n + (" (invariato)" if s == s2 else ""))

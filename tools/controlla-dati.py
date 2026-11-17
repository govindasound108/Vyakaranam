#!/usr/bin/env python3
"""Controlla i dati dell'app prima di pubblicare:  python3 tools/controlla-dati.py

Legge index.html (senza modificarlo) e verifica:
  - nomi: tabella 8 righe x 3 colonne, nessuna cella vuota, devanāgarī coerente con l'IAST
  - pronomi: 7 righe x 3 colonne
  - verbi: 3 x 3, e la parte evidenziata della desinenza chiude davvero la forma
  - vocabolario: campi pieni, nessun doppione, devanāgarī coerente con l'IAST
  - versione: window.VR_N in index.html = VERSION in sw.js
Non controlla (ancora): versi e scansione dei metri, sūtra del sandhi.
Esce con codice 1 se trova errori; gli avvisi (celle aperte sul Notion) non bloccano."""
import json, pathlib, re, sys

root = pathlib.Path(__file__).resolve().parent.parent
html = (root / "index.html").read_text(encoding="utf-8")
errors, warns = [], []


def grab(name):
    m = re.search(r"^\s*const %s = (\[.*\]|\{.*\});\s*$" % name, html, re.M)
    if not m:
        errors.append("non trovo i dati %s in index.html" % name)
        return None
    return json.loads(m.group(1))


# ---- IAST -> devanāgarī (solo per il confronto) ----
VOW = {"a": "", "ā": "ा", "i": "ि", "ī": "ी", "u": "ु", "ū": "ू", "ṛ": "ृ", "ṝ": "ॄ", "ḷ": "ॢ", "e": "े", "ai": "ै", "o": "ो", "au": "ौ"}
VOW_IND = {"a": "अ", "ā": "आ", "i": "इ", "ī": "ई", "u": "उ", "ū": "ऊ", "ṛ": "ऋ", "ṝ": "ॠ", "ḷ": "ऌ", "e": "ए", "ai": "ऐ", "o": "ओ", "au": "औ"}
CON = {"k": "क", "kh": "ख", "g": "ग", "gh": "घ", "ṅ": "ङ", "c": "च", "ch": "छ", "j": "ज", "jh": "झ", "ñ": "ञ",
       "ṭ": "ट", "ṭh": "ठ", "ḍ": "ड", "ḍh": "ढ", "ṇ": "ण", "t": "त", "th": "थ", "d": "द", "dh": "ध", "n": "न",
       "p": "प", "ph": "फ", "b": "ब", "bh": "भ", "m": "म", "y": "य", "r": "र", "l": "ल", "v": "व",
       "ś": "श", "ṣ": "ष", "s": "स", "h": "ह"}
SIGN = {"ṁ": "ं", "ṃ": "ं", "ḥ": "ः"}
TOK = sorted(list(VOW) + list(CON) + list(SIGN), key=len, reverse=True)


def to_dev(s):
    s = s.lower().replace("’", "")
    out, i, pend, first = [], 0, False, True   # pend: ultima consonante senza vocale
    while i < len(s):
        ch = s[i]
        if ch in " /-":
            if pend:
                out.append("्"); pend = False
            out.append(ch); i += 1; first = True; continue
        tk = next((t for t in TOK if s.startswith(t, i)), None)
        if tk is None:
            return None
        i += len(tk)
        if tk in VOW:
            if pend:
                out.append(VOW[tk]); pend = False
            else:
                out.append(VOW_IND[tk])
            first = False
        elif tk in SIGN:
            if pend:
                out.append("्"); pend = False
            out.append(SIGN[tk]); first = False
        else:
            if pend:
                out.append("्")
            out.append(CON[tk]); pend = True; first = False
    if pend:
        out.append("्")
    return "".join(out)


def norm_dev(d):
    return re.sub(r"[\s/]+", " ", d.replace("ṃ", "ṁ")).strip()


def dev_ok(iast, dev):
    exp = to_dev(iast)
    return exp is not None and norm_dev(exp).replace("ं", "ं") == norm_dev(dev)


NOUNS = grab("NOUNS")
PRONS = grab("PRONS")
VERBS = grab("VERBS")
VOCAB = grab("VOCAB")

# ---- nomi ----
for n in NOUNS or []:
    nm = n["id"]
    if len(n["t"]) != 8 or any(len(r) != 3 for r in n["t"]):
        errors.append("nomi/%s: la tabella non è 8 righe x 3 colonne" % nm)
        continue
    for c, row in enumerate(n["t"]):
        for k, cell in enumerate(row):
            if not cell[0].strip():
                errors.append("nomi/%s: cella vuota (riga %d, colonna %d)" % (nm, c + 1, k + 1))
            elif len(cell) > 1 and cell[1] and not dev_ok(cell[0], cell[1]):
                errors.append("nomi/%s: IAST e devanāgarī non coincidono (riga %d, col %d): %s ≠ %s" % (nm, c + 1, k + 1, cell[0], cell[1]))
            if len(cell) > 2 and cell[2]:
                warns.append("nomi/%s: cella aperta sul Notion (riga %d, col %d): %s" % (nm, c + 1, k + 1, cell[0]))

# ---- pronomi ----
for p in PRONS or []:
    if len(p["t"]) != 7 or any(len(r) != 3 for r in p["t"]):
        errors.append("pronomi/%s: la tabella non è 7 righe x 3 colonne" % p["id"])
    elif any(not x.strip() for r in p["t"] for x in r):
        errors.append("pronomi/%s: cella vuota" % p["id"])

# ---- verbi ----
for v in VERBS or []:
    nm = v["id"]
    for key in ("f", "d", "suf", "hl"):
        if len(v.get(key, [])) != 3 or any(len(r) != 3 for r in v[key]):
            errors.append("verbi/%s: «%s» non è 3 x 3" % (nm, key))
    if errors and errors[-1].startswith("verbi/%s" % nm):
        continue
    for p in range(3):
        for n in range(3):
            f, h = v["f"][p][n], v["hl"][p][n]
            if not f.endswith(h):
                errors.append("verbi/%s: la desinenza evidenziata «%s» non chiude la forma «%s» (%d,%d)" % (nm, h, f, p + 1, n + 1))
            if not dev_ok(f, v["d"][p][n]):
                errors.append("verbi/%s: IAST e devanāgarī non coincidono (%d,%d): %s ≠ %s" % (nm, p + 1, n + 1, f, v["d"][p][n]))

# ---- vocabolario ----
seen = {}
for w in VOCAB or []:
    for key in ("d", "i", "m"):
        if not str(w.get(key, "")).strip():
            errors.append("vocab/%s: campo «%s» vuoto" % (w.get("i", "?"), key))
    if w["i"] in seen:
        errors.append("vocab: parola doppia: %s" % w["i"])
    seen[w["i"]] = 1
    if w.get("d") and not dev_ok(w["i"], w["d"]):
        errors.append("vocab: IAST e devanāgarī non coincidono: %s ≠ %s" % (w["i"], w["d"]))

# ---- versione ----
vr = re.search(r"VR_N\s*=\s*(\d+)", html)
sw = re.search(r'VERSION = "vyakaranam-v(\d+)"', (root / "sw.js").read_text(encoding="utf-8"))
if not vr or not sw:
    errors.append("versione: non trovo VR_N o VERSION")
elif vr.group(1) != sw.group(1):
    errors.append("versione: VR_N=%s in index.html ma sw.js dice v%s (lancia tools/sync-sw-version.py)" % (vr.group(1), sw.group(1)))

print("Controllati: %d nomi, %d pronomi, %d verbi, %d parole di vocabolario" % (len(NOUNS or []), len(PRONS or []), len(VERBS or []), len(VOCAB or [])))
for w in warns:
    print("AVVISO ", w)
for e in errors:
    print("ERRORE ", e)
print("Esito: %d errori, %d avvisi" % (len(errors), len(warns)))
sys.exit(1 if errors else 0)

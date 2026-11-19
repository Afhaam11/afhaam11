#!/usr/bin/env python3
"""Check the repository the way GitHub will see it.

    python scripts/validate.py

SVGs: well-formed XML, viewBox + explicit size, role="img" with <title> and <desc>, and nothing GitHub would
block or that would break offline (scripts, event handlers, raster images, foreignObject, external references).
README: every local image exists, light/dark pairs exist, no remote images.
"""
import os, re, sys
import xml.etree.ElementTree as ET

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
errors = []
def fail(msg): errors.append(msg); print("  FAIL", msg)

svgs = sorted(f for f in os.listdir(os.path.join(ROOT, "assets")) if f.endswith(".svg"))
print("SVG files:", len(svgs))
for f in svgs:
    path = os.path.join(ROOT, "assets", f); raw = open(path, encoding="utf-8").read()
    try: root = ET.fromstring(raw)
    except ET.ParseError as e: fail("%s: not well-formed (%s)" % (f, e)); continue
    ns = "{http://www.w3.org/2000/svg}"
    if root.tag != ns + "svg": fail(f + ": root is not <svg>")
    for a in ("viewBox", "width", "height", "role"):
        if a not in root.attrib: fail("%s: missing %s" % (f, a))
    if root.find(ns + "title") is None or root.find(ns + "desc") is None: fail(f + ": missing <title>/<desc>")
    tags = {el.tag.replace(ns, "") for el in root.iter()}
    for bad in ("script", "image", "foreignObject", "iframe", "use"):
        if bad in tags: fail("%s: contains <%s>" % (f, bad))
    if re.search(r"\son[a-z]+\s*=", raw): fail(f + ": event handler attribute")
    if re.search(r"(href|src)\s*=\s*[\"']https?:", raw) or "@import" in raw or re.search(r"url\(\s*[\"']?https?:", raw): fail(f + ": external reference")
    print("  ok   %-26s %6.1f KB  viewBox=%s" % (f, len(raw.encode()) / 1024, root.attrib.get("viewBox")))
for f in svgs:
    if not f.endswith("-dark.svg") and f.replace(".svg", "-dark.svg") not in svgs and f != "portrait-contour.svg": fail(f + ": no dark variant")

readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
refs = re.findall(r'(?:src|srcset)="([^"]+)"', readme) + re.findall(r"!\[[^\]]*\]\(([^)]+)\)", readme)
print("README image references:", len(refs))
for r in refs:
    if r.startswith("http"): fail("README: remote image " + r)
    elif not os.path.exists(os.path.join(ROOT, r)): fail("README: missing file " + r)
for f in sorted(os.listdir(os.path.join(ROOT, "assets"))):
    if f.endswith(".gif"):
        mb = os.path.getsize(os.path.join(ROOT, "assets", f)) / 1e6
        print("  %s   %-26s %5.2f MB" % ("ok  " if mb < 5 else "FAIL", f, mb))
        if mb >= 5: fail(f + ": over 5 MB, too heavy for a README")
used = {os.path.basename(r) for r in refs}
for f in svgs:
    if f not in used: print("  note  %s is not referenced by README.md" % f)
print("\nOK: no problems found" if not errors else "\n%d problem(s)" % len(errors)); sys.exit(1 if errors else 0)

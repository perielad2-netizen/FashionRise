from pathlib import Path
import re

p = Path(__file__).resolve().parents[1] / ".env"
raw = p.read_bytes()
if raw.startswith(b"\xef\xbb\xbf"):
    raw = raw[3:]
text = raw.decode("utf-8", errors="replace")
replacements = {
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u2013": "-",
    "\u2014": "-",
    "\u00a0": " ",
}
for a, b in replacements.items():
    text = text.replace(a, b)
text = re.sub(
    r"(PUBLIC_UPLOAD_BASE_URL=.*?)(localhost|127\.0\.0\.1):8000",
    r"\1\2:8001",
    text,
)
# Drop non-cp1252 chars so Starlette Config can load .env on Windows
cleaned = text.encode("cp1252", errors="ignore").decode("cp1252")
p.write_text(cleaned, encoding="utf-8", newline="\n")
cleaned.encode("cp1252")
print("env_fixed", p.stat().st_size)
for line in cleaned.splitlines():
    if line.startswith("PUBLIC_UPLOAD_BASE_URL="):
        print(line)

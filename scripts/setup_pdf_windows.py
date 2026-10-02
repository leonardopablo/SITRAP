import hashlib
import urllib.request
import zipfile
from pathlib import Path

url = "https://github.com/Kozea/WeasyPrint/releases/download/v70.0/weasyprint-windows-onedir.zip"
sha = "ab1151f210b4e6bb7aa7a79e91a67e8ddb760094c107bfda55241b6aaefe7d53"
root = Path(__file__).resolve().parents[1] / ".local" / "weasyprint70"
root.mkdir(parents=True, exist_ok=True)
archive = root / "runtime.zip"
if not archive.exists():
    urllib.request.urlretrieve(url, archive)
if hashlib.sha256(archive.read_bytes()).hexdigest() != sha:
    raise SystemExit("SHA256 mismatch")
with zipfile.ZipFile(archive) as bundle:
    for member in bundle.infolist():
        if not (root / member.filename).resolve().is_relative_to(root):
            raise SystemExit("Unsafe archive path")
    bundle.extractall(root)
for dll in root.rglob("libpango-1.0-0.dll"):
    print(dll.parent)

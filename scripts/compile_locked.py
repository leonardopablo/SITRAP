"""Generate pip-tools locks using index-advertised SHA-256 where available.

pip-tools already trusts hashes from the PyPI JSON API. The Simple API publishes
the same artifact hashes on links. Reusing those avoids downloading every wheel
for every platform when the JSON API is unavailable. pip --require-hashes verifies
the selected artifacts at installation. Links without SHA-256 use pip-tools'
normal download-and-hash implementation. Run against the intended HTTPS index.
"""

import re

from piptools.repositories.pypi import PyPIRepository
from piptools.scripts.compile import cli

original_hash = PyPIRepository._get_file_hash


def index_hash_or_download(self, link):
    if link.hash_name == "sha256" and re.fullmatch(r"[0-9a-fA-F]{64}", link.hash or ""):
        return "sha256:" + link.hash.lower()
    return original_hash(self, link)


if __name__ == "__main__":
    PyPIRepository._get_file_hash = index_hash_or_download
    cli()

"""Stage generated host packages and catalogs for remote installation."""

import argparse
import hashlib
import json
from pathlib import Path

from labledger.packaging import build_marketplace

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", default="dist/marketplace")
parser.add_argument("--archives", default="dist/plugins")
args = parser.parse_args()
result = build_marketplace(args.output, args.archives)
archives = [Path(plugin["archive"]) for plugin in result["plugins"]]
checksums = Path(args.archives) / "SHA256SUMS"
checksums.write_text(
    "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in archives)
)
print(json.dumps({**result, "checksums": str(checksums)}, indent=2))

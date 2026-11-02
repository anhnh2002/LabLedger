import argparse
import json

from labledger.packaging import build_plugins

parser = argparse.ArgumentParser(description="Build generated LabLedger host adapters")
parser.add_argument("--output", default="dist/plugins")
parser.add_argument("--hooks", action="store_true", help="Build opt-in local hook variants")
args = parser.parse_args()
print(json.dumps(build_plugins(args.output, args.hooks), indent=2))

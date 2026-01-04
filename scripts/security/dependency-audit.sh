#!/usr/bin/env bash
set -euo pipefail

# Generates a lightweight SBOM-like JSON from installed packages.
# For production, prefer CycloneDX/SPDX generated in CI.

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
OUTPUT_SBOM="${ROOT_DIR}/docs/security/SBOM.json"

python - <<PY
import json
import os
import sys
from datetime import datetime, timezone

try:
    import pkg_resources
except Exception as exc:
    print(f"Failed to import pkg_resources: {exc}", file=sys.stderr)
    sys.exit(1)

output_path = os.environ.get("OUTPUT_SBOM", "") or "${OUTPUT_SBOM}"

components = sorted(
    (
        {"name": d.project_name, "version": d.version, "type": "python"}
        for d in pkg_resources.working_set
    ),
    key=lambda x: x["name"].lower(),
)

data = {
    "schema": "internal-sbom-v1",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "components": components,
}

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
    f.write("\n")

print(f"Wrote {output_path} ({len(components)} components)")
PY

"""Export the FastAPI OpenAPI schema offline (no DB / LLM calls).

Usage:
    python scripts/export_openapi_ai.py            # write docs/contracts/ai-service.openapi.json
    python scripts/export_openapi_ai.py --check    # exit 1 if the committed snapshot is stale
"""

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "apps" / "ai-service"))

# The service builds its LLM client at import time; a dummy key is enough (no network call is made).
os.environ.setdefault("GEMINI_API_KEY", "dummy-key-for-openapi-export")

OUT = REPO_ROOT / "docs" / "contracts" / "ai-service.openapi.json"


def render() -> str:
    from app.main import app

    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    text = render()
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8").replace("\r\n", "\n") if OUT.exists() else ""
        if current != text:
            print("OpenAPI snapshot is stale: run python scripts/export_openapi_ai.py")
            raise SystemExit(1)
        print("OpenAPI snapshot up to date")
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {OUT}")

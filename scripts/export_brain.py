#!/usr/bin/env python3
"""Export brain files for assignment submission.

    python scripts/export_brain.py
"""
from __future__ import annotations

import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    import os
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    brain_dir = Path(os.getenv("BRAIN_DIR", "./data/brain"))
    if not brain_dir.is_absolute():
        brain_dir = (ROOT / brain_dir).resolve()

    if not brain_dir.exists():
        print(f"Brain dir not found: {brain_dir}")
        print("Run the bot and chat first.")
        return 1

    out_dir = ROOT / "submission" / "brain"
    out_dir.mkdir(parents=True, exist_ok=True)

    for name in ("identity.md", "relationship.md", "avatar.png"):
        src = brain_dir / name
        if src.exists():
            shutil.copy2(src, out_dir / name)
            print(f"  copied {name}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    zip_path = ROOT / "submission" / f"companion-brain-{stamp}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in out_dir.iterdir():
            zf.write(f, arcname=f.name)

    print(f"\nExported to:\n  {out_dir}\n  {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

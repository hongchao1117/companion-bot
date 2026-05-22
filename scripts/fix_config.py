"""Fix config.py to not include secrets - use env vars only."""
from pathlib import Path

config_path = Path("src/companion/config.py")
content = config_path.read_text(encoding="utf-8")

# Remove hardcoded defaults
old_defaults = 'token = os.getenv("DISCORD_TOKEN") or "MTUwNzIyMzA3MTA1NTE1MTEwNA.GDpiBV.nUSVMSNMri5chFf0qv5YKyypic1zZccNe2ZPO0"\n        api_key = os.getenv("OPENAI_API_KEY") or "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"'
new_defaults = 'token = os.getenv("DISCORD_TOKEN", "").strip()\n        api_key = os.getenv("OPENAI_API_KEY", "").strip()'

if old_defaults in content:
    content = content.replace(old_defaults, new_defaults)
    config_path.write_text(content, encoding="utf-8")
    print("config.py fixed - secrets removed")
else:
    print("Pattern not found - checking current content...")
    # Show relevant lines
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if "DISCORD_TOKEN" in line or "OPENAI_API_KEY" in line:
            print(f"  {i+1}: {line}")

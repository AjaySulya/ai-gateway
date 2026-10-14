
from pathlib import Path

path = Path("AGENTS.md")
raw = path.read_bytes()

try:
    content = raw.decode("utf-8")
    print("File is already valid UTF-8.")
except UnicodeDecodeError:
    content = raw.decode("cp1252")
    print("Decoded using Windows-1252.")

# Replace visible Unicode replacement characters with a normal separator.
content = content.replace("\uFFFD", "-")

# Save with UTF-8 encoding.
path.write_text(content, encoding="utf-8", newline="\n")

# Verify
path.read_bytes().decode("utf-8")
print("AGENTS.md is now valid UTF-8.")

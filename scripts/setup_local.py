"""Create private local development configuration without overwriting existing settings."""

from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
target = root / ".env.docker"
if target.exists():
    raise SystemExit(".env.docker already exists; left unchanged.")
content = (root / ".env.docker.example").read_text()
while "GENERATE_LOCALLY" in content:
    content = content.replace("GENERATE_LOCALLY", secrets.token_hex(32), 1)
with target.open("x") as config:
    config.write(content)
target.chmod(0o600)
print("Created private .env.docker. Start with: docker compose up --build -d")
print("Local administrator: admin@localhost. Web login uses a link printed in backend logs.")

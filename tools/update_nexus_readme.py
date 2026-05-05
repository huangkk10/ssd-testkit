#!/usr/bin/env python3
"""
update_nexus_readme.py — Add (or remove) a tool entry in https://10.252.170.171/readme

Usage:
    # Add a new tool row
    python tools/update_nexus_readme.py --name "Google Chrome" --id chrome --version 147.0.7727.138

    # Remove a tool row
    python tools/update_nexus_readme.py --remove --id chrome

What it does (in order):
    1. Fetch current README.html from GitLab
    2. Insert/remove the <tr> row in the tools table
    3. Update "Install all tools" command
    4. Update "Updated: YYYY-MM-DD" in the header
    5. Commit to GitLab (packages/windows/bootstrap/README.html)
    6. SSH to Nexus server → git pull  (nginx bind-mount picks up change immediately)

Credentials (override via env vars):
    GITLAB_URL      http://10.252.170.172
    GITLAB_TOKEN    glpat-...
    NEXUS_SSH_HOST  10.252.170.171
    NEXUS_SSH_USER  owner
    NEXUS_SSH_PASS  12345678
    NEXUS_REPO_PATH /home/owner/Codes/packages-win-linux
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date

# ── Defaults (override with env vars) ─────────────────────────────────────────
# All credentials MUST be provided via environment variables.
# Set them before running, e.g.:
#   $env:GITLAB_TOKEN   = "glpat-..."
#   $env:NEXUS_SSH_PASS = "..."
GITLAB_URL      = os.environ.get("GITLAB_URL",      "http://10.252.170.172")
GITLAB_TOKEN    = os.environ.get("GITLAB_TOKEN",    "")
GITLAB_PROJECT  = "chunwei%2Fpackages-win-linux"
README_FILE     = "packages/windows/bootstrap/README.html"
README_BRANCH   = "main"

NEXUS_SSH_HOST  = os.environ.get("NEXUS_SSH_HOST",  "10.252.170.171")
NEXUS_SSH_USER  = os.environ.get("NEXUS_SSH_USER",  "owner")
NEXUS_SSH_PASS  = os.environ.get("NEXUS_SSH_PASS",  "")
NEXUS_REPO_PATH = os.environ.get("NEXUS_REPO_PATH", "/home/owner/Codes/packages-win-linux")


# ── GitLab helpers ─────────────────────────────────────────────────────────────

def _gitlab_request(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{GITLAB_URL}/api/v4/projects/{GITLAB_PROJECT}/{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "PRIVATE-TOKEN": GITLAB_TOKEN,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"[ERROR] GitLab {method} {path}: HTTP {e.code} — {e.read().decode()}")
        sys.exit(1)


def fetch_readme() -> tuple[str, str]:
    """Returns (content_str, last_commit_id)."""
    info = _gitlab_request("GET", f"repository/files/{urllib.request.quote(README_FILE, safe='')}?ref={README_BRANCH}")
    content = base64.b64decode(info["content"]).decode("utf-8")
    return content, info["last_commit_id"]


def commit_readme(content: str, message: str) -> None:
    encoded = base64.b64encode(content.encode("utf-8")).decode()
    _gitlab_request("PUT", f"repository/files/{urllib.request.quote(README_FILE, safe='')}", {
        "branch": README_BRANCH,
        "content": encoded,
        "encoding": "base64",
        "commit_message": message,
    })


# ── HTML editing helpers ───────────────────────────────────────────────────────

ROW_TEMPLATE = (
    '        <tr><td>{name}</td><td>{version}</td>'
    '<td><div class="cmd-block">choco install {id} --version {version} -y'
    '<button class="copy-btn" onclick="copyCmd(this)">Copy</button></div></td></tr>'
)


def _make_row(name: str, tool_id: str, version: str) -> str:
    return ROW_TEMPLATE.format(name=name, id=tool_id, version=version)


def add_tool_row(html: str, name: str, tool_id: str, version: str) -> str:
    """Insert a new <tr> row before </tbody>."""
    row = _make_row(name, tool_id, version)
    # Avoid duplicate (same id)
    if f'choco install {tool_id} --version' in html:
        print(f"[WARN] id '{tool_id}' already exists in the table — skipping row insert (use --remove first to replace)")
        return html
    return html.replace("      </tbody>", f"{row}\n      </tbody>")


def remove_tool_row(html: str, tool_id: str) -> str:
    """Remove the <tr> row that contains 'choco install {tool_id} --version'."""
    pattern = rf'\s*<tr>.*?choco install {re.escape(tool_id)} --version.*?</tr>'
    new_html, n = re.subn(pattern, "", html, flags=re.DOTALL)
    if n == 0:
        print(f"[WARN] id '{tool_id}' not found in table rows — nothing removed")
    else:
        print(f"[OK] Removed row for '{tool_id}'")
    return new_html


def update_install_all(html: str, tool_id: str, version: str, remove: bool = False) -> str:
    """Update the 'Install all tools' choco install one-liner.

    Strategy: locate the block by its unique paragraph marker, then parse the
    command as (id, version) pairs, add/remove the tool, and rebuild.
    """
    marker = "Install all tools at once"
    marker_pos = html.find(marker)
    if marker_pos == -1:
        print("[WARN] Could not locate 'Install all tools at once' section — edit manually")
        return html

    # Find the next <div class="cmd-block"> after the marker
    DIV_OPEN = '<div class="cmd-block">'
    div_start = html.find(DIV_OPEN, marker_pos)
    if div_start == -1:
        print("[WARN] Could not find cmd-block after install-all marker — edit manually")
        return html

    cmd_text_start = div_start + len(DIV_OPEN)
    btn_start = html.find("<button", cmd_text_start)
    div_close_end = html.find("</div>", btn_start) + len("</div>")

    cmd_text = html[cmd_text_start:btn_start]   # "choco install ... -y"
    btn_html = html[btn_start:div_close_end]     # "<button ...>Copy</button></div>"

    # Parse: choco install id1 --version v1 id2 --version v2 ... -y
    pairs: list[tuple[str, str]] = re.findall(r'(\S+) --version (\S+)', cmd_text)

    if remove:
        original_len = len(pairs)
        pairs = [(i, v) for i, v in pairs if i != tool_id]
        if len(pairs) == original_len:
            print(f"[WARN] '{tool_id}' not found in install-all command")
    else:
        if any(i == tool_id for i, _ in pairs):
            print(f"[WARN] '{tool_id}' already in install-all command")
        else:
            pairs.append((tool_id, version))

    install_parts = " ".join(f"{i} --version {v}" for i, v in pairs)
    new_cmd = f"choco install {install_parts} -y"
    new_block = DIV_OPEN + new_cmd + btn_html

    return html[:div_start] + new_block + html[div_close_end:]


def update_date(html: str) -> str:
    today = date.today().strftime("%Y-%m-%d")
    if not re.search(r'Updated: \d{4}-\d{2}-\d{2}', html):
        print("[WARN] Could not find 'Updated: YYYY-MM-DD' in header")
        return html
    return re.sub(r'Updated: \d{4}-\d{2}-\d{2}', f'Updated: {today}', html)


# ── SSH git pull ───────────────────────────────────────────────────────────────

def server_git_pull() -> None:
    try:
        import paramiko
    except ImportError:
        print("[WARN] paramiko not installed — skipping SSH git pull")
        print(f"       Run manually:  ssh {NEXUS_SSH_USER}@{NEXUS_SSH_HOST}")
        print(f"       Then:          cd {NEXUS_REPO_PATH} && git pull")
        return

    print(f"[SSH] Connecting to {NEXUS_SSH_USER}@{NEXUS_SSH_HOST} ...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(NEXUS_SSH_HOST, username=NEXUS_SSH_USER, password=NEXUS_SSH_PASS, timeout=10)

    cmd = f"cd {NEXUS_REPO_PATH} && git pull 2>&1"
    _, stdout, _ = ssh.exec_command(cmd)
    output = stdout.read().decode().strip()
    print(f"[SSH] git pull:\n{output}")
    ssh.close()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Update Nexus /readme page")
    parser.add_argument("--name",    help='Display name, e.g. "Google Chrome"')
    parser.add_argument("--id",      required=True, help="Chocolatey package id, e.g. chrome")
    parser.add_argument("--version", help="Package version, e.g. 147.0.7727.138")
    parser.add_argument("--remove",  action="store_true", help="Remove the tool from the readme")
    parser.add_argument("--dry-run", action="store_true", help="Print diff only, do not commit or git pull")
    args = parser.parse_args()

    if not args.remove and (not args.name or not args.version):
        parser.error("--name and --version are required unless --remove is specified")

    # 1. Fetch
    print("[1/4] Fetching README.html from GitLab ...")
    html, _ = fetch_readme()

    # 2. Edit
    print("[2/4] Editing HTML ...")
    if args.remove:
        html = remove_tool_row(html, args.id)
        html = update_install_all(html, args.id, args.version or "", remove=True)
    else:
        html = add_tool_row(html, args.name, args.id, args.version)
        html = update_install_all(html, args.id, args.version)
    html = update_date(html)

    if args.dry_run:
        print("[DRY-RUN] Would commit the following content:")
        sys.stdout.buffer.write(html.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        return

    # 3. Commit
    action = "remove" if args.remove else "add"
    msg = f"chore: {action} {args.id} {args.version or ''} in readme".strip()
    print(f"[3/4] Committing to GitLab: '{msg}' ...")
    commit_readme(html, msg)
    print("[OK] Committed.")

    # 4. SSH git pull
    print("[4/4] Triggering git pull on Nexus server ...")
    server_git_pull()

    print(f"\n[DONE] https://{NEXUS_SSH_HOST}/readme updated.")


if __name__ == "__main__":
    main()

"""
Download Python Installer

Pre-downloads the official Python Windows installer (.exe) from python.org
and saves it to the standard bin directory so that integration tests can run
on machines without internet access.

Default save location (matches integration test lookup):
    tests/unit/lib/testtool/bin/python_installer/python-<version>-<arch>.exe

Usage
-----
    # Download Python 3.11 amd64 (default)
    python tools/download_python_installer.py

    # Download a specific version
    python tools/download_python_installer.py --version 3.11.8

    # Download 32-bit installer
    python tools/download_python_installer.py --arch win32

    # Save to a custom directory
    python tools/download_python_installer.py --output-dir C:\\Downloads
"""

import argparse
import ssl
import sys
import urllib.request
import urllib.error
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_VERSION = "3.11"
_DEFAULT_ARCH = "amd64"
_DOWNLOAD_URL_TEMPLATE = (
    "https://www.python.org/ftp/python/{full_version}/python-{full_version}-{arch}.exe"
)

# Default output directory: tests/unit/lib/testtool/bin/python_installer/
_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_OUTPUT_DIR = (
    _REPO_ROOT / "tests" / "unit" / "lib" / "testtool" / "bin" / "python_installer"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ssl_context(verify: bool) -> ssl.SSLContext:
    """Return an SSL context, optionally skipping certificate verification."""
    if verify:
        return ssl.create_default_context()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def resolve_full_version(version: str, arch: str, ssl_context: ssl.SSLContext) -> str:
    """
    If version is 'MAJOR.MINOR', try to find the latest available patch release
    by probing the download server. Falls back to '<version>.0' on any error.
    """
    parts = version.split(".")
    if len(parts) == 3:
        return version  # already fully specified

    # Try .0 first
    candidate = f"{version}.0"
    url = _DOWNLOAD_URL_TEMPLATE.format(full_version=candidate, arch=arch)
    print(f"  Probing: {url}")
    try:
        req = urllib.request.Request(url, method="HEAD")
        urllib.request.urlopen(req, timeout=10, context=ssl_context)
        return candidate
    except urllib.error.HTTPError as exc:
        print(f"  WARNING: HEAD request returned {exc.code}. Defaulting to {candidate}")
        return candidate
    except Exception as exc:
        print(f"  WARNING: Could not probe version ({exc}). Defaulting to {candidate}")
        return candidate


def download_installer(
    full_version: str, arch: str, output_dir: Path, ssl_context: ssl.SSLContext
) -> Path:
    """
    Download the Python installer to output_dir.
    Returns the local Path of the downloaded file.
    Skips download if the file already exists.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"python-{full_version}-{arch}.exe"
    dest = output_dir / filename

    if dest.is_file():
        print(f"  Already exists (skipping download): {dest}")
        return dest

    url = _DOWNLOAD_URL_TEMPLATE.format(full_version=full_version, arch=arch)
    print(f"  Downloading: {url}")
    print(f"  Saving to:   {dest}")

    try:
        def _progress(block_num, block_size, total_size):
            if total_size > 0:
                downloaded = block_num * block_size
                pct = min(downloaded * 100 // total_size, 100)
                bar = "#" * (pct // 5)
                sys.stdout.write(
                    f"\r  [{bar:<20}] {pct:>3}%"
                    f"  ({downloaded/1_048_576:.1f} / {total_size/1_048_576:.1f} MB)"
                )
                sys.stdout.flush()

        # urllib.request.urlretrieve does not accept an ssl context directly;
        # install an opener that uses our context.
        https_handler = urllib.request.HTTPSHandler(context=ssl_context)
        opener = urllib.request.build_opener(https_handler)
        with opener.open(url) as response:
            total_size = int(response.headers.get('Content-Length', 0))
            block_size = 65536  # 64 KB
            downloaded = 0
            block_num = 0
            with open(dest, 'wb') as f:
                while True:
                    chunk = response.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    block_num += 1
                    _progress(block_num, block_size, total_size)
        print()  # newline after progress bar
    except Exception as exc:
        if dest.exists():
            dest.unlink()
        raise RuntimeError(f"Download failed: {exc}") from exc

    print(f"  Download complete: {dest}")
    return dest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pre-download Python Windows installer for offline integration tests."
    )
    parser.add_argument(
        "--version",
        default=_DEFAULT_VERSION,
        help=f"Python version to download (default: {_DEFAULT_VERSION}). "
             "May be MAJOR.MINOR (e.g. '3.11') or MAJOR.MINOR.PATCH (e.g. '3.11.8').",
    )
    parser.add_argument(
        "--arch",
        default=_DEFAULT_ARCH,
        choices=["amd64", "win32"],
        help=f"Installer architecture (default: {_DEFAULT_ARCH}).",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_DEFAULT_OUTPUT_DIR),
        help=f"Directory to save the installer (default: {_DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--no-verify-ssl",
        action="store_true",
        default=False,
        help="Disable SSL certificate verification (use behind corporate proxies).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)

    ssl_context = _make_ssl_context(verify=not args.no_verify_ssl)
    if args.no_verify_ssl:
        print("  WARNING: SSL certificate verification is DISABLED.")

    print(f"Python Installer Downloader")
    print(f"  Version     : {args.version}")
    print(f"  Architecture: {args.arch}")
    print(f"  Output dir  : {output_dir}")
    print()

    print(f"[1/2] Resolving full version ...")
    full_version = resolve_full_version(args.version, args.arch, ssl_context)
    print(f"      Full version: {full_version}")
    print()

    print(f"[2/2] Downloading installer ...")
    try:
        dest = download_installer(full_version, args.arch, output_dir, ssl_context)
    except RuntimeError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1

    print()
    print(f"Done. Installer saved to:")
    print(f"  {dest}")
    print()
    print("To use in integration tests, set the environment variable:")
    print(f"  $env:PYTHON_INSTALLER_PATH = \"{dest}\"")
    print()
    print("Or the integration tests will auto-detect it from the default bin directory.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

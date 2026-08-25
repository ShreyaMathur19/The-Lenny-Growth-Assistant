import argparse
import io
import shutil
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_ARCHIVE = "https://github.com/ChatPRD/lennys-podcast-transcripts/archive/refs/heads/main.zip"


def main():
    parser = argparse.ArgumentParser(description="Download Lenny's Podcast transcript archive")
    parser.add_argument("--url", default=DEFAULT_ARCHIVE)
    parser.add_argument("--output", default="/data/transcripts")
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    print(f"Downloading transcript archive from {args.url}")
    with urllib.request.urlopen(args.url, timeout=120) as response:
        payload = response.read()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [m for m in archive.namelist() if "/episodes/" in m and not m.endswith("/")]
        if not members:
            raise RuntimeError("Archive did not contain an episodes directory")
        for member in members:
            parts = Path(member).parts
            idx = parts.index("episodes")
            relative = Path(*parts[idx + 1 :])
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    print(f"Extracted {len(members)} transcript files into {output}")


if __name__ == "__main__":
    main()

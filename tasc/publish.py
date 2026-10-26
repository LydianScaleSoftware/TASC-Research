"""Copy the documentation site (src/html) into a web server's tree.

    python -m tasc.publish DEST [--snippet FILE]

Every file is copied as it is, except that with --snippet the contents of FILE (a
site's own additions, such as its cookie consent banner and analytics) go just before
</body> on every page. src/html itself stays free of them, so the archive and other
copies of the site load nothing from elsewhere. Files already in DEST that the site no
longer has are left alone.

For lydianscale.com:
    python -m tasc.publish ~/testpage/tasc --snippet ~/testpage/_includes/cookie-consent-static.html
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from tasc.docview import OUT


def publish(dest: Path, snippet: str | None = None) -> list[Path]:
    """Copy OUT to dest; return the pages written."""
    pages = []
    for src in sorted(OUT.rglob("*")):
        if src.is_dir() or src.name == ".DS_Store":
            continue
        dst = dest / src.relative_to(OUT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix == ".html" and snippet:
            text = src.read_text()
            if text.count("</body>") != 1:
                raise ValueError(f"{src.name}: expected one </body>")
            dst.write_text(text.replace("</body>", snippet.rstrip("\n") + "\n</body>"))
            pages.append(dst)
        else:
            shutil.copyfile(src, dst)
    return pages


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m tasc.publish", description=__doc__.split("\n\n")[0])
    p.add_argument("dest", type=Path)
    p.add_argument("--snippet", type=Path, help="HTML to add before </body> on every page")
    a = p.parse_args()
    pages = publish(a.dest.expanduser(), a.snippet.expanduser().read_text() if a.snippet else None)
    print(f"{OUT} -> {a.dest}" + (f"; snippet added to {len(pages)} pages" if a.snippet else ""))


if __name__ == "__main__":
    main()

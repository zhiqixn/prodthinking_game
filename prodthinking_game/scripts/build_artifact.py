"""Build publishable copies of lessons and reference pages.

Usage: python3 scripts/build_artifact.py lessons/0001-x.html [reference/y.html ...]

Writes to build/. Shared assets/course.css and assets/course.js are inlined so each
page works on its own. The first argument is the artifact's main page: its document
skeleton is stripped (the Artifact host adds one) and "../reference/" links become
"reference/" so they match the published file paths. Other arguments are written as
full HTML documents under build/<their folder>/.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "assets/course.css").read_text()
JS = (ROOT / "assets/course.js").read_text()

# Published artifact URL for each lesson. Links between lessons are rewritten to these.
LESSON_URLS = {
    "0001-problems-before-solutions.html": "https://claude.ai/artifact/DvGKgPRUMDnnxxvRUM6HBi",
    "0002-start-with-the-whys.html": "https://claude.ai/artifact/Tg5UqPTu7CgJTKA8sypiHL",
}


def inline(html: str, name: str) -> str:
    html = re.sub(r'<link\b[^>]*href="\.\./assets/course\.css"[^>]*>', lambda m: f"<style>\n{CSS}\n</style>", html)
    html = re.sub(r'<script\b[^>]*src="\.\./assets/course\.js"[^>]*>\s*</script>', lambda m: f"<script>\n{JS}\n</script>", html)
    if "../assets/" in html:
        sys.exit(f"{name}: still references ../assets/ after inlining; the artifact would load without it.")
    return html


def strip_skeleton(html: str) -> str:
    html = re.sub(r"<!DOCTYPE html>\s*", "", html, flags=re.I)
    html = re.sub(r"</?(html|head|body)\b[^>]*>\s*", "", html, flags=re.I)
    html = re.sub(r'<meta (charset|name="viewport")[^>]*>\s*', "", html, flags=re.I)
    return html


def main(args):
    out = ROOT / "build"
    for i, rel in enumerate(args):
        src = ROOT / rel
        html = inline(src.read_text(), rel)
        if i == 0:
            html = strip_skeleton(html).replace('href="../reference/', 'href="reference/')
            for name, url in LESSON_URLS.items():
                html = html.replace(f'href="{name}"', f'href="{url}"')
                html = html.replace(f'href="../lessons/{name}"', f'href="{url}"')
            dest = out / src.name
        else:
            dest = out / src.parent.name / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html)
        print(dest.relative_to(ROOT))


if __name__ == "__main__":
    main(sys.argv[1:])

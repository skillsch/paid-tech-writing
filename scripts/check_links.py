"""Check every program link in README.md and report dead or closed ones.

Writes a Markdown report to stdout. Exits 1 if any problem is found.
"""

import concurrent.futures
import html
import re
import sys
import urllib.error
import urllib.request

README = "README.md"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"
SKIP = ("creativecommons.org",)

CLOSED = re.compile(
    r"not (currently )?(accepting|taking|looking for new)"
    r"|no longer (accepting|taking|running|paying|offering)"
    r"|(program|applications?|submissions?|pitches|proposals) (is |are |has been |have been )?"
    r"(currently |now )?(closed|paused|on hold|suspended|discontinued)"
    r"|temporarily (closed|paused|suspended)"
    r"|paused until|positions filled|stopped accepting|program closed",
    re.I,
)


def links():
    text = open(README, encoding="utf-8").read()
    seen = []
    for name, url in re.findall(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", text):
        if not any(s in url for s in SKIP) and url not in [u for _, u in seen]:
            seen.append((name, url))
    return seen


def page_text(raw):
    raw = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def check(item):
    name, url = item
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            final = resp.geturl()
            text = page_text(resp.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        # 401/403/429 usually mean bot protection, not a dead page.
        if e.code in (401, 403, 429):
            return None
        return name, url, f"HTTP {e.code}"
    except Exception as e:
        return name, url, f"unreachable ({type(e).__name__})"

    match = CLOSED.search(text)
    if match:
        snippet = text[max(0, match.start() - 60) : match.end() + 60].strip()
        return name, url, f'closed notice: "…{snippet}…"'

    def host_path(u):
        return re.sub(r"^https?://(www\.)?", "", u).rstrip("/")

    if host_path(final).count("/") == 0 and host_path(url).count("/") > 0:
        return name, url, f"redirects to homepage ({final})"
    return None


def main():
    items = links()
    with concurrent.futures.ThreadPoolExecutor(16) as pool:
        problems = [p for p in pool.map(check, items) if p]

    if not problems:
        print(f"All {len(items)} links look open.")
        return 0

    print(f"Checked {len(items)} links. {len(problems)} need a look:\n")
    print("| Program | Problem |")
    print("|---|---|")
    for name, url, why in sorted(problems):
        print(f"| [{name}]({url}) | {why.replace('|', '/')} |")
    print("\nConfirm each one by hand, then remove it from README.md or fix the link.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

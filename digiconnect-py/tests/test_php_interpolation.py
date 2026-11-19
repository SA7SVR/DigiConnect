"""PHP reads every byte above 127 as part of a variable name, so "«$key»" is the variable $key» (undefined: the name is silently missing from the text, and PHP prints a warning
where warnings are on - this is what failed the macOS Intel run of 2.3.12). A variable that is followed by a non-ASCII character in a string must be written {$key}."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BAD = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*[^\x00-\x7f]")


def test_no_php_variable_is_followed_directly_by_a_non_ascii_character():
    found = []
    for p in sorted((ROOT / "server").rglob("*.php")):
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if BAD.search(line): found.append(f"{p.relative_to(ROOT)}:{n}")
    assert not found, "write {$var} before a non-ASCII character: " + ", ".join(found)

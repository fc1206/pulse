"""report.html embeds the registry as JSON inside an inline <script>. Registry text is the
model's summary of UNTRUSTED web content, so it must not be able to break out of, or confuse,
the script element (stored XSS). Guards scripts/render_report.py:_js_json."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import render_report  # noqa: E402


def test_js_json_neutralizes_script_breakout():
    # Closing-tag breakout AND the <!--<script> double-escape vector.
    payload = [{"what": "</script><img src=x onerror=alert(1)>", "name": "<!--<script>"}]
    out = render_report._js_json(payload)
    assert "<" not in out and ">" not in out        # no literal angle brackets reach the <script>
    assert "\\u003c" in out                          # the JSON-legal escaped form is present
    # data round-trips byte-for-byte
    parsed = json.loads(out)[0]
    assert parsed["what"] == "</script><img src=x onerror=alert(1)>"
    assert parsed["name"] == "<!--<script>"


def test_md_inline_url_does_not_inject_attributes():
    # a URL with a quote must stop at the quote, so an injected attribute lands as inert
    # text after </a>, never inside the opening <a ...> tag.
    out = render_report.md_inline('http://evil.com/x"onmouseover="alert(1)')
    assert '<a href="http://evil.com/x" target="_blank" rel="noopener">link</a>' in out
    assert out.index("</a>") < out.index("onmouseover")


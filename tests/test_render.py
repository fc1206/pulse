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

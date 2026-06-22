"""Inject payload.json into template.html -> plain.html (decrypted dashboard)."""
import os, re, json

HERE = os.path.dirname(__file__)
tpl = open(os.path.join(HERE, "template.html"), encoding="utf8").read()
payload = open(os.path.join(HERE, "payload.json"), encoding="utf8").read()
pat = re.compile(r'(<script id="payload" type="application/json">)(.*?)(</script>)', re.S)
assert len(pat.findall(tpl)) == 1, "expected exactly one #payload script tag"
out = pat.sub(lambda m: m.group(1) + payload + m.group(3), tpl)
open(os.path.join(HERE, "plain.html"), "w", encoding="utf8").write(out)
print(f"wrote plain.html: {len(out)} bytes, payload rows: {len(json.loads(payload)['rows'])}")

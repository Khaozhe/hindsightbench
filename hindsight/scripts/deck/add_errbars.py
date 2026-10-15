"""Add custom error bars (node-level 95% CIs) to the false-place chart on slide 6.
OOXML c:ser child order for bar charts: ... dLbls, trendline*, errBars, cat, val ... -> insert errBars before c:cat."""
import json, re, sys, zipfile, shutil
from pathlib import Path

deck = Path(sys.argv[1]); data = json.loads(Path(sys.argv[2]).read_text())
R = data["reloc"]
order = ["deepseek-v4-flash", "gemini-2.5-flash-pooled", "claude-sonnet-5", "gpt-5.4-mini"]
series = [("relocation", [R[t]["relocation"] for t in order]), ("interference", [R[t]["interference"] for t in order])]

z = zipfile.ZipFile(deck)
files = {n: z.read(n) for n in z.namelist()}
z.close()
rels = files["ppt/slides/_rels/slide6.xml.rels"].decode()
chart = re.search(r'Target="(?:\.\./|/ppt/)charts/(chart\d+\.xml)"', rels).group(1)
key = f"ppt/charts/{chart}"
xml = files[key].decode()


def numlit(vals):
    pts = "".join(f'<c:pt idx="{i}"><c:v>{v:.2f}</c:v></c:pt>' for i, v in enumerate(vals))
    return f'<c:numLit><c:formatCode>General</c:formatCode><c:ptCount val="{len(vals)}"/>{pts}</c:numLit>'


sers = re.findall(r"<c:ser>.*?</c:ser>", xml, flags=re.S)
assert len(sers) == 2, len(sers)
for raw, (_, cis) in zip(sers, series):
    plus = [c["hi"] - c["pt"] for c in cis]; minus = [c["pt"] - c["lo"] for c in cis]
    eb = ('<c:errBars><c:errBarType val="both"/><c:errValType val="cust"/><c:noEndCap val="0"/>'
          f'<c:plus>{numlit(plus)}</c:plus><c:minus>{numlit(minus)}</c:minus>'
          '<c:spPr><a:ln w="9525"><a:solidFill><a:srgbClr val="333333"/></a:solidFill></a:ln></c:spPr></c:errBars>')
    assert "<c:cat>" in raw
    new = raw.replace("<c:cat>", eb + "<c:cat>", 1)
    xml = xml.replace(raw, new, 1)
files[key] = xml.encode()
# scatter on slide 5: tick labels at the plot edge, not on the zero lines
rels5 = files["ppt/slides/_rels/slide5.xml.rels"].decode()
c5 = "ppt/charts/" + re.search(r'Target="(?:\.\./|/ppt/)charts/(chart\d+\.xml)"', rels5).group(1)
files[c5] = files[c5].decode().replace('<c:tickLblPos val="nextTo"/>', '<c:tickLblPos val="low"/>').encode()
tmp = deck.with_suffix(".tmp.pptx")
with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
    for n, b in files.items():
        out.writestr(n, b)
shutil.move(tmp, deck)
print("error bars added to", chart)

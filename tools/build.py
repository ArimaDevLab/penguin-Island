"""assets/penguins.glb を埋め込んで index.html（日本語）と en/index.html（英語）を作る。
使い方（リポジトリのルートで）: python3 tools/build.py
"""
import base64, pathlib, re, sys
root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / 'tools'))
from i18n_en import PAIRS, NAMES_EN

tpl = (root / 'src/game.template.html').read_text(encoding='utf-8')
glb = base64.b64encode((root / 'assets/penguins.glb').read_bytes()).decode()

# 日本語版
(root / 'index.html').write_text(tpl.replace('__GLB__', glb), encoding='utf-8')

# 英語版
en = tpl
missing = []
for ja, eng in sorted(PAIRS, key=lambda x: -len(x[0])):
    if ja in en:
        en = en.replace(ja, eng)
    elif eng not in en:
        missing.append(ja)
en, n = re.subn(r"const NAMES=\[[^\]]*\];", "const NAMES=" + repr(NAMES_EN).replace('"', "'") + ";", en)
assert n == 1, 'NAMES not found'
# 英語版は og:image などの相対パスを一つ上に
en = en.replace('content="https://penguin-island.vercel.app/og.jpg"', 'content="https://penguin-island.vercel.app/og.jpg"')
script = en[en.index('<script type="module">'):]
left = sorted(set(m.group(0) for m in re.finditer(r'[^\x00-\x7f’“”…〜→↺↻⭐✕✏️❓]*[぀-ヿ一-鿿][^\x00-\x7f]*', en)))
left = [x for x in left if '日本語' not in x]
(root / 'en').mkdir(exist_ok=True)
(root / 'en/index.html').write_text(en.replace('__GLB__', glb), encoding='utf-8')
print('index.html / en/index.html を生成しました')
if missing:
    print('未使用の置換:', missing)
if left:
    print('英語版に残った日本語:', left)

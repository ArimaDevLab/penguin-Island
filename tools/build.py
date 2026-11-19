"""assets/penguins.glb を src/game.template.html に埋め込んで index.html を作る。
使い方（リポジトリのルートで）: python3 tools/build.py
"""
import base64, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
tpl = (root / 'src/game.template.html').read_text(encoding='utf-8')
glb = base64.b64encode((root / 'assets/penguins.glb').read_bytes()).decode()
(root / 'index.html').write_text(tpl.replace('__GLB__', glb), encoding='utf-8')
print('index.html を生成しました')

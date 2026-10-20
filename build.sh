#!/usr/bin/env bash
set -o errexit
python -m pip install --upgrade pip
pip install -r requirements.txt
mkdir -p runtime_fonts
python - <<'PY'
from urllib.request import urlretrieve
fonts={
'runtime_fonts/NanumGothic-Regular.ttf':'https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothic/NanumGothic-Regular.ttf',
'runtime_fonts/NanumGothic-Bold.ttf':'https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothic/NanumGothic-Bold.ttf'}
for p,u in fonts.items(): urlretrieve(u,p)
PY

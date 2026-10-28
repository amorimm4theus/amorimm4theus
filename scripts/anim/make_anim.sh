#!/bin/bash
# Grava o efeito `decrypt` do ttfx (o mesmo do screensaver do Omarchy) sobre art.txt e gera
# assets/hero-dark.gif e assets/hero-light.gif.
#
# Requisitos: ttfx, script (util-linux), ffmpeg e Python com pyte + pillow.
# uso: PY=python3 scripts/anim/make_anim.sh
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
assets=$here/../../assets
PY=${PY:-python3}
cols=124 rows=36

# nome  fundo   marca   cor da página do GitHub (cantos)  cifra             gradiente final
themes=(
  "dark  121722 f7f8f5 0d1117 004a41,00594e,00c9ae f7f8f5,5fe3cf,00c9ae"
  "light f7f8f5 121722 ffffff 5fe3cf,00c9ae,00594e 121722,00594e,00a08b"
)

for spec in "${themes[@]}"; do
  read -r name bg mark page cipher final <<<"$spec"
  work=$(mktemp -d)
  timeout 120 script -q -T "$work/timing.log" --log-out "$work/out.raw" -c \
    "stty cols $cols rows $rows; ttfx -i $here/art.txt --frame-rate 60 --canvas-width 0 --canvas-height 0 \
     --anchor-canvas c --anchor-text c --no-eol decrypt --typing-speed 4 \
     --ciphertext-colors ${cipher//,/ } --final-gradient-stops ${final//,/ } \
     --final-gradient-steps 40 --final-gradient-direction horizontal" >/dev/null 2>&1 || true

  # 1,8x mais rápido que o tempo real; no fim, crossfade para as cores oficiais (M + seta verde-água)
  BRAND_ART=$here/art.txt BRAND_MARK=$mark BRAND_ACCENT=00c9ae SPEED=1.8 \
    "$PY" -I "$here/render.py" "$work/out.raw" "$work/timing.log" $cols $rows 30 "$work/frames" "$bg"

  "$PY" -I "$here/corners.py" 880 562 18 "#$page" "$work/mask.png"
  ffmpeg -loglevel error -y -framerate 30 -i "$work/frames/f%05d.png" -i "$work/mask.png" -filter_complex \
    "[0]tpad=stop_mode=clone:stop_duration=4,fps=15,scale=880:-1:flags=lanczos[v];[v][1]overlay=0:0,split[a][b];\
[a]palettegen=max_colors=56:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle" \
    -loop 0 "$assets/hero-$name.gif"
  rm -rf "$work"
  ls -la "$assets/hero-$name.gif"
done

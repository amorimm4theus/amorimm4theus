# Como regenerar o perfil

Tudo o que aparece no README sai daqui, com a identidade visual do [amorim-co.de](https://amorim-co.de).

```sh
python -m venv .venv && .venv/bin/pip install fonttools brotli pillow pyte

# SVGs (assets/*-dark.svg e *-light.svg) e o próprio README.md
.venv/bin/python scripts/build.py

# Animação do topo: o efeito decrypt do ttfx (o do screensaver do Omarchy) sobre anim/art.txt
PY=.venv/bin/python scripts/anim/make_anim.sh
```

- `build.py`: peças do README, tokens dos temas escuro e claro e o conteúdo (trabalhos, sigilo, stack).
  Cada SVG embute só os glifos que usa, em woff2, porque o GitHub serve SVG como `<img>` e não carrega fonte externa.
- `anim/`: grava o `ttfx` com `script -T`, reproduz num terminal virtual (pyte) e no fim assenta
  nas cores oficiais da marca (M claro, seta verde-água). `art.txt` é o mesmo do screensaver.
- `shots/`: capturas dos sites no ar usadas nos cards.

As animações dos SVGs partem de um estado visível: quem ignora CSS vê tudo pronto, e quem prefere menos movimento (`prefers-reduced-motion`) recebe a versão estática.

Fontes: Inter e JetBrains Mono, ambas sob a SIL Open Font License 1.1.

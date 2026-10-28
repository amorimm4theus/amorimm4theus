"""Gera os SVGs do perfil (assets/*-dark.svg e *-light.svg) com o design system do amorim-co.de.

Cada SVG leva só os glifos que usa (Inter + JetBrains Mono em subset woff2 embutido), porque o
GitHub serve o SVG como <img> e não carrega fonte externa.

uso: pip install fonttools brotli pillow && python scripts/build.py
"""
import base64
import io
import math
from html import escape
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "scripts" / "fonts"
ASSETS = ROOT / "assets"
W = 1280  # largura do viewBox de todas as peças largas

THEMES = {
    "dark": dict(
        bg="#121722", surface="#1a2130", fg="#f7f8f5", muted="#a9b1be", line="#f7f8f51f",
        accent="#00c9ae", accent_text="#5fe3cf", dim="#004a41", on_accent="#121722", glow=0.22,
    ),
    "light": dict(
        bg="#f7f8f5", surface="#ffffff", fg="#121722", muted="#4a5260", line="#1217221f",
        accent="#00c9ae", accent_text="#00594e", dim="#c9f3ec", on_accent="#121722", glow=0.16,
    ),
}


class Font:
    def __init__(self, key, file):
        self.key, self.path = key, FONTS / file
        tt = TTFont(self.path)
        self.cmap, self.hmtx = tt.getBestCmap(), tt["hmtx"]
        self.upm = tt["head"].unitsPerEm

    def width(self, text, size, ls=0.0):
        missing = [c for c in text if ord(c) not in self.cmap]
        if missing:
            raise ValueError(f"{self.path.name} não tem os glifos {missing!r} em {text!r}")
        adv = sum(self.hmtx[self.cmap[ord(c)]][0] for c in text)
        return adv * size / self.upm + ls * len(text)


DISPLAY = Font("fd", "Inter-ExtraBold.ttf")
SEMI = Font("fs", "Inter-SemiBold.ttf")
BODY = Font("fb", "Inter-Regular.ttf")
MONO = Font("fm", "JetBrainsMono-Medium.ttf")

# Monograma do brandbook (mesmos traçados do favicon do site)
MARK_PATHS = (
    "M274 352 H333 L740 644 L640 721 L410 563 Q396 556 388 568 V853 L274 929 Z",
    "M916 352 H979 V931 L862 851 V580 Q858 566 846 573 L782 613 L670 524 Z",
)
MARK_ARROW = "M434 648 L578 748 L434 851 V782 L480 748 L434 716 Z"

# Estado base sempre visível: quem ignora CSS (rasterizadores, app) vê tudo pronto; o navegador
# anima partindo do invisível via fill-mode both. O Chromium só inicia a animação quando o <img> entra na tela.
CSS = """
text{text-rendering:geometricPrecision}
.fu{animation:fu .9s cubic-bezier(.2,.7,.2,1) both;transform-box:fill-box}
@keyframes fu{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
.wd{animation:wd .5s ease both}
@keyframes wd{from{opacity:.16}to{opacity:1}}
.blink{animation:blink 1.1s steps(1) infinite}
@keyframes blink{50%{opacity:0}}
.pulse{opacity:0;transform-box:fill-box;transform-origin:center;animation:pulse 2.4s ease-out infinite}
@keyframes pulse{0%{opacity:.7;transform:scale(1)}100%{opacity:0;transform:scale(3.2)}}
.nudge{animation:nudge 2.6s ease-in-out infinite}
@keyframes nudge{0%,60%,100%{transform:none}75%{transform:translateX(5px)}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""


class Canvas:
    """Acumula elementos e os glifos usados por fonte para montar um SVG por tema."""

    def __init__(self, t):
        self.t, self.parts, self.used = t, [], {}

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, font, size, fill, anchor="start", ls=0.0, cls="", delay=None, extra=""):
        font.width(s, size, ls)  # valida glifos
        self.used.setdefault(font.key, set()).update(s)
        attrs = f'x="{x:.1f}" y="{y:.1f}" font-family="{font.key}" font-size="{size}" fill="{fill}"'
        if anchor != "start":
            attrs += f' text-anchor="{anchor}"'
        if ls:
            attrs += f' letter-spacing="{ls}"'
        if cls:
            attrs += f' class="{cls}"'
        if delay is not None:
            attrs += f' style="animation-delay:{delay:.2f}s"'
        self.add(f"<text {attrs} {extra}>{escape(s)}</text>")

    def rich(self, x, y, runs, size, maxw, lh, cls_words=False, delay0=0.0, step=0.06, fu=None):
        """Texto corrido com trechos de cores/pesos diferentes, quebrado por largura medida.

        runs: [(texto, Font, cor)]. Devolve o y da última linha.
        """
        words = []
        for s, font, fill in runs:
            for i, w in enumerate(s.split(" ")):
                if w:
                    words.append((w, font, fill))
        lines, cur, curw = [], [], 0.0
        for w in words:
            ww = w[1].width(w[0], size)
            sp = w[1].width(" ", size) if cur else 0
            if cur and curw + sp + ww > maxw:
                lines.append(cur)
                cur, curw = [], 0.0
                sp = 0
            cur.append(w)
            curw += sp + ww
        lines.append(cur)
        if cls_words:
            n = 0
            for li, line in enumerate(lines):
                xx = x
                for w, font, fill in line:
                    self.text(xx, y + li * lh, w, font, size, fill, cls="wd", delay=delay0 + n * step)
                    xx += font.width(w + " ", size)
                    n += 1
            return y + (len(lines) - 1) * lh
        n = 0
        for li, line in enumerate(lines):
            spans = []
            for wi, (w, font, fill) in enumerate(line):
                self.used.setdefault(font.key, set()).update(w + " ")
                lead = " " if wi else ""
                st = ""
                if cls_words:
                    st = f' class="wd" style="animation-delay:{delay0 + n * step:.2f}s"'
                n += 1
                spans.append(f'<tspan font-family="{font.key}" fill="{fill}"{st}>{escape(lead + w)}</tspan>')
            yy = y + li * lh
            wrap = ""
            if fu is not None:
                wrap = f' class="fu" style="animation-delay:{fu + li * 0.08:.2f}s"'
            self.add(f'<text x="{x:.1f}" y="{yy:.1f}" font-size="{size}" xml:space="preserve"{wrap}>{"".join(spans)}</text>')
        return y + (len(lines) - 1) * lh

    def arrow(self, x, y, size, color, diag=False, cls=""):
        """Seta → (ou ↗) desenhada em path, porque as fontes do site não têm o glifo."""
        s = size
        c = f' class="{cls}"' if cls else ""
        if diag:
            d = f"M{x:.1f} {y:.1f} L{x + s:.1f} {y - s:.1f} M{x + s * .35:.1f} {y - s:.1f} H{x + s:.1f} V{y - s * .65:.1f}"
        else:
            d = f"M{x:.1f} {y:.1f} H{x + s:.1f} M{x + s * .6:.1f} {y - s * .38:.1f} L{x + s:.1f} {y:.1f} L{x + s * .6:.1f} {y + s * .38:.1f}"
        self.add(f'<path{c} d="{d}" fill="none" stroke="{color}" stroke-width="{max(2, s * .12):.1f}" stroke-linecap="round" stroke-linejoin="round"/>')

    def mark(self, x, y, size, fill, accent):
        sc = size / 760
        self.add(
            f'<g transform="translate({x:.1f} {y:.1f}) scale({sc:.4f}) translate(-246 -262)">'
            f'<g fill="{fill}">{"".join(f"<path d={chr(34)}{p}{chr(34)}/>" for p in MARK_PATHS)}</g>'
            f'<path d="{MARK_ARROW}" fill="{accent}"/></g>'
        )

    def dot(self, x, y, r, color, pulse=True):
        if pulse:
            self.add(f'<circle class="pulse" cx="{x}" cy="{y}" r="{r}" fill="{color}"/>')
        self.add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>')

    def chip(self, x, y, label, size=17, filled=False):
        """Etiqueta mono com borda; devolve a largura ocupada."""
        t = self.t
        pad = 16
        w = MONO.width(label, size) + pad * 2
        h = size + 20
        if filled:
            self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h}" rx="{h / 2}" fill="{t["accent"]}"/>')
        else:
            self.add(f'<rect x="{x + .5:.1f}" y="{y + .5:.1f}" width="{w - 1:.1f}" height="{h - 1}" rx="{h / 2}" fill="none" stroke="{t["line"]}" stroke-width="1.5"/>')
        self.text(x + pad, y + h / 2 + size * .36, label, MONO, size, t["on_accent"] if filled else t["fg"])
        return w

    def render(self, w, h, title):
        faces = []
        for key, chars in self.used.items():
            font = next(f for f in (DISPLAY, SEMI, BODY, MONO) if f.key == key)
            faces.append(f'@font-face{{font-family:{key};src:url(data:font/woff2;base64,{subset_woff2(font, chars)}) format("woff2")}}')
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">'
            f"<title>{escape(title)}</title><style>{''.join(faces)}{CSS}</style>"
            f'{"".join(self.parts)}</svg>'
        )


_subset_cache = {}


def subset_woff2(font, chars):
    key = (font.key, "".join(sorted(chars)))
    if key not in _subset_cache:
        tt = TTFont(font.path)
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern"]
        opts.name_IDs = []
        opts.notdef_outline = True
        sub = subset.Subsetter(opts)
        sub.populate(text="".join(chars))
        sub.subset(tt)
        tt.flavor = "woff2"
        buf = io.BytesIO()
        tt.save(buf)
        _subset_cache[key] = base64.b64encode(buf.getvalue()).decode()
    return _subset_cache[key]


def jpeg_data(path, width):
    im = Image.open(path).convert("RGB")
    im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=74, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def defs_glow(c, cx, cy, r, op, gid="g"):
    t = c.t
    c.add(
        f'<defs><radialGradient id="{gid}" cx="{cx}" cy="{cy}" r="{r}" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{t["accent"]}" stop-opacity="{op}"/>'
        f'<stop offset="1" stop-color="{t["accent"]}" stop-opacity="0"/></radialGradient>'
        f'<pattern id="dots" width="28" height="28" patternUnits="userSpaceOnUse">'
        f'<circle cx="2" cy="2" r="1.3" fill="{t["fg"]}" fill-opacity=".09"/></pattern></defs>'
    )


def panel(c, w, h, glow=None, dots=False, rx=24):
    t = c.t
    c.add(f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="{rx}" fill="{t["surface"] if t is THEMES["light"] else t["bg"]}" stroke="{t["line"]}" stroke-width="1.5"/>')
    if dots:
        c.add(f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="{rx}" fill="url(#dots)"/>')
    if glow:
        c.add(f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="{rx}" fill="url(#{glow})"/>')


# ───────────────────────────── peças ─────────────────────────────


def intro(t):
    c = Canvas(t)
    x = 8
    c.text(x, 40, "TATUÍ-SP · REMOTO PARA TODO O BRASIL", MONO, 17, t["muted"], ls=3, cls="fu", delay=0)
    c.text(x - 4, 140, "Matheus Amorim", DISPLAY, 104, t["fg"], ls=-3, cls="fu", delay=.1)
    y = c.rich(x, 214, [
        ("Desenvolvedor de software sênior.", SEMI, t["fg"]),
        ("Coloco", SEMI, t["muted"]), ("IA", SEMI, t["accent_text"]),
        ("para trabalhar dentro do sistema que a sua empresa já usa.", SEMI, t["muted"]),
    ], 40, 1200, 54, fu=.25)
    y = c.rich(x, y + 62, [
        ("Há 6 anos crio sistemas, sites, apps e APIs, boa parte em PHP. Arrumo o sistema em que "
         "ninguém quer mexer e crio o que ainda falta. A IA entra onde poupa trabalho da sua equipe.", BODY, t["muted"]),
    ], 26, 1180, 38, fu=.45)
    h = y + 30
    return c.render(W, h, "Matheus Amorim, desenvolvedor de software sênior que coloca IA para trabalhar dentro do sistema que a sua empresa já usa")


def button(t, label, kind):
    c = Canvas(t)
    size, h = 22, 64
    font = SEMI
    tw = font.width(label, size)
    has_arrow = kind in ("primary", "ghost")
    has_diag = kind == "link"
    w = round(tw + 64 + (34 if has_arrow or has_diag else 0))
    if kind == "primary":
        c.add(f'<rect x="0" y="0" width="{w}" height="{h}" rx="{h / 2}" fill="{t["accent"]}"/>')
        fg = t["on_accent"]
    else:
        c.add(f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="{h / 2 - 1}" fill="none" stroke="{t["line"]}" stroke-width="2"/>')
        fg = t["fg"]
    c.text(32, h / 2 + 8, label, font, size, fg)
    if has_arrow:
        c.arrow(32 + tw + 14, h / 2, 20, fg, cls="nudge" if kind == "primary" else "")
    if has_diag:
        c.arrow(32 + tw + 16, h / 2 + 9, 16, t["accent_text"], diag=True)
    return c.render(w, h, label)


def manifesto(t):
    c = Canvas(t)
    c.text(8, 36, "( MANIFESTO )", MONO, 18, t["accent_text"], ls=3)
    hot = {"parar", "de", "travar", "IA"}
    text = "Meu trabalho é fazer o seu sistema parar de travar e colocar IA para poupar o tempo da sua equipe."
    runs, seen_travar = [], False
    for w in text.split(" "):
        is_hot = (w in hot and not seen_travar and w != "IA") or w == "IA"
        if w == "travar":
            seen_travar = True
        runs.append((w, DISPLAY, t["accent_text"] if is_hot else t["fg"]))
    y = c.rich(4, 116, runs, 62, 1250, 76, cls_words=True, delay0=.3, step=.07)
    return c.render(W, y + 30, text)


def section(t, num, title, sub):
    c = Canvas(t)
    c.text(8, 40, f"( {num} )", MONO, 20, t["accent_text"], ls=2)
    c.text(4, 112, title, DISPLAY, 64, t["fg"], ls=-1.5)
    y = c.rich(8, 162, [(sub, BODY, t["muted"])], 26, 1200, 36)
    y += 34
    c.add(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="{t["line"]}" stroke-width="1.5"/>')
    c.add(f'<line x1="0" y1="{y}" x2="96" y2="{y}" stroke="{t["accent"]}" stroke-width="3"/>')
    return c.render(W, y + 4, f"{num}. {title}: {sub}")


def work(t, num, name, seg, status, url, line, techs, shot):
    c = Canvas(t)
    h = 500
    panel(c, W, h, rx=24)
    # janela de navegador com o endereço, igual à moldura do site
    sx, sy, sw = 28, 28, 640
    sh = 400 + 44
    c.add(f'<clipPath id="win"><rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="16"/></clipPath>')
    c.add(f'<g clip-path="url(#win)"><rect x="{sx}" y="{sy}" width="{sw}" height="44" fill="{t["surface"] if t is THEMES["dark"] else t["bg"]}"/>')
    c.add(f'<image x="{sx}" y="{sy + 44}" width="{sw}" height="{400}" preserveAspectRatio="xMidYMin slice" xlink:href="{jpeg_data(shot, 1280)}"/></g>')
    c.add(f'<rect x="{sx + .75}" y="{sy + .75}" width="{sw - 1.5}" height="{sh - 1.5}" rx="16" fill="none" stroke="{t["line"]}" stroke-width="1.5"/>')
    c.text(sx + 20, sy + 28, ">", MONO, 16, t["accent_text"])
    c.text(sx + 40, sy + 28, url, MONO, 16, t["muted"])
    # texto
    x, mw = 712, W - 712 - 44
    c.text(x, 76, num, MONO, 20, t["accent_text"], ls=2)
    c.text(x + 50, 76, seg.upper(), MONO, 17, t["muted"], ls=1.5)
    ts = min(46, int(46 * mw / DISPLAY.width(name, 46, -1)))
    c.text(x - 2, 136, name, DISPLAY, ts, t["fg"], ls=-1)
    y = c.rich(x, 188, [(line, BODY, t["muted"])], 26, mw, 37)
    cx, cy = x, y + 34
    for tech in techs:
        wch = MONO.width(tech, 18) + 32
        if cx + wch > x + mw:
            cx, cy = x, cy + 50
        cx += c.chip(cx, cy, tech, size=18) + 10
    by = h - 64
    c.dot(x + 6, by - 6, 6, t["accent"])
    c.text(x + 24, by, status.split(" · ")[0], MONO, 19, t["fg"])
    lw = SEMI.width("Ver o site no ar", 23)
    c.text(W - 44 - lw - 28, by, "Ver o site no ar", SEMI, 23, t["accent_text"])
    c.arrow(W - 44 - 16, by + 1, 15, t["accent_text"], diag=True)
    return c.render(W, h, f"{name}: {line}")


def shop(t):
    c = Canvas(t)
    h = 320
    defs_glow(c, W - 160, 40, 620, t["glow"])
    panel(c, W, h, glow="g", dots=True)
    c.add(f'<rect x="44" y="44" width="78" height="32" rx="16" fill="{t["accent"]}"/>')
    c.text(83, 66, "NOVO", MONO, 15, t["on_accent"], anchor="middle", ls=2)
    c.text(140, 66, "LOJA VIRTUAL SOB MEDIDA", MONO, 15, t["muted"], ls=2)
    c.text(42, 140, "Sua loja aberta 24 horas,", DISPLAY, 46, t["fg"], ls=-1)
    c.text(42, 194, "com a cara da sua marca", DISPLAY, 46, t["accent_text"], ls=-1)
    c.rich(44, 248, [("Pix que confirma sozinho, frete calculado na hora, estoque que não vende o que acabou, "
                      "etiqueta e rastreio num painel só.", BODY, t["muted"])], 25, 820, 35)
    label = "Quero uma loja assim"
    bw = SEMI.width(label, 22) + 64 + 34
    bx, byy = W - 44 - bw, 120
    c.add(f'<rect x="{bx:.1f}" y="{byy}" width="{bw:.1f}" height="64" rx="32" fill="{t["accent"]}"/>')
    c.text(bx + 32, byy + 40, label, SEMI, 22, t["on_accent"])
    c.arrow(bx + bw - 32 - 20, byy + 32, 20, t["on_accent"], cls="nudge")
    return c.render(W, h, "Loja virtual sob medida: sua loja aberta 24 horas, com a cara da sua marca")


SIGILO = [
    ("Plataforma de gestão de frotas", "Os dados precisavam passar para outros sistemas sozinhos e sem erro.",
     "Integrações financeira e de CIOT, entregues uma de cada vez.", "Logística / Integração"),
    ("Posto de saúde universitário", "Recepção confirmava cada consulta manualmente.",
     "Confirmação automática por WhatsApp, com chat para remarcar.", "Saúde / Automação"),
    ("Gestão de saúde pública", "Cidadão ia até a farmácia para saber se havia o remédio.",
     "Consulta pública ligada ao estoque da farmácia.", "Saúde pública / Transparência"),
    ("Instituição de ensino superior", "Aluno precisava de uma senha a mais para o sistema de saúde.",
     "Login único com a conta Microsoft da instituição.", "Educação / SSO"),
    ("Consultoria agro", "As informações dos produtores parceiros ficavam espalhadas.",
     "ERP sob medida para cadastro e acompanhamento da rede.", "Agro / ERP"),
]


def sigilo(t):
    c = Canvas(t)
    c.text(8, 44, "Sob sigilo de contrato", DISPLAY, 44, t["fg"], ls=-.8)
    c.rich(8, 92, [("Sistemas que entreguei para clientes que, por contrato, eu não posso citar.", BODY, t["muted"])], 26, 1240, 36)
    y = 150
    c1, c2 = 8, 440
    c.text(c1, y, "SEGMENTO E ÁREA", MONO, 17, t["muted"], ls=2.5)
    c.text(c2, y, "PROBLEMA E SOLUÇÃO", MONO, 17, t["muted"], ls=2.5)
    y += 24
    c.add(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="{t["line"]}" stroke-width="1.5"/>')
    for i, (seg, prob, sol, area) in enumerate(SIGILO):
        top = y + 50
        c.add(f'<g class="fu" style="animation-delay:{.15 + i * .12:.2f}s">')
        yl = c.rich(c1, top, [(seg, SEMI, t["fg"])], 28, 400, 36)
        c.text(c1, yl + 38, area.upper(), MONO, 17, t["accent_text"], ls=1.5)
        yl += 38
        yp = c.rich(c2, top, [(prob, BODY, t["muted"])], 26, W - c2 - 8, 36)
        c.arrow(c2 + 2, yp + 38, 20, t["accent_text"])
        ys = c.rich(c2 + 36, yp + 46, [(sol, SEMI, t["fg"])], 26, W - c2 - 44, 36)
        c.add("</g>")
        y = max(yl, ys) + 38
        c.add(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="{t["line"]}" stroke-width="1.5"/>')
    return c.render(W, y + 4, "Trabalhos sob sigilo de contrato: segmento, problema, solução e área")


PROBLEMS = [
    ("Planilha", "Um sistema simples no lugar da planilha"),
    ("Integrações", "Integração que tenta de novo sozinha quando o outro sistema cai"),
    ("Logística", "App que manda a foto do canhoto direto para o sistema"),
    ("Sistema antigo", "Como arrumo o sistema que só uma pessoa entende"),
]


def problems(t):
    c = Canvas(t)
    gap, cw, chh = 24, (W - 24) / 2, 190
    for i, (tag, title) in enumerate(PROBLEMS):
        x = (i % 2) * (cw + gap)
        y = (i // 2) * (chh + gap)
        c.add(f'<g class="fu" style="animation-delay:{.1 + i * .1:.2f}s">')
        c.add(f'<rect x="{x + 1:.1f}" y="{y + 1}" width="{cw - 2:.1f}" height="{chh - 2}" rx="20" fill="{t["surface"] if t is THEMES["light"] else t["bg"]}" stroke="{t["line"]}" stroke-width="1.5"/>')
        c.text(x + 32, y + 50, f"0{i + 1}", MONO, 19, t["accent_text"], ls=2)
        c.text(x + 78, y + 50, tag.upper(), MONO, 18, t["muted"], ls=2)
        c.rich(x + 32, y + 104, [(title, SEMI, t["fg"])], 30, cw - 100, 40)
        c.arrow(x + cw - 56, y + 52, 20, t["accent_text"])
        c.add("</g>")
    return c.render(W, 2 * chh + gap + 2, "Problemas que eu resolvo: " + "; ".join(p[1] for p in PROBLEMS))


STACK = [
    ("FOCO", [("IA aplicada", True), ("PHP · 6 anos", False)]),
    ("BACK-END", [("PHP", False), ("Laravel", False), ("NestJS", False), ("Node.js", False)]),
    ("FRONT-END", [("React", False), ("Next.js", False), ("Angular", False), ("Tailwind CSS", False), ("GSAP", False)]),
    ("MOBILE", [("React Native", False)]),
    ("DADOS E INFRA", [("PostgreSQL", False), ("MySQL", False), ("Docker", False), ("Linux", False), ("Git", False)]),
    ("DESIGN", [("Figma", False)]),
]


def stack(t):
    c = Canvas(t)
    y = 0
    for i, (label, items) in enumerate(STACK):
        c.add(f'<g class="fu" style="animation-delay:{.1 + i * .08:.2f}s">')
        c.text(8, y + 42, label, MONO, 18, t["muted"], ls=2.5)
        x = 290
        for name, filled in items:
            x += c.chip(x, y + 10, name, size=23, filled=filled) + 14
        c.add("</g>")
        y += 78
        if i < len(STACK) - 1:
            c.add(f'<line x1="0" y1="{y - 6}" x2="{W}" y2="{y - 6}" stroke="{t["line"]}" stroke-width="1"/>')
    return c.render(W, y, "Tecnologias: " + "; ".join(f"{l}: " + ", ".join(n for n, _ in it) for l, it in STACK))


STATS = [
    ("6", "anos", "de PHP em sistemas que estão em uso"),
    ("4", "setores", "com sistema no ar: saúde, logística, educação e agro"),
    ("100%", "", "dos projetos começam com escopo e prazo fechados por escrito"),
]


def stats(t):
    c = Canvas(t)
    colw = W / 3
    for i, (big, unit, cap) in enumerate(STATS):
        x = i * colw + (8 if i == 0 else 28)
        c.add(f'<g class="fu" style="animation-delay:{.1 + i * .15:.2f}s">')
        c.text(x - 4, 112, big, DISPLAY, 112, t["accent_text"], ls=-4)
        if unit:
            c.text(x + DISPLAY.width(big, 112, -4) + 10, 112, unit, SEMI, 30, t["fg"])
        c.rich(x, 166, [(cap, BODY, t["muted"])], 25, colw - 56, 35)
        c.add("</g>")
        if i:
            c.add(f'<line x1="{i * colw}" y1="20" x2="{i * colw}" y2="230" stroke="{t["line"]}" stroke-width="1.5"/>')
    y = 300
    y = c.rich(8, y, [
        ("Já atuei em healthtech, logtech e fintech. Além do PHP, faço telas em React, Next.js e Angular, apps de "
         "celular em React Native e APIs em NestJS. Meu foco hoje é", BODY, t["muted"]),
        ("IA aplicada:", SEMI, t["accent_text"]),
        ("colocar IA dentro de sistemas que já existem, para tirar trabalho repetitivo das pessoas.", BODY, t["muted"]),
    ], 26, 1240, 38, fu=.5)
    y = c.rich(8, y + 64, [("Você fala direto comigo. Eu mesmo leio e respondo cada contato.", SEMI, t["fg"])], 26, 1240, 36, fu=.7)
    return c.render(W, y + 24, "6 anos de PHP; 4 setores com sistema no ar; 100% dos projetos com escopo e prazo fechados por escrito")


def cta(t):
    c = Canvas(t)
    body = Canvas(t)  # mede a altura do texto antes de desenhar o painel
    yt = body.rich(56, 304, [("Me conte como ele funciona hoje. São 30 minutos: eu entendo o problema e digo "
                              "se consigo ajudar.", BODY, t["muted"])], 24, 720, 36)
    by = yt + 52
    h = by + 68 + 56
    defs_glow(c, W * .82, h * .15, 760, t["glow"] + .06)
    panel(c, W, h, glow="g", dots=True, rx=28)
    c.text(56, 84, "( 04 )  CONTATO", MONO, 18, t["accent_text"], ls=3)
    c.text(52, 170, "O seu caso parece", DISPLAY, 68, t["fg"], ls=-2)
    c.text(52, 246, "com algum destes?", DISPLAY, 68, t["fg"], ls=-2)
    c.parts += body.parts
    for k, v in body.used.items():
        c.used.setdefault(k, set()).update(v)
    label = "Quero uma conversa sem custo"
    bw = SEMI.width(label, 24) + 64 + 36
    bx = 56
    c.add(f'<rect x="{bx}" y="{by}" width="{bw:.1f}" height="68" rx="34" fill="{t["accent"]}"/>')
    c.text(bx + 32, by + 43, label, SEMI, 24, t["on_accent"])
    c.arrow(bx + bw - 32 - 22, by + 34, 22, t["on_accent"], cls="nudge")
    # terminal com o domínio, como na imagem de compartilhamento do site
    term = "amorim-co.de"
    tw = MONO.width(term, 28) + 120
    tx, ty = W - 56 - tw, by
    c.add(f'<rect x="{tx:.1f}" y="{ty}" width="{tw:.1f}" height="68" rx="14" fill="{t["bg"]}" fill-opacity=".6" stroke="{t["line"]}" stroke-width="1.5"/>')
    c.text(tx + 28, ty + 44, ">", MONO, 28, t["accent_text"])
    c.text(tx + 62, ty + 44, term, MONO, 28, t["fg"])
    c.add(f'<rect class="blink" x="{tx + 62 + MONO.width(term, 28) + 10:.1f}" y="{ty + 46}" width="18" height="4" fill="{t["accent"]}"/>')
    c.mark(W - 56 - 210, 70, 210, t["fg"], t["accent"])
    return c.render(W, h, "Contato: o seu caso parece com algum destes? Quero uma conversa sem custo em amorim-co.de")


def footer(t):
    c = Canvas(t)
    c.add(f'<line x1="0" y1="1" x2="{W}" y2="1" stroke="{t["line"]}" stroke-width="1.5"/>')
    c.mark(8, 36, 52, t["fg"], t["accent"])
    c.text(80, 60, "Matheus Amorim", SEMI, 22, t["fg"])
    c.text(80, 88, "IA aplicada e PHP", BODY, 20, t["muted"])
    c.text(W - 8, 60, "amorim-co.de", MONO, 22, t["fg"], anchor="end")
    c.text(W - 8, 88, "lê-se “Amorim code”", MONO, 18, t["muted"], anchor="end")
    return c.render(W, 112, "Matheus Amorim · amorim-co.de")


PIECES = {
    "intro": intro,
    "btn-conversa": lambda t: button(t, "Quero uma conversa sem custo", "primary"),
    "btn-trabalhos": lambda t: button(t, "Ver o que já entreguei", "ghost"),
    "btn-instagram": lambda t: button(t, "@matheus_amorimcode", "link"),
    "manifesto": manifesto,
    "sec-trabalhos": lambda t: section(t, "01", "Trabalhos", "Feito para você parar de rolar e se perguntar como eu fiz"),
    "work-estanagel": lambda t: work(
        t, "01", "Estanagel Filmes", "Produtora audiovisual", "Site no ar", "estanagel.amorim-co.de",
        "Página com cara de cinema que leva cada visitante para o WhatsApp do diretor. Vídeo que se adapta à rede.",
        ["Next.js", "GSAP", "Tailwind CSS", "Docker"], ROOT / "scripts/shots/estanagel.jpg"),
    "work-dimdim": lambda t: work(
        t, "02", "DIMDIM Papelaria Criativa", "Varejo · papelaria feita à mão", "Site no ar · loja em construção",
        "dimdim.art.br",
        "Site em português, espanhol e inglês que recebe pedidos de orçamento. A loja virtual vem em seguida.",
        ["Next.js", "Laravel", "MySQL", "Docker"], ROOT / "scripts/shots/dimdim.jpg"),
    "shop": shop,
    "sigilo": sigilo,
    "sec-faco": lambda t: section(t, "02", "O que faço", "Problemas que eu resolvo: cada um talvez seja o que a sua empresa tem hoje"),
    "problems": problems,
    "stack": stack,
    "sec-sobre": lambda t: section(t, "03", "Prazer, Matheus.", "Seis anos escrevendo sistemas que empresas usam todo dia e não podem parar"),
    "stats": stats,
    "cta": cta,
    "footer": footer,
}


# ───────────────────────────── README ─────────────────────────────


def pic(name, alt, ext="svg", size='width="100%"'):
    return (
        f'<picture><source media="(prefers-color-scheme: dark)" srcset="assets/{name}-dark.{ext}">'
        f'<source media="(prefers-color-scheme: light)" srcset="assets/{name}-light.{ext}">'
        f'<img alt="{escape(alt)}" src="assets/{name}-dark.{ext}" {size}></picture>'
    )


def link(href, inner):
    return f'<a href="{href}">{inner}</a>'


SITE = "https://amorim-co.de"
GAP = "<br><br>"

README = [
    "<!-- Gerado por scripts/build.py (SVGs) e scripts/anim (animação). Identidade visual: amorim-co.de -->",
    link(SITE, pic("hero", "Monograma M e o domínio amorim-co.de se revelando em texto cifrado", "gif")),
    "<br>",
    pic("intro", "Matheus Amorim. Desenvolvedor de software sênior. Coloco IA para trabalhar dentro do sistema que a sua empresa já usa."),
    "<p>\n  " + "\n  ".join([
        link(f"{SITE}/#contato", pic("btn-conversa", "Quero uma conversa sem custo", size='height="48"')),
        link("#trabalhos", pic("btn-trabalhos", "Ver o que já entreguei", size='height="48"')),
        link("https://www.instagram.com/matheus_amorimcode/", pic("btn-instagram", "Instagram @matheus_amorimcode", size='height="48"')),
    ]) + "\n</p>",
    "<br>",
    pic("manifesto", "Manifesto: meu trabalho é fazer o seu sistema parar de travar e colocar IA para poupar o tempo da sua equipe."),
    GAP,
    f'<a name="trabalhos"></a>{pic("sec-trabalhos", "01. Trabalhos: feito para você parar de rolar e se perguntar como eu fiz")}',
    link("https://estanagel.amorim-co.de", pic("work-estanagel", "Estanagel Filmes, produtora audiovisual: página com cara de cinema que leva cada visitante para o WhatsApp do diretor")),
    link("https://dimdim.art.br", pic("work-dimdim", "DIMDIM Papelaria Criativa: site em três idiomas que recebe pedidos de orçamento")),
    link(f"{SITE}/#case-loja", pic("shop", "Loja virtual sob medida: sua loja aberta 24 horas, com a cara da sua marca")),
    GAP,
    pic("sigilo", "Trabalhos sob sigilo de contrato: frotas, saúde universitária, saúde pública, ensino superior e consultoria agro"),
    GAP,
    pic("sec-faco", "02. O que faço: problemas que eu resolvo"),
    link(f"{SITE}/#em-movimento", pic("problems", "Problemas que eu resolvo: planilha, integrações, logística e sistema antigo")),
    GAP,
    pic("stack", "Tecnologias: IA aplicada, PHP, Laravel, NestJS, Node.js, React, Next.js, Angular, Tailwind CSS, GSAP, React Native, PostgreSQL, MySQL, Docker, Linux, Git e Figma"),
    GAP,
    pic("sec-sobre", "03. Prazer, Matheus."),
    pic("stats", "6 anos de PHP, 4 setores com sistema no ar e 100% dos projetos com escopo e prazo fechados por escrito"),
    GAP,
    link(f"{SITE}/#contato", pic("cta", "O seu caso parece com algum destes? Quero uma conversa sem custo em amorim-co.de")),
    GAP,
    link(SITE, pic("footer", "Matheus Amorim · amorim-co.de")),
]


def main():
    ASSETS.mkdir(exist_ok=True)
    total = 0
    for name, fn in PIECES.items():
        for theme, t in THEMES.items():
            svg = fn(t)
            out = ASSETS / f"{name}-{theme}.svg"
            out.write_text(svg, encoding="utf-8")
            total += len(svg)
    (ROOT / "README.md").write_text("\n\n".join(README) + "\n", encoding="utf-8")
    print(f"{len(PIECES) * 2} SVGs, {total / 1024:.0f} KB, README.md")


if __name__ == "__main__":
    main()

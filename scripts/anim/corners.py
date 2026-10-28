"""Máscara com os cantos pintados na cor da página do GitHub, para o GIF parecer arredondado.

uso: corners.py largura altura raio cor saida.png
"""
import sys

from PIL import Image, ImageDraw

w, h, r = map(int, sys.argv[1:4])
color, out = sys.argv[4], sys.argv[5]
s = 4  # supersampling para a curva sair suave
m = Image.new("RGBA", (w * s, h * s), color)
ImageDraw.Draw(m).rounded_rectangle([0, 0, w * s - 1, h * s - 1], r * s, fill=(0, 0, 0, 0))
m.resize((w, h), Image.LANCZOS).save(out)

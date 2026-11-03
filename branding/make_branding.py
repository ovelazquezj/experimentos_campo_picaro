#!/usr/bin/env python3
"""
make_branding.py  -  Genera el icono de PiCARO en todos los tamanos.

PiCARO = Pi (dispositivos embebidos) + Icaro (mitologia griega: el vuelo, el
ascenso). El emblema une las dos lecturas:

  · un NODO embebido brillante en la base        -> "Pi"
  · una PLUMA/ALA dorada que asciende, cuyas      -> "Icaro" + ondas de radio
    barbas son a la vez arcos de senal LoRa          que irradian hacia arriba
  · un cielo nocturno de fondo                    -> la altura, el alcance

Se dibuja con Pillow y supermuestreo (SS x4) para que quede limpio hasta en el
favicon de 16 px. Salidas en este mismo directorio.
"""
import math
import os

from PIL import Image, ImageDraw

AQUI = os.path.dirname(os.path.abspath(__file__))
SS = 4  # supermuestreo

# --- Paleta ---------------------------------------------------------------
NAVY_TOP = (26, 56, 104)     # indigo (arriba)
NAVY_BOT = (7, 16, 36)       # casi negro (abajo)
GOLD_HI  = (255, 216, 128)   # oro claro
GOLD_MI  = (255, 168, 66)    # oro
GOLD_LO  = (255, 120, 42)    # sol / naranja
CORE     = (240, 249, 255)   # nucleo casi blanco
CYAN     = (122, 228, 255)   # resplandor del nodo


def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def fondo(size):
    """Gradiente vertical cielo nocturno + un halo suave detras del emblema."""
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        c = _lerp(NAVY_TOP, NAVY_BOT, y / (size - 1))
        for x in range(size):
            px[x, y] = c
    # Halo radial calido, centrado algo por encima del medio (donde nace el ala).
    halo = Image.new("L", (size, size), 0)
    hd = ImageDraw.Draw(halo)
    cx, cy = size * 0.5, size * 0.44
    R = size * 0.42
    for i in range(60, 0, -1):
        r = R * i / 60
        a = int(38 * (1 - i / 60))
        hd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=a)
    tinte = Image.new("RGB", (size, size), (60, 90, 150))
    img = Image.composite(tinte, img, halo)
    return img.convert("RGBA")


def _arco(draw, cx, cy, r, a0, a1, width, color):
    """Arco liso (Pillow nativo) con extremos redondeados."""
    draw.arc([cx - r, cy - r, cx + r, cy + r], a0, a1, fill=color, width=int(width))
    rr = width / 2
    for a in (a0, a1):
        x = cx + r * math.cos(math.radians(a))
        y = cy + r * math.sin(math.radians(a))
        draw.ellipse([x - rr, y - rr, x + rr, y + rr], fill=color)


def _pluma(draw, nodo, tip, ancho, color):
    """Hoja/pluma puntiaguda entre 'nodo' (base) y 'tip' (punta)."""
    nx, ny = nodo
    tx, ty = tip
    dx, dy = tx - nx, ty - ny
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L      # a lo largo
    px, py = -uy, ux             # perpendicular
    izq, der = [], []
    N = 60
    for k in range(N + 1):
        t = k / N
        # Grosor: 0 en la base, maximo hacia 1/3, 0 en la punta (forma de hoja).
        w = ancho * math.sin(math.pi * t) ** 0.85 * (1 - 0.35 * t)
        bx = nx + ux * L * t
        by = ny + uy * L * t
        izq.append((bx + px * w, by + py * w))
        der.append((bx - px * w, by - py * w))
    draw.polygon(izq + der[::-1], fill=color)


def emblema(size, escala=0.82):
    """Emblema centrado sobre fondo transparente."""
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Marco util (zona segura) centrado.
    m = S * (1 - escala) / 2
    W = S - 2 * m
    nodo = (m + W * 0.40, m + W * 0.70)     # base: el nodo embebido

    # 1) Arcos de senal / barbas del ala, irradiando hacia arriba-derecha.
    #    En Pillow el angulo crece en sentido horario con y hacia abajo:
    #    270 = arriba, 0 = derecha. Abanico centrado un poco a la derecha.
    for i, (r, w, col) in enumerate([
        (W * 0.30, W * 0.045, GOLD_LO),
        (W * 0.42, W * 0.050, GOLD_MI),
        (W * 0.55, W * 0.055, GOLD_HI),
    ]):
        _arco(d, nodo[0], nodo[1], r, 202, 348, int(w), col)

    # 2) UNA pluma principal ascendente (el "vuelo"), que sube por el centro sin
    #    rebasar el arco superior: es lo que convierte el abanico de senal en ala.
    _pluma(d, nodo, (m + W * 0.50, m + W * 0.18), W * 0.055, GOLD_HI)

    # 3) Base embebida: una pequena placa/chip bajo el nodo (guino a lo "Pi"),
    #    en vez de patitas sueltas que parecian un compas.
    bw, bh = W * 0.13, W * 0.05
    bx, by = nodo[0], nodo[1] + W * 0.15
    d.rounded_rectangle([bx - bw, by - bh, bx + bw, by + bh],
                        radius=bh * 0.5, fill=GOLD_MI)
    for k in (-1, 0, 1):   # tres "pines"
        px_ = bx + k * bw * 0.6
        d.line([(px_, by + bh), (px_, by + bh + W * 0.03)],
               fill=GOLD_HI, width=int(W * 0.018))

    # 4) Nucleo del nodo con resplandor.
    for r, col, a in [(W * 0.11, CYAN, 70), (W * 0.075, CYAN, 130)]:
        glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse([nodo[0] - r, nodo[1] - r, nodo[0] + r, nodo[1] + r],
                   fill=col + (a,))
        img = Image.alpha_composite(img, glow)
        d = ImageDraw.Draw(img)
    rr = W * 0.055
    d.ellipse([nodo[0] - rr, nodo[1] - rr, nodo[0] + rr, nodo[1] + rr], fill=CORE)

    return img.resize((size, size), Image.LANCZOS)


def icono_completo(size):
    bg = fondo(size)
    em = emblema(size, escala=0.86)
    return Image.alpha_composite(bg, em)


def guardar(img, nombre):
    ruta = os.path.join(AQUI, nombre)
    img.save(ruta)
    print(f"  {nombre}  ({img.size[0]}x{img.size[1]})")


def main():
    print("Generando branding PiCARO en", AQUI)

    # Icono maestro (con fondo) y derivados cuadrados.
    maestro = icono_completo(1024)
    guardar(maestro, "icon_1024.png")
    for s in (512, 192, 180, 48, 32, 16):
        guardar(icono_completo(s), f"icon_{s}.png")

    # Icono adaptativo de Android: primer plano (emblema) + fondo por separado.
    guardar(emblema(1024, escala=0.62), "adaptive_foreground_1024.png")  # zona segura 66%
    guardar(fondo(1024), "adaptive_background_1024.png")

    # Splash: emblema sobre transparente, para flutter_native_splash.
    guardar(emblema(1152, escala=0.70), "splash_logo_1152.png")

    # Favicon .ico multiescala.
    ico = icono_completo(256)
    ico.save(os.path.join(AQUI, "favicon.ico"),
             sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    print("  favicon.ico  (16/32/48/64)")

    print("Listo.")


if __name__ == "__main__":
    main()

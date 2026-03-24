"""
inspeccionar_csv.py
───────────────────
Inspección de archivos CSV/TXT pesados SIN cargar todo en memoria.

Reporte:
  1. Tamaño del archivo en disco
  2. Número total de filas y columnas
  3. Tipos de datos inferidos por columna
  4. Porcentaje de nulos por columna
  5. Primeras 5 y últimas 5 filas

Estrategia de memoria:
  - Encoding y separador: detectados leyendo solo los primeros bytes
  - Filas/nulos/tipos   : pd.read_csv con chunksize (nunca >CHUNK_SIZE filas en RAM)
  - Últimas 5 filas     : collections.deque de tamaño 5 sobre el iterador de chunks
  - Primeras 5 filas    : pd.read_csv con nrows=5

Uso:
  python3 inspeccionar_csv.py <archivo> [separador] [encoding] [--chunk N]

Ejemplos:
  python3 inspeccionar_csv.py datos.txt
  python3 inspeccionar_csv.py datos.txt |
  python3 inspeccionar_csv.py datos.csv ; cp1252 --chunk 200000
"""

import argparse
import csv
import os
import sys
import time
from collections import defaultdict, deque

import pandas as pd

# ── Constantes ─────────────────────────────────────────────────────────────────
CHUNK_SIZE     = 100_000   # filas por chunk (≈ 50-200 MB según columnas)
SEP_VISUAL     = "=" * 65
SEP_THIN       = "-" * 65


# ══════════════════════════════════════════════════════════════════════════════
# Detección de encoding y separador
# ══════════════════════════════════════════════════════════════════════════════

def detectar_encoding(ruta: str) -> str:
    """Detecta encoding leyendo solo los primeros bytes."""
    with open(ruta, "rb") as f:
        bom = f.read(4)

    if bom[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    if bom[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"
    if bom[:4] in (b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff"):
        return "utf-32"

    # Intentar chardet si está disponible (más preciso)
    try:
        import chardet
        with open(ruta, "rb") as f:
            muestra = f.read(200_000)
        res = chardet.detect(muestra)
        enc = res.get("encoding") or "utf-8"
        conf = res.get("confidence", 0)
        print(f"[INFO] Encoding detectado: {enc!r}  (confianza {conf:.0%})")
        return enc
    except ImportError:
        pass

    # Fallback: probar encodings comunes
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(ruta, encoding=enc, errors="strict") as f:
                f.read(100_000)
            print(f"[INFO] Encoding detectado por prueba: {enc!r}")
            return enc
        except (UnicodeDecodeError, LookupError):
            continue

    print("[AVISO] No se pudo detectar encoding con certeza, usando latin-1")
    return "latin-1"


def detectar_separador(ruta: str, encoding: str) -> str:
    """Detecta el separador leyendo solo las primeras 20 líneas."""
    try:
        with open(ruta, encoding=encoding, errors="replace") as f:
            muestra = "".join(f.readline() for _ in range(20))
        dialecto = csv.Sniffer().sniff(muestra, delimiters=",;|\t:")
        sep = dialecto.delimiter
        nombre = {"\\t": "tabulador", ",": "coma", ";": "punto y coma",
                  "|": "pipe", ":": "dos puntos"}.get(repr(sep).strip("'"), repr(sep))
        print(f"[INFO] Separador detectado: {nombre!r}  ({repr(sep)})")
        return sep
    except csv.Error:
        print("[AVISO] No se pudo detectar separador; usando coma.")
        return ","


# ══════════════════════════════════════════════════════════════════════════════
# Helpers de formato
# ══════════════════════════════════════════════════════════════════════════════

def fmt_bytes(n: int) -> str:
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.2f} {unidad}"
        n /= 1024
    return f"{n:.2f} PB"


def barra(pct: float, ancho: int = 20) -> str:
    lleno = int(pct / 100 * ancho)
    return "█" * lleno + "░" * (ancho - lleno)


def progreso(filas_vistas: int, t0: float, total_bytes: int = 0, bytes_leidos: int = 0):
    elapsed = time.time() - t0
    if bytes_leidos and total_bytes:
        pct = bytes_leidos / total_bytes * 100
        print(f"\r  Procesando… {filas_vistas:>12,} filas  |  "
              f"{pct:5.1f}%  {fmt_bytes(bytes_leidos)}/{fmt_bytes(total_bytes)}  "
              f"({elapsed:.0f}s)", end="", flush=True)
    else:
        print(f"\r  Procesando… {filas_vistas:>12,} filas  ({elapsed:.0f}s)",
              end="", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# Núcleo: una sola pasada en chunks
# ══════════════════════════════════════════════════════════════════════════════

def inspeccionar(ruta: str, sep: str, encoding: str, chunk_size: int) -> None:

    tam_bytes = os.path.getsize(ruta)

    # ── 1. Tamaño en disco ────────────────────────────────────────────────────
    print(f"\n{SEP_VISUAL}")
    print("  ARCHIVO")
    print(SEP_VISUAL)
    print(f"  Ruta    : {ruta}")
    print(f"  Tamaño  : {fmt_bytes(tam_bytes)}  ({tam_bytes:,} bytes)")

    # ── 2. Primeras 5 filas (nrows=5, coste mínimo) ───────────────────────────
    df_head = pd.read_csv(ruta, sep=sep, encoding=encoding, nrows=5,
                          low_memory=False, on_bad_lines="warn")
    columnas = list(df_head.columns)
    n_cols   = len(columnas)

    # ── Acumuladores para la pasada única ─────────────────────────────────────
    total_filas  = 0
    null_counts  = defaultdict(int)          # col → total nulos
    dtype_votos  = defaultdict(lambda: defaultdict(int))  # col → {dtype: count}
    cola_5       = deque(maxlen=5)           # últimas 5 filas (DataFrames de 1 fila)

    t0 = time.time()
    bytes_offset = 0

    reader = pd.read_csv(
        ruta,
        sep=sep,
        encoding=encoding,
        chunksize=chunk_size,
        low_memory=False,
        on_bad_lines="warn",
    )

    print(f"\n  Pasada única en chunks de {chunk_size:,} filas …")

    for chunk in reader:
        total_filas  += len(chunk)
        bytes_offset += chunk.memory_usage(deep=True).sum()

        # Nulos
        for col in columnas:
            if col in chunk.columns:
                null_counts[col] += int(chunk[col].isna().sum())

        # Votos de dtype (pandas puede cambiar el tipo entre chunks)
        for col in columnas:
            if col in chunk.columns:
                dtype_votos[col][str(chunk[col].dtype)] += 1

        # Cola para últimas 5 filas
        for i in range(max(0, len(chunk) - 5), len(chunk)):
            cola_5.append(chunk.iloc[[i]])

        progreso(total_filas, t0, tam_bytes, bytes_offset)

    print()  # salto de línea tras la barra de progreso

    elapsed = time.time() - t0
    print(f"  Completado en {elapsed:.1f}s  |  "
          f"velocidad ≈ {fmt_bytes(int(tam_bytes / elapsed))}/s")

    # ── Dtype final: el más votado por chunk ──────────────────────────────────
    dtype_final = {}
    for col in columnas:
        votos = dtype_votos[col]
        dtype_final[col] = max(votos, key=votos.get)

    # ── Últimas 5 filas ───────────────────────────────────────────────────────
    df_tail = pd.concat(list(cola_5), ignore_index=True) if cola_5 else pd.DataFrame()

    # ════════════════════════════════════════════════════════════════════════
    # REPORTE
    # ════════════════════════════════════════════════════════════════════════

    pd.set_option("display.max_columns",  None)
    pd.set_option("display.width",        220)
    pd.set_option("display.max_colwidth", 30)

    # ── Dimensiones ───────────────────────────────────────────────────────────
    print(f"\n{SEP_VISUAL}")
    print("  DIMENSIONES")
    print(SEP_VISUAL)
    print(f"  Filas    : {total_filas:,}")
    print(f"  Columnas : {n_cols:,}")

    # ── Tipos de datos ────────────────────────────────────────────────────────
    print(f"\n{SEP_VISUAL}")
    print("  TIPOS DE DATOS POR COLUMNA")
    print(SEP_VISUAL)
    ancho = max(len(c) for c in columnas) + 2
    print(f"  {'Columna':<{ancho}}  {'Tipo inferido'}")
    print(f"  {'-'*ancho}  {'-'*20}")
    for col in columnas:
        print(f"  {col:<{ancho}}  {dtype_final.get(col, '?')}")

    # ── Nulos ─────────────────────────────────────────────────────────────────
    print(f"\n{SEP_VISUAL}")
    print("  NULOS POR COLUMNA")
    print(SEP_VISUAL)
    print(f"  {'Columna':<{ancho}}  {'Nulos':>10}  {'%':>7}  Barra (100%)")
    print(f"  {'-'*ancho}  {'-'*10}  {'-'*7}  {'-'*22}")
    nulos_ord = sorted(columnas, key=lambda c: null_counts[c], reverse=True)
    for col in nulos_ord:
        n    = null_counts[col]
        pct  = n / total_filas * 100 if total_filas else 0
        alerta = "  ⚠" if pct > 20 else ""
        print(f"  {col:<{ancho}}  {n:>10,}  {pct:>6.2f}%  {barra(pct)}{alerta}")

    # ── Primeras 5 filas ──────────────────────────────────────────────────────
    print(f"\n{SEP_VISUAL}")
    print("  PRIMERAS 5 FILAS")
    print(SEP_VISUAL)
    print(df_head.to_string(index=True))

    # ── Últimas 5 filas ───────────────────────────────────────────────────────
    print(f"\n{SEP_VISUAL}")
    print("  ÚLTIMAS 5 FILAS")
    print(SEP_VISUAL)
    if not df_tail.empty:
        # Restaurar índice real aproximado
        df_tail.index = range(total_filas - len(df_tail), total_filas)
        print(df_tail.to_string(index=True))
    else:
        print("  (sin datos)")

    print(f"\n{SEP_VISUAL}")
    print("  Inspección completada.")
    print(SEP_VISUAL)


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Inspecciona un CSV/TXT grande sin cargarlo completo en memoria.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("archivo",  help="Ruta al archivo CSV o TXT")
    parser.add_argument("separador", nargs="?", default=None,
                        help="Separador de columnas (auto-detectado si se omite)")
    parser.add_argument("encoding",  nargs="?", default=None,
                        help="Encoding (auto-detectado si se omite)")
    parser.add_argument("--chunk", type=int, default=CHUNK_SIZE,
                        help=f"Filas por chunk (default: {CHUNK_SIZE:,})")
    args = parser.parse_args()

    if not os.path.exists(args.archivo):
        print(f"[ERROR] No se encontró: {args.archivo}")
        sys.exit(1)

    enc = args.encoding  or detectar_encoding(args.archivo)
    sep = args.separador or detectar_separador(args.archivo, enc)

    inspeccionar(args.archivo, sep=sep, encoding=enc, chunk_size=args.chunk)


if __name__ == "__main__":
    main()
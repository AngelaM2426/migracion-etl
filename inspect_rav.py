"""
=============================================================
  EJERCICIO 1 — INSPECCIÓN DEL ARCHIVO FUENTE CSV (RAV)
  Sección 3.1: Inspección sin cargar el archivo en memoria
=============================================================
Reporta:
  1. Número total de filas y columnas
  2. Tipos de datos inferidos por columna
  3. Porcentaje de nulos por columna
  4. Primeras 5 y últimas 5 filas (detección de anomalías)

USO DIRECTO (ejecutar el script):
  Editar la sección "CONFIGURACIÓN" al final del archivo:

      path     = "datos_rav.csv"
      sep      = ","
      encoding = "utf-8"

  Luego ejecutar:
      python inspect_rav_csv.py

USO COMO MÓDULO (importar en otro script o notebook):
  from inspect_rav_csv import inspect_csv, save_report

  result = inspect_csv(
      filepath     = "datos_rav.csv",
      sep          = ";",
      encoding     = "latin-1",
      save_report  = True,
  )
"""

import csv
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# UTILIDADES DE TIPO
# ─────────────────────────────────────────────────────────────────────────────
DATE_FORMATS = [
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
    "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S",
    "%Y%m%d",
]

def infer_type(value: str) -> str:
    """Infiere el tipo de un valor de texto."""
    if value is None or value.strip() == "":
        return "null"
    v = value.strip()
    # Entero
    try:
        int(v.replace(",", ""))
        return "integer"
    except ValueError:
        pass
    # Float
    try:
        float(v.replace(",", ""))
        return "float"
    except ValueError:
        pass
    # Fecha
    for fmt in DATE_FORMATS:
        try:
            datetime.strptime(v, fmt)
            return "date"
        except ValueError:
            pass
    # Booleano
    if v.lower() in ("true", "false", "yes", "no", "1", "0", "si", "sí", "no"):
        return "boolean"
    return "string"

def dominant_type(type_counts: dict, null_count: int, total: int) -> str:
    """Devuelve el tipo dominante ignorando nulos."""
    non_null = {k: v for k, v in type_counts.items() if k != "null"}
    if not non_null:
        return "null"
    dom = max(non_null, key=non_null.get)
    # Si hay mezcla significativa de int+float → float
    if "integer" in non_null and "float" in non_null:
        return "float"
    return dom

# ─────────────────────────────────────────────────────────────────────────────
# LECTURA DE COLA DEL ARCHIVO (sin cargar todo en memoria)
# ─────────────────────────────────────────────────────────────────────────────
def read_tail_lines(filepath: str, n: int = 10, encoding: str = "utf-8") -> list[str]:
    """Lee las últimas n líneas del archivo de forma eficiente."""
    chunk_size = 1024 * 64  # 64 KB
    with open(filepath, "rb") as f:
        f.seek(0, 2)  # ir al final
        file_size = f.tell()
        buffer = b""
        lines = []
        pos = file_size

        while len(lines) <= n and pos > 0:
            read_size = min(chunk_size, pos)
            pos -= read_size
            f.seek(pos)
            chunk = f.read(read_size)
            buffer = chunk + buffer
            # Decodificar con manejo de errores parciales
            try:
                decoded = buffer.decode(encoding)
            except UnicodeDecodeError:
                decoded = buffer.decode(encoding, errors="replace")
            lines = decoded.splitlines()

    return lines[-n:] if len(lines) >= n else lines

# ─────────────────────────────────────────────────────────────────────────────
# INSPECCIÓN PRINCIPAL (streaming por chunks)
# ─────────────────────────────────────────────────────────────────────────────
def inspect_csv(
    filepath: str,
    sep: str = ";",
    encoding: str = "utf-8",
    sample_rows: int = 5,
    type_sample_limit: int = 200_000,
    chunk_report_every: int = 500_000,
    save_report: bool = False,
):
    """
    Inspecciona el CSV línea a línea sin cargarlo en memoria.

    Parámetros
    ----------
    filepath          : Ruta al archivo CSV.
    sep               : Separador de columnas (default: ',').
    encoding          : Encoding del archivo   (default: 'utf-8').
    sample_rows       : Nº de filas a mostrar en cabecera/pie (default: 5).
    type_sample_limit : Nº de filas usadas para inferir tipos  (default: 200_000).
    chunk_report_every: Cada cuántas filas imprimir progreso   (default: 500_000).
    save_report       : Si True, guarda el reporte en un .txt  (default: False).

    Retorna
    -------
    dict con: filepath, total_rows, num_cols, headers,
              inferred_types, null_pct, first_rows, last_rows, elapsed_s.

    Ejemplo
    -------
    result = inspect_csv(
        filepath    = "datos_rav.csv",
        sep         = ";",
        encoding    = "latin-1",
        save_report = True,
    )
    """
    print(f"\n{'═'*60}")
    print(f"  INSPECCIÓN CSV — {os.path.basename(filepath)}")
    print(f"{'═'*60}")
    print(f"  Archivo : {filepath}")
    print(f"  Tamaño  : {os.path.getsize(filepath) / (1024**3):.2f} GB")
    print(f"  Encoding: {encoding}  |  Separador: {repr(sep)}")
    print(f"{'═'*60}\n")

    t0 = time.time()

    # ── PASO 1: cabecera y primeras 5 filas ──────────────────────────────────
    first_rows = []
    headers = []

    with open(filepath, encoding=encoding, errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter=sep)
        for i, row in enumerate(reader):
            if i == 0:
                headers = row
            elif i <= sample_rows:
                first_rows.append(row)
            else:
                break

    num_cols = len(headers)

    # ── PASO 2: streaming completo — conteo + nulos + tipos (sample) ─────────
    total_rows = 0
    null_counts = defaultdict(int)      # col_idx → count nulos
    type_counts = defaultdict(lambda: defaultdict(int))  # col_idx → {tipo: count}
    type_sampling_done = False

    with open(filepath, encoding=encoding, errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter=sep)
        next(reader)  # saltar cabecera

        for row in reader:
            total_rows += 1

            # Contar nulos en todas las filas
            for idx in range(num_cols):
                val = row[idx].strip() if idx < len(row) else ""
                if val == "":
                    null_counts[idx] += 1

            # Inferir tipos solo en las primeras `type_sample_limit` filas
            if not type_sampling_done:
                for idx in range(num_cols):
                    val = row[idx].strip() if idx < len(row) else ""
                    t = infer_type(val)
                    type_counts[idx][t] += 1
                if total_rows >= type_sample_limit:
                    type_sampling_done = True

            # Reporte de progreso
            if total_rows % chunk_report_every == 0:
                elapsed = time.time() - t0
                speed = total_rows / elapsed / 1_000
                print(f"  ↳ Procesadas {total_rows:,} filas  ({elapsed:.1f}s, {speed:.0f}k filas/s)")

    elapsed_total = time.time() - t0

    # ── PASO 3: últimas 5 filas ───────────────────────────────────────────────
    tail_raw = read_tail_lines(filepath, n=sample_rows + 2, encoding=encoding)
    # Parsear las líneas crudas con csv
    last_rows = []
    for line in tail_raw[-sample_rows:]:
        try:
            parsed = next(csv.reader([line], delimiter=sep))
            last_rows.append(parsed)
        except Exception:
            last_rows.append([line])

    # ── PASO 4: calcular porcentajes de nulos y tipos dominantes ─────────────
    null_pct = {
        headers[i]: round(null_counts[i] / total_rows * 100, 2)
        for i in range(num_cols)
    }
    inferred_types = {
        headers[i]: dominant_type(type_counts[i], null_counts[i], total_rows)
        for i in range(num_cols)
    }

    # ─────────────────────────────────────────────────────────────────────────
    # REPORTE FINAL
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"  RESUMEN GENERAL")
    print(f"{'─'*60}")
    print(f"  Total de filas    : {total_rows:,}")
    print(f"  Total de columnas : {num_cols}")
    print(f"  Tiempo total      : {elapsed_total:.2f}s")
    print(f"  Tipos inferidos en: primeras {min(type_sample_limit, total_rows):,} filas")

    # ── Tabla de columnas ────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"  COLUMNAS — TIPOS Y NULOS")
    print(f"{'─'*60}")
    header_fmt = f"  {'#':>4}  {'Columna':<35}  {'Tipo inferido':<12}  {'% Nulos':>8}"
    print(header_fmt)
    print(f"  {'─'*4}  {'─'*35}  {'─'*12}  {'─'*8}")

    columns_summary = []
    for i, col in enumerate(headers):
        tipo = inferred_types.get(col, "string")
        pct  = null_pct.get(col, 0.0)
        flag = " ⚠ ALTO" if pct > 30 else ""
        print(f"  {i+1:>4}  {col:<35}  {tipo:<12}  {pct:>7.2f}%{flag}")
        columns_summary.append({"col": col, "type": tipo, "null_pct": pct})

    # ── Primeras 5 filas ─────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"  PRIMERAS {sample_rows} FILAS")
    print(f"{'─'*60}")
    _print_rows_table(headers, first_rows)

    # ── Últimas 5 filas ──────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"  ÚLTIMAS {sample_rows} FILAS")
    print(f"{'─'*60}")
    _print_rows_table(headers, last_rows)

    # ── Columnas con nulos altos ─────────────────────────────────────────────
    high_null = [(c, p) for c, p in null_pct.items() if p > 30]
    if high_null:
        print(f"\n{'─'*60}")
        print(f"  ⚠  COLUMNAS CON MÁS DEL 30% DE NULOS ({len(high_null)} columnas)")
        print(f"{'─'*60}")
        for col, pct in sorted(high_null, key=lambda x: -x[1]):
            print(f"  {col:<35}  {pct:.2f}%")

    print(f"\n{'═'*60}")
    print(f"  Inspección completada en {elapsed_total:.2f} segundos.")
    print(f"{'═'*60}\n")

    result = {
        "filepath": filepath,
        "total_rows": total_rows,
        "num_cols": num_cols,
        "headers": headers,
        "inferred_types": inferred_types,
        "null_pct": null_pct,
        "first_rows": first_rows,
        "last_rows": last_rows,
        "elapsed_s": elapsed_total,
    }

    if save_report:
        base = os.path.splitext(os.path.basename(filepath))[0]
        _save_report(result, f"inspection_report_{base}.txt")

    return result


def _print_rows_table(headers: list, rows: list, max_col_width: int = 20):
    """Imprime filas en formato tabla simple."""
    trunc = [h[:max_col_width] for h in headers]
    widths = [max(len(h), 6) for h in trunc]

    sep = "  " + "  ".join("─" * w for w in widths)
    hdr = "  " + "  ".join(f"{h:<{w}}" for h, w in zip(trunc, widths))
    print(hdr)
    print(sep)
    for row in rows:
        cells = []
        for idx, w in enumerate(widths):
            val = row[idx] if idx < len(row) else ""
            val = str(val)[:w]
            cells.append(f"{val:<{w}}")
        print("  " + "  ".join(cells))


#def _save_report(result: dict, output_path: str = "inspection_report.txt"):
 #   """Guarda el reporte de inspección en un archivo de texto."""
    #with open(output_path, "w", encoding="utf-8") as f:
    #    f.write(f"REPORTE DE INSPECCIÓN CSV — {result['filepath']}\n")
    #   f.write(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    #    f.write("=" * 60 + "\n\n")

    #    f.write(f"Total de filas    : {result['total_rows']:,}\n")
    #    f.write(f"Total de columnas : {result['num_cols']}\n")
    #    f.write(f"Tiempo de análisis: {result['elapsed_s']:.2f}s\n\n")

    #    f.write("COLUMNAS — TIPOS Y PORCENTAJE DE NULOS\n")
    #    f.write("-" * 60 + "\n")
    #    f.write(f"{'#':>4}  {'Columna':<35}  {'Tipo':<12}  {'% Nulos':>8}\n")
    #    f.write(f"{'─'*4}  {'─'*35}  {'─'*12}  {'─'*8}\n")
    #    for i, col in enumerate(result["headers"]):
    #        tipo = result["inferred_types"].get(col, "?")
    #        pct  = result["null_pct"].get(col, 0.0)
    #        f.write(f"{i+1:>4}  {col:<35}  {tipo:<12}  {pct:>7.2f}%\n")

    #print(f"\n  Reporte guardado en: {output_path}")


# ═════════════════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN — editar aquí y ejecutar:  python inspect_rav_csv.py
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":

    path     = "/home/angela/Documents/migracion-etl/config/0002_UNIVERSO_VICTIMAS_LB.txt"   # ← ruta al archivo CSV
    sep      = "»"               # ← separador: "," | ";" | "\t" | "|"
    encoding = "latin-1"           # ← encoding:  "utf-8" | "latin-1" | "utf-8-sig"
    save     = False             # ← True para generar inspection_report_*.txt

    # ── Validación básica ────────────────────────────────────────────────────
    if not os.path.isfile(path):
        print(f"\n  ERROR: No se encontró el archivo: {path}")
        print(  "  Edita la variable 'path' en la sección CONFIGURACIÓN.\n")
        sys.exit(1)

    # ── Ejecutar inspección ──────────────────────────────────────────────────
    result = inspect_csv(
        filepath    = path,
        sep         = sep,
        encoding    = encoding,
        save_report = save,
    )
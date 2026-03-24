"""
benchmark_carga_prueba.py
════════════════════════════════════════════════════════════════════════════════
VERSIÓN DE PRUEBA RÁPIDA - Con batch_sizes pequeños y lectura limitada (10k filas)
Válida para verificar el funcionamiento SIN esperar mucho tiempo.
Una vez validado, usar benchmark_carga.py para los lotes completos.
════════════════════════════════════════════════════════════════════════════════
"""

import io
import logging
import os
import time
from datetime import datetime
import re
import json

import pandas as pd
import psutil
import psycopg2
import numpy as np
from psycopg2.extras import execute_values

# ── Configuración ──────────────────────────────────────────────────────────────
DB_CONFIG = {
    'host':     'localhost',
    'port':     5433,
    'dbname':   'ruv_victimas',
    'user':     'angela',
    'password': 'angela123',
}

CSV_PATH    = 'config/0002_UNIVERSO_VICTIMAS_LB.txt'
SEP         = '»'
ENCODING    = 'latin-1'
TARGET_TABLE = 'universo_victimas_v1'
LOG_PATH    = 'logs/benchmark_carga_prueba.log'
BATCH_SIZES = [1_000, 5_000, 10_000]  # Pequeños para prueba rápida
MAX_ROWS    = 50_000  # Limitar a primeros 50k registros para prueba

# ── Logging ────────────────────────────────────────────────────────────────────
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(console_handler)

# ── Columnas ──────────────────────────────────────────────────────────────────
CSV_COLUMNS = [
    'origen','fuente','programa','idpersona','idhogar','tipodocumento','documento',
    'primernombre','segundonombre','primerapellido','segundoapellido','fechanacimiento',
    'expediciondocumento','fechaexpediciondocumento','pertenenciaetnica','genero',
    'tipohecho','hecho','fechaocurrencia','coddanemunicipioocurrencia','zonaocurrencia',
    'ubicacionocurrencia','presuntoactor','presuntovictimizante','fechareporte',
    'tipopoblacion','tipovictima','pais','ciudad','coddanemunicipioresidencia',
    'zonaresidencia','ubicacionresidencia','direccion','numtelefonofijo',
    'numtelefonocelular','email','fechavaloracion','estadovictima','nombrecompleto',
    'idsiniestro','idmijefe','tipodesplazamiento','registraduria','vigenciadocumento',
    'conspersona','relacion','coddanedeclaracion','coddanellegada','codigohecho',
    'discapacidad','descripciondiscapacidad','fud_ficha','afectaciones',
]

INT_COLS = [
    'idpersona','idhogar','documento','coddanemunicipioocurrencia',
    'coddanemunicipioresidencia','idsiniestro','idmijefe','registraduria',
    'conspersona','coddanedeclaracion','coddanellegada','codigohecho','discapacidad',
]

DATE_COLS = [
    'fechanacimiento','fechaexpediciondocumento','vigenciadocumento',
    'fechaocurrencia','fechareporte','fechavaloracion',
]

# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def ram_mb() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024

def create_log_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS carga_lotes_log (
            id SERIAL PRIMARY KEY,
            lote INTEGER NOT NULL,
            filas_leidas INTEGER NOT NULL,
            filas_insertadas INTEGER NOT NULL,
            filas_rechazadas INTEGER NOT NULL,
            inicio TIMESTAMPTZ NOT NULL,
            fin TIMESTAMPTZ NOT NULL,
            duracion_segundos NUMERIC(10,2) NOT NULL,
            estrategia VARCHAR(20) NOT NULL,
            detalle TEXT
        )
    """)

def insert_log(cur, lote, leidas, insertadas, rechazadas, inicio, fin, duracion, estrategia, detalle=''):
    cur.execute("""
        INSERT INTO carga_lotes_log
            (lote, filas_leidas, filas_insertadas, filas_rechazadas,
             inicio, fin, duracion_segundos, estrategia, detalle)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (lote, leidas, insertadas, rechazadas, inicio, fin, round(duracion, 2), estrategia, detalle[:500]))

def ensure_unique_index(cur):
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'universo_victimas_v1'
                  AND indexname = 'idx_uv_documento_unique'
            ) THEN
                CREATE UNIQUE INDEX idx_uv_documento_unique
                    ON universo_victimas_v1 (documento);
            END IF;
        END $$;
    """)

def get_db_columns(cur) -> list:
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s AND column_name NOT IN ('id', 'cargado_en')
        ORDER BY ordinal_position
    """, (TARGET_TABLE,))
    return [r[0].lower() for r in cur.fetchall()]

def clean_numeric_value(val):
    if pd.isna(val) or val is None:
        return None
    s = str(val).strip().lower()
    if s in ('', 'nan', 'none', 'null', 'inf', '-inf'):
        return None
    s = re.sub(r'[^\d.-]', '', s)
    if s == '' or s == '-' or s == '.':
        return None
    try:
        num = float(s)
        if np.isinf(num) or num > 9223372036854775807:
            return None
        return int(num)
    except:
        return None

def clean_date_value(val):
    if pd.isna(val) or val is None:
        return None
    s = str(val).strip().lower()
    if s in ('', 'nan', 'none', 'null', '0', '0000', '0000-00-00'):
        return None
    try:
        if '/' in s:
            parts = s.split('/')
            if len(parts) == 3:
                year = int(parts[2])
                if 1900 <= year <= 2100:
                    return pd.to_datetime(s, dayfirst=True, errors='coerce')
        return pd.to_datetime(s, errors='coerce')
    except:
        return None

def normalize_chunk(chunk: pd.DataFrame, db_cols: list) -> tuple:
    chunk.columns = [c.strip().lower() for c in chunk.columns]
    for col in chunk.columns:
        chunk[col] = chunk[col].apply(lambda x: None if pd.isna(x) else str(x).strip() if str(x).strip() else None)
    
    for col in INT_COLS:
        if col in chunk.columns:
            chunk[col] = chunk[col].apply(clean_numeric_value)
    for col in DATE_COLS:
        if col in chunk.columns:
            dates = chunk[col].apply(clean_date_value)
            chunk[col] = dates.apply(lambda x: x.date() if pd.notna(x) and hasattr(x, 'date') else None)
    for col in chunk.columns:
        if col not in INT_COLS and col not in DATE_COLS:
            chunk[col] = chunk[col].apply(lambda x: str(x).strip() if x else None)
    
    insert_cols = [c for c in chunk.columns if c in db_cols]
    return chunk[insert_cols], insert_cols

def insert_execute_values(cur, cols: list, rows: list) -> int:
    if not rows:
        return 0
    cols_sql = ', '.join(cols)
    sql = f"INSERT INTO {TARGET_TABLE} ({cols_sql}) VALUES %s ON CONFLICT (documento) DO NOTHING"
    try:
        execute_values(cur, sql, rows, page_size=min(5000, len(rows)))
        return cur.rowcount if cur.rowcount >= 0 else len(rows)
    except Exception as e:
        logging.error(f"Error en execute_values: {e}")
        raise

def insert_copy(cur, cols: list, chunk: pd.DataFrame) -> int:
    if len(chunk) == 0:
        return 0
    try:
        buf = io.StringIO()
        chunk_copy = chunk.copy()
        for col in chunk_copy.columns:
            chunk_copy[col] = chunk_copy[col].apply(lambda x: '' if x is None else str(x))
        chunk_copy.to_csv(buf, sep='\t', index=False, header=False)
        buf.seek(0)
        cur.copy_from(buf, TARGET_TABLE, sep='\t', null='', columns=cols)
        return len(chunk)
    except Exception as e:
        logging.error(f"Error en COPY: {e}")
        raise

# ══════════════════════════════════════════════════════════════════════════════
# BENCHMARK PRUEBA
# ══════════════════════════════════════════════════════════════════════════════

def run_benchmark_prueba():
    logging.info("="*70)
    logging.info("INICIANDO BENCHMARK DE PRUEBA (RÁPIDO)")
    logging.info(f"Limitado a primeros {MAX_ROWS:,d} registros")
    logging.info("="*70)
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    create_log_table(cur)
    ensure_unique_index(cur)
    conn.commit()
    
    db_cols = get_db_columns(cur)
    logging.info(f'Columnas en tabla destino: {len(db_cols)}')
    
    results = []
    
    for batch_size in BATCH_SIZES:
        logging.info(f'══ Iniciando lote {batch_size:,d} ══')
        cur.execute(f'TRUNCATE TABLE {TARGET_TABLE} RESTART IDENTITY CASCADE')
        conn.commit()
        
        total_read = 0
        total_ins = 0
        total_rej = 0
        ram_pico = ram_mb()
        t0 = time.perf_counter()
        chunk_count = 0
        row_count_global = 0
        
        try:
            reader = pd.read_csv(
                CSV_PATH,
                sep=SEP,
                encoding=ENCODING,
                chunksize=batch_size,
                dtype=str,
                header=0,
                on_bad_lines='skip',
                nrows=MAX_ROWS  # ← LÍMITE PARA PRUEBA RÁPIDA
            )
            
            for chunk in reader:
                chunk_count += 1
                try:
                    chunk_norm, insert_cols = normalize_chunk(chunk, db_cols)
                except Exception as e:
                    logging.error(f"Error normalizando chunk {chunk_count}: {e}")
                    total_rej += len(chunk)
                    continue
                
                n_leidas = len(chunk_norm)
                total_read += n_leidas
                
                strategy = 'execute_values' if batch_size <= 100000 else 'copy'
                t_chunk = datetime.now()
                inserted = 0
                errored = 0
                detail = ''
                
                if n_leidas > 0:
                    try:
                        rows = [tuple(r) for r in chunk_norm.itertuples(index=False, name=None)]
                        if strategy == 'execute_values':
                            inserted = insert_execute_values(cur, insert_cols, rows)
                        else:
                            inserted = insert_copy(cur, insert_cols, chunk_norm)
                        conn.commit()
                        total_ins += inserted
                        errored = n_leidas - inserted
                        total_rej += errored
                    except Exception as exc:
                        conn.rollback()
                        errored = n_leidas
                        detail = str(exc)[:500]
                        logging.error(f'Error: {detail}')
                        total_rej += errored
                
                t_fin = datetime.now()
                dur = (t_fin - t_chunk).total_seconds()
                insert_log(cur, batch_size, n_leidas, inserted, errored, t_chunk, t_fin, dur, strategy, detail)
                conn.commit()
                
                ram_now = ram_mb()
                if ram_now > ram_pico:
                    ram_pico = ram_now
                
                row_count_global += n_leidas
                print(f'\r  lote={batch_size:,d} | leídas={total_read:,d} | ins={total_ins:,d}',
                      end='', flush=True)
                
                if row_count_global >= MAX_ROWS:
                    break
            
            print()
            
        except Exception as e:
            logging.error(f"Error en lote {batch_size}: {e}")
            continue
        
        t_total = time.perf_counter() - t0
        throughput = total_read / t_total if t_total > 0 else 0
        
        logging.info(f'Lote {batch_size}: {total_read} leídas, {total_ins} insertadas en {t_total:.2f}s')
        
        results.append({
            'lote': batch_size,
            'estrategia': 'execute_values' if batch_size <= 100000 else 'copy',
            'tiempo_s': round(t_total, 2),
            'throughput_fs': round(throughput, 0),
            'ram_pico_mb': round(ram_pico, 1),
            'filas_leidas': total_read,
            'insertadas': total_ins,
            'rechazadas': total_rej,
        })
    
    if results:
        df = pd.DataFrame(results)
        print('\n' + '='*90)
        print("RESULTADOS - PRUEBA RÁPIDA")
        print('='*90)
        print(df.to_string(index=False))
        print('='*90)
        
        # ── CSV ────
        csv_path = 'benchmark_resultados_prueba.csv'
        df.to_csv(csv_path, index=False)
        print(f'\n✓ CSV: {csv_path}')
        
        # ── JSON ───
        json_path = 'benchmark_resultados_prueba.json'
        json_data = {
            'timestamp': datetime.now().isoformat(),
            'tipo': 'prueba_rapida',
            'max_rows': MAX_ROWS,
            'total_rows': df['filas_leidas'].sum(),
            'total_inserted': df['insertadas'].sum(),
            'resultados': df.to_dict('records')
        }
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)
        print(f'✓ JSON: {json_path}')
        
        print("\nRESUMEN:")
        print(f"  Total procesado: {df['filas_leidas'].sum():,d}")
        print(f"  Mejor throughput: {df['throughput_fs'].max():.0f} f/s")
        print(f"  Menor RAM: {df['ram_pico_mb'].min():.1f} MB")
        print("="*90)
    else:
        logging.error("No se generaron resultados")
    
    cur.close()
    conn.close()
    logging.info("Benchmark prueba completado")


if __name__ == '__main__':
    run_benchmark_prueba()

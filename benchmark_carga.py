"""
benchmark_carga.py
══════════════════
Benchmark de carga masiva CSV → PostgreSQL con distintos tamaños de lote.

Estrategias:
  - execute_values (psycopg2)  → lotes ≤ 100 000 filas
  - COPY vía StringIO          → lotes > 100 000 filas

Métricas por combinación:
  - Tiempo total (s), Throughput (filas/s), RAM pico (MB)
  - Filas leídas / insertadas / rechazadas

Salidas:
  - benchmark_resultados.csv
  - benchmark_carga.log
  - Tabla carga_lotes_log en PostgreSQL
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
SEP         = '»'          # separador real del archivo
ENCODING    = 'latin-1'
TARGET_TABLE = 'universo_victimas_v1'
LOG_PATH    = 'logs/benchmark_carga.log'
BATCH_SIZES = [5_000, 25_000, 100_000, 250_000, 500_000]

# ── Logging ────────────────────────────────────────────────────────────────────
# Crear directorio logs si no existe
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
# Agregar handler para consola también
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(console_handler)

# ── Columnas de la tabla destino (orden CSV → tabla) ──────────────────────────
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
            id                  SERIAL PRIMARY KEY,
            lote                INTEGER         NOT NULL,
            filas_leidas        INTEGER         NOT NULL,
            filas_insertadas    INTEGER         NOT NULL,
            filas_rechazadas    INTEGER         NOT NULL,
            inicio              TIMESTAMPTZ     NOT NULL,
            fin                 TIMESTAMPTZ     NOT NULL,
            duracion_segundos   NUMERIC(10,2)   NOT NULL,
            estrategia          VARCHAR(20)     NOT NULL,
            detalle             TEXT
        )
    """)


def insert_log(cur, lote, leidas, insertadas, rechazadas,
               inicio, fin, duracion, estrategia, detalle=''):
    cur.execute("""
        INSERT INTO carga_lotes_log
            (lote, filas_leidas, filas_insertadas, filas_rechazadas,
             inicio, fin, duracion_segundos, estrategia, detalle)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (lote, leidas, insertadas, rechazadas,
          inicio, fin, round(duracion, 2), estrategia, detalle[:500]))


def ensure_unique_index(cur):
    """Asegura que exista el índice único en documento"""
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


def get_db_columns(cur) -> list[str]:
    """Obtiene las columnas de la tabla destino"""
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
          AND column_name NOT IN ('id', 'cargado_en')
        ORDER BY ordinal_position
    """, (TARGET_TABLE,))
    return [r[0].lower() for r in cur.fetchall()]


def clean_numeric_value(val):
    """Limpia valores numéricos problemáticos"""
    if pd.isna(val) or val is None:
        return None
    
    # Convertir a string y limpiar
    s = str(val).strip().lower()
    
    # Valores problemáticos
    if s in ('', 'nan', 'none', 'null', 'inf', '-inf', 'infinity', '-infinity'):
        return None
    
    # Remover caracteres no numéricos excepto punto y signo menos
    s = re.sub(r'[^\d.-]', '', s)
    
    if s == '' or s == '-' or s == '.':
        return None
    
    try:
        num = float(s)
        # Verificar si es infinito
        if np.isinf(num):
            return None
        # Verificar rango bigint
        if num > 9223372036854775807 or num < -9223372036854775807:
            return None
        return int(num)
    except (ValueError, OverflowError):
        return None


def clean_date_value(val):
    """Limpia valores de fecha problemáticos"""
    if pd.isna(val) or val is None:
        return None
    
    s = str(val).strip().lower()
    
    # Valores problemáticos
    if s in ('', 'nan', 'none', 'null', '0', '0000', '0000-00-00', '00/00/0000'):
        return None
    
    try:
        # Intentar diferentes formatos
        if '/' in s:
            # Formato DD/MM/YYYY
            parts = s.split('/')
            if len(parts) == 3:
                # Validar año
                year = int(parts[2])
                if year < 1900 or year > 2100:
                    return None
                return pd.to_datetime(s, dayfirst=True, errors='coerce')
        else:
            return pd.to_datetime(s, errors='coerce')
    except:
        return None


def normalize_chunk(chunk: pd.DataFrame, db_cols: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """Normaliza tipos y filtra columnas que existen en la tabla destino."""
    # Limpiar nombres de columnas
    chunk.columns = [c.strip().lower() for c in chunk.columns]
    
    # Primero, limpiar todos los valores problemáticos en todas las columnas
    for col in chunk.columns:
        # Reemplazar valores problemáticos con None
        chunk[col] = chunk[col].apply(lambda x: None if pd.isna(x) or str(x).strip().lower() in 
                                       ('', 'nan', 'none', 'null', 'inf', '-inf', 'infinity', '-infinity') 
                                       else str(x).strip())
    
    # Procesar columnas numéricas
    for col in INT_COLS:
        if col in chunk.columns:
            chunk[col] = chunk[col].apply(clean_numeric_value)
    
    # Procesar columnas de fecha
    for col in DATE_COLS:
        if col in chunk.columns:
            dates = chunk[col].apply(clean_date_value)
            # Convertir a date nativo si es datetime
            chunk[col] = dates.apply(lambda x: x.date() if pd.notna(x) and hasattr(x, 'date') else None)
    
    # Procesar columnas de texto
    for col in chunk.columns:
        if col not in INT_COLS and col not in DATE_COLS:
            chunk[col] = chunk[col].apply(lambda x: str(x).strip() if x and str(x).strip() not in ('', 'nan', 'none', 'null') else None)
    
    # Solo columnas que existen en la tabla destino
    insert_cols = [c for c in chunk.columns if c in db_cols]
    
    # Verificar que documento esté en las columnas para ON CONFLICT
    if 'documento' not in insert_cols:
        logging.warning("La columna 'documento' no está en las columnas a insertar")
    
    return chunk[insert_cols], insert_cols


# ══════════════════════════════════════════════════════════════════════════════
# Estrategias de inserción
# ══════════════════════════════════════════════════════════════════════════════

def insert_execute_values(cur, cols: list[str], rows: list[tuple]) -> int:
    """Inserta usando execute_values con ON CONFLICT"""
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


def insert_copy(cur, cols: list[str], chunk: pd.DataFrame) -> int:
    """Inserta usando COPY (más rápido para lotes grandes)"""
    if len(chunk) == 0:
        return 0
    
    try:
        buf = io.StringIO()
        # Para COPY, necesitamos manejar NULLs correctamente
        chunk_copy = chunk.copy()
        # Reemplazar None con string vacío para COPY
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
# Benchmark principal
# ══════════════════════════════════════════════════════════════════════════════

def run_benchmark():
    """Ejecuta benchmark con diferentes tamaños de lote"""
    
    logging.info("="*70)
    logging.info("INICIANDO BENCHMARK DE CARGA")
    logging.info("="*70)
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Crear tabla de logs y asegurar índice único
    create_log_table(cur)
    ensure_unique_index(cur)
    conn.commit()
    
    # Obtener columnas de la tabla destino
    db_cols = get_db_columns(cur)
    logging.info('Columnas en tabla destino: %d', len(db_cols))
    logging.info('Primeras 10 columnas: %s', db_cols[:10])
    
    results = []
    
    for batch_size in BATCH_SIZES:
        logging.info('══ Iniciando benchmark lote %s ══', batch_size)
        
        # Truncar tabla para condiciones iguales entre corridas
        cur.execute(f'TRUNCATE TABLE {TARGET_TABLE} RESTART IDENTITY CASCADE')
        conn.commit()
        
        total_read = 0
        total_ins = 0
        total_rej = 0
        ram_pico = ram_mb()
        t0 = time.perf_counter()
        chunk_count = 0
        
        try:
            # Leer CSV en chunks - usar engine='c' optimizado
            try:
                reader = pd.read_csv(
                    CSV_PATH,
                    sep=SEP,
                    encoding=ENCODING,
                    engine='c',  # Motor C es más rápido
                    chunksize=batch_size,
                    dtype=str,
                    header=0,
                    on_bad_lines='skip'  # Saltar líneas problemáticas
                )
            except Exception as e:
                logging.error(f"Error con engine='c', reintentando con engine='python': {e}")
                reader = pd.read_csv(
                    CSV_PATH,
                    sep=SEP,
                    encoding=ENCODING,
                    engine='python',
                    chunksize=batch_size,
                    dtype=str,
                    header=0,
                    on_bad_lines='skip'
                )
            
            for chunk in reader:
                chunk_count += 1
                
                # Normalizar chunk
                try:
                    chunk_norm, insert_cols = normalize_chunk(chunk, db_cols)
                except Exception as e:
                    logging.error(f"Error normalizando chunk {chunk_count}: {e}")
                    total_rej += len(chunk)
                    continue
                
                n_leidas = len(chunk_norm)
                total_read += n_leidas
                
                # Determinar estrategia
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
                        logging.error(f'Error chunk lote {batch_size}: {detail}')
                        total_rej += errored
                
                # Registrar log
                t_fin = datetime.now()
                dur = (t_fin - t_chunk).total_seconds()
                insert_log(cur, batch_size, n_leidas, inserted, errored,
                          t_chunk, t_fin, dur, strategy, detail)
                conn.commit()
                
                # Monitoreo de RAM
                ram_now = ram_mb()
                if ram_now > ram_pico:
                    ram_pico = ram_now
                
                # Mostrar progreso
                elapsed = time.perf_counter() - t0
                thr = total_read / elapsed if elapsed > 0 else 0
                print(f'\r  lote={batch_size:>7,} | chk={chunk_count:3d} | '
                      f'leídas={total_read:>10,} | {thr:>8,.0f} f/s | '
                      f'RAM {ram_pico:.0f} MB | ins={total_ins:,d}',
                      end='', flush=True)
            
            print()  # Nueva línea después del progreso
            
        except Exception as e:
            logging.error(f"Error en lote {batch_size}: {e}")
            continue
        
        # Métricas finales del lote
        t_total = time.perf_counter() - t0
        throughput = total_read / t_total if t_total > 0 else 0
        
        logging.info(
            'Lote %s → leídas=%s ins=%s rej=%s | %.2fs | %.0f f/s | %.0f MB',
            batch_size, total_read, total_ins, total_rej,
            t_total, throughput, ram_pico
        )
        
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
    
    # Tabla comparativa
    if results:
        df = pd.DataFrame(results)
        print('\n' + '='*90)
        print("RESULTADOS DEL BENCHMARK")
        print('='*90)
        print(df.to_string(index=False))
        print('='*90)
        
        # ── Exportar CSV ──────────────────────────────────────────────────────────────
        csv_path = 'benchmark_resultados.csv'
        df.to_csv(csv_path, index=False)
        logging.info(f'Exportado: {csv_path}')
        print(f'\n✓ Archivo CSV: {csv_path}')
        
        # ── Exportar JSON ─────────────────────────────────────────────────────────────
        json_path = 'benchmark_resultados.json'
        json_data = {
            'timestamp': datetime.now().isoformat(),
            'csv_path': CSV_PATH,
            'target_table': TARGET_TABLE,
            'total_rows': df['filas_leidas'].sum(),
            'total_inserted': df['insertadas'].sum(),
            'total_rejected': df['rechazadas'].sum(),
            'resultados': df.to_dict('records'),
            'resumen': {
                'mejor_throughput': {
                    'lote': int(df.loc[df['throughput_fs'].idxmax()]['lote']),
                    'throughput_fs': float(df['throughput_fs'].max()),
                    'tiempo_s': float(df.loc[df['throughput_fs'].idxmax()]['tiempo_s']),
                    'ram_mb': float(df.loc[df['throughput_fs'].idxmax()]['ram_pico_mb'])
                },
                'menor_tiempo': {
                    'lote': int(df.loc[df['tiempo_s'].idxmin()]['lote']),
                    'tiempo_s': float(df['tiempo_s'].min()),
                    'throughput_fs': float(df.loc[df['tiempo_s'].idxmin()]['throughput_fs'])
                },
                'menor_ram': {
                    'lote': int(df.loc[df['ram_pico_mb'].idxmin()]['lote']),
                    'ram_mb': float(df['ram_pico_mb'].min()),
                    'throughput_fs': float(df.loc[df['ram_pico_mb'].idxmin()]['throughput_fs'])
                }
            }
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)
        logging.info(f'Exportado: {json_path}')
        print(f'✓ Archivo JSON: {json_path}')
        
        # ── Resumen ejecutivo ────────────────────────────────────────────────────────
        print("\n" + "="*90)
        print("RESUMEN EJECUTIVO")
        print("="*90)
        print(f"\nTotal de filas procesadas: {df['filas_leidas'].sum():,d}")
        print(f"Total insertadas exitosamente: {df['insertadas'].sum():,d}")
        print(f"Total rechazadas: {df['rechazadas'].sum():,d}")
        print(f"Tasa de éxito: {(df['insertadas'].sum() / df['filas_leidas'].sum() * 100):.2f}%")
        
        best_thr = df.loc[df['throughput_fs'].idxmax()]
        print(f"\n🏆 Mejor throughput: {best_thr['throughput_fs']:.0f} f/s (lote {int(best_thr['lote']):,d})")
        print(f"   Tiempo: {best_thr['tiempo_s']:.2f}s | RAM: {best_thr['ram_pico_mb']:.1f} MB")
        
        best_time = df.loc[df['tiempo_s'].idxmin()]
        print(f"\n⚡ Menor tiempo: {best_time['tiempo_s']:.2f}s (lote {int(best_time['lote']):,d})")
        print(f"   Throughput: {best_time['throughput_fs']:.0f} f/s")
        
        best_ram = df.loc[df['ram_pico_mb'].idxmin()]
        print(f"\n💾 Menor RAM: {best_ram['ram_pico_mb']:.1f} MB (lote {int(best_ram['lote']):,d})")
        print(f"   Throughput: {best_ram['throughput_fs']:.0f} f/s | Tiempo: {best_ram['tiempo_s']:.2f}s")
        print("="*90)
    else:
        logging.error("No se generaron resultados")
    
    cur.close()
    conn.close()
    logging.info("Benchmark completado")


if __name__ == '__main__':
    run_benchmark()
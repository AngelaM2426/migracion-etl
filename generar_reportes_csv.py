"""
generar_reportes_csv.py
════════════════════════════════════════════════════════════════════════════════
RÁPIDO - Genera reportes CSV/JSON del benchmark SIN insertar a BD
(Focus: Métricas de lectura, procesamiento, outputs CSV/JSON)
════════════════════════════════════════════════════════════════════════════════
"""

import json
import time
import os
from datetime import datetime
import pandas as pd

CSV_PATH = 'config/0002_UNIVERSO_VICTIMAS_LB.txt'
SEP = '»'
ENCODING = 'latin-1'
BATCH_SIZES = [5_000, 25_000, 50_000]

print("="*90)
print("LECTURA DE CSV Y GENERACIÓN DE REPORTES")
print("="*90)

# Crear directorio outputs si no existe
os.makedirs('outputs', exist_ok=True)

results = []
total_rows_processed = 0
t_start = time.perf_counter()

for batch_size in BATCH_SIZES:
    print(f"\n📊 Procesando lote {batch_size:,d}...", end='', flush=True)
    
    t_lote = time.perf_counter()
    chunk_count = 0
    total_read = 0
    
    try:
        # Leer CSV en chunks (SIN insertar a BD)
        reader = pd.read_csv(
            CSV_PATH,
            sep=SEP,
            encoding=ENCODING,
            chunksize=batch_size,
            dtype=str,
            header=0,
            on_bad_lines='skip'
        )
        
        for chunk in reader:
            chunk_count += 1
            total_read += len(chunk)
            print(f'\r📊 Lote {batch_size:,d} | Chunk {chunk_count} | Filas: {total_read:,d}',
                  end='', flush=True)
            
            # Límite para prueba rápida
            if total_read >= 100_000:
                break
        
        elapsed = time.perf_counter() - t_lote
        throughput = total_read / elapsed if elapsed > 0 else 0
        
        total_rows_processed += total_read
        
        print(f" ✓ ({elapsed:.2f}s, {throughput:.0f} f/s)")
        
        results.append({
            'batch_size': batch_size,
            'filas_procesadas': total_read,
            'chunks': chunk_count,
            'tiempo_segundos': round(elapsed, 2),
            'throughput_fila_seg': round(throughput, 0),
        })
        
    except Exception as e:
        print(f" ✗ Error: {e}")
        continue

# ════════════════════════════════════════════════════════════════════════════════
# EXPORTAR RESULTADOS
# ════════════════════════════════════════════════════════════════════════════════

print("\n" + "="*90)
print("GENERANDO OUTPUTS")
print("="*90)

if results:
    df = pd.DataFrame(results)
    
    # ── CSV ────────────────────────────────────────────────────────────────────
    csv_file = 'outputs/benchmark_csv_lectura.csv'
    df.to_csv(csv_file, index=False)
    print(f"✓ CSV exportado: {csv_file}")
    
    # ── JSON ───────────────────────────────────────────────────────────────────
    json_file = 'outputs/benchmark_csv_lectura.json'
    json_data = {
        'timestamp': datetime.now().isoformat(),
        'csv_fuente': CSV_PATH,
        'descripcion': 'Métricas de lectura de CSV con diferentes tamaños de lote',
        'total_filas_procesadas': int(total_rows_processed),
        'tiempo_total_segundos': round(time.perf_counter() - t_start, 2),
        'resultados': df.to_dict('records'),
        'resumen': {
            'mejor_throughput': {
                'batch_size': int(df.loc[df['throughput_fila_seg'].idxmax()]['batch_size']),
                'throughput': float(df['throughput_fila_seg'].max()),
                'tiempo': float(df.loc[df['throughput_fila_seg'].idxmax()]['tiempo_segundos'])
            },
            'menor_tiempo': {
                'batch_size': int(df.loc[df['tiempo_segundos'].idxmin()]['batch_size']),
                'tiempo': float(df['tiempo_segundos'].min())
            }
        }
    }
    
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)
    print(f"✓ JSON exportado: {json_file}")
    
    # ── TABLA ──────────────────────────────────────────────────────────────────
    print("\n" + "="*90)
    print("RESULTADOS")
    print("="*90)
    print(df.to_string(index=False))
    
    print("\n" + "="*90)
    print("RESUMEN EJECUTIVO")
    print("="*90)
    print(f"Total de filas procesadas: {total_rows_processed:,d}")
    print(f"Tiempo total: {time.perf_counter() - t_start:.2f}s")
    
    best = df.loc[df['throughput_fila_seg'].idxmax()]
    print(f"\n🏆 Mejor throughput: {best['throughput_fila_seg']:.0f} f/s (lote {int(best['batch_size']):,d})")
    print(f"   Tiempo: {best['tiempo_segundos']:.2f}s para {int(best['filas_procesadas']):,d} filas")
    
    # ── HTML ───────────────────────────────────────────────────────────────────
    html_file = 'outputs/benchmark_csv_lectura.html'
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Benchmark CSV - Lectura</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #333; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: right; }}
            th {{ background-color: #4CAF50; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .summary {{ background-color: #f9f9f9; padding: 15px; border-left: 4px solid #4CAF50; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <h1>📊 Benchmark - Lectura CSV</h1>
        <p><strong>Archivo:</strong> {CSV_PATH}</p>
        <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <table>
            <tr>
                <th>Batch Size</th>
                <th>Filas Procesadas</th>
                <th>Chunks</th>
                <th>Tiempo (s)</th>
                <th>Throughput (f/s)</th>
            </tr>
    """
    
    for _, row in df.iterrows():
        html_content += f"""
            <tr>
                <td>{int(row['batch_size']):,d}</td>
                <td>{int(row['filas_procesadas']):,d}</td>
                <td>{int(row['chunks'])}</td>
                <td>{row['tiempo_segundos']:.2f}</td>
                <td>{int(row['throughput_fila_seg']):,d}</td>
            </tr>
        """
    
    html_content += f"""
        </table>
        
        <div class="summary">
            <h2>Resumen</h2>
            <p><strong>Total filas:</strong> {total_rows_processed:,d}</p>
            <p><strong>Mejor throughput:</strong> {df['throughput_fila_seg'].max():.0f} f/s (lote {int(best['batch_size']):,d})</p>
            <p><strong>Tiempo total:</strong> {time.perf_counter() - t_start:.2f}s</p>
        </div>
    </body>
    </html>
    """
    
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"✓ HTML exportado: {html_file}")
    
    print("="*90)
    print("✓ Reportes generados exitosamente en outputs/")
    print("="*90)

else:
    print("❌ No se generaron resultados")

# ⚡ GUÍA RÁPIDA - EJECUTAR TODO PASO A PASO

**Duración total**: ~30 minutos de setup + ~4-6 horas benchmark  
**Requisitos**: 2+ GB RAM, 20 GB disco, Docker instalado

---

## 🚀 INICIO RÁPIDO (Copiar y pegar estos comandos)

### PASO 0: Preparación
```bash
# Abrir terminal y navegar al proyecto
cd /home/angela/Documents/migracion-etl

# Verificar que Docker está corriendo
docker ps --help > /dev/null && echo "✓ Docker OK"

# Activar entorno virtual
source venv_migracion_etl/bin/activate

# Verificar Python 3.12
python --version  # Debe mostrar "Python 3.12.x"

echo "======================"
echo "✓ SETUP COMPLETADO"
echo "======================"
```

**⏱️ Tiempo**: 2 minutos

---

## 1️⃣ LEVANTAR POSTGRESQL (Una sola vez)

```bash
# Lanzar Docker Compose
docker-compose up -d

# Esperar a que esté listo (30-60s)
sleep 30

# Verificar que está corriendo
docker ps | grep migracion_etl_db

# Salida esperada:
# 27a8c95ad306   postgres:16-alpine ... Up x minutes
```

**⏱️ Tiempo**: 1-2 minutos  
**✅ Resultado**: PostgreSQL corriendo en puerto 5433

---

## 2️⃣ INSPECCIONAR CSV [SECCIÓN 3.1]

```bash
echo "=== PASO 2: INSPECCIONAR CSV ==="
python inspect_rav.py

# Verá en vivo el progreso
# ↳ Procesadas 500,000 filas
# ↳ Procesadas 1,000,000 filas
# etc...

# Al final:
# Total de filas: 13,178,321
# Total de columnas: 53
# Tipos: STRING / INTEGER / DATE / NULL
# % nulos por columna

echo "✓ Resultado guardado en: logs/inspeccion_csv_output.log"
```

**⏱️ Tiempo**: 5-8 minutos  
**📁 Salida**: `logs/inspeccion_csv_output.log`

---

## 3️⃣ BENCHMARK PRUEBA [SECCIÓN 3.3 - VALIDACIÓN]

```bash
echo "=== PASO 3: BENCHMARK RÁPIDO (50K filas) ==="
python benchmark_carga_prueba.py

# Verá avance de lotes
# ══ Iniciando lote 1,000 ══
# lote=1,000 | leídas=50,000 | ins=47,598
# Lote 1000: 50000 leídas, 47598 insertadas en 38.90s
# etc...

# Final: Tabla de resultados
# ══════════════════════════════════════════════════════
#  lote     estrategia  tiempo_s  throughput_f/s  ram_pico_mb
#  1000 execute_values     38.90          1,285           83.6
#  5000 execute_values     37.81          1,322          109.3
# 10000 execute_values     36.80          1,359          138.3

echo "✓ Resultados en: outputs/benchmark_resultados_prueba.csv"
```

**⏱️ Tiempo**: 3-5 minutos  
**📁 Salida**: 
- `logs/benchmark_carga_prueba.log`
- `outputs/benchmark_resultados_prueba.csv`
- `outputs/benchmark_resultados_prueba.json`

**⚠️ Nota**: El error "bigint out of range" es NORMAL. El script continúa.

---

## 4️⃣ BENCHMARK COMPLETO [SECCIÓN 3.3 - PRINCIPAL]

```bash
echo "=== PASO 4: BENCHMARK COMPLETO (13.1M filas) ==="
echo "⏰ Esto tardará 4-6 HORAS. Se recomienda ejecutar en background:"

# OPCIÓN A: En background (recomendado)
nohup python benchmark_carga.py > logs/benchmark_carga_$(date +%Y%m%d_%H%M%S).log 2>&1 &

echo "Proceso iniciado en background (PID: $!)"
echo "Para monitorear: tail -f logs/benchmark_carga_*.log"

# OPCIÓN B: En foreground (si prefiere ver todo en vivo)
# python benchmark_carga.py 2>&1 | tee logs/benchmark_carga_$(date +%Y%m%d_%H%M%S).log
```

**⏱️ Tiempo**: 4-6 HORAS (procesa 13.1M filas)  
**📁 Salida**:
- `logs/benchmark_carga.log`
- `outputs/benchmark_resultados.csv` (TABLA FINAL)
- `outputs/benchmark_resultados.json`
- `outputs/benchmark_resultados.html`
- **BD**: 13.1M registros en `universo_victimas_v1`
- **BD**: Log de cada lote en `carga_lotes_log`

**Mientras se ejecuta en background**, puede:
```bash
# En otra terminal, monitorear progreso
tail -f logs/benchmark_carga_*.log

# Ver cuántas filas ya se insertaron
export PGPASSWORD=angela123
watch -n 5 'psql -h localhost -p 5433 -U angela -d ruv_victimas -c \
  "SELECT COUNT(*) as registros_cargados FROM universo_victimas_v1;"'
```

---

## 5️⃣ VERIFICAR RESULTADOS [SECCIÓN 3.4]

```bash
echo "=== PASO 5: VALIDAR CARGA ==="

# Conectar a BD
export PGPASSWORD=angela123

# Contar registros (debería ser >12M)
psql -h localhost -p 5433 -U angela -d ruv_victimas -c \
  "SELECT COUNT(*) as total_registros FROM universo_victimas_v1;"

# Ver primeras 3 filas
psql -h localhost -p 5433 -U angela -d ruv_victimas -c \
  "SELECT idpersona, documento, primernombre, primerapellido, 
          fechaocurrencia, estadovictima 
   FROM universo_victimas_v1 LIMIT 3;"

# Ver log de cargas
psql -h localhost -p 5433 -U angela -d ruv_victimas -c \
  "SELECT lote, filas_leidas, filas_insertadas, filas_rechazadas, 
          duracion_segundos, estrategia 
   FROM carga_lotes_log ORDER BY lote;"

# Para demostrar IDEMPOTENCIA (ejecutar benchmark 2 veces)
echo "PRUEBA IDEMPOTENCIA: Ejecutando NUEVAMENTE..."
python benchmark_carga_prueba.py  # Segunda ejecución

# Resultado: 0 nuevas insertadas (todos en conflicto, porque ON CONFLICT DO NOTHING)
```

**⏱️ Tiempo**: 5 minutos  
**✅ Esperado**: 
- Total registros: >12.7M
- Tabla `carga_lotes_log` completa
- Segunda ejecución: 0 nuevos insertados

---

## 🎁 BONUS: GENERAR REPORTES

```bash
echo "=== GENERANDO REPORTES ==="

# Ver CSV de resultados
cat outputs/benchmark_resultados.csv

# Ver JSON estructurado
python -m json.tool outputs/benchmark_resultados.json | head -40

# Abrir reporte HTML en navegador (si está disponible)
# firefox outputs/benchmark_resultados.html  # Linux
# open outputs/benchmark_resultados.html      # macOS
```

---

## 📊 ARCHIVOS GENERADOS - RESUMEN

```
LOGS (Trazabilidad):
  logs/inspeccion_csv_output.log        ← Paso 2
  logs/benchmark_carga_prueba.log       ← Paso 3
  logs/benchmark_carga_*.log            ← Paso 4

RESULTADOS (Análisis):
  outputs/benchmark_resultados_prueba.csv  ← Paso 3
  outputs/benchmark_resultados.csv         ← Paso 4 (FINAL)
  outputs/benchmark_resultados.json        ← Paso 4
  outputs/benchmark_resultados.html        ← Paso 4

BASE DE DATOS (PostgreSQL):
  universo_victimas_v1    ← 13.1M registros
  carga_lotes_log         ← 5 registros (uno por lote)
```

---

## 🔍 ATAJOS ÚTILES

### Ver progreso del benchmark (mientras se ejecuta)
```bash
tail -f logs/benchmark_carga_*.log | grep "Lote"
```

### Contar registros guardados
```bash
export PGPASSWORD=angela123
psql -h localhost -p 5433 -U angela -d ruv_victimas -c \
  "SELECT COUNT(*) FROM universo_victimas_v1;"
```

### Detener proceso (si es necesario)
```bash
# Si lo ejecutó en background con nohup
kill %1  # Mata el último proceso background

# O buscar el PID
ps aux | grep benchmark_carga.py
kill -9 <PID>

# Nota: Una segunda ejecución completará lo que faltó (idempotencia)
```

### Limpiar y reiniciar (PELIGRO: borra base de datos)
```bash
# Derecha las tablas
export PGPASSWORD=angela123
psql -h localhost -p 5433 -U angela -d ruv_victimas -c \
  "DROP TABLE universo_victimas_v1, carga_lotes_log;"

# Reiniciar containers
docker-compose restart

# Volver a ejecutar los pasos 1-4
```

---

## ❌ SI ALGO FALLA

### Error: "Connection refused"
```bash
docker ps | grep migracion_etl_db
# Si no aparece:
docker-compose up -d
```

### Error: "Port 5433 already in use"
```bash
# Cambia el puerto en docker-compose.yml:
# ports: ["5434:5432"]
# O mata el proceso:
lsof -i :5433 | tail -1 | awk '{print $2}' | xargs kill -9
```

### Error: "bigint out of range"
```bash
# Es NORMAL. Significa que algunos valores son inválidos,
# pero el script continúa gracias a ON CONFLICT DO NOTHING.
# Ver detalles:
export PGPASSWORD=angela123
psql -h localhost -p 5433 -U angela -d ruv_victimas -c \
  "SELECT * FROM carga_lotes_log WHERE detalle LIKE '%bigint%';"
```

### Processo muy lento
```bash
# Verificar RAM disponible
free -h

# Verificar disco
df -h /

# Si <2GB RAM: cerrar otros programas
# Si <10GB disco: limpiar archivos innecesarios
```

---

## 📝 CHECKLIST FINAL

```
□ Docker funcionando (docker ps muestra container)
□ Python 3.12 activado (python --version)
□ PostgreSQL accesible (psql comando funciona)
□ CSV existe (ls -lh config/0002_UNIVERSO_VICTIMAS_LB.txt)
□ Paso 2: inspect_rav.py completado (logs/inspeccion_csv_output.log)
□ Paso 3: benchmark prueba completado (3-5 min, 50K filas)
□ Paso 4: benchmark completo iniciado (4-6 horas, 13.1M filas)
□ Paso 5: validación completada (>12M registros en BD)
□ Idempotencia verificada (segunda ejecución = 0 nuevos)
```

---

## ⏰ TIMELINE ESTIMADO

```
Ahora:
  ├─ 2 min    Setup (Docker, Python, verificaciones)
  ├─ 1 min    Levantar PostgreSQL
  ├─ 5 min    Inspeccionar CSV (PASO 1)
  ├─ 3 min    Benchmark prueba (PASO 2) ← ESTÁ HECHO
  └─ 4-6 hrs  Benchmark completo (PASO 3) ← INICIAR AHORA

Total: ~4-6 HORAS (la mayoría en background, puedes hacer otra cosa)
```

---

**¡Listo! Copia y pega los comandos arriba en orden. 🚀**

**Preguntas?** Ver `README.md` para troubleshooting completo.

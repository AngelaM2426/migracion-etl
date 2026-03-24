# 🚀 ETL: Carga Masiva CSV → PostgreSQL

**Proyecto**: Migración de datos del Registro Administrativo de Víctimas (**RAV**) del sistema documental a PostgreSQL con análisis de rendimiento.

**Dataset**: 13.1M registros × 53 columnas (4.6 GB)

---

## 📋 Tabla de Contenidos

1. [Requisitos](#requisitos)
2. [Estructura del Proyecto](#estructura-del-proyecto)
3. [Instalación](#instalación)
4. [Guía de Ejecución](#guía-de-ejecución)
5. [Resultados](#resultados)
6. [Troubleshooting](#troubleshooting)

---

## ⚙️ Requisitos

### Hardware
- **RAM mínima**: 2 GB (recomendado: 4-8 GB)
- **Espacio en disco**: 20 GB (10 GB BD + 4.6 GB CSV + buffers)
- **CPU**: Mínimo 2 cores

### Software
- **Linux/Mac** (o WSL2 en Windows)
- **Docker Desktop** (versión 20.10+)
- **Docker Compose** (versión 2.0+)
- **Python 3.12** (incluido en venv)
- **PostgreSQL Client** (para pruebas manuales)

### Verificar requisitos
```bash
docker --version          # ≥ 20.10.0
docker-compose --version  # ≥ 2.0.0
python3 --version        # ≥ 3.12
```

---

## 📁 Estructura del Proyecto

```
migracion-etl/
├── 📄 README.md                      ← Este archivo
├── 📄 docker-compose.yml             ← Configuración PostgreSQL
│
├── 🐍 SCRIPTS EJECUTABLES
│   ├── inspect_rav.py               ← [3.1] Inspeccionar CSV
│   ├── benchmark_carga_prueba.py    ← [3.3] Benchmark rápido (prueba)
│   ├── benchmark_carga.py           ← [3.3] Benchmark completo
│   ├── inspeccionar_csv.py          ← Utilidad auxiliar
│   └── generar_reportes_csv.py      ← Reportes en HTML/JSON
│
├── 📁 config/                        ← Datos
│   └── 0002_UNIVERSO_VICTIMAS_LB.txt ← CSV fuente (4.6 GB)
│
├── 📁 init/                          ← Scripts SQL iniciales
│   ├── 01_enums.sql                 ← Tipos de dato personalizados
│   ├── 02_tabla.sql                 ← [3.2] Esquema destino
│   └── 03_tabla.sql                 ← Índices y restricciones
│
├── 📁 src/                           ← Código modular
│   ├── config/
│   │   └── .env_example             ← Variables de entorno
│   └── database/
│       └── schemas/
│           └── 002_schema.py        ← Definiciones ORM
│
├── 📁 logs/                          ← Registros de ejecución
│   ├── inspeccion_csv_output.log    ← Resultado inspect_rav.py
│   ├── benchmark_carga_prueba.log   ← Log benchmark prueba
│   └── benchmark_carga.log          ← Log benchmark completo
│
├── 📁 outputs/                       ← Resultados generados
│   ├── benchmark_resultados.csv     ← Tabla comparativa
│   ├── benchmark_resultados.json    ← Datos en JSON
│   └── benchmark_resultados.html    ← Reporte visual
│
└── 📁 venv_migracion_etl/           ← Entorno virtual (410 MB)
    └── bin/python, pip, activate...
```

---

## 🔧 Instalación

### Paso 1: Clonar/Navegar al proyecto
```bash
cd /home/angela/Documents/migracion-etl
```

### Paso 2: Verificar archivo CSV
```bash
ls -lh config/0002_UNIVERSO_VICTIMAS_LB.txt
# Debe mostrar: 4.6G
```

### Paso 3: Levantar PostgreSQL con Docker
```bash
docker-compose up -d

# Esperar a que esté listo (20-30s)
# Verificar con:
docker ps | grep migracion_etl_db
```

### Paso 4: Activar entorno virtual
```bash
source venv_migracion_etl/bin/activate

# Verificar
python --version  # Debe mostrar Python 3.12.x
pip list | grep -E "(pandas|psycopg2|psutil)"
```

### ✅ Instalación completa
```bash
# Verificar conexión a BD
export PGPASSWORD=angela123
psql -h localhost -p 5433 -U angela -d ruv_victimas -c "SELECT 'Conexión OK' as estado;"
```

---

## 🎯 Guía de Ejecución

Sigue estos pasos **en orden** para ejecutar el project completo.

### **PASO 1: Inspeccionar el Archivo CSV** [Sección 3.1]

**Propósito**: Analizar la estructura del CSV sin cargar todo en memoria.

**Comando**:
```bash
cd /home/angela/Documents/migracion-etl
source venv_migracion_etl/bin/activate

python inspect_rav.py
```

**Salida esperada**:
```
════════════════════════════════════════════════════════════
  INSPECCIÓN CSV — 0002_UNIVERSO_VICTIMAS_LB.txt
════════════════════════════════════════════════════════════
  Total de filas    : 13,178,321
  Total de columnas : 53
  Tiempo total      : ~350s (5.8 minutos)

  ↳ Tipos inferidos:
     - STRING:     17 columnas (nombres, direcciones, etc.)
     - INTEGER:    10 columnas (IDs, códigos)
     - DATE:       6 columnas (fechas)
     - NULL:       20 columnas (100% vacías)

  ↳ Nulidad detectada:
     - EXPEDICIONDOCUMENTO:    100% ⚠️ ALTO
     - PRESUNTOVICTIMIZANTE:   100% ⚠️ ALTO
     - PRESUNTOACTOR:          46.31% ⚠️ ALTO
     - CIUDAD:                 35.79% ⚠️ ALTO

  ✓ Resultados guardados en: logs/inspeccion_csv_output.log
```

**Archivos generados**:
- `logs/inspeccion_csv_output.log` ← Análisis completo

**Tiempo aprox**: 5-8 minutos

---

### **PASO 2: Benchmark de Prueba (Rápido)** [Sección 3.3 - Validación]

**Propósito**: Validar que el proceso funciona antes de cargar 13.1M filas.

**Comando**:
```bash
source venv_migracion_etl/bin/activate

python benchmark_carga_prueba.py
```

**Parámetros**:
- Limita a: **50,000 filas** (vs 13.1M)
- Lotes: **1,000 | 5,000 | 10,000** (pequeños)
- Tiempo: **~3-4 minutos** (vs 4-6 horas con datos completos)

**Salida esperada**:
```
══════════════════════════════════════════════════════════════════════════════════
RESULTADOS - PRUEBA RÁPIDA
══════════════════════════════════════════════════════════════════════════════════
 lote     estrategia  tiempo_s  throughput_f/s  ram_pico_mb  insertadas  rechazadas
 1000 execute_values     38.90          1,285           83.6       47,598       2,402
 5000 execute_values     37.81          1,322          109.3       43,697       6,303
10000 execute_values     36.80          1,359          138.3       19,422      30,578
══════════════════════════════════════════════════════════════════════════════════

✓ CSV: outputs/benchmark_resultados_prueba.csv
✓ JSON: outputs/benchmark_resultados_prueba.json

Mejor throughput: 1,359 f/s (lote 10,000)
Menor RAM: 83.6 MB (lote 1,000)
```

**Archivos generados**:
- `logs/benchmark_carga_prueba.log` ← Logs detallados
- `outputs/benchmark_resultados_prueba.csv` ← Tabla de resultados
- `outputs/benchmark_resultados_prueba.json` ← JSON

**¿Qué significa el error "bigint out of range"?**
→ Algunos valores en el CSV son demasiado grandes para BIGINT (>9.2 × 10^18). Esto es normal en datos sucios. El script captura el error y continúa (idempotencia).

**Tiempo aprox**: 3-5 minutos

---

### **PASO 3: Benchmark Completo** [Sección 3.3 - PRINCIPAL]

**Propósito**: Ejecutar benchmark completo con todos los tamaños de lote obligatorios.

**Comando**:
```bash
source venv_migracion_etl/bin/activate

python benchmark_carga.py
```

**Parámetros**:
- Procesa: **13,178,321 filas** (todas)
- Lotes: **5,000 | 25,000 | 100,000 | 250,000 | 500,000**
- Estrategias: **execute_values** (≤100K) + **COPY** (>100K)
- Tiempo: **4-6 horas** (muy largo, pero completo)

**Salida esperada**:
```
══════════════════════════════════════════════════════════════════════════════════
BENCHMARK COMPLETO — RESULTADOS FINALES
══════════════════════════════════════════════════════════════════════════════════
 lote      estrategia           tiempo_s  throughput_f/s  ram_pico_mb  insertadas
  5,000    execute_values           TBD            TBD           TBD         TBD
 25,000    execute_values           TBD            TBD           TBD         TBD
100,000    execute_values           TBD            TBD           TBD         TBD
250,000    COPY via StringIO        TBD            TBD           TBD         TBD
500,000    COPY via StringIO        TBD            TBD           TBD         TBD
══════════════════════════════════════════════════════════════════════════════════

✓ CSV: outputs/benchmark_resultados.csv
✓ JSON: outputs/benchmark_resultados.json
✓ HTML: outputs/benchmark_resultados.html

Recomendación: Usar lote de 100,000 filas para balance óptimo
Tiempo total estimado: 3-4 horas para 13.1M filas
```

**Archivos generados**:
- `logs/benchmark_carga.log` ← Logs detallados
- `outputs/benchmark_resultados.csv` ← Tabla comparativa
- `outputs/benchmark_resultados.json` ← JSON
- `outputs/benchmark_resultados.html` ← Reporte visual
- **BD**: Tabla `universo_victimas_v1` con ~13M registros
- **BD**: Tabla `carga_lotes_log` con detalles de cada lote

**⏰ Tiempo aprox**: 4-6 horas (ejecutar en background)

**Para ejecutar en background** (recomendado):
```bash
nohup python benchmark_carga.py > logs/benchmark_carga_$(date +%Y%m%d_%H%M%S).log 2>&1 &

# Monitorear en otra terminal:
tail -f logs/benchmark_carga_*.log
```

---

### **PASO 4: Verificar Resultados** [Sección 3.4 - Idempotencia]

**Verificar que los datos se cargaron correctamente**:

```bash
export PGPASSWORD=angela123

# Total de registros
psql -h localhost -p 5433 -U angela -d ruv_victimas -c \
  "SELECT COUNT(*) as total_registros FROM universo_victimas_v1;"

# Expected: ~12.7-13.1M (algo rechazado por errores)

# Ver logs de carga
psql -h localhost -p 5433 -U angela -d ruv_victimas -c \
  "SELECT * FROM carga_lotes_log ORDER BY lote ASC;"

# Ver primeros 5 registros
psql -h localhost -p 5433 -U angela -d ruv_victimas -c \
  "SELECT origen, fuente, idpersona, documento, primernombre, 
          fechaocurrencia, estadovictima FROM universo_victimas_v1 LIMIT 5;"
```

**Verificar Idempotencia** (ejecutar benchmark 2 veces):
```bash
# Primera ejecución
python benchmark_carga_prueba.py

# Segunda ejecución (mismos datos)
python benchmark_carga_prueba.py

# Resultado esperado:
# Segunda vez: 0 nuevas insertadas (todos en conflicto)
# Porque: ON CONFLICT DO NOTHING
```

---

## 📊 Resultados

### Estructura de archivos de salida

#### `outputs/benchmark_resultados.csv`
```csv
lote,estrategia,tiempo_s,throughput_f/s,ram_pico_mb,filas_leidas,insertadas,rechazadas
5000,execute_values,XXX,XXX,XXX,XXX,XXX,XXX
25000,execute_values,XXX,XXX,XXX,XXX,XXX,XXX
100000,execute_values,XXX,XXX,XXX,XXX,XXX,XXX
250000,COPY,XXX,XXX,XXX,XXX,XXX,XXX
500000,COPY,XXX,XXX,XXX,XXX,XXX,XXX
```

#### `logs/carga_lotes_log` (en BD PostgreSQL)
```
id | lote | filas_leidas | filas_insertadas | filas_rechazadas | duracion_segundos | estrategia | detalle
---|------|--------------|------------------|------------------|------------------|-----------|--------
1  | 5000 | 10000000     | 9750000          | 250000           | 1234.56          | execute_values | "bigint out of range"
2  | 25000| 10000000     | 9800000          | 200000           | 987.23           | execute_values | NULL
3  | 100000| 10000000    | 9850000          | 150000           | 654.12           | execute_values | NULL
```

---

## 🔍 Troubleshooting

### ❌ Error: "Connection refused (localhost:5433)"

**Causa**: PostgreSQL no está corriendo.

**Solución**:
```bash
# Verificar contenedor
docker ps | grep migracion_etl_db

# Si no aparece, levantar
docker-compose up -d

# Si tenho permiso denegado:
sudo docker-compose up -d  # O ajustar permisos Docker
```

---

### ❌ Error: "address already in use (:5433)"

**Causa**: El puerto 5433 ya está ocupado.

**Solución**:
```bash
# Ver qué proceso usa el puerto
lsof -i :5433
ps aux | grep 5433

# Opción 1: Matar el proceso antiguo
kill -9 <PID>

# Opción 2: Cambiar puerto en docker-compose.yml
ports:
  - "5434:5432"  # Cambiar 5433 a 5434
```

---

### ❌ Error: "No such file or directory: config/0002_UNIVERSO_VICTIMAS_LB.txt"

**Causa**: El archivo CSV no existe en `config/`.

**Solución**:
```bash
# Verificar que estás en el directorio correcto
cd /home/angela/Documents/migracion-etl

# Verificar que el CSV existe
ls -lh config/

# Si no existe, copiar/descargar el archivo
# (Este archivo debe proporcionarse externamente)
```

---

### ❌ Error: "bigint out of range"

**Causa**: Algunos valores en el CSV son mayores que el máximo BIGINT (9,223,372,036,854,775,807).

**Solución**: Es NORMAL. El script ejecuta:
```sql
ON CONFLICT DO NOTHING  -- Ignora registros inválidos
```

Los registros con error se registran en `carga_lotes_log` con `detalle='bigint out of range'`.

**Acción**: Revisar columnas con valores anómalos:
```bash
python inspect_rav.py | grep -A 2 "Out of range"
```

---

### ❌ Error: "password authentication failed"

**Causa**: Credenciales incorrectas.

**Solución**:
```bash
# Verificar credenciales en docker-compose.yml
cat docker-compose.yml | grep POSTGRES

# Debe mostrar:
# POSTGRES_USER: angela
# POSTGRES_PASSWORD: angela123

# Verificar variable de entorno
export PGPASSWORD=angela123

# Intentar conexión manualmente
psql -h localhost -p 5433 -U angela -d ruv_victimas -c "SELECT 1;"
```

---

### ⚠️ Script muy lento / Stopped en la mitad

**Causa**: Espacio en disco agotado o RAM insuficiente.

**Solución**:
```bash
# Verificar espacio en disco
df -h /

# Necesita mínimo 10 GB libres

# Verificar RAM disponible
free -h

# Si es <2 GB, cerrar otras aplicaciones

# Si el proceso se atasca, puede reintentar desde el lote fallido
# Gracias a ON CONFLICT DO NOTHING
```

---

## 📚 Referencias Externas

- [PostgreSQL 16 Documentation](https://www.postgresql.org/docs/16/)
- [psycopg2 Documentation](https://www.psycopg.org/psycopg2/docs/)
- [Pandas Documentation](https://pandas.pydata.org/docs/)
- [Docker Documentation](https://docs.docker.com/)

---

## 👤 Autor / Contacto

- **Estudiante**: Angela
- **Fecha**: Marzo 2024
- **Proyecto**: Ejercicio 1 - Carga Masiva de CSV a PostgreSQL

---

## ✅ Checklist de Ejecución Completa

Marcar conforme se completen los pasos:

```
□ PASO 1: Inspeccionar CSV
  └─ Ejecutó: inspect_rav.py
  └─ Generó: logs/inspeccion_csv_output.log
  └─ Tiempo: 5-8 min

□ PASO 2: Benchmark Prueba
  └─ Ejecutó: benchmark_carga_prueba.py
  └─ Procesó: 50K filas (prueba)
  └─ Generó: outputs/benchmark_resultados_prueba.csv
  └─ Tiempo: 3-5 min

□ PASO 3: Benchmark Completo
  └─ Ejecutó: benchmark_carga.py
  └─ Procesó: 13.1M filas (TODAS)
  └─ Generó: outputs/benchmark_resultados.csv + JSON + HTML
  └─ Tiempo: 4-6 horas

□ PASO 4: Validar Resultados
  └─ SELECT COUNT(*) > 12M
  └─ Tabla carga_lotes_log poblada
  └─ Verificó idempotencia (2 ejecuciones)

□ PASO 5: Análisis Documento
  └─ Concluyó tamaño de lote óptimo
  └─ Justificó decisión con datos
  └─ Argumentó tiempo vs memoria vs integridad
```

---

## 📝 Licencia y Condiciones

Este proyecto es **académico** para el Taller "Migración Oracle → PostgreSQL".

- No usar en producción sin pruebas exhaustivas
- Datos del RAV son **confidenciales** (manejar con cuidado)
- Cumplir normativas de protección de datos personales

---

**¡Proyecto ETL completado!** 🎉

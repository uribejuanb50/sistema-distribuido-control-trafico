# generarGraficas.py (PC3)
# Proceso independiente de reportería analítica y visual.
# Se conecta a MongoDB directamente evitando colisiones de puertos ZMQ.

import time
from pymongo import MongoClient
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

def conectar_base_datos(host="localhost", puerto=27017, nombre_bd="trafico_principal"):
    try:
        cliente = MongoClient(f"mongodb://{host}:{puerto}/", serverSelectionTimeoutMS=2000)
        # Forzar una consulta para validar conexión
        cliente.server_info()
        print(f"[Graficador] Conectado exitosamente a MongoDB en {host}:{puerto}")
        return cliente[nombre_bd]
    except Exception as e:
        print(f"[Error Conexión] No se pudo acceder a MongoDB: {e}")
        return None

def extraer_y_limpiar_datos(bd):
    coleccion = bd["eventos"]
    registros = list(coleccion.find({}))
    
    if not registros:
        print("[Graficador] La base de datos está vacía. Esperando más eventos...")
        return pd.DataFrame()
    
    datos_procesados = []
    for r in registros:
        # Normalización de marcas de tiempo
        ts = r.get("timestamp")
        if not ts or ts == "no registra":
            continue
            
        try:
            ts_dt = pd.to_datetime(ts)
        except:
            continue

        # Extraer métricas manejando la variabilidad de los tres tipos de sensores
        tipo = r.get("tipo_sensor", "").upper()
        interseccion = r.get("interseccion", "General")
        
        volumen = 0
        if "camara" in r.get("tipo_sensor", "").lower():
            volumen = float(r.get("volumen", 0))
        elif "espira" in r.get("tipo_sensor", "").lower():
            volumen = float(r.get("vehiculos_contados", 0))

        velocidad = float(r.get("velocidad_promedio", r.get("velocidad_vehicular", 0)))
        emergencia = 1 if r.get("emergencia") is True else 0

        datos_processed = {
            "timestamp": ts_dt,
            "tipo_sensor": tipo,
            "interseccion": interseccion,
            "volumen": volumen,
            "velocidad": velocidad,
            "emergencia": emergencia
        }
        datos_procesados.append(datos_processed)
        
    return pd.DataFrame(datos_procesados)

def generar_reporte_visual(df):
    if df.empty:
        return

    df = df.sort_values("timestamp")
    
    # --- GRÁFICA 1: VOLUMEN VEHICULAR POR INTERSECCIÓN (C vs F) ---
    plt.figure(figsize=(12, 5))
    for inter in ["C", "F"]:
        sub_df = df[df["interseccion"] == inter]
        if not sub_df.empty:
            # Agrupar por bloques de tiempo para suavizar líneas si hay ráfagas pesadas
            sub_df = sub_df.set_index("timestamp").resample("5s").mean().dropna().reset_index()
            plt.plot(sub_df["timestamp"], sub_df["volumen"], marker='o', label=f"Intersección {inter}")
            
    plt.title("Evolución del Volumen Vehicular en Tiempo Real (Filas vs Columnas)")
    plt.xlabel("Tiempo de Simulación")
    plt.ylabel("Vehículos Detectados")
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    
    ruta_grafica1 = "reporte_volumen_trafico.png"
    plt.savefig(ruta_grafica1, dpi=150)
    plt.close()
    print(f"[Graficador] Guardada: {os.path.abspath(ruta_grafica1)}")

    # --- GRÁFICA 2: COMPORTAMIENTO DE VELOCIDADES Y ALERTAS ---
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    
    # Velocidades promedio generales
    df_gps = df[df["tipo_sensor"] == "GPS"]
    if not df_gps.empty:
        ax1.plot(df_gps["timestamp"], df_gps["velocidad"], color="teal", marker="x", linestyle="-.", label="Velocidad Promedio (GPS)")
    else:
        ax1.plot(df["timestamp"], df["velocidad"], color="darkorange", marker="x", linestyle="-", label="Velocidad Global")
        
    ax1.axhline(y=20, color="red", linestyle=":", label="Umbral Congestión Crítica (<20 km/h)")
    ax1.set_title("Perfiles de Velocidad y Detección de Congestión")
    ax1.set_ylabel("Velocidad (km/h)")
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend()

    # Emergencias (Paso de ambulancias detectados por cámaras)
    ax2.fill_between(df["timestamp"], df["emergencia"], color="crimson", alpha=0.4, label="Priorización Activa (Ambulancia / Alerta)")
    ax2.set_title("Eventos Críticos de Emergencia Registrados (PC2 -> PC3)")
    ax2.set_ylabel("Estado de Alerta")
    ax2.set_xlabel("Tiempo")
    ax2.set_ylim(-0.1, 1.1)
    ax2.grid(True, linestyle="--", alpha=0.3)
    ax2.legend()
    
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    plt.tight_layout()
    
    ruta_grafica2 = "reporte_velocidades_emergencias.png"
    plt.savefig(ruta_grafica2, dpi=150)
    plt.close()
    print(f"[Graficador] Guardada: {os.path.abspath(ruta_grafica2)}")

def main():
    bd = conectar_base_datos()
    if bd is None:
        return
        
    print("[Reportes] Iniciando bucle de actualización de gráficas cada 10 segundos...")
    while True:
        try:
            df = extraer_y_limpiar_datos(bd)
            if not df.empty:
                generar_reporte_visual(df)
            time.sleep(10)
        except KeyboardInterrupt:
            print("\n[Graficador] Deteniendo generación de reportes.")
            break
        except Exception as e:
            print(f"[Error en Ciclo] {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
# analitica.py  (PC2)
# - Recibe eventos de sensores vía SUB desde el broker en PC1
# - Aplica reglas y manda comandos a controlSemaforos vía PUSH
# - Replica eventos a BD Réplica (PC2) y BD Principal (PC3) vía PUSH
# - Hilo nuevo: REP en 7002 para indicaciones directas del monitor
#   (ola verde / ambulancia, cambio manual, volver a normal)

import zmq
import json
import time
import threading
from datetime import datetime

saltoLinea = "\n"


# ===================== utilidades de archivos =====================

def leerArchivoAString(archivoTxt):
    with open(archivoTxt, 'r', encoding='utf-8') as f:
        return f.read()

def eliminarCaracter(texto, caracter):
    return texto.replace(caracter, '')

def separarPorCaracter(texto, caracter):
    return texto.split(caracter)

def cargarArchivoADiccionario(nombreArchivo):
    contenido = leerArchivoAString(nombreArchivo)
    lineas = separarPorCaracter(contenido, saltoLinea)
    diccionario = {}
    for linea in lineas:
        linea = eliminarCaracter(linea, " ")
        if len(linea) == 0:
            continue
        partes = separarPorCaracter(linea, ";")
        if len(partes) == 2:
            diccionario[partes[0]] = partes[1]
    return diccionario


# ===================== sockets =====================

def crearSocketSubscriber(context, ipPublisher, puerto=5555):
    socket = context.socket(zmq.SUB)
    socket.connect(f"tcp://{ipPublisher}:{puerto}")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")
    return socket

def crearSocketPushConexion(context, ip, puerto):
    """PUSH que se conecta al PULL del otro lado."""
    socket = context.socket(zmq.PUSH)
    socket.connect(f"tcp://{ip}:{puerto}")
    return socket

def crearSocketRep(context, puerto):
    """REP que escucha indicaciones del monitor."""
    socket = context.socket(zmq.REP)
    socket.bind(f"tcp://0.0.0.0:{puerto}")
    return socket


# ===================== reglas =====================

def evaluarReglas(datoSensor, diccionarioGps):
    """
    Reglas:
      GPS    → nivel_congestion == 'Alta'           → extiende 15s
      Cámara → velocidad < 10 o emergencia == True  → extiende 13s
      Espira → vehiculos_contados > 25              → extiende 7s
    Retorna comando para controlSemaforos o None si tráfico normal.
    """
    tipo = datoSensor.get("tipo_sensor", "")

    if tipo == "gps":
        if datoSensor.get("nivel_congestion") == "Alta":
            interseccion = diccionarioGps.get(datoSensor["sensor_id"], "C")
            fila = interseccion[0]
            print(f"[Analítico] GPS congestión alta → fila {fila} extiende 15s")
            return {"fila": fila, "tiempoExtendido": 15, "motivo": "GPS_CONGESTION"}

    elif tipo == "camara":
        if float(datoSensor.get("velocidad_promedio", 100)) < 10 or datoSensor.get("emergencia") is True:
            fila = datoSensor["interseccion"][4]
            print(f"[Analítico] Cámara congestión/emergencia → fila {fila} extiende 13s")
            return {"fila": fila, "tiempoExtendido": 13, "motivo": "CAMARA_CONGESTION"}

    elif tipo == "espira":
        if float(datoSensor.get("vehiculos_contados", 0)) > 25:
            fila = datoSensor["interseccion"][4]
            print(f"[Analítico] Espira alta → fila {fila} extiende 7s")
            return {"fila": fila, "tiempoExtendido": 7, "motivo": "ESPIRA_ALTA"}

    return None


# ===================== hilo de indicaciones del monitor =====================

def hiloIndicacionesMonitor(socketRep, socketSemaforos, lockSocketSem):
    """
    Atiende REQ del monitor (puerto 7002) y traduce a comandos PUSH para controlSemaforos.
    Tipos de indicación soportados:
      - {"tipo":"ambulancia",     "fila":"C"|"F", "duracion":30}
      - {"tipo":"cambio_manual",  "fila":"C"|"F", "duracion":15}
      - {"tipo":"normal"}  → vuelve al ciclo normal
    """
    print("[Analítico-Indicaciones] Esperando indicaciones del monitor en 7002...")
    while True:
        try:
            mensaje = socketRep.recv_string()
            indicacion = json.loads(mensaje)
            print(f"[Analítico-Indicaciones] Recibido: {indicacion}")

            tipo = indicacion.get("tipo", "")

            if tipo == "ambulancia":
                comando = {
                    "fila": indicacion.get("fila", "C").upper(),
                    "tiempoExtendido": float(indicacion.get("duracion", 30)),
                    "motivo": "AMBULANCIA",
                    "forzar": True,
                }
            elif tipo == "cambio_manual":
                comando = {
                    "fila": indicacion.get("fila", "C").upper(),
                    "tiempoExtendido": float(indicacion.get("duracion", 15)),
                    "motivo": "CAMBIO_MANUAL",
                    "forzar": True,
                }
            elif tipo == "normal":
                comando = {"motivo": "RESET_NORMAL"}
            else:
                socketRep.send_string(json.dumps({"status": "ERROR", "razon": f"tipo desconocido: {tipo}"}))
                continue

            with lockSocketSem:
                socketSemaforos.send_string(json.dumps(comando))

            socketRep.send_string(json.dumps({"status": "OK", "comando": comando}))
            print(f"[Analítico-Indicaciones] Comando enviado a control: {comando}")

        except Exception as e:
            print(f"[Error Analítico-Indicaciones] {type(e).__name__}: {e}")
            try:
                socketRep.send_string(json.dumps({"status": "ERROR", "razon": str(e)}))
            except Exception:
                pass


# ===================== main =====================

def main():
    context = zmq.Context()

    IP_PC1 = "10.43.100.181"
    IP_PC3 = "10.43.100.106"

    PUERTO_EVENTOS_PC1     = 5555
    PUERTO_SEMAFOROS       = 6000
    PUERTO_BD_REPLICA      = 6001
    PUERTO_BD_PRINCIPAL    = 6002
    PUERTO_INDICACIONES    = 7002

    diccionarioGps = cargarArchivoADiccionario("GPS.txt")
    print(f"[Analítico] GPS cargados: {diccionarioGps}")

    socketEntrada      = crearSocketSubscriber(context, IP_PC1, PUERTO_EVENTOS_PC1)
    socketSemaforos    = crearSocketPushConexion(context, "localhost", PUERTO_SEMAFOROS)
    socketBDReplica    = crearSocketPushConexion(context, "localhost", PUERTO_BD_REPLICA)
    socketBDPrincipal  = crearSocketPushConexion(context, IP_PC3, PUERTO_BD_PRINCIPAL)
    socketIndicaciones = crearSocketRep(context, PUERTO_INDICACIONES)

    # Lock para no escribir al PUSH de semáforos desde dos hilos a la vez
    lockSocketSem = threading.Lock()

    hiloInd = threading.Thread(
        target=hiloIndicacionesMonitor,
        args=(socketIndicaciones, socketSemaforos, lockSocketSem),
        daemon=True,
    )
    hiloInd.start()

    time.sleep(2)
    print("[Analítico] Esperando eventos de PC1 e indicaciones del monitor...")

    while True:
        try:
            mensaje = socketEntrada.recv_string()
            evento = json.loads(mensaje)
            print(f"[Analítico] Evento recibido: {evento}")

            # Replicar a ambas BD (asíncrono, no bloquea)
            socketBDReplica.send_string(json.dumps(evento))
            socketBDPrincipal.send_string(json.dumps(evento))

            # Aplicar reglas
            comando = evaluarReglas(evento, diccionarioGps)
            if comando:
                with lockSocketSem:
                    socketSemaforos.send_string(json.dumps(comando))
                print(f"[Analítico] Comando enviado: {comando}")
            else:
                print("[Analítico] Tráfico normal — sin cambios")

        except Exception as e:
            print(f"[Error analitica] {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
# healthcheck.py  (PC2)
# Hace ping cada N segundos a bdPrincipal en PC3 (puerto REP 7001).
# Publica estado UP/DOWN por PUB en 7100 para que el monitor lo consuma.
# Si detecta DOWN, lanza monitorConsulta.py --respaldo en una terminal nueva.
# Si PC3 vuelve (UP), cierra el monitor de respaldo.

import zmq
import json
import time
import subprocess
import sys
import os
from datetime import datetime

procesoMonitorRespaldo = None


# ─────────────────────────── ping ───────────────────────────

def hacerPing(context, ip, puerto):
    """
    Crea un socket REQ nuevo en cada intento para evitar que quede
    en estado inválido tras un timeout.
    Retorna (vivo: bool, detalle: str).
    """
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.LINGER,   0)
    socket.setsockopt(zmq.RCVTIMEO, 1500)
    socket.setsockopt(zmq.SNDTIMEO, 1500)
    socket.connect(f"tcp://{ip}:{puerto}")
    try:
        socket.send_string(json.dumps({"consulta": "ping"}))
        respuesta = socket.recv_string()
        return True, respuesta
    except zmq.Again:
        return False, "timeout"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    finally:
        socket.close()


# ─────────────────────────── monitor de respaldo ───────────────────────────

def levantarMonitorRespaldo():
    global procesoMonitorRespaldo

    # Si ya corre, no lanzar otro
    if procesoMonitorRespaldo is not None and procesoMonitorRespaldo.poll() is None:
        print("[Healthcheck] Monitor de respaldo ya está corriendo")
        return

    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitorConsulta.py")

    # Intenta abrir una terminal nueva (orden de preferencia)
    terminales = [
        ["gnome-terminal", "--", sys.executable, ruta, "--respaldo"],
        ["xterm",          "-e", sys.executable, ruta, "--respaldo"],
        ["x-terminal-emulator", "-e", f"{sys.executable} {ruta} --respaldo"],
        ["konsole",        "-e", sys.executable, ruta, "--respaldo"],
    ]

    for cmd in terminales:
        try:
            procesoMonitorRespaldo = subprocess.Popen(cmd)
            print(f"[Healthcheck] Monitor de respaldo lanzado con '{cmd[0]}' "
                  f"(PID {procesoMonitorRespaldo.pid})")
            return
        except FileNotFoundError:
            continue

    # Fallback: misma consola (stdin compartido, menos ideal pero funciona)
    print("[Healthcheck] No se encontró terminal gráfica — lanzando en consola actual")
    procesoMonitorRespaldo = subprocess.Popen([sys.executable, ruta, "--respaldo"])
    print(f"[Healthcheck] Monitor de respaldo PID: {procesoMonitorRespaldo.pid}")


def bajarMonitorRespaldo():
    global procesoMonitorRespaldo
    if procesoMonitorRespaldo is not None and procesoMonitorRespaldo.poll() is None:
        print(f"[Healthcheck] PC3 recuperado — cerrando monitor de respaldo "
              f"(PID {procesoMonitorRespaldo.pid})")
        procesoMonitorRespaldo.terminate()
    procesoMonitorRespaldo = None


# ─────────────────────────── main ───────────────────────────

def main():
    context = zmq.Context()

    IP_PC3          = "10.43.100.106"
    PUERTO_PING     = 7001   # REP de bdPrincipal
    PUERTO_PUB      = 7100   # PUB de estado para suscriptores
    INTERVALO       = 3      # segundos entre pings

    publicador = context.socket(zmq.PUB)
    publicador.bind(f"tcp://0.0.0.0:{PUERTO_PUB}")

    print("[Healthcheck] Iniciado")
    print(f"[Healthcheck]   Verificando BD Principal → {IP_PC3}:{PUERTO_PING}")
    print(f"[Healthcheck]   Publicando estado        → puerto {PUERTO_PUB}")
    print(f"[Healthcheck]   Intervalo de ping        → {INTERVALO}s")

    ultimoEstado = None

    while True:
        try:
            vivo, info = hacerPing(context, IP_PC3, PUERTO_PING)
            estado = "UP" if vivo else "DOWN"

            publicador.send_string(json.dumps({
                "componente": "BD_PRINCIPAL_PC3",
                "estado":     estado,
                "timestamp":  str(datetime.now()),
                "detalle":    "OK" if vivo else info,
            }))

            if estado != ultimoEstado:
                print(f"[Healthcheck] *** Cambio → {estado} *** | {info if not vivo else 'OK'}")
                if estado == "DOWN":
                    levantarMonitorRespaldo()
                else:
                    bajarMonitorRespaldo()
                ultimoEstado = estado
            else:
                print(f"[Healthcheck] {estado}")

            time.sleep(INTERVALO)

        except Exception as e:
            print(f"[Error healthcheck] {type(e).__name__}: {e}")
            time.sleep(INTERVALO)


if __name__ == "__main__":
    main()
# healthcheck.py  (PC2)
# Proceso independiente: hace ping cada N segundos a la BD Principal del PC3.
# Si responde dentro del timeout, publica "UP"; si no, publica "DOWN".
# Los suscriptores (típicamente el monitor) usan ese estado para decidir
# si consultar la BD Principal o caer a la réplica.

import zmq
import json
import time
from datetime import datetime


def crearSocketReqConTimeout(context, ip, puerto, timeoutMs=1500):
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.LINGER, 0)
    socket.setsockopt(zmq.RCVTIMEO, timeoutMs)
    socket.setsockopt(zmq.SNDTIMEO, timeoutMs)
    socket.connect(f"tcp://{ip}:{puerto}")
    return socket


def hacerPing(context, ip, puerto):
    """
    Intenta un ping REQ/REP rápido al hilo de consultas de la BD Principal.
    Retorna (vivo: bool, detalle: str).
    Importante: tras un timeout, el socket REQ queda en estado inválido,
    por eso se cierra y se recrea en cada intento.
    """
    socket = crearSocketReqConTimeout(context, ip, puerto)
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


def main():
    context = zmq.Context()

    IP_PC3                       = "10.43.100.106"
    PUERTO_BD_PRINCIPAL_CONSULTA = 7001
    PUERTO_PUB_HEALTH            = 7100
    INTERVALO_SEGUNDOS           = 3

    publicador = context.socket(zmq.PUB)
    publicador.bind(f"tcp://0.0.0.0:{PUERTO_PUB_HEALTH}")

    print(f"[Healthcheck] Iniciado.")
    print(f"[Healthcheck]   - Verificando BD Principal en {IP_PC3}:{PUERTO_BD_PRINCIPAL_CONSULTA}")
    print(f"[Healthcheck]   - Publicando estado en puerto {PUERTO_PUB_HEALTH}")
    print(f"[Healthcheck]   - Intervalo: {INTERVALO_SEGUNDOS}s")

    ultimoEstado = None

    while True:
        try:
            vivo, info = hacerPing(context, IP_PC3, PUERTO_BD_PRINCIPAL_CONSULTA)
            estado = "UP" if vivo else "DOWN"

            mensaje = {
                "componente": "BD_PRINCIPAL_PC3",
                "estado": estado,
                "timestamp": str(datetime.now()),
                "detalle": info if not vivo else "OK",
            }
            publicador.send_string(json.dumps(mensaje))

            if estado != ultimoEstado:
                print(f"[Healthcheck] *** Cambio de estado → {estado} *** | detalle: {info}")
                ultimoEstado = estado
            else:
                print(f"[Healthcheck] {estado}")

            time.sleep(INTERVALO_SEGUNDOS)
        except Exception as e:
            print(f"[Error healthcheck] {type(e).__name__}: {e}")
            time.sleep(INTERVALO_SEGUNDOS)


if __name__ == "__main__":
    main()
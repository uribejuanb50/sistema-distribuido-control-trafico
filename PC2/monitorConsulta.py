# monitorConsulta.py
#
# Corre en PC3 (modo normal) o en PC2 (modo respaldo cuando PC3 cae).
#
# Uso:
#   python3 monitorConsulta.py             ← PC3, consulta BD Principal
#   python3 monitorConsulta.py --respaldo  ← PC2, consulta BD Réplica
#
# Funcionalidades:
#   consultar → pregunta a la BD (con failover automático si PC3 está DOWN)
#   indicar   → envía orden a analítica para mover semáforos (ambulancia, etc.)
#   estado    → muestra salud conocida del PC3

import zmq
import json
import threading
import time
import sys
from datetime import datetime


# ─────────────────────────── estado de salud ───────────────────────────

class EstadoSalud:
    """Cache thread-safe del último estado conocido del PC3."""

    def __init__(self, inicial="DESCONOCIDO"):
        self._lock   = threading.Lock()
        self._estado = inicial

    def actualizar(self, estado):
        with self._lock:
            self._estado = estado

    def obtener(self):
        with self._lock:
            return self._estado


# ─────────────────────────── sockets ───────────────────────────

def crearSocketReq(context, ip, puerto, timeoutMs=2000):
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.LINGER,   0)
    socket.setsockopt(zmq.RCVTIMEO, timeoutMs)
    socket.setsockopt(zmq.SNDTIMEO, timeoutMs)
    socket.connect(f"tcp://{ip}:{puerto}")
    return socket


def crearSocketSubHealth(context, ipPC2, puerto):
    socket = context.socket(zmq.SUB)
    socket.connect(f"tcp://{ipPC2}:{puerto}")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")
    return socket


# ─────────────────────────── hilo healthcheck ───────────────────────────

def hiloSuscriptorSalud(socket, estadoSalud):
    print("[Monitor-Salud] Suscrito al healthcheck, esperando estados...")
    while True:
        try:
            data = json.loads(socket.recv_string())
            if data.get("componente") == "BD_PRINCIPAL_PC3":
                nuevo    = data.get("estado", "DESCONOCIDO")
                anterior = estadoSalud.obtener()
                estadoSalud.actualizar(nuevo)
                if anterior != nuevo:
                    print(f"\n[Monitor-Salud] *** BD_PRINCIPAL_PC3 cambió a {nuevo} ***\n")
        except Exception as e:
            print(f"[Error Monitor-Salud] {type(e).__name__}: {e}")


# ─────────────────────────── consultas con failover ───────────────────────────

def consultarBD(context, consulta, config, estadoSalud):
    """
    Decide a qué BD preguntar según el healthcheck.
    En modo respaldo va directo a la réplica.
    En modo normal intenta principal primero y cae a réplica si falla.
    """
    if config["MODO_RESPALDO"] or estadoSalud.obtener() == "DOWN":
        intentos = [
            (config["IP_PC2"], config["PUERTO_BD_REPLICA"], "BD_RÉPLICA (PC2)"),
        ]
    else:
        intentos = [
            (config["IP_PC3"], config["PUERTO_BD_PRINCIPAL"], "BD_PRINCIPAL (PC3)"),
            (config["IP_PC2"], config["PUERTO_BD_REPLICA"],   "BD_RÉPLICA (PC2) [fallback]"),
        ]

    for ip, puerto, etiqueta in intentos:
        print(f"[Monitor] Consultando {etiqueta}...")
        socket = crearSocketReq(context, ip, puerto)
        try:
            socket.send_string(json.dumps(consulta))
            respuesta = socket.recv_string()
            return respuesta, etiqueta
        except zmq.Again:
            print(f"[Monitor] Timeout en {etiqueta}")
        except Exception as e:
            print(f"[Monitor] Error en {etiqueta}: {e}")
        finally:
            socket.close()

    return json.dumps({"error": "Ninguna BD respondió"}), "NINGUNA"


# ─────────────────────────── flujos de usuario ───────────────────────────

def imprimirMenuConsultas():
    print("\n  === CONSULTAS ===")
    print("  1. Todas las emergencias")
    print("  2. Emergencias en los últimos 10 segundos")
    print("  3. Eventos en hora pico (16h-17h)")
    print("  4. Eventos de cámara")
    print("  5. Eventos de GPS")
    print("  6. Eventos de espira")
    print("  7. Consultar por intersección (ej. INT-C5)")


def flujoConsultar(context, config, estadoSalud):
    imprimirMenuConsultas()
    numero = input("[Monitor] Número de consulta: ").strip()
    interseccion = ""
    if numero == "7":
        interseccion = input("[Monitor] Intersección: ").strip()

    consulta  = {"consulta": numero, "interseccion": interseccion}
    respuesta, fuente = consultarBD(context, consulta, config, estadoSalud)

    print(f"\n[Monitor] Fuente: {fuente}")
    print(f"[Monitor] Resultado:\n{respuesta}\n")


def imprimirMenuIndicaciones():
    print("\n  === INDICACIONES ===")
    print("  1. Ola verde / paso de ambulancia")
    print("  2. Cambio manual de semáforo")
    print("  3. Volver al ciclo normal")


def flujoIndicar(context, config):
    imprimirMenuIndicaciones()
    opc = input("[Monitor] Opción: ").strip()

    if opc == "1":
        fila     = (input("[Monitor] Fila a priorizar (C/F): ").strip() or "C").upper()
        dur      = input("[Monitor] Duración en segundos [30]: ").strip()
        indicacion = {"tipo": "ambulancia",    "fila": fila, "duracion": float(dur) if dur else 30}
    elif opc == "2":
        fila     = (input("[Monitor] Fila a poner en verde (C/F): ").strip() or "C").upper()
        dur      = input("[Monitor] Duración en segundos [15]: ").strip()
        indicacion = {"tipo": "cambio_manual", "fila": fila, "duracion": float(dur) if dur else 15}
    elif opc == "3":
        indicacion = {"tipo": "normal"}
    else:
        print("[Monitor] Opción inválida")
        return

    socket = crearSocketReq(context, config["IP_PC2"], config["PUERTO_ANALITICA"])
    try:
        socket.send_string(json.dumps(indicacion))
        respuesta = socket.recv_string()
        print(f"[Monitor] Respuesta de analítica: {respuesta}")
    except zmq.Again:
        print("[Monitor] Timeout: analítica no respondió")
    except Exception as e:
        print(f"[Monitor] Error al indicar: {e}")
    finally:
        socket.close()


def imprimirMenuPrincipal(estadoSalud, modoRespaldo):
    estado = estadoSalud.obtener()
    modo   = "RESPALDO (PC2)" if modoRespaldo else "NORMAL (PC3)"
    print(f"\n[Monitor] ══════════════════════════════")
    print(f"[Monitor]   Modo: {modo}")
    print(f"[Monitor]   Estado BD Principal: {estado}")
    print(f"[Monitor] ══════════════════════════════")
    print("[Monitor]   consultar  → hacer consulta a la BD")
    print("[Monitor]   indicar    → enviar orden a analítica")
    print("[Monitor]   estado     → ver salud del sistema")
    print("[Monitor]   salir      → terminar")


# ─────────────────────────── main ───────────────────────────

def main():
    modoRespaldo = "--respaldo" in sys.argv

    context = zmq.Context()

    config = {
        "MODO_RESPALDO":        modoRespaldo,
        "IP_PC2":               "localhost" if modoRespaldo else "10.43.98.207",
        "IP_PC3":               "10.43.100.106",
        "PUERTO_BD_PRINCIPAL":  7001,
        "PUERTO_BD_REPLICA":    7003,
        "PUERTO_ANALITICA":     7002,
        "PUERTO_HEALTH":        7100,
    }

    estadoSalud = EstadoSalud(inicial="DOWN" if modoRespaldo else "DESCONOCIDO")

    # Hilo suscriptor al healthcheck (siempre en PC2)
    socketSalud = crearSocketSubHealth(context, config["IP_PC2"], config["PUERTO_HEALTH"])
    hilo = threading.Thread(
        target=hiloSuscriptorSalud,
        args=(socketSalud, estadoSalud),
        daemon=True,
    )
    hilo.start()

    if modoRespaldo:
        print("[Monitor] *** MODO RESPALDO — BD Réplica en PC2 ***")
    else:
        print("[Monitor] === Servicio de Monitoreo y Consulta (PC3) ===")

    time.sleep(1)  # espera el primer mensaje del healthcheck

    while True:
        try:
            imprimirMenuPrincipal(estadoSalud, modoRespaldo)
            eleccion = input("[Monitor] > ").strip().lower()

            if eleccion == "consultar":
                flujoConsultar(context, config, estadoSalud)
            elif eleccion == "indicar":
                flujoIndicar(context, config)
            elif eleccion == "estado":
                print(f"[Monitor] Estado actual de PC3: {estadoSalud.obtener()}")
            elif eleccion == "salir":
                print("[Monitor] Finalizando...")
                break
            else:
                print("[Monitor] Opción no reconocida")

        except KeyboardInterrupt:
            print("\n[Monitor] Interrumpido")
            break
        except Exception as e:
            print(f"[Error monitor] {type(e).__name__}: {e}")

    context.term()


if __name__ == "__main__":
    main()
# monitorConsulta.py
# Servicio UNIFICADO de monitoreo y consulta.
# Sustituye a monitor.py + consulta.py de la primera entrega.
#
# Funcionalidades:
#   - "consultar"  → pregunta a la BD (Principal en PC3 o Réplica en PC2 como fallback)
#                    qué BD consultar lo decide el estado del healthcheck publicado en PC2
#   - "indicar"    → envía indicación al servicio de analítica (REQ/REP en 7002)
#                    para forzar el cambio de semáforos (ola verde, manual, normal)
#   - "estado"     → muestra el último estado de salud conocido del PC3
#
# Puede correr en PC3 (modo normal) o en PC2 (modo respaldo cuando PC3 cae).
# El healthcheck siempre vive en PC2, así que la IP de healthcheck no cambia.

import zmq
import json
import threading
import time
from datetime import datetime


# ===================== estado de salud compartido =====================

class EstadoSalud:
    """Cache thread-safe del último estado conocido del PC3."""
    def __init__(self):
        self.lock = threading.Lock()
        self.estado = "DESCONOCIDO"
        self.ultimoTimestamp = None

    def actualizar(self, estado):
        with self.lock:
            self.estado = estado
            self.ultimoTimestamp = datetime.now()

    def obtener(self):
        with self.lock:
            return self.estado


# ===================== sockets =====================

def crearSocketReq(context, ip, puerto, timeoutMs=2000):
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.LINGER, 0)
    socket.setsockopt(zmq.RCVTIMEO, timeoutMs)
    socket.setsockopt(zmq.SNDTIMEO, timeoutMs)
    socket.connect(f"tcp://{ip}:{puerto}")
    return socket


def crearSocketSubHealth(context, ipPC2, puerto):
    socket = context.socket(zmq.SUB)
    socket.connect(f"tcp://{ipPC2}:{puerto}")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")
    return socket


# ===================== hilo suscriptor al healthcheck =====================

def hiloSuscriptorSalud(socket, estadoSalud):
    print("[Monitor-Salud] Suscrito al healthcheck. Esperando estados...")
    while True:
        try:
            mensaje = socket.recv_string()
            data = json.loads(mensaje)
            if data.get("componente") == "BD_PRINCIPAL_PC3":
                nuevoEstado = data.get("estado", "DESCONOCIDO")
                anterior = estadoSalud.obtener()
                estadoSalud.actualizar(nuevoEstado)
                if anterior != nuevoEstado:
                    print(f"\n[Monitor-Salud] *** Cambio detectado: BD_PRINCIPAL_PC3 ahora está {nuevoEstado} ***")
        except Exception as e:
            print(f"[Error Monitor-Salud] {type(e).__name__}: {e}")


# ===================== consultas a BD con failover =====================

def consultarBD(context, eleccionUsuario, config, estadoSalud):
    """
    Decide a qué BD consultar (principal o réplica) según el healthcheck.
    Cae automáticamente a la réplica si la principal falla o está marcada DOWN.
    """
    estado = estadoSalud.obtener()

    if estado == "DOWN":
        # ya sabemos que PC3 está caído, vamos directo a la réplica
        intentos = [
            (config["IP_PC2"], config["PUERTO_BD_REPLICA"], "BD_RÉPLICA (PC2)"),
        ]
    else:
        # UP o DESCONOCIDO → intentamos principal primero, réplica como respaldo
        intentos = [
            (config["IP_PC3"], config["PUERTO_BD_PRINCIPAL"], "BD_PRINCIPAL (PC3)"),
            (config["IP_PC2"], config["PUERTO_BD_REPLICA"],   "BD_RÉPLICA (PC2) [fallback]"),
        ]

    for ip, puerto, etiqueta in intentos:
        print(f"[Monitor] Consultando {etiqueta} en {ip}:{puerto}...")
        socket = crearSocketReq(context, ip, puerto)
        try:
            socket.send_string(json.dumps(eleccionUsuario))
            respuesta = socket.recv_string()
            return respuesta, etiqueta
        except zmq.Again:
            print(f"[Monitor] Timeout en {etiqueta}")
        except Exception as e:
            print(f"[Monitor] Error en {etiqueta}: {e}")
        finally:
            socket.close()

    return json.dumps({"error": "Ninguna BD respondió"}), "NINGUNA"


# ===================== flujos de UI =====================

def imprimirMenuConsultas():
    print("\n[Monitor] === MENÚ DE CONSULTAS ===")
    print("[Monitor]   1. Emergencias")
    print("[Monitor]   2. Emergencias en los últimos 10 segundos")
    print("[Monitor]   3. Hora pico (16-17h)")
    print("[Monitor]   4. Novedades de cámara")
    print("[Monitor]   5. Novedades de GPS")
    print("[Monitor]   6. Novedades de espira")
    print("[Monitor]   7. Consultar por intersección")


def flujoConsultar(context, config, estadoSalud):
    imprimirMenuConsultas()
    consulta = input("[Monitor] Número de consulta: ").strip()
    interseccion = ""
    if consulta == "7":
        interseccion = input("[Monitor] Intersección (ej. INT-C5): ").strip()
    envio = {"consulta": consulta, "interseccion": interseccion}

    respuesta, fuente = consultarBD(context, envio, config, estadoSalud)
    print(f"\n[Monitor] Fuente: {fuente}")
    print(f"[Monitor] Respuesta:\n{respuesta}\n")


def imprimirMenuIndicaciones():
    print("\n[Monitor] === MENÚ DE INDICACIONES ===")
    print("[Monitor]   1. Ola verde / paso de ambulancia")
    print("[Monitor]   2. Cambio manual de semáforo")
    print("[Monitor]   3. Volver al ciclo normal")


def flujoIndicar(context, config):
    imprimirMenuIndicaciones()
    opc = input("[Monitor] Opción: ").strip()

    if opc == "1":
        fila = (input("[Monitor] Fila a priorizar (C/F): ").strip() or "C").upper()
        duracion = input("[Monitor] Duración en segundos (default 30): ").strip()
        duracion = float(duracion) if duracion else 30
        indicacion = {"tipo": "ambulancia", "fila": fila, "duracion": duracion}
    elif opc == "2":
        fila = (input("[Monitor] Fila a poner en verde (C/F): ").strip() or "C").upper()
        duracion = input("[Monitor] Duración en segundos (default 15): ").strip()
        duracion = float(duracion) if duracion else 15
        indicacion = {"tipo": "cambio_manual", "fila": fila, "duracion": duracion}
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


def imprimirMenuPrincipal(estadoSalud):
    estado = estadoSalud.obtener()
    print(f"\n[Monitor] ====================================")
    print(f"[Monitor]   Estado BD Principal (PC3): {estado}")
    print(f"[Monitor] ====================================")
    print("[Monitor] Opciones:")
    print("[Monitor]   consultar  → hacer consulta a la BD")
    print("[Monitor]   indicar    → enviar indicación a analítica")
    print("[Monitor]   estado     → ver estado de salud")
    print("[Monitor]   salir      → terminar")


# ===================== main =====================

def main():
    context = zmq.Context()

    # Ajustá las IPs según el despliegue
    config = {
        "IP_PC2":               "10.43.98.207",
        "IP_PC3":               "10.43.100.106",
        "PUERTO_BD_PRINCIPAL":  7001,
        "PUERTO_BD_REPLICA":    7003,
        "PUERTO_ANALITICA":     7002,
        "PUERTO_HEALTH":        7100,
    }

    estadoSalud = EstadoSalud()

    # Hilo suscriptor al healthcheck
    socketSalud = crearSocketSubHealth(context, config["IP_PC2"], config["PUERTO_HEALTH"])
    hiloSalud = threading.Thread(
        target=hiloSuscriptorSalud,
        args=(socketSalud, estadoSalud),
        daemon=True,
    )
    hiloSalud.start()

    print("[Monitor] === Servicio de Monitoreo y Consulta ===")
    print(f"[Monitor]   PC2 (analítica/réplica/health): {config['IP_PC2']}")
    print(f"[Monitor]   PC3 (BD principal): {config['IP_PC3']}")

    # Esperar el primer mensaje del healthcheck para no arrancar en DESCONOCIDO
    time.sleep(1)

    while True:
        try:
            imprimirMenuPrincipal(estadoSalud)
            eleccion = input("[Monitor] > ").strip().lower()

            if eleccion == "consultar":
                flujoConsultar(context, config, estadoSalud)
            elif eleccion == "indicar":
                flujoIndicar(context, config)
            elif eleccion == "estado":
                print(f"[Monitor] Estado actual: {estadoSalud.obtener()}")
            elif eleccion == "salir":
                print("[Monitor] Finalizando...")
                break
            else:
                print("[Monitor] Opción no reconocida")
        except KeyboardInterrupt:
            print("\n[Monitor] Interrumpido por usuario")
            break
        except Exception as e:
            print(f"[Error monitor] {type(e).__name__}: {e}")

    context.term()


if __name__ == "__main__":
    main()
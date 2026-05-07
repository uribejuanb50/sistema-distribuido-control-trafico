import zmq
import json
import time
from datetime import datetime

saltoLinea = "\n"

def devolverDiferenciaTimestampsEnSegundos(timestamp1, timestamp2):
    return abs((timestamp1 - timestamp2).total_seconds())

def leer_archivo_a_string(archivo_txt):
    with open(archivo_txt, 'r', encoding='utf-8') as f:
        return f.read()

def eliminar_caracter(texto, caracter):
    return texto.replace(caracter, '')

def separar_por_caracter(texto, caracter):
    return texto.split(caracter)

def cargarArchivoADiccionario(nombreArchivo):
    contenido = leer_archivo_a_string(nombreArchivo)
    lineas = separar_por_caracter(contenido, saltoLinea)
    diccionario = {}
    for linea in lineas:
        linea = eliminar_caracter(linea, " ")
        if len(linea) == 0:
            continue
        partes = separar_por_caracter(linea, ";")
        if len(partes) == 2:
            diccionario[partes[0]] = partes[1]
    return diccionario

def crearSocketSubscriber(context, ipPublisher, puerto=5555):
    socket = context.socket(zmq.SUB)
    socket.connect(f"tcp://{ipPublisher}:{puerto}")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")
    return socket

def crearSocketPushConexion(context, ip, puerto):
    """PUSH que conecta hacia un servidor que ya está esperando"""
    socket = context.socket(zmq.PUSH)
    socket.connect(f"tcp://{ip}:{puerto}")
    return socket

def recibirEvento(socket):
    mensaje = socket.recv_string()
    evento = json.loads(mensaje)
    print(f"[ZMQ] Evento recibido: {evento}")
    return evento

def evaluarReglas(datoSensor, diccionarioGps):
    """
    Evalúa las reglas y retorna un comando de semáforo si aplica,
    o None si el tráfico es normal.
    """
    print("[Analítico] Reglas del sistema:")
    print("  GPS    → nivel_congestion == 'Alta'          → extiende 15s")
    print("  Camara → velocidad < 10 o emergencia == True → extiende 13s")
    print("  Espira → vehiculos_contados > 25             → extiende 7s")

    tipo = datoSensor.get("tipo_sensor", "")

    if tipo == "gps":
        if datoSensor["nivel_congestion"] == "Alta":
            interseccion = diccionarioGps.get(datoSensor["sensor_id"], "C")
            fila = interseccion[0]
            print(f"[Analítico] GPS congestión alta → fila {fila} extiende 15s")
            return {"fila": fila, "tiempoExtendido": 15, "motivo": "GPS_CONGESTION"}

    elif tipo == "camara":
        if float(datoSensor["velocidad_promedio"]) < 10 or datoSensor["emergencia"] == True:
            fila = datoSensor["interseccion"][4]
            print(f"[Analítico] Cámara congestión/emergencia → fila {fila} extiende 13s")
            return {"fila": fila, "tiempoExtendido": 13, "motivo": "CAMARA_CONGESTION"}

    elif tipo == "espira":
        if float(datoSensor["vehiculos_contados"]) > 25:
            fila = datoSensor["interseccion"][4]
            print(f"[Analítico] Espira alta → fila {fila} extiende 7s")
            return {"fila": fila, "tiempoExtendido": 7, "motivo": "ESPIRA_ALTA"}

    print("[Analítico] Tráfico normal — sin cambios")
    return None

def main():
    context = zmq.Context()

    IP_PC1 = "10.43.100.181"

    diccionarioGps = cargarArchivoADiccionario("GPS.txt")
    print(f"[Analítico] GPS cargados: {diccionarioGps}")

    # Socket que recibe eventos de PC1
    socketEntrada = crearSocketSubscriber(context, IP_PC1, 5555)

    # Socket que envía comandos al control de semáforos
    socketSemaforos = crearSocketPushConexion(context, "localhost", 6000)

    # BD réplica local PC2
    socketBDReplica = crearSocketPushConexion(context, "localhost", 6001)

    # BD principal PC3
    IP_PC3 = "10.43.100.106"  # IP real de PC3
    socketBDPrincipal = crearSocketPushConexion(context, IP_PC3, 6002)

    time.sleep(5)
    print("[Analítico] Esperando eventos de PC1...")

    while True:
        try:
            evento = recibirEvento(socketEntrada)

            # Guarda en BD réplica (PC2)
            socketBDReplica.send_string(json.dumps(evento))

            # Guarda en BD principal (PC3)
            socketBDPrincipal.send_string(json.dumps(evento))

            # Evalúa reglas y envía comando si hay congestión
            comando = evaluarReglas(evento, diccionarioGps)

            print(f"comando: {comando}")

            if comando:
                socketSemaforos.send_string(json.dumps(comando))

        except Exception as e:
            print(f"[Error analitica] {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
# bdReplica.py  (PC2)
# Dos hilos:
#   - hiloEscritura : PULL en 6001, inserta eventos en mongo
#   - hiloConsulta  : REP  en 7003, atiende consultas síncronas del monitor

import zmq
import json
import threading
from pymongo import MongoClient
from datetime import datetime, timedelta


# ===================== mongo =====================

def conectarMongoBD(host="localhost", puerto=27017, nombreBD="trafico_replica"):
    cliente = MongoClient(f"mongodb://{host}:{puerto}/")
    print(f"[BD Réplica] Conectado a {host}:{puerto} - BD: {nombreBD}")
    return cliente[nombreBD]


def consultarMongo(bd, coleccion, filtro, proyeccion={"_id": 0}):
    return list(bd[coleccion].find(filtro, proyeccion))


def menuConsultas(eleccion, bd):
    coleccion = "eventos"
    datetimeya = datetime.now()
    datetimemenos10 = datetimeya - timedelta(seconds=10)
    inicio_str = datetimemenos10.strftime("%Y-%m-%d %H:%M:%S.%f")
    fin_str    = datetimeya.strftime("%Y-%m-%d %H:%M:%S.%f")

    opciones = {
        "1": lambda: consultarMongo(bd, coleccion, {"emergencia": True}),
        "2": lambda: consultarMongo(bd, coleccion, {
            "emergencia": True,
            "timestamp_recepcion": {"$gte": inicio_str, "$lte": fin_str},
        }),
        "3": lambda: consultarMongo(bd, coleccion, {"timestamp": {"$regex": r"1[6-7]"}}),
        "4": lambda: consultarMongo(bd, coleccion, {"tipo_sensor": "camara"}),
        "5": lambda: consultarMongo(bd, coleccion, {"tipo_sensor": "gps"}),
        "6": lambda: consultarMongo(bd, coleccion, {"tipo_sensor": "espira"}),
        "7": lambda: consultarMongo(bd, coleccion, {"interseccion": eleccion.get("interseccion", "")}),
        "ping": lambda: {"status": "OK", "rol": "replica", "timestamp": str(datetime.now())},
    }

    resultados = opciones.get(eleccion.get("consulta"), lambda: "No hay opción")()
    return json.dumps(resultados, indent=4, default=str)


# ===================== hilos =====================

def hiloEscritura(bd, puerto):
    """Hilo ASÍNCRONO: recibe eventos vía PULL y los guarda en mongo."""
    context = zmq.Context.instance()
    socket = context.socket(zmq.PULL)
    socket.bind(f"tcp://0.0.0.0:{puerto}")
    print(f"[BD Réplica - Escritura] PULL en puerto {puerto}")

    while True:
        try:
            mensaje = socket.recv_string()
            evento = json.loads(mensaje)
            evento["timestamp_recepcion"] = str(datetime.now())
            resultado = bd["eventos"].insert_one(evento)
            print(f"[BD Réplica - Escritura] Guardado: {resultado.inserted_id}")
        except Exception as e:
            print(f"[Error bdReplica-Escritura] {type(e).__name__}: {e}")


def hiloConsulta(bd, puerto):
    """Hilo SÍNCRONO: atiende consultas REQ/REP."""
    context = zmq.Context.instance()
    socket = context.socket(zmq.REP)
    socket.bind(f"tcp://0.0.0.0:{puerto}")
    print(f"[BD Réplica - Consulta] REP en puerto {puerto}")

    while True:
        try:
            mensaje = socket.recv_string()
            consulta = json.loads(mensaje)
            respuesta = menuConsultas(consulta, bd)
            socket.send_string(respuesta)
        except Exception as e:
            print(f"[Error bdReplica-Consulta] {type(e).__name__}: {e}")
            try:
                socket.send_string(json.dumps({"error": str(e)}))
            except Exception:
                pass


# ===================== main =====================

def main():
    PUERTO_ESCRITURA = 6001
    PUERTO_CONSULTA  = 7003

    bd = conectarMongoBD()

    hiloW = threading.Thread(target=hiloEscritura, args=(bd, PUERTO_ESCRITURA), daemon=True)
    hiloR = threading.Thread(target=hiloConsulta,  args=(bd, PUERTO_CONSULTA),  daemon=True)

    hiloW.start()
    hiloR.start()

    print("[BD Réplica] Servicio iniciado (escritura asíncrona + consulta síncrona)")

    hiloW.join()
    hiloR.join()


if __name__ == "__main__":
    main()
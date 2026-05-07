from pymongo import MongoClient
from datetime import datetime, timedelta
import json
import os
import zmq

def conectarMongoBD(host = "localhost", puerto = "27017", nombreBD = "trafico_principal"):
    cliente = MongoClient(f"mongodb://{host}:{puerto}/")
    print(f"[BD Principal]: Conectado a {host}:{puerto} - BD: {nombreBD}")
    return cliente[nombreBD]

def consultarMongo(bd, coleccion, filtro, proyeccion ={"_id" : 0}) :
    
    return list(bd[coleccion].find(filtro, proyeccion))

def menuConsultas(eleccion):

    os.system("clear")

    bd = conectarMongoBD()
    coleccion = "eventos"

    datetimeya = datetime.now()
    datetimemenos10 = datetimeya - timedelta(seconds = 10)

    inicio_str = datetimemenos10.strftime("%Y-%m-%d %H:%M:%S.%f")
    fin_str = datetimeya.strftime("%Y-%m-%d %H:%M:%S.%f")

    opciones ={
        "1" : lambda: consultarMongo(bd, coleccion, {"emergencia" : True}),
        "2" : lambda: consultarMongo(bd, coleccion, {
                                            "emergencia" : True, 
                                             "timestamp_recepcion" : {"$gte" : inicio_str, "$lte" : fin_str}
                                            }),

        "3" : lambda: consultarMongo(bd, coleccion, { "timestamp": {"$regex" : r"1[6-7]"}}),
        "4" : lambda: consultarMongo(bd, coleccion, { "tipo_sensor" : "camara" }),
        "5" : lambda: consultarMongo(bd, coleccion, { "tipo_sensor" : "gps"}),
        "6" : lambda: consultarMongo(bd, coleccion, { "tipo_sensor" : "espira"}),
        "7" : lambda: consultarMongo(bd, coleccion, { "interseccion" : eleccion["interseccion"]})
    }

    resultados = opciones.get(eleccion["consulta"], lambda : "No hay opción")()

    return json.dumps(resultados, indent= 4, default= str)

def crearSocketRep(context, ipPublisher, puerto) :
    socket = context.socket(zmq.REP)
    socket.bind(f"tcp://{ipPublisher}:{puerto}")

    return socket

def main():

    context = zmq.Context()

    IP_PC3 = "localhost"
    puertoConsulta = 7001

    socketConsulta = crearSocketRep(context, IP_PC3, puertoConsulta)

    print("[Consulta] Bienvenido al servicio de consulta")
    print("[Consulta] Opciones para consultar: ")
    print("[Consulta] 1. Emergencaias: ")
    print("[Consulta] 2. Emergencias en los ultimos 10 segundos")
    print("[Consulta] 3. Hora pico")
    print("[Consulta] 4. Novedades camara")
    print("[Consulta] 5. Novedades gps")
    print("[Consulta] 6. Novedades espira")


    
    while True:
        solicitud = socketConsulta.recv_string()
        consulta = json.loads(solicitud)

        print(f"llega: {solicitud}")

        respuesta = menuConsultas(consulta)

        socketConsulta.send_string(respuesta)


if __name__ == "__main__" :
    main()
#monitor.py
import zmq
import json

def crearSocketReq(context, ipPublisher, puerto):

    socket = context.socket(zmq.REQ)
    socket.connect(f"tcp://{ipPublisher}:{puerto}")

    return socket

def switchMenu(eleccion, socketConsulta, socketAnaliticas):
    opciones = {
        "consultar" : lambda: consultar(socketConsulta),
        "indicar" : lambda: indicar(socketAnaliticas)
    }

    return opciones.get(eleccion, lambda: "Eleccion fuera de los parámetros, considera escribir bien la elección")()

def consultar(socket) :

    print("[Monitor] Bienvenido al servicio de monitoreo y consulta")
    print("[Monitor] Opciones para consultar: ")
    print("[Monitor] 1. Emergencaias: ")
    print("[Monitor] 2. Emergencias en los ultimos 10 segundos")
    print("[Monitor] 3. Hora pico")
    print("[Monitor] 4. Novedades camara")
    print("[Monitor] 5. Novedades gps")
    print("[Monitor] 6. Novedades espira")
    print("[Monitor] 7. Consultar intersección")

    consulta = input("[Monitor] Ingrese el número de su consulta")
    interseccion = " "
    
    if(consulta == "7") : 
        interseccion = input("[Monitor] ingrese la interseccion")


    envio = {"consulta" : consulta, "interseccion" : interseccion}

    socket.send_string(json.dumps(envio))

    print("[Monitor] consultando...")

    respuesta = socket.recv_string()
    print(f"[Monitor] respuesta: {respuesta}")

    return

def indicar(socket) :
    return

def main():

    context = zmq.Context()

    IP_PC2 = "10.43.98.207"
    puertoAnaliticas = "7002"

    socketAnaliticas = crearSocketReq(context, IP_PC2, puertoAnaliticas)

    IP_PC3 = "localhost"
    puertoConsulta = "7001"

    socketConsulta = crearSocketReq(context, IP_PC3, puertoConsulta)

    print("[Monitor] Monitor funcionando correctamente")

    while True:

        eleccion = input("[Monitor] ¿Deseas consultar o indicar?")

        switchMenu(eleccion, socketConsulta, socketAnaliticas)


        
    

    pass

if __name__ == "__main__":
    main()
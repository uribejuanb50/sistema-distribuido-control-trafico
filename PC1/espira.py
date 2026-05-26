import json
import random
import math
from datetime import datetime
import threading
from sensor import (Sensor, funcionCiclica, leer_archivo_a_string, eliminar_caracter, 
                    separar_por_caracter, crearSocketPublicador, devolverDiferenciaTimestampsEnSegundos, 
                    saltoLinea)

class Espira(Sensor):
    def __init__(self, idSensor, tipoSensor, interseccion, timestamp, intervaloDeTiempo):
        super().__init__(idSensor, tipoSensor)
        self.interseccion = interseccion
        self.timestampPrevio = timestamp
        self.vehiculosContados = 0
        self.intervaloDeTiempo = float(intervaloDeTiempo)

    def informacionSensor(self):
        stringRetorno = super().informacionSensor()
        stringRetorno += f"interseccion : {self.interseccion}" + saltoLinea
        stringRetorno += f"timeStampPrevio: {self.timestampPrevio}" + saltoLinea
        stringRetorno += f"vehiculosContados: {math.floor(self.vehiculosContados)}" + saltoLinea
        stringRetorno += f"intervaloDeTiempo (segundos) : {self.intervaloDeTiempo}" + saltoLinea
        return stringRetorno
    
    def crearJSON(self):
        return json.dumps({
            "sensor_id": f"ESP-{self.idSensor}",
            "tipo_sensor": "espira",
            "timestamp": str(self.timeStampEnvio),
            "interseccion": self.interseccion,
            "timestamp_previo": str(self.timestampPrevio),
            "vehiculos_contados": math.floor(self.vehiculosContados),
            "intervalo_segundos": self.intervaloDeTiempo
        })

    def simular(self, 
                chanceGeneracionVehicular, 
                volumenVehicular, 
                varianzaVehicular, 
                chanceGeneracionEmergencia, 
                volumenEmergencia, 
                varianzaEmergencia, 
                timestamp,
                socket,
                congestion):
        timestampAntes = self.timestampPrevio
        timestampDespues = timestamp
        diferenciaTimestamps = devolverDiferenciaTimestampsEnSegundos(timestampAntes, timestampDespues)

        if diferenciaTimestamps > self.intervaloDeTiempo:
            print(f"timestamp previo: {self.timestampPrevio} | timestampEnvio: {self.timeStampEnvio} | timestampDespues: {timestampDespues}")
            self.timestampPrevio = timestampAntes
            self.timeStampEnvio = timestampDespues
            
            if congestion:
                self.vehiculosContados = 30
                socket.send_string(self.crearJSON())
                print(f"Evento generado por espira {self.idSensor}")
                self.timestampPrevio = timestampDespues
                return 

            print(f"Volumen vehicular: {volumenVehicular*3}")
            sumador = random.randint(1, math.floor(volumenVehicular*3))
            self.vehiculosContados = sumador

            socket.send_string(self.crearJSON())
            print(f"Evento generado por espira {self.idSensor}")
            self.timestampPrevio = timestampDespues

if __name__ == "__main__":
    txtCondicionesTrafico = leer_archivo_a_string("condicionesTrafico.txt")
    condicionesTrafico = eliminar_caracter(txtCondicionesTrafico, saltoLinea)
    listaCondicionesTrafico = separar_por_caracter(condicionesTrafico, ";")

    chanceGeneracionVehicular = float(listaCondicionesTrafico[0])
    volumenVehicular = float(listaCondicionesTrafico[1])
    desviacionVehicular = float(listaCondicionesTrafico[2])
    chanceGeneracionEmergencia = float(listaCondicionesTrafico[3])
    volumenEmergencia = float(listaCondicionesTrafico[4])
    desviacionEmergencia = float(listaCondicionesTrafico[5])

    socket = crearSocketPublicador(5553)

    contenidoArchivoSensores = leer_archivo_a_string("inicializacionSensores.txt")
    lineasSensores = separar_por_caracter(contenidoArchivoSensores, saltoLinea)

    hilos = []
    timestampInicio = datetime.now()

    for linea in lineasSensores:
        if not linea.strip():
            continue
        especificaciones = separar_por_caracter(linea, ";")
        if len(especificaciones) == 5:
            id_sensor, tipo_sensor, interseccion, intervalo_de_tiempo, tiempo_loop = (
                especificaciones[0], especificaciones[1], especificaciones[2], especificaciones[3], especificaciones[4]
            )
            espira_instance = Espira(id_sensor, tipo_sensor, interseccion, timestampInicio, intervalo_de_tiempo)
            
            hilo = threading.Thread(target=funcionCiclica, args=(
                espira_instance, tiempo_loop, timestampInicio, 21,
                chanceGeneracionVehicular, volumenVehicular, desviacionVehicular,
                chanceGeneracionEmergencia, volumenEmergencia, desviacionEmergencia, socket
            ))
            hilo.daemon = True
            hilo.start()
            hilos.append(hilo)

    for hilo in hilos:
        hilo.join()

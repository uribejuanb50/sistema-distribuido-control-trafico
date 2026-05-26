import json
import random
from datetime import datetime
import threading
from sensor import (Sensor, funcionCiclica, leer_archivo_a_string, eliminar_caracter, 
                    separar_por_caracter, crearSocketPublicador, postVarianza, evaluarProbabilidad, 
                    saltoLinea, serviciosEmergencia)

class Camara(Sensor):
    def __init__(self, idSensor, tipoSensor, interseccion): 
        super().__init__(idSensor, tipoSensor)
        self.interseccion = interseccion
        self.volumenVehicular = 0
        self.velocidadPromedio = 0
        self.emergencia = False
        self.nombreEmergencia = "-"

    def informacionSensor(self):
        stringRetorno = super().informacionSensor()
        stringRetorno += f"volumenVehicular: {self.volumenVehicular}" + saltoLinea
        stringRetorno += f"velocidadPromedio: {self.velocidadPromedio}" + saltoLinea
        stringRetorno += f"emergencia: {self.emergencia}" + saltoLinea
        stringRetorno += f"nombreEmergencia: {self.nombreEmergencia}" + saltoLinea
        return stringRetorno

    def crearJSON(self):
        return json.dumps({
            "sensor_id": f"CAM-{self.idSensor}",
            "tipo_sensor": "camara",
            "timestamp": str(self.timeStampEnvio),
            "interseccion": self.interseccion,
            "volumen": self.volumenVehicular,
            "velocidad_promedio": self.velocidadPromedio,
            "emergencia": self.emergencia,
            "nombre_emergencia": self.nombreEmergencia
        })

    def reiniciarSensor(self):
        super().reiniciarSensor()
        self.volumenVehicular = 0
        self.velocidadPromedio = 0
        self.emergencia = False
        self.nombreEmergencia = "-"

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
        if congestion:
            self.timeStampEnvio = timestamp
            self.volumenVehicular = 45
            self.velocidadPromedio = super().calcularVelocidad(self.volumenVehicular, 1)

            if evaluarProbabilidad(chanceGeneracionEmergencia):
                self.emergencia = True 
                self.nombreEmergencia = random.choice(serviciosEmergencia)
            else:
                self.emergencia = False
                self.nombreEmergencia = ""

            socket.send_string(self.crearJSON())
            print(f"Evento generado por camara {self.idSensor}")

        elif evaluarProbabilidad(chanceGeneracionVehicular):
            self.timeStampEnvio = timestamp
            nVehiculos = postVarianza(volumenVehicular, varianzaVehicular)
            self.volumenVehicular = nVehiculos
            self.velocidadPromedio = super().calcularVelocidad(nVehiculos, varianzaVehicular)

            if evaluarProbabilidad(chanceGeneracionEmergencia):
                self.emergencia = True 
                self.nombreEmergencia = random.choice(serviciosEmergencia)
            else:
                self.emergencia = False
                self.nombreEmergencia = ""

            socket.send_string(self.crearJSON())
            print(f"Evento generado por camara {self.idSensor}")

        else:
            self.reiniciarSensor()

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

    socket = crearSocketPublicador(5552)

    contenidoArchivoSensores = leer_archivo_a_string("inicializacionSensores.txt")
    lineasSensores = separar_por_caracter(contenidoArchivoSensores, saltoLinea)

    hilos = []
    timestampInicio = datetime.now()

    for linea in lineasSensores:
        if not linea.strip():
            continue
        especificaciones = separar_por_caracter(linea, ";")
        if len(especificaciones) == 4:
            id_sensor, tipo_sensor, interseccion, tiempo_loop = especificaciones[0], especificaciones[1], especificaciones[2], especificaciones[3]
            camara_instance = Camara(id_sensor, tipo_sensor, interseccion)
            
            hilo = threading.Thread(target=funcionCiclica, args=(
                camara_instance, tiempo_loop, timestampInicio, 21,
                chanceGeneracionVehicular, volumenVehicular, desviacionVehicular,
                chanceGeneracionEmergencia, volumenEmergencia, desviacionEmergencia, socket
            ))
            hilo.daemon = True
            hilo.start()
            hilos.append(hilo)

    for hilo in hilos:
        hilo.join()

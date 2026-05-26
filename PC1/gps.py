import json
from datetime import datetime
import threading
from sensor import (Sensor, funcionCiclica, leer_archivo_a_string, eliminar_caracter, 
                    separar_por_caracter, crearSocketPublicador, postVarianza, evaluarProbabilidad, saltoLinea)

class Gps(Sensor): 
    def __init__(self, idSensor, tipoSensor):
        super().__init__(idSensor, tipoSensor)
        self.nivelCongestion = "Nula"
        self.velocidadVehicular = 0

    def informacionSensor(self):
        stringRetorno = super().informacionSensor()
        stringRetorno += f"nivelCongestion: {self.nivelCongestion}" + saltoLinea
        stringRetorno += f"velocidadVehicular: {self.velocidadVehicular}" + saltoLinea
        return stringRetorno

    def reiniciarSensor(self):
        super().reiniciarSensor()
        self.nivelCongestion = "Nula"
        self.velocidadVehicular = 0

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
            self.nivelCongestion = "Alta"
            self.velocidadVehicular = postVarianza(5, 2)
            socket.send_string(self.crearJSON())
        elif evaluarProbabilidad(chanceGeneracionVehicular):
            self.timeStampEnvio = timestamp
            nVehiculos = postVarianza(volumenVehicular, varianzaVehicular)
            velocidadPromedio = super().calcularVelocidad(nVehiculos, varianzaVehicular)
            self.velocidadVehicular = velocidadPromedio
            print("Velocidad promedio:")
            print(velocidadPromedio)
            if velocidadPromedio >= 70:
                self.nivelCongestion = "Nula"
            elif velocidadPromedio >= 50:
                self.nivelCongestion = "Baja"
            elif velocidadPromedio >= 30:
                self.nivelCongestion = "Mdia"
            elif velocidadPromedio >= 10:
                self.nivelCongestion = "Alta"

            socket.send_string(self.crearJSON())
        else:
            self.reiniciarSensor()

        print(f"Evento generado por GPS {self.idSensor}")

    def crearJSON(self):
        return json.dumps({
            "sensor_id": f"GPS-{self.idSensor}",
            "tipo_sensor": "gps",
            "timestamp": str(self.timeStampEnvio),
            "nivel_congestion": self.nivelCongestion,
            "velocidad_promedio": self.velocidadVehicular
        })

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

    socket = crearSocketPublicador(5551)

    contenidoArchivoSensores = leer_archivo_a_string("inicializacionSensores.txt")
    lineasSensores = separar_por_caracter(contenidoArchivoSensores, saltoLinea)

    hilos = []
    timestampInicio = datetime.now()

    for linea in lineasSensores:
        if not linea.strip():
            continue
        especificaciones = separar_por_caracter(linea, ";")
        if len(especificaciones) == 3:
            id_sensor, tipo_sensor, tiempo_loop = especificaciones[0], especificaciones[1], especificaciones[2]
            gps_instance = Gps(id_sensor, tipo_sensor)
            
            hilo = threading.Thread(target=funcionCiclica, args=(
                gps_instance, tiempo_loop, timestampInicio, 21,
                chanceGeneracionVehicular, volumenVehicular, desviacionVehicular,
                chanceGeneracionEmergencia, volumenEmergencia, desviacionEmergencia, socket
            ))
            hilo.daemon = True
            hilo.start()
            hilos.append(hilo)

    for hilo in hilos:
        hilo.join()

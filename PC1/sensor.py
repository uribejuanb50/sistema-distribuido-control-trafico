from abc import ABC, abstractmethod
import random
from datetime import datetime
import time
import zmq

saltoLinea = "\n"
serviciosEmergencia = ["Ambulacia", "Policia", "Bomberos"]

class Sensor(ABC):
    def __init__(self, idSensor, tipoSensor):
        self.idSensor = idSensor
        self.tipoSensor = tipoSensor
        self.timeStampEnvio = ""
    
    def informacionSensor(self):
        stringRetorno = f"idSensor: {self.idSensor}" + saltoLinea
        stringRetorno += f"tipoSensor: {self.tipoSensor}" + saltoLinea
        stringRetorno += f"timeStampEnvío: {self.timeStampEnvio}" + saltoLinea
        return stringRetorno
    
    def reiniciarSensor(self):
        self.timeStampEnvio = "no registra"

    def calcularVelocidad(self, numeroVehicular, varianzaVehicular):
        print("Numero vehicular: ")
        print(numeroVehicular)

        if numeroVehicular > 30:
            return postVarianza(10, varianzaVehicular)
        if numeroVehicular > 20:
            return postVarianza(30, varianzaVehicular)
        if numeroVehicular > 10:
            return postVarianza(50, varianzaVehicular)
        if numeroVehicular >= 0:
            return postVarianza(70, varianzaVehicular)
        return 70

    @abstractmethod 
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
        pass

    @abstractmethod
    def crearJSON(self):
        pass

def separar_por_caracter(texto, caracter):
    return texto.split(caracter)

def eliminar_caracter(texto, caracter):
    return texto.replace(caracter, '')

def leer_archivo_a_string(archivo_txt):
    with open(archivo_txt, 'r', encoding='utf-8') as f:
        contenido = f.read()
    return contenido

def evaluarProbabilidad(probabilidad):
    return random.randint(1, 100) <= probabilidad

def postVarianza(numero, varianza):
    if evaluarProbabilidad(50):
        return int(numero) - random.randint(0, int(varianza))
    else:
        return int(numero) + random.randint(0, int(varianza))
    
def devolverDiferenciaTimestampsEnSegundos(timestamp1, timestamp2):
    diferencia = timestamp2 - timestamp1
    return abs(diferencia.total_seconds())

def crearSocketPublicador(puerto=5553):
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.connect(f"tcp://localhost:{puerto}")
    print(f"Conectado al broker en tcp://localhost:{puerto}. Esperando estabilización...")
    time.sleep(2)
    return socket

def funcionCiclica(sensor: Sensor, 
                    tiempo: int, 
                    timestampInicio, 
                    segundoCambio,
                    chanceGeneracionVehicular,
                    volumenVehicular,
                    desviacionVehicular,
                    chanceGeneracionEmergencia,
                    volumenEmergencia,
                    desviacionEmergencia,
                    socket):
    while True:
        try:
            timestampActual = datetime.now()
            segundoActual = devolverDiferenciaTimestampsEnSegundos(timestampInicio, timestampActual)
            congestion = float(segundoActual) > float(segundoCambio)

            if congestion:
                print(f"[{sensor.tipoSensor} {sensor.idSensor}] Entró en congestión")
            else:
                print(f"[{sensor.tipoSensor} {sensor.idSensor}] Entró en tráfico normal")
            
            time.sleep(float(tiempo))
            sensor.simular(chanceGeneracionVehicular, volumenVehicular, desviacionVehicular, 
                           chanceGeneracionEmergencia, volumenEmergencia, desviacionEmergencia, 
                           timestampActual, socket, congestion)
        except Exception as e:
            print(f"Error en funcionCiclica para {sensor.tipoSensor} {sensor.idSensor}: {type(e).__name__} - {e}")
            return

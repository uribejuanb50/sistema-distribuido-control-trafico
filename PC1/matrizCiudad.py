from abc import ABC, abstractmethod
import random
from datetime import datetime
import math
import time
import threading
import zmq
import json


saltoLinea = "\n"
relojTiempo = 0

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

    #devuelve una velocidad hipotetica basada en el número de vehiculos
    def calcularVelocidad(self, numeroVehicular, varianzaVehicular):

        print("Numero vehicular: ")
        print(numeroVehicular)

        if(numeroVehicular > 30):
            return postVarianza(10, varianzaVehicular)

        if(numeroVehicular > 20):
            return postVarianza(30, varianzaVehicular)
        
        if(numeroVehicular > 10):
            return postVarianza(50, varianzaVehicular)
        
        if(numeroVehicular >= 0):
            return postVarianza(70, varianzaVehicular)

    @abstractmethod 
    def simular(self,
                chanceGeneracionVehicular, 
                volumenVehicular, 
                varianzaVehicular, 
                chanceGeneracionEmergencia, 
                volumenEmergencia, 
                varianzaEmergencia,
                timestamp,
                socket):
        pass

    @abstractmethod
    def crearJSON():
         pass
    
class Gps(Sensor) : 
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
        if(congestion) :
            self.nivelCongestion = "Alta"
            self.velocidadVehicular = postVarianza(5, 2)

            socket.send_string(self.crearJSON())
        
        elif(evaluarProbabilidad(chanceGeneracionVehicular)):
            self.timeStampEnvio = timestamp
            
            nVehiculos = postVarianza(volumenVehicular, varianzaVehicular)

            velocidadPromedio = super().calcularVelocidad(nVehiculos, varianzaVehicular)
            self.velocidadVehicular = velocidadPromedio
            print("Velocidad promedio:")
            print(velocidadPromedio)
            if(velocidadPromedio >= 70) :
                self.nivelCongestion = "Nula"
            elif(velocidadPromedio >= 50):
                self.nivelCongestion = "Baja"
            elif(velocidadPromedio >= 30) :
                self.nivelCongestion = "Mdia"
            elif(velocidadPromedio >= 10) :
                self.nivelCongestion = "Alta"

            socket.send_string(self.crearJSON())
            
        else:
            self.reiniciarSensor()

        print("Evento generado por GPS")

    def crearJSON(self):
        return json.dumps({
            "sensor_id": self.idSensor,
            "tipo_sensor": self.tipoSensor,
            "timestamp": str(self.timeStampEnvio),
            "nivel_congestion": self.nivelCongestion,
            "velocidad_promedio": self.velocidadVehicular
        })

class Camara(Sensor) :
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
        stringRetorno += f"emergecia: {self.emergencia}" + saltoLinea
        stringRetorno += f"nombreEmergencia: {self.nombreEmergencia}" + saltoLinea

        return stringRetorno

    def crearJSON(self):
        return json.dumps({
            "sensor_id": self.idSensor,
            "tipo_sensor": self.tipoSensor,
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
        if(congestion):
            self.timeStampEnvio = timestamp
            self.volumenVehicular = 45
            self.velocidadPromedio = super().calcularVelocidad(self.volumenVehicular, 1)

            if(evaluarProbabilidad(chanceGeneracionEmergencia)):
                self.emergencia = True 
                self.nombreEmergencia = random.choice(serviciosEmergencia)


            else:
                self.emergencia = False
                self.nombreEmergencia = ""

            socket.send_string(self.crearJSON())
            print("Evento generado por camara")

        elif(evaluarProbabilidad(chanceGeneracionVehicular)):
            self.timeStampEnvio = timestamp

            nVehiculos = postVarianza(volumenVehicular, varianzaVehicular)
            self.volumenVehicular = nVehiculos

            self.velocidadPromedio = super().calcularVelocidad(nVehiculos, varianzaVehicular)

            if(evaluarProbabilidad(chanceGeneracionEmergencia)):
                self.emergencia = True 
                self.nombreEmergencia = random.choice(serviciosEmergencia)


            else:
                self.emergencia = False
                self.nombreEmergencia = ""

            socket.send_string(self.crearJSON())
            print("Evento generado por camara")

        else:
            self.reiniciarSensor()
    
class Espira(Sensor):
    def __init__ (self, idSensor, tipoSensor, interseccion, timestamp, intervaloDeTiempo):
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
            "sensor_id": self.idSensor,
            "tipo_sensor": self.tipoSensor,
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

        #print(f"Diferencia: {diferenciaTimestamps} > intervalo tiempo: {self.intervaloDeTiempo}  = {diferenciaTimestamps > self.intervaloDeTiempo}")

        if(diferenciaTimestamps > self.intervaloDeTiempo) :

            
            print(f"timestamp previo: {self.timestampPrevio} | timestampEnvio: {self.timeStampEnvio} | timestampDespues: {timestampDespues}")
            self.timestampPrevio = timestampAntes
            self.timeStampEnvio = timestampDespues
            
            if(congestion):
                self.vehiculosContados = 30
                socket.send_string(self.crearJSON())

                print("Evento generado por espira")

                self.timestampPrevio = timestampDespues

                return 

            print(f"Volumen vehicual: {volumenVehicular*3}")
            sumador = random.randint(1, math.floor(volumenVehicular*3))
            self.vehiculosContados = sumador

            #Envio
            socket.send_string(self.crearJSON())
            print("Evento generado por espira")

            self.timestampPrevio = timestampDespues

            
            pass
        else:
            pass
        
        

class Semaforo:
    def __init__(self, idSemaforo, fila, columna, tiempoCambio, timestamp):
        self.idSemaforo = idSemaforo
        self.fila = fila
        self.columna = columna
        self.enVerde = True
        self.tiempoCambio = tiempoCambio
        self.timestampInicio = timestamp
        self.timestampFinal = "-"

    def informacionSemaforo(self):
        stringRetorno = f"ID semafor: {self.idSemaforo}" + saltoLinea
        stringRetorno += f"fila: {self.fila} | columna: {self.columna}" + saltoLinea
        stringRetorno += f"Semaforo en verde: {self.enVerde}" + saltoLinea
        stringRetorno += f"Tiempo cambio: {self.tiempoCambio}" + saltoLinea
        stringRetorno += f"Inicio cambio: {self.timestampInicio}" + saltoLinea
        stringRetorno += f"Final cambio : {self.timestampFinal}" + saltoLinea

        return stringRetorno

    def cambiarLuz(self, instruccion):
        self.enVerde = not self.enVerde
        print(instruccion)
        print(f"esta en verde actualmente? {self.enVerde}")

    def simular(self, timestamp):
        
        if(devolverDiferenciaTimestampsEnSegundos(self.timestampInicio, timestamp) > self.tiempoCambio):
            self.timestampFinal = timestamp
            self.cambiarLuz(f"Cambio de luz por intervalo cumplido")

            #envio

            self.timestampInicio = timestamp
        
        else:
            pass

class ManejoSemaforos:
    def __init__(self):
        self.listaSensores: list[Sensor] = []
        self.listaSemaforos: list[Semaforo] = []
        self.listaTiempos: list[int] = []

    def agregarSensor(self, sensor : Sensor):
        self.listaSensores.append(sensor)

    def agregarSemaforo(self, semaforo : Semaforo):
        self.listaSemaforos.append(semaforo)

    def agregarTiempo(self, tiempo : int):
        self.listaTiempos.append(tiempo)

    def informacionManejoSemaforos(self) :
        
        stringRetorno = "==========================================" + saltoLinea
        stringRetorno += "Informacion de los sensores:" + saltoLinea
        
        for s in self.listaSensores :
            stringRetorno += s.informacionSensor()

        stringRetorno += "-----------------------------------------" + saltoLinea

        for s in self.listaSemaforos :
            stringRetorno += s.informacionSemaforo()

        stringRetorno += "-----------------------------------------" + saltoLinea

        for t in self.listaTiempos:
            stringRetorno += str(t) + ", "

        stringRetorno +=saltoLinea
        stringRetorno += "==========================================" + saltoLinea

        return stringRetorno

    def levantarSistemas(self):
        contenidoArchivoSensores = leer_archivo_a_string("inicializacionSensores.txt")

        sensores = separar_por_caracter(contenidoArchivoSensores, saltoLinea)

        timestamp = datetime.now()

        for sensor in sensores :

            especificaciones = separar_por_caracter(sensor, ";")

            if(len(especificaciones) == 3):
                gps : Sensor = Gps(especificaciones[0], especificaciones[1])
                self.agregarSensor(gps)
                self.agregarTiempo(especificaciones[2])

            elif(len(especificaciones) == 4):
                camara : Sensor = Camara(especificaciones[0], especificaciones[1], especificaciones[2])
                self.agregarSensor(camara)
                self.agregarTiempo(especificaciones[3])

            elif(len(especificaciones) == 5) :
                espira : Sensor = Espira(especificaciones[0], especificaciones[1], especificaciones[2], timestamp, especificaciones[3] )
                self.agregarSensor(espira)
                self.agregarTiempo(especificaciones[4])

        contenidoArchivoSemaforos = leer_archivo_a_string("inicializacionSemaforos.txt")

        semaforos = separar_por_caracter(contenidoArchivoSemaforos, saltoLinea)

        for semaforo in semaforos :
            
            especificaciones = separar_por_caracter(semaforo, ";")
            
            semaforo : Semaforo = Semaforo(especificaciones[0], especificaciones[1], especificaciones[2], especificaciones[3], timestamp)
            self.agregarSemaforo(semaforo)

        print("Salió levantar sistemas")

    
    
    def lanzarHilos(self, 
                    chanceGeneracionVehicular,
                    volumenVehicular,
                    desviacionVehicular,
                    chanceGeneracionEmergencia,
                    volumenEmergencia,
                    desviacionEmergencia):

        hilos = []

        timestampInicio = datetime.now()

        socket = crearSocketPublicador()

        for i in range(len(self.listaSensores)):
            hilo = threading.Thread(target=funcionCiclica, args= (self.listaSensores[i], 
                                                                  self.listaTiempos[i], 
                                                                  timestampInicio, 
                                                                  21,
                                                                  chanceGeneracionVehicular,
                                                                  volumenVehicular,
                                                                  desviacionVehicular,
                                                                  chanceGeneracionEmergencia,
                                                                  volumenEmergencia,
                                                                  desviacionEmergencia,
                                                                  socket
                                                                  ))
            hilo.daemon = True
            hilo.start()
            hilos.append(hilo)

        
        for hilo in hilos:
            hilo.join()

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
                    socket
                    ):
    
    #print("Valores de llegada")print("Informacion sensor")print(sensor.informacionSensor())print(f"tiempo: {tiempo} | tiempoInicio: {timestampInicio} | segundoCambio: {segundoCambio} | chanceGeneracion {chanceGeneracionVehicular}")print(f"volumenVehicular {volumenVehicular} | desviacionVehicular: {desviacionVehicular} | chanceGeneracionEmergencia: {chanceGeneracionEmergencia}")print(f"volumenEmergencia: {volumenEmergencia} | desviacionVehicular: {desviacionVehicular}")
    while True:
        try:
            timestampActual = datetime.now()

            segundoActual = devolverDiferenciaTimestampsEnSegundos(timestampInicio, timestampActual)

            congestion = float(segundoActual) > float(segundoCambio)

            if congestion:
                print("Entró en congestión")
            else:
                print("Entro en trafico normal")
            
            time.sleep(float(tiempo))

            sensor.simular(chanceGeneracionVehicular,volumenVehicular, desviacionVehicular, chanceGeneracionEmergencia, volumenEmergencia, desviacionEmergencia, timestampActual, socket, congestion)

            #print(f"segundoActual: {segundoActual} | segundoCambio {segundoCambio} comparativa: {float(segundoActual) > float(segundoCambio)}")

        except Exception as e:
            print(f"Error en funcionCiclica: {type(e).__name__} - {e}")
            return

#retorna una lista de strings a partir de un string seperado por x caracter
def separar_por_caracter(texto, caracter):
    textoRetornar = texto.split(caracter)
    return textoRetornar

def eliminar_caracter(texto, caracter):
    """
    Recibe un string y un caracter a quitar, retorna el string sin ese caracter
    
    Parámetros:
    texto: str - el string original
    caracter: str - el caracter a eliminar (puede ser espacio, salto de línea, etc.)
    
    Retorna:
    str - el string sin el caracter especificado
    """
    return texto.replace(caracter, '')

def leer_archivo_a_string(archivo_txt):
    """
    Lee un archivo .txt y devuelve su contenido como un string
    """
    with open(archivo_txt, 'r', encoding='utf-8') as f:
        contenido = f.read()
    return contenido

def evaluarProbabilidad(probabilidad):
    return random.randint(1,100) <= probabilidad

def postVarianza(numero, varianza) :

    if(evaluarProbabilidad(50)):
        return numero - random.randint(0, varianza)
    else:
        return numero + random.randint(0, varianza)
    
def devolverDiferenciaTimestampsEnSegundos(timestamp1, timestamp2):
    #print(f"Contenido timestamp1: {timestamp1} | timestamp2: {timestamp2}")
    diferencia = timestamp2 - timestamp1

    #print(f"Diferencia: {diferencia.total_seconds()}")
    return abs(diferencia.total_seconds())

def crearSocketPublicador(puerto = 5551):

    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.connect(f"tcp://localhost:{puerto}")

    print("Esperando al socket")

    time.sleep(2)

    return socket

# Uso


txtCondicionesTrafico = leer_archivo_a_string("condicionesTrafico.txt")

condicionesTrafico = eliminar_caracter(txtCondicionesTrafico, saltoLinea)

listaCondicionesTrafico = separar_por_caracter(condicionesTrafico, ";")

"""
socketiii = crearSocketPublicador(5555)

print(listaCondicionesTrafico)

gps : Sensor = Gps(1, "GPS1")

gps.simular(100, 70, 2, 0, 0, 0, datetime.now(), socketiii)

print(gps.informacionSensor())

camara : Sensor = Camara(2, "Camara", "INT_C5")
camara.simular(100, 70, 2, 100, 2, 0, datetime.now(), socketiii)

print(camara.informacionSensor())

espira : Sensor = Espira(3, "Espira-tec", "INT_T5", datetime.now(), 5)

#while True:    espira.simular(100,40,23,0, 0, 12, datetime.now(), socketiii)

#while True:   semaforo.simular(datetime.now())
"""
manejoSemaforos : ManejoSemaforos = ManejoSemaforos()
manejoSemaforos.levantarSistemas()
manejoSemaforos.lanzarHilos(float(listaCondicionesTrafico[0]), 
                            float(listaCondicionesTrafico[1]),
                            float(listaCondicionesTrafico[2]),
                            float(listaCondicionesTrafico[3]),
                            float(listaCondicionesTrafico[4]),
                            float(listaCondicionesTrafico[5]))


import zmq
import json
import time
from datetime import datetime

saltoLinea = "\n"

def devolverDiferenciaTimestampsEnSegundos(timestamp1, timestamp2):
    return abs((timestamp1 - timestamp2).total_seconds())

class Semaforo:
    def __init__(self, idSemaforo, interseccion, tiempoCambioOriginal, timestamp, enVerde):
        self.idSemaforo = idSemaforo
        self.interseccion = interseccion
        self.enVerde = enVerde
        self.tiempoCambioOriginal = float(tiempoCambioOriginal)
        self.tiempoCambioAuxiliar = float(tiempoCambioOriginal)
        self.timestampInicio = timestamp
        self.timestampFinal = "-"

    def informacionSemaforo(self):
        stringRetorno  = f"ID semaforo: {self.idSemaforo}" + saltoLinea
        stringRetorno += f"En verde: {self.enVerde}" + saltoLinea
        stringRetorno += f"Tiempo original: {self.tiempoCambioOriginal}s" + saltoLinea
        stringRetorno += f"Tiempo auxiliar: {self.tiempoCambioAuxiliar}s" + saltoLinea
        return stringRetorno

    def cambiarLuz(self):
        self.enVerde = not self.enVerde

        estado = "VERDE" if self.enVerde else "ROJO"
        estado1 = "ROJO" if self.enVerde else "VERDE"
        
        print(f"[Semaforo {self.idSemaforo}] Cambió a {estado} | desde {estado1}")

    def extenderTiempo(self, tiempoExtendido: float):
        self.tiempoCambioAuxiliar = max(self.tiempoCambioAuxiliar, tiempoExtendido)
        print(f"[Semaforo {self.idSemaforo}] Tiempo extendido a {self.tiempoCambioAuxiliar}s")

class GestorSemaforos:
    def __init__(self):
        timestamp = datetime.now()
        self.semaforoC = Semaforo("SEM_C", "C", 2, timestamp, True)
        self.semaforoF = Semaforo("SEM_F", "F", 2, timestamp, False)

    def procesarComando(self, comando: dict):
        """Recibe un comando del analítico y extiende el tiempo del semáforo indicado"""

        print(comando)
        
        fila = comando.get("fila", "C")
        tiempo = float(comando.get("tiempoExtendido", 10))
        motivo = comando.get("motivo", "")

        if fila == self.semaforoC.interseccion:
            self.semaforoC.extenderTiempo(tiempo)
            print(f"[Control] Comando aplicado a SEM_C | motivo: {motivo}")
        else:
            self.semaforoF.extenderTiempo(tiempo)
            print(f"[Control] Comando aplicado a SEM_F | motivo: {motivo}")

    def simular(self):
        timestamp = datetime.now()

        if self.semaforoC.enVerde:
            diferencia = devolverDiferenciaTimestampsEnSegundos(
                self.semaforoC.timestampInicio, timestamp)
            if diferencia > self.semaforoC.tiempoCambioAuxiliar:
                self.semaforoC.timestampFinal = timestamp
                self.semaforoC.cambiarLuz()
                self.semaforoC.timestampInicio = timestamp
                self.semaforoC.tiempoCambioAuxiliar = self.semaforoC.tiempoCambioOriginal
                self.semaforoC.enVerde = False
                self.semaforoF.enVerde = True
                self.semaforoF.timestampInicio = timestamp
        else:
            diferencia = devolverDiferenciaTimestampsEnSegundos(
                self.semaforoF.timestampInicio, timestamp)
            if diferencia > self.semaforoF.tiempoCambioAuxiliar:
                self.semaforoF.timestampFinal = timestamp
                self.semaforoF.cambiarLuz()
                self.semaforoF.timestampInicio = timestamp
                self.semaforoF.tiempoCambioAuxiliar = self.semaforoF.tiempoCambioOriginal
                self.semaforoF.enVerde = False
                self.semaforoC.enVerde = True
                self.semaforoC.timestampInicio = timestamp

def crearSocketPull(puerto):
    """Crea socket PULL para recibir comandos del analítico"""
    context = zmq.Context()
    socket = context.socket(zmq.PULL)
    #socket.connect(f"tcp://localhost:{puerto}")
    socket.bind(f"tcp://0.0.0.0:{puerto}")
    socket.setsockopt(zmq.RCVTIMEO, 100)
    
    return socket

def main():
    socketComandos = crearSocketPull(6000)
    socketComandos.setsockopt(zmq.RCVTIMEO, 100)  # espera max 100ms por mensaje

    gestor = GestorSemaforos()
    print("[Control Semáforos] Corriendo...")

    while True:
        try:
            # Intenta recibir un comando sin bloquearse
            try:
                mensaje = socketComandos.recv_string()
                comando = json.loads(mensaje)
                print(f"[Control] Comando recibido: {comando}")
                gestor.procesarComando(comando)
            except zmq.Again:
                pass  # no había mensaje, sigue simulando

            gestor.simular()
            time.sleep(1)

        except Exception as e:
            print(f"[Error controlSemaforos] {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
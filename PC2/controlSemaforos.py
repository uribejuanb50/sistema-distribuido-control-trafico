# controlSemaforos.py  (PC2)
# - Recibe comandos PUSH/PULL desde analitica en el puerto 6000.
# - Comandos normales: extienden el tiempo del semáforo correspondiente.
# - Comandos "forzar": fuerzan el estado (verde la fila pedida, rojo la otra).
#   Sirven para ola verde / paso de ambulancia y para cambios manuales.
# - "RESET_NORMAL": vuelve al ciclo base.

import zmq
import json
import time
from datetime import datetime

saltoLinea = "\n"


def devolverDiferenciaTimestampsEnSegundos(t1, t2):
    return abs((t1 - t2).total_seconds())


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
        s  = f"ID semaforo: {self.idSemaforo}" + saltoLinea
        s += f"En verde: {self.enVerde}" + saltoLinea
        s += f"Tiempo original: {self.tiempoCambioOriginal}s" + saltoLinea
        s += f"Tiempo auxiliar: {self.tiempoCambioAuxiliar}s" + saltoLinea
        return s

    def cambiarLuz(self):
        self.enVerde = not self.enVerde
        estado  = "VERDE" if self.enVerde else "ROJO"
        estado1 = "ROJO" if self.enVerde else "VERDE"
        print(f"[Semaforo {self.idSemaforo}] Cambió a {estado} | desde {estado1}")

    def extenderTiempo(self, tiempoExtendido):
        self.tiempoCambioAuxiliar = max(self.tiempoCambioAuxiliar, float(tiempoExtendido))
        print(f"[Semaforo {self.idSemaforo}] Tiempo extendido a {self.tiempoCambioAuxiliar}s")


class GestorSemaforos:
    def __init__(self):
        timestamp = datetime.now()
        # Tiempo base 15s (lo que dice el enunciado para tráfico normal)
        self.semaforoC = Semaforo("SEM_C", "C", 15, timestamp, True)
        self.semaforoF = Semaforo("SEM_F", "F", 15, timestamp, False)
        self.modoAmbulancia = False

    def _forzarEstado(self, filaVerde, tiempo, motivo):
        """Pone filaVerde en verde, la otra en rojo, y extiende tiempo."""
        timestamp = datetime.now()

        if filaVerde == "C":
            if not self.semaforoC.enVerde:
                self.semaforoC.cambiarLuz()
            if self.semaforoF.enVerde:
                self.semaforoF.cambiarLuz()
            self.semaforoC.timestampInicio = timestamp
            self.semaforoF.timestampInicio = timestamp
            self.semaforoC.extenderTiempo(tiempo)
        else:  # F
            if not self.semaforoF.enVerde:
                self.semaforoF.cambiarLuz()
            if self.semaforoC.enVerde:
                self.semaforoC.cambiarLuz()
            self.semaforoC.timestampInicio = timestamp
            self.semaforoF.timestampInicio = timestamp
            self.semaforoF.extenderTiempo(tiempo)

        print(f"[Control] Estado FORZADO → fila {filaVerde} en verde | motivo: {motivo}")

    def procesarComando(self, comando):
        motivo = comando.get("motivo", "")

        # Reset al ciclo normal
        if motivo == "RESET_NORMAL":
            self.modoAmbulancia = False
            self.semaforoC.tiempoCambioAuxiliar = self.semaforoC.tiempoCambioOriginal
            self.semaforoF.tiempoCambioAuxiliar = self.semaforoF.tiempoCambioOriginal
            print("[Control] Reseteado al ciclo normal")
            return

        fila   = comando.get("fila", "C")
        tiempo = float(comando.get("tiempoExtendido", 10))
        forzar = comando.get("forzar", False)

        if forzar:
            self.modoAmbulancia = (motivo == "AMBULANCIA")
            self._forzarEstado(fila, tiempo, motivo)
            return

        # Comando normal: solo extiende
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
                self.semaforoC.timestampInicio, timestamp
            )
            if diferencia > self.semaforoC.tiempoCambioAuxiliar:
                self.semaforoC.timestampFinal = timestamp
                self.semaforoC.cambiarLuz()
                self.semaforoF.cambiarLuz()
                self.semaforoC.timestampInicio = timestamp
                self.semaforoF.timestampInicio = timestamp
                self.semaforoC.tiempoCambioAuxiliar = self.semaforoC.tiempoCambioOriginal
                if self.modoAmbulancia:
                    self.modoAmbulancia = False
                    print("[Control] Ola verde finalizada, vuelve al ciclo normal")
        else:
            diferencia = devolverDiferenciaTimestampsEnSegundos(
                self.semaforoF.timestampInicio, timestamp
            )
            if diferencia > self.semaforoF.tiempoCambioAuxiliar:
                self.semaforoF.timestampFinal = timestamp
                self.semaforoF.cambiarLuz()
                self.semaforoC.cambiarLuz()
                self.semaforoC.timestampInicio = timestamp
                self.semaforoF.timestampInicio = timestamp
                self.semaforoF.tiempoCambioAuxiliar = self.semaforoF.tiempoCambioOriginal
                if self.modoAmbulancia:
                    self.modoAmbulancia = False
                    print("[Control] Ola verde finalizada, vuelve al ciclo normal")


def crearSocketPull(context, puerto):
    socket = context.socket(zmq.PULL)
    socket.bind(f"tcp://0.0.0.0:{puerto}")
    socket.setsockopt(zmq.RCVTIMEO, 100)
    return socket


def main():
    context = zmq.Context()
    socketComandos = crearSocketPull(context, 6000)
    gestor = GestorSemaforos()
    print("[Control Semáforos] Corriendo en puerto 6000...")

    while True:
        try:
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
# broker.py  (PC1)
# Escucha tres puertos separados (uno por tipo de sensor) y reenvía todo al PC2.
#
# GPS     → publica en 5551
# Cámara  → publica en 5552
# Espira  → publica en 5553
# Broker  → reenvía hacia PC2 en 5555

import zmq

def main():
    context = zmq.Context()

    # ── Entradas: una por tipo de sensor ──────────────────────────────────
    gps = context.socket(zmq.SUB)
    gps.bind("tcp://0.0.0.0:5551")
    gps.setsockopt_string(zmq.SUBSCRIBE, "")

    camara = context.socket(zmq.SUB)
    camara.bind("tcp://0.0.0.0:5552")
    camara.setsockopt_string(zmq.SUBSCRIBE, "")

    espira = context.socket(zmq.SUB)
    espira.bind("tcp://0.0.0.0:5553")
    espira.setsockopt_string(zmq.SUBSCRIBE, "")

    # ── Salida: hacia analítica en PC2 ────────────────────────────────────
    salida = context.socket(zmq.PUB)
    salida.bind("tcp://0.0.0.0:5555")

    # Poller para escuchar los tres al mismo tiempo sin bloquearse
    poller = zmq.Poller()
    poller.register(gps,    zmq.POLLIN)
    poller.register(camara, zmq.POLLIN)
    poller.register(espira, zmq.POLLIN)

    print("[Broker] Corriendo")
    print("[Broker]   GPS    → :5551")
    print("[Broker]   Cámara → :5552")
    print("[Broker]   Espira → :5553")
    print("[Broker]   Salida → :5555 (PC2)")

    while True:
        try:
            eventos = dict(poller.poll())

            if gps in eventos:
                msg = gps.recv_string()
                print(f"[Broker][GPS]    {msg[:80]}...")
                salida.send_string(msg)

            if camara in eventos:
                msg = camara.recv_string()
                print(f"[Broker][Cámara] {msg[:80]}...")
                salida.send_string(msg)

            if espira in eventos:
                msg = espira.recv_string()
                print(f"[Broker][Espira] {msg[:80]}...")
                salida.send_string(msg)

        except Exception as e:
            print(f"[Error broker] {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
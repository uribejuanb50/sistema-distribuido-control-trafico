import zmq

def main():
    context = zmq.Context()

    # Recibe de los sensores (mismo PC)
    entrada = context.socket(zmq.SUB)
    entrada.bind("tcp://0.0.0.0:5554")
    entrada.setsockopt_string(zmq.SUBSCRIBE, "")

    # Publica hacia PC2
    salida = context.socket(zmq.PUB)
    salida.bind("tcp://0.0.0.0:5555")

    print("[Broker] Corriendo — recibe :5554, publica :5555")

    while True:
        mensaje = entrada.recv_string()
        print(f"[Broker] Reenviando: {mensaje[:80]}...")
        salida.send_string(mensaje)

if __name__ == "__main__":
    main()
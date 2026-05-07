import zmq
import json
from pymongo import MongoClient
from datetime import datetime

def conectarMongoDB(host="localhost", puerto=27017, nombreBD="trafico_principal"):
    cliente = MongoClient(f"mongodb://{host}:{puerto}/")
    print(f"[BD Principal] Conectado a {host}:{puerto} - BD: {nombreBD}")
    return cliente[nombreBD]

def main():
    context = zmq.Context()
    socket = context.socket(zmq.PULL)
    socket.bind("tcp://0.0.0.0:6002")

    bd = conectarMongoDB()
    print("[BD Principal] Esperando eventos...")

    while True:
        try:
            mensaje = socket.recv_string()
            evento = json.loads(mensaje)
            evento["timestamp_recepcion"] = str(datetime.now())
            resultado = bd["eventos"].insert_one(evento)
            print(f"[BD Principal] Guardado: {resultado.inserted_id}")
        except Exception as e:
            print(f"[Error bdReplica] {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
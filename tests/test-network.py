#!/usr/bin/env python3
import os
import time
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from network import EthernetSocket

def test_network_basic():
    # Configuración
    interface = "eth0"  # Cambia por tu interfaz de red (eth0, wlan0, etc.)
    
    try:
        # Crear socket
        sock = EthernetSocket(interface)
        print("Socket creado exitosamente")
        
        # Probar envío de broadcast
        test_data = b"Hola, esto es una prueba!"
        sock.send_frame("ff:ff:ff:ff:ff:ff", test_data)
        
        # Esperar y recibir posibles respuestas
        print("Esperando frames por 10 segundos...")
        start_time = time.time()
        while time.time() - start_time < 10:
            frame = sock.recv_frame(2)  # Timeout de 2 segundos
            if frame:
                print(f"Frame recibido de {frame['src_mac']}: {frame['data']}")
        
    except Exception as e:
        print(f"Error en prueba: {e}")
    finally:
        sock.close()
        print("Prueba completada")

if __name__ == "__main__":
    test_network_basic()
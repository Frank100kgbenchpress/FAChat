import socket
import struct
import fcntl
import os

class EthernetSocket:
    def __init__(self, interface, ethertype=0x8888):
        self.interface = interface
        self.ethertype = ethertype
        self.socket = None
        self.mac = self._get_mac_address()
        self._setup_socket()
    
    def _get_mac_address(self):
        """Obtiene la dirección MAC de la interfaz"""
        try:
            with open(f'/sys/class/net/{self.interface}/address') as f:
                return f.read().strip()
        except:
            return "00:00:00:00:00:00"  # Fallback
    
    def _setup_socket(self):
        """Configura el socket Ethernet raw"""
        try:
            # Crear socket raw Ethernet
            self.socket = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
            self.socket.bind((self.interface, 0))
            print(f"Socket configurado en interfaz {self.interface} con MAC {self.mac}")
        except Exception as e:
            print(f"Error configurando socket: {e}")
            raise
    
    def send_frame(self, dest_mac, data):
        """Envía un frame Ethernet"""
        try:
            # Convertir MAC addresses a bytes
            dest_mac_bytes = bytes.fromhex(dest_mac.replace(':', ''))
            src_mac_bytes = bytes.fromhex(self.mac.replace(':', ''))
            
            # Crear el frame Ethernet
            ethertype_bytes = struct.pack('>H', self.ethertype)
            frame = dest_mac_bytes + src_mac_bytes + ethertype_bytes + data
            
            # Enviar el frame
            self.socket.send(frame)
            print(f"Frame enviado a {dest_mac}")
            return True
        except Exception as e:
            print(f"Error enviando frame: {e}")
            return False
    
    def recv_frame(self, timeout=1):
        """Recibe frames Ethernet con timeout"""
        self.socket.settimeout(timeout)
        try:
            frame = self.socket.recv(4096)
            if len(frame) < 14:  # Tamaño mínimo del header Ethernet
                return None
            
            # Parsear el frame
            dest_mac = ':'.join(f'{b:02x}' for b in frame[0:6])
            src_mac = ':'.join(f'{b:02x}' for b in frame[6:12])
            ethertype = struct.unpack('>H', frame[12:14])[0]
            
            # Filtrar por nuestro ethertype personalizado
            if ethertype == self.ethertype:
                return {
                    'dest_mac': dest_mac,
                    'src_mac': src_mac,
                    'data': frame[14:]
                }
        except socket.timeout:
            pass
        except Exception as e:
            print(f"Error recibiendo frame: {e}")
        return None
    
    def close(self):
        """Cierra el socket"""
        if self.socket:
            self.socket.close()
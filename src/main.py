#!/usr/bin/env python3
"""
Main menu de LinkChat:
 - lista archivos desde una carpeta compartida (por defecto <repo_root>/LinkChatShared o override con LINKCHAT_SHARED_DIR)
 - copia el archivo seleccionado a <repo_root>/.tmp_send/ y lo envía desde ahí (evita problemas de permisos/mounts)
 - detecta automáticamente use_ack según la MAC destino (broadcast -> no ACK)
Ejecutar:
    sudo python3 src/main.py
"""

import os
import sys
import shutil
from pathlib import Path
from typing import List, Tuple

# Importar funcionalidades del proyecto
from chat import chat_mode
from files import send_file  # implementación de transferencia con/without ACK

# ---------- rutas ----------
def get_repo_root() -> str:
    this_dir = os.path.dirname(os.path.abspath(__file__))   # .../repo/src
    return os.path.abspath(os.path.join(this_dir, ".."))     # .../repo

REPO_ROOT = get_repo_root()

def get_shared_dir() -> str:
    # override por variable de entorno si el usuario lo define
    env = os.environ.get("LINKCHAT_SHARED_DIR")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    return os.path.join(REPO_ROOT, "LinkChatShared")

SHARED_DIR = get_shared_dir()
TMP_SEND_DIR = os.path.join(REPO_ROOT, ".tmp_send")   # donde copiamos antes de enviar

# MAC por defecto (broadcast)
DEFAULT_DEST_MAC = "ff:ff:ff:ff:ff:ff"

# ---------- utilidades ----------
def ensure_dirs():
    Path(SHARED_DIR).mkdir(parents=True, exist_ok=True)
    Path(TMP_SEND_DIR).mkdir(parents=True, exist_ok=True)

def human_size(n: int) -> str:
    for unit in ("B","KB","MB","GB"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024.0
    return f"{n:.1f}TB"

def list_shared_files() -> List[Tuple[str,int]]:
    files = []
    try:
        for entry in sorted(os.listdir(SHARED_DIR)):
            if entry.startswith("."):
                continue
            p = os.path.join(SHARED_DIR, entry)
            if os.path.isfile(p):
                files.append((entry, os.path.getsize(p)))
    except Exception as e:
        print("Error listando carpeta compartida:", e)
    return files

def ask_dest_mac() -> str:
    txt = input(f"MAC destino (vacío = broadcast {DEFAULT_DEST_MAC}): ").strip()
    if txt == "":
        return DEFAULT_DEST_MAC
    return txt

def _copy_to_tmp_and_prepare(src_path: str) -> str:
    """
    Copia src_path a TMP_SEND_DIR con un nombre seguro y devuelve la ruta destino.
    Si el archivo ya existe en tmp con el mismo contenido, reutiliza la copia.
    """
    abs_src = os.path.abspath(src_path)
    base = os.path.basename(abs_src)
    dest = os.path.join(TMP_SEND_DIR, base)

    # Si ya existe y el tamaño coincide, asumimos que es la misma copia y la reutilizamos.
    try:
        if os.path.exists(dest):
            if os.path.getsize(dest) == os.path.getsize(abs_src):
                return dest
            # si distinto, añadir sufijo incremental
            name, ext = os.path.splitext(base)
            i = 1
            while True:
                candidate = os.path.join(TMP_SEND_DIR, f"{name}_{i}{ext}")
                if not os.path.exists(candidate):
                    dest = candidate
                    break
                i += 1
    except Exception:
        # fallback: crear un nuevo destino
        dest = os.path.join(TMP_SEND_DIR, base)

    # copiar (preserva metadata cuando sea posible)
    shutil.copy2(abs_src, dest)
    return dest

# ---------- flujo de envío desde carpeta ----------
def send_files_from_shared():
    ensure_dirs()
    files = list_shared_files()
    if not files:
        print(f"No hay archivos en {SHARED_DIR}. Coloca archivos ahí y vuelve a intentarlo.")
        return

    print("\nArchivos disponibles en carpeta compartida:")
    for i, (name, size) in enumerate(files, start=1):
        print(f"  {i}. {name}  ({human_size(size)})")
    print("  a. Enviar todos")
    print("  0. Volver")

    sel = input("Elige (#/a/0): ").strip().lower()
    if sel == "0":
        return

    chosen_paths = []
    if sel == "a":
        chosen_paths = [os.path.join(SHARED_DIR, n) for n, _ in files]
    else:
        try:
            idx = int(sel)
            if 1 <= idx <= len(files):
                chosen_paths = [os.path.join(SHARED_DIR, files[idx-1][0])]
            else:
                print("Número inválido.")
                return
        except ValueError:
            print("Entrada inválida.")
            return

    dest = ask_dest_mac()
    use_ack = (dest.lower() != DEFAULT_DEST_MAC)

    temp_created = []
    try:
        for orig in chosen_paths:
            print(f"\n[main] Preparando archivo: {orig}")
            try:
                prepared = _copy_to_tmp_and_prepare(orig)
            except Exception as e:
                print(f"[main] error preparando {orig}: {e}")
                # limpiar temporales creados hasta ahora
                for t in temp_created:
                    try:
                        os.remove(t)
                    except Exception:
                        pass
                return

            print(f"[main] Enviando desde copia '{prepared}' -> destino {dest} (use_ack={use_ack})")
            try:
                send_file(dest, prepared, use_ack=use_ack)
                print(f"[main] Envío finalizado: {orig}")
            except Exception as e:
                print(f"[main] Error al enviar {orig}: {e}")
            # guardar temporales para posible limpieza posterior
            if os.path.dirname(prepared) == TMP_SEND_DIR:
                temp_created.append(prepared)
    finally:
        # limpiar archivos temporales creados durante esta sesión
        for t in temp_created:
            try:
                os.remove(t)
            except Exception:
                pass

# ---------- recepción blocking (helper) ----------
def _move_received_to_received(path: str) -> str:
    """
    Mueve `path` (archivo recibido en la carpeta del proyecto) a REPO_ROOT/Received/
    - Si el nombre empieza con 'recv_' se recupera el nombre original.
    - Evita sobrescribir añadiendo sufijos _1, _2, ...
    Retorna la ruta final (destino) o la ruta original si hubo error.
    """
    try:
        received_dir = os.path.join(REPO_ROOT, "Received")
        Path(received_dir).mkdir(parents=True, exist_ok=True)

        base = os.path.basename(path)
        # Si empieza con 'recv_', quitamos el prefijo
        if base.startswith("recv_"):
            original_name = base[len("recv_"):]
        else:
            original_name = base

        dest = os.path.join(received_dir, original_name)
        name, ext = os.path.splitext(original_name)

        # Evitar sobrescribir
        i = 1
        while os.path.exists(dest):
            dest = os.path.join(received_dir, f"{name}_{i}{ext}")
            i += 1

        shutil.move(path, dest)
        return dest
    except Exception as e:
        print(f"[main] Error moviendo recibido a Received/: {e}")
        return path


def recv_file_flow():
    from files import receive_file_blocking
    print("Esperando la llegada de un archivo (esto bloqueará) ...")
    src, path = receive_file_blocking()
    if path:
        final_path = _move_received_to_received(path)
        print(f"Archivo recibido desde {src}: {final_path}")
    else:
        print("No se recibió archivo o hubo error.")


# ---------- menú principal ----------
def main_menu():
    print(f"Carpeta compartida usada para listar: {SHARED_DIR}")
    print(f"Carpeta temporal para envío: {TMP_SEND_DIR}")

    while True:
        print("\n=== LinkChat - Menú principal ===")
        print("1. Chat de mensajes")
        print("2. Enviar archivo desde carpeta compartida (se copia al repo antes de enviar)")
        print("3. Recibir archivo (blocking)")
        print("4. Salir")
        opt = input("Elige opción: ").strip()
        if opt == "1":
            chat_mode()
        elif opt == "2":
            send_files_from_shared()
        elif opt == "3":
            recv_file_flow()
        elif opt == "4":
            print("Saliendo.")
            break
        else:
            print("Opción inválida, intenta de nuevo.")

if __name__ == "__main__":
    main_menu()

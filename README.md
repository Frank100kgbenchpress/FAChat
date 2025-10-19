# FRABChat - Aplicación de Chat y Transferencia de Archivos en Red Local

## 📖 Descripción

FRABChat es una aplicación de mensajería y transferencia de archivos que funciona directamente sobre la red local Ethernet, permitiendo comunicación peer-to-peer sin necesidad de servidores externos o conexión a Internet.

## ✨ Características

- **Chat en tiempo real** entre dispositivos en la misma red local
- **Transferencia de archivos** directa entre usuarios
- **Chat grupal** para enviar mensajes a múltiples usuarios simultáneamente
- **Envío de carpetas** completas manteniendo la estructura de directorios
- **Interfaz web moderna** y responsive
- **Descubrimiento automático** de usuarios en la red
- **Comunicación directa** via protocolo Ethernet personalizado

## 🛠️ Tecnologías

- **Backend**: Python, Flask
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Red**: Sockets raw Ethernet, protocolo personalizado
- **Interfaz**: Web responsive con diseño moderno

## 📋 Requisitos del Sistema

- Python 3.8+
- Sistema operativo Linux
- Permisos de administrador para sockets raw
- Interfaz de red Ethernet/Wi-Fi

## 🚀 Instalación y Ejecución

### 1. Clonar el repositorio
```bash
git clone <repository-url>
cd FAChat
```
### 2. Crear entorno virtual
```bash
python3 -m venv venv
source venv/bin/activate
```
### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```
### 4. Ejecuta aplicacion fuera del venv
```bash
sudo venv/bin/python3 web/app.py
```

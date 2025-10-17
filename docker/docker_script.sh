#!/bin/bash

# --- CONFIGURACIÓN ---
IMAGE_NAME="fachat_image"
NETWORK_NAME="fachat_net"
SUBNET="172.28.0.0/16"

# --- 1. Construir la imagen ---
echo "🔧 Construyendo imagen Docker..."
docker build -t $IMAGE_NAME -f Dockerfile ..

# --- 2. Crear red si no existe ---
if ! docker network inspect $NETWORK_NAME >/dev/null 2>&1; then
  echo "🌐 Creando red $NETWORK_NAME..."
  docker network create --driver bridge --subnet=$SUBNET $NETWORK_NAME
else
  echo "✅ Red $NETWORK_NAME ya existe."
fi

# --- 3. Ejecutar contenedor user1 ---
echo "🚀 Iniciando contenedor fachat_user1..."
docker run -d \
  --name fachat_user1 \
  --hostname user1 \
  --env PORT=5000 \
  --env SESSION_COOKIE_NAME=session_app1 \
  --publish 5005:5000 \
  --network $NETWORK_NAME \
  --ip 172.28.0.2 \
  $IMAGE_NAME python3 web/app.py

# --- 4. Ejecutar contenedor user2 ---
echo "🚀 Iniciando contenedor fachat_user2..."
docker run -d \
  --name fachat_user2 \
  --hostname user2 \
  --env PORT=5000 \
  --env SESSION_COOKIE_NAME=session_app2 \
  --publish 5006:5000 \
  --network $NETWORK_NAME \
  --ip 172.28.0.3 \
  $IMAGE_NAME python3 web/app.py

echo "🎉 Contenedores en ejecución:"
docker ps --filter "name=fachat_"

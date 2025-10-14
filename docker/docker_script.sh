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
  --env USER_NAME=Alice \
  --env PORT=5000 \
  --env MY_MAC=02:42:ac:1c:00:02 \
  --env SECRET_KEY=c8a6d95a3b912f58e9b2f214f1e3e13f627c04f7a1cb0d8c08d27e7b45e76e90 \
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
  --env USER_NAME=Bob \
  --env PORT=5000 \
  --env MY_MAC=02:42:ac:1c:00:03 \
  --env SECRET_KEY=6f88f120cecd5a6eeb1a2d7b92fd1b1434cb4c692a933b2f3ec90bb80e7546e2 \
  --env SESSION_COOKIE_NAME=session_app2 \
  --publish 5006:5000 \
  --network $NETWORK_NAME \
  --ip 172.28.0.3 \
  $IMAGE_NAME python3 web/app.py

echo "🎉 Contenedores en ejecución:"
docker ps --filter "name=fachat_"

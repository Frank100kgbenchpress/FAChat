# Usar imagen oficial de Python ligera
FROM python:3.11-slim
RUN apt-get update
RUN apt-get install -y iproute2

# Establecer directorio de trabajo
WORKDIR /app

#Variables de entorno de Python
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copiar solo lo necesario
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del proyecto
COPY . /app/

# Exponer puerto de Flask
EXPOSE 5000

# Comando por defecto
CMD ["python","-u", "web/app.py"]

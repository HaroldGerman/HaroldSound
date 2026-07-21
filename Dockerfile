FROM python:3.11-slim

# Instalar ffmpeg para procesamiento de audio de YouTube
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Usar la variable $PORT dinámica asignada por Railway o puerto 8000 por defecto
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]

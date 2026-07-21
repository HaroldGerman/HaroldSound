# 🎵 HaroldSound - Servidor de Streaming y Descargas MP3

Backend en **Python (FastAPI)** listo para desplegar en **Render.com** con soporte de `yt-dlp` y `ffmpeg` para convertir y transmitir audio en MP3 a dispositivos Android y clientes Web.

## 🚀 Características
- **Búsqueda y Streaming**: Búsqueda ultrarrápida de audio vía `yt-dlp`.
- **Panel Administrador Web (`/admin`)**: Sistema de aprobación y control de acceso de usuarios/dispositivos.
- **Despliegue Docker**: Configurado con `Dockerfile` y `requirements.txt` optimizado para **Render.com**.

## 🛠️ Instalación Local

```bash
pip install -r requirements.txt
python main.py
```

El servidor estará disponible en `http://localhost:8000`.
El Panel Administrador estará en `http://localhost:8000/admin`.

## ☁️ Despliegue en Render.com
1. Conecta este repositorio en Render.com.
2. Selecciona **Docker** como el entorno de ejecución.
3. ¡Despliega y obtén tu URL pública HTTPS!

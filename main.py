import os
import logging
import socket
from urllib.parse import quote

from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.youtube_service import YoutubeService
from services.user_service import UserService
from services.storage_service import StorageService

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

# Inicialización de la aplicación FastAPI
app = FastAPI(
    title="HaroldSound API & Admin Panel",
    description="Backend optimizado y robusto para HaroldSound con integración resiliente a YouTube.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variables de entorno y configuración general
DESCARGAS_DIR = os.getenv("DESCARGAS_DIR", "descargas")
USERS_FILE = os.getenv("USERS_FILE", "users.json")
COOKIES_FILE = os.getenv("COOKIES_FILE", "cookies.txt")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "harold_admin_2026")
PORT = int(os.getenv("PORT", 8000))

# Inicialización de servicios desacoplados
youtube_service = YoutubeService(cookies_file=COOKIES_FILE, downloads_dir=DESCARGAS_DIR)
user_service = UserService(users_file=USERS_FILE)
storage_service = StorageService(downloads_dir=DESCARGAS_DIR)

# Montar directorio estático para descargas
app.mount("/descargas", StaticFiles(directory=DESCARGAS_DIR), name="descargas")


class RegisterRequest(BaseModel):
    deviceId: str
    nombre: str
    telefono: str


def obtener_ip_local() -> str:
    """
    Obtiene la dirección IP local para facilitar pruebas en red local.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# --- ENDPOINTS DE REGISTRO Y DISPOSITIVOS ---

@app.post("/api/register")
async def registrar_usuario(data: RegisterRequest):
    if not data.deviceId or not data.nombre or not data.telefono:
        raise HTTPException(status_code=400, detail="Faltan datos requeridos para el registro")

    res = user_service.registrar_usuario(
        device_id=data.deviceId,
        nombre=data.nombre,
        telefono=data.telefono
    )
    return res


@app.get("/api/check-status")
async def verificar_estado_usuario(deviceId: str):
    if not deviceId or not deviceId.strip():
        return {"registered": False, "status": "unregistered"}

    return user_service.verificar_estado(device_id=deviceId)


# --- PANEL ADMINISTRADOR WEB EN /admin ---

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(passkey: str = ""):
    users = user_service.cargar_usuarios()
    
    users_html = ""
    for dev_id, user in users.items():
        status = user.get("status", "pending")
        badge_class = "badge-pending"
        badge_text = "⏳ PENDIENTE"
        
        if status == "approved":
            badge_class = "badge-approved"
            badge_text = "✅ APROBADO"
        elif status == "blocked":
            badge_class = "badge-blocked"
            badge_text = "🚫 BLOQUEADO"

        users_html += f"""
        <tr>
            <td><strong>{user.get('nombre', 'Desconocido')}</strong></td>
            <td>{user.get('telefono', '-')}</td>
            <td><small>{user.get('created_at', '-')}</small></td>
            <td><span class="badge {badge_class}">{badge_text}</span></td>
            <td>
                <form action="/admin/action" method="post" style="display:inline-block;">
                    <input type="hidden" name="passkey" value="{passkey}">
                    <input type="hidden" name="deviceId" value="{dev_id}">
                    <input type="hidden" name="action" value="approve">
                    <button type="submit" class="btn btn-approve">✅ APROBAR</button>
                </form>
                <form action="/admin/action" method="post" style="display:inline-block;">
                    <input type="hidden" name="passkey" value="{passkey}">
                    <input type="hidden" name="deviceId" value="{dev_id}">
                    <input type="hidden" name="action" value="block">
                    <button type="submit" class="btn btn-block">🚫 BLOQUEAR</button>
                </form>
                <form action="/admin/action" method="post" style="display:inline-block;">
                    <input type="hidden" name="passkey" value="{passkey}">
                    <input type="hidden" name="deviceId" value="{dev_id}">
                    <input type="hidden" name="action" value="delete">
                    <button type="submit" class="btn btn-delete">🗑️ ELIMINAR</button>
                </form>
            </td>
        </tr>
        """

    if not users_html:
        users_html = "<tr><td colspan='5' style='text-align:center; color:#94a3b8;'>No hay solicitudes de registro aún.</td></tr>"

    auth_display = ""
    if passkey != ADMIN_PASSWORD:
        auth_display = """
        <div class="login-overlay">
            <div class="login-card">
                <h2>🔐 Panel Administrador HaroldSound</h2>
                <p>Ingresa tu clave de administrador para acceder:</p>
                <form method="get" action="/admin">
                    <input type="password" name="passkey" placeholder="Contraseña de admin" required class="input-pass">
                    <button type="submit" class="btn btn-approve" style="width:100%; margin-top:1rem;">Ingresar al Panel</button>
                </form>
            </div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HaroldSound - Admin Panel</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ background:#121212; color:#f8fafc; font-family:'Outfit', sans-serif; margin:0; padding:2rem; }}
        .header {{ max-width:1000px; margin:0 auto 2rem; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #282828; padding-bottom:1rem; }}
        h1 {{ color:#1DB954; margin:0; font-size:1.8rem; }}
        .card {{ max-width:1000px; margin:0 auto; background:#181818; border-radius:12px; padding:1.5rem; border:1px solid #282828; }}
        table {{ width:100%; border-collapse:collapse; margin-top:1rem; }}
        th, td {{ padding:12px 16px; text-align:left; border-bottom:1px solid #282828; }}
        th {{ color:#1DB954; font-size:0.9rem; text-transform:uppercase; }}
        .badge {{ padding:4px 10px; border-radius:12px; font-size:0.8rem; font-weight:bold; }}
        .badge-pending {{ background:#F59E0B; color:#000; }}
        .badge-approved {{ background:#1DB954; color:#fff; }}
        .badge-blocked {{ background:#E11D48; color:#fff; }}
        .btn {{ padding:6px 12px; border:none; border-radius:6px; font-weight:bold; cursor:pointer; margin-right:4px; font-size:0.8rem; }}
        .btn-approve {{ background:#1DB954; color:#fff; }}
        .btn-block {{ background:#E11D48; color:#fff; }}
        .btn-delete {{ background:#4B5563; color:#fff; }}
        .login-overlay {{ position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(18,18,18,0.95); display:flex; align-items:center; justify-content:center; z-index:999; }}
        .login-card {{ background:#181818; border:1px solid #282828; padding:2rem; border-radius:14dp; width:100%; max-width:380px; text-align:center; }}
        .input-pass {{ width:100%; padding:10px 14px; border-radius:8px; border:1px solid #333; background:#242424; color:#fff; box-sizing:border-box; font-size:1rem; }}
    </style>
</head>
<body>
    {auth_display}
    <div class="header">
        <h1>👑 HaroldSound Admin Panel</h1>
        <div>Acceso Autorizado</div>
    </div>
    <div class="card">
        <h2>Solicitudes de Dispositivos y Usuarios</h2>
        <p style="color:#b3b3b3; font-size:0.9rem;">Solo las personas en estado <strong>✅ APROBADO</strong> podrán utilizar tu aplicación Android.</p>
        <table>
            <thead>
                <tr>
                    <th>Nombre</th>
                    <th>Teléfono</th>
                    <th>Fecha</th>
                    <th>Estado</th>
                    <th>Acciones</th>
                </tr>
            </thead>
            <tbody>
                {users_html}
            </tbody>
        </table>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.post("/admin/action")
async def admin_action(passkey: str = Form(...), deviceId: str = Form(...), action: str = Form(...)):
    if passkey != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Contraseña de administrador incorrecta")

    user_service.actualizar_estado(device_id=deviceId, accion=action)
    return RedirectResponse(url=f"/admin?passkey={passkey}", status_code=303)


# --- ENDPOINTS DE MÚSICA & DESCARGAS ---

@app.get("/descargar")
async def descargar_cancion(url: str, request: Request):
    try:
        resultado = youtube_service.download_audio(url)
        solo_nombre = resultado["archivo"]
        
        # Guardar metadatos en almacenamiento local
        storage_service.guardar_cancion_metadata(
            archivo=solo_nombre,
            titulo=resultado["titulo"],
            thumbnail=resultado["thumbnail"],
            canal=resultado["canal"],
            duracion=resultado["duracion"],
            video_id=resultado.get("id", "")
        )

        base_url = str(request.base_url).rstrip('/')
        url_encoded = quote(solo_nombre)
        url_publica = f"{base_url}/descargas/{url_encoded}"

        return {
            "status": "success",
            "url": url_publica,
            "titulo": resultado["titulo"],
            "archivo": solo_nombre,
            "thumbnail": resultado["thumbnail"],
            "canal": resultado["canal"],
            "duracion": resultado["duracion"]
        }
    except Exception as e:
        logger.error(f"Error procesando descarga para '{url}': {e}")
        return {"status": "error", "message": str(e)}


@app.get("/buscar")
async def buscar_cancion(termino: str):
    if not termino or not termino.strip():
        return {"canciones": []}

    canciones = youtube_service.search_songs(query=termino, max_results=16)
    return {"canciones": canciones}


@app.get("/canciones")
async def listar_canciones(request: Request):
    base_url = str(request.base_url).rstrip('/')
    canciones = storage_service.listar_canciones(base_url=base_url)
    return {"canciones": canciones}


@app.delete("/canciones/{archivo}")
async def eliminar_cancion(archivo: str):
    try:
        eliminado = storage_service.eliminar_cancion(archivo=archivo)
        if eliminado:
            return {"status": "success", "message": f"Canción '{archivo}' eliminada correctamente."}
        else:
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al eliminar canción '{archivo}': {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar archivo: {str(e)}")


@app.get("/", response_class=HTMLResponse)
async def reproductor_web():
    html_content = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HaroldSound - Server & Player</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body { background:#121212; color:#fff; font-family:'Outfit', sans-serif; text-align:center; padding:3rem; }
        h1 { color:#1DB954; font-size:2.5rem; }
        .btn { display:inline-block; padding:12px 24px; background:#1DB954; color:#fff; text-decoration:none; border-radius:99px; font-weight:bold; margin-top:1.5rem; }
    </style>
</head>
<body>
    <h1>HaroldSound Server 🎵</h1>
    <p>Servidor activo en Render / Cloud. Para administrar accesos, entra al Panel de Control:</p>
    <a href="/admin" class="btn">👑 Entrar al Panel de Control Admin</a>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    import uvicorn
    ip_local = obtener_ip_local()
    print(f"\n==========================================")
    print(f" 🎵 HaroldSound Server iniciado correctamente!")
    print(f" 👑 Panel Admin Web: http://localhost:{PORT}/admin")
    print(f"==========================================\n")
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
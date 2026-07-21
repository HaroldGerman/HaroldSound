import os
import logging
import socket
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Form, Response, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.youtube_service import YoutubeService
from services.user_service import UserService
from services.storage_service import StorageService
from services.auth_service import AuthService

# Cargar variables de entorno desde .env si existe
load_dotenv()

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

# Inicialización de la aplicación FastAPI
app = FastAPI(
    title="HaroldSound API & Admin Panel",
    description="Backend optimizado y seguro para HaroldSound con autenticación PIN y JWT.",
    version="2.2.1"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variables de entorno y configuración general de seguridad
DESCARGAS_DIR = os.getenv("DESCARGAS_DIR", "descargas")
USERS_FILE = os.getenv("USERS_FILE", "users.json")
COOKIES_FILE = os.getenv("COOKIES_FILE", "cookies.txt")
PORT = int(os.getenv("PORT", 8000))

# Inicialización de servicios desacoplados
auth_service = AuthService()
youtube_service = YoutubeService(cookies_file=COOKIES_FILE, downloads_dir=DESCARGAS_DIR)
user_service = UserService(users_file=USERS_FILE)
storage_service = StorageService(downloads_dir=DESCARGAS_DIR)

# Montar directorio estático para descargas
app.mount("/descargas", StaticFiles(directory=DESCARGAS_DIR), name="descargas")


class RegisterRequest(BaseModel):
    deviceId: str
    nombre: str
    telefono: str


class VerifyCodeRequest(BaseModel):
    deviceId: str
    code: str


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


def obtener_base_url_publica(request: Request) -> str:
    """
    Construye la URL base pública garantizando el uso de HTTPS seguro para streaming.
    """
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)

    if "railway.app" in host or "onrender.com" in host or "fly.dev" in host or proto == "https":
        proto = "https"

    return f"{proto}://{host}"


# --- ENDPOINTS DE REGISTRO Y VERIFICACIÓN PIN (APP ANDROID) ---

@app.post("/api/register")
@app.post("/api/send-code")
async def registrar_usuario_y_enviar_codigo(data: RegisterRequest):
    if not data.deviceId or not data.nombre or not data.telefono:
        raise HTTPException(status_code=400, detail="Faltan datos requeridos para el registro")

    return user_service.enviar_codigo_verificacion(
        device_id=data.deviceId,
        nombre=data.nombre,
        telefono=data.telefono
    )


@app.post("/api/verify-code")
async def verificar_codigo_pin(data: VerifyCodeRequest):
    if not data.deviceId or not data.code:
        raise HTTPException(status_code=400, detail="Faltan datos requeridos para la verificación")

    return user_service.verificar_codigo(
        device_id=data.deviceId,
        code=data.code
    )


@app.get("/api/check-status")
async def verificar_estado_usuario(deviceId: str):
    if not deviceId or not deviceId.strip():
        return {"registered": False, "status": "unregistered"}

    return user_service.verificar_estado(device_id=deviceId)


# --- AUTENTICACIÓN SEGURA Y PANEL DE ADMINISTRACIÓN ---

@app.get("/admin/login", response_class=HTMLResponse)
async def login_page(error: bool = False):
    error_msg = '<div style="color:#ef4444; margin-bottom:1rem; font-size:0.9rem;">❌ Contraseña incorrecta. Inténtalo de nuevo.</div>' if error else ''
    
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HaroldSound - Iniciar Sesión Admin</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ background:#121212; color:#fff; font-family:'Outfit', sans-serif; display:flex; align-items:center; justify-content:center; min-height:100vh; margin:0; }}
        .card {{ background:#181818; border:1px solid #282828; padding:2.5rem; border-radius:16px; width:100%; max-width:380px; text-align:center; box-shadow:0 10px 25px rgba(0,0,0,0.5); }}
        h2 {{ color:#1DB954; margin-top:0; font-size:1.6rem; }}
        p {{ color:#b3b3b3; font-size:0.9rem; margin-bottom:1.5rem; }}
        input {{ width:100%; padding:12px 14px; border-radius:8px; border:1px solid #333; background:#242424; color:#fff; box-sizing:border-box; font-size:1rem; margin-bottom:1rem; }}
        input:focus {{ outline:none; border-color:#1DB954; }}
        .btn {{ width:100%; padding:12px; border:none; border-radius:99px; background:#1DB954; color:#fff; font-weight:bold; font-size:1rem; cursor:pointer; transition:background 0.2s; }}
        .btn:hover {{ background:#1ed760; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>🔐 HaroldSound Admin</h2>
        <p>Ingresa tu clave de administrador para gestionar accesos:</p>
        {error_msg}
        <form method="post" action="/admin/login">
            <input type="password" name="password" placeholder="Contraseña de administrador" required autofocus>
            <button type="submit" class="btn">Ingresar al Panel</button>
        </form>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.post("/admin/login")
async def process_login(password: str = Form(...)):
    if auth_service.verificar_password(password):
        token = auth_service.crear_token_acceso()
        response = RedirectResponse(url="/admin", status_code=303)
        response.set_cookie(
            key="session_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=86400
        )
        logger.info("Sesión de administrador iniciada correctamente.")
        return response

    logger.warning("Intento fallido de inicio de sesión en /admin/login.")
    return RedirectResponse(url="/admin/login?error=true", status_code=303)


@app.get("/admin/logout")
async def logout():
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie("session_token")
    return response


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    session_token = request.cookies.get("session_token")
    if not auth_service.verificar_token(session_token):
        return RedirectResponse(url="/admin/login", status_code=303)

    users = user_service.cargar_usuarios()
    
    users_html = ""
    for dev_id, user in users.items():
        status = user.get("status", "unregistered")
        badge_class = "badge-pending"
        badge_text = "⏳ PENDIENTE"
        pin_info = f"<br><small style='color:#38bdf8;'>PIN: <strong>{user.get('verification_code', '-')}</strong></small>"
        
        if status == "code_sent":
            badge_class = "badge-code"
            badge_text = "🔑 PIN ENVIADO"
        elif status == "pending":
            badge_class = "badge-pending"
            badge_text = "⏳ VERIFICADO (PENDIENTE ADMIN)"
        elif status == "approved":
            badge_class = "badge-approved"
            badge_text = "✅ APROBADO"
        elif status == "blocked":
            badge_class = "badge-blocked"
            badge_text = "🚫 BLOQUEADO"

        users_html += f"""
        <tr>
            <td><strong>{user.get('nombre', 'Desconocido')}</strong>{pin_info}</td>
            <td>{user.get('telefono', '-')}</td>
            <td><small>{user.get('created_at', '-')}</small></td>
            <td><span class="badge {badge_class}">{badge_text}</span></td>
            <td>
                <form action="/admin/action" method="post" style="display:inline-block;">
                    <input type="hidden" name="deviceId" value="{dev_id}">
                    <input type="hidden" name="action" value="approve">
                    <button type="submit" class="btn btn-approve">✅ APROBAR</button>
                </form>
                <form action="/admin/action" method="post" style="display:inline-block;">
                    <input type="hidden" name="deviceId" value="{dev_id}">
                    <input type="hidden" name="action" value="block">
                    <button type="submit" class="btn btn-block">🚫 BLOQUEAR</button>
                </form>
                <form action="/admin/action" method="post" style="display:inline-block;">
                    <input type="hidden" name="deviceId" value="{dev_id}">
                    <input type="hidden" name="action" value="delete">
                    <button type="submit" class="btn btn-delete">🗑️ ELIMINAR</button>
                </form>
            </td>
        </tr>
        """

    if not users_html:
        users_html = "<tr><td colspan='5' style='text-align:center; color:#94a3b8;'>No hay solicitudes de registro aún.</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HaroldSound - Panel Administrador</title>
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
        .badge-code {{ background:#0284c7; color:#fff; }}
        .badge-pending {{ background:#F59E0B; color:#000; }}
        .badge-approved {{ background:#1DB954; color:#fff; }}
        .badge-blocked {{ background:#E11D48; color:#fff; }}
        .btn {{ padding:6px 12px; border:none; border-radius:6px; font-weight:bold; cursor:pointer; margin-right:4px; font-size:0.8rem; text-decoration:none; display:inline-block; }}
        .btn-approve {{ background:#1DB954; color:#fff; }}
        .btn-block {{ background:#E11D48; color:#fff; }}
        .btn-delete {{ background:#4B5563; color:#fff; }}
        .btn-logout {{ background:#333; color:#ef4444; border:1px solid #444; font-size:0.85rem; padding:8px 16px; border-radius:99px; }}
        .btn-logout:hover {{ background:#444; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>👑 HaroldSound Admin Panel</h1>
        <div>
            <a href="/admin/logout" class="btn btn-logout">🚪 Cerrar Sesión</a>
        </div>
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
async def admin_action(request: Request, deviceId: str = Form(...), action: str = Form(...)):
    session_token = request.cookies.get("session_token")
    if not auth_service.verificar_token(session_token):
        raise HTTPException(status_code=401, detail="No autorizado. Inicia sesión en /admin/login")

    user_service.actualizar_estado(device_id=deviceId, accion=action)
    return RedirectResponse(url="/admin", status_code=303)


# --- ENDPOINTS DE MÚSICA & DESCARGAS (APP ANDROID) ---

@app.get("/descargar")
async def descargar_cancion(url: str, request: Request):
    try:
        resultado = youtube_service.download_audio(url)
        solo_nombre = resultado["archivo"]
        
        storage_service.guardar_cancion_metadata(
            archivo=solo_nombre,
            titulo=resultado["titulo"],
            thumbnail=resultado["thumbnail"],
            canal=resultado["canal"],
            duracion=resultado["duracion"],
            video_id=resultado.get("id", "")
        )

        base_url = obtener_base_url_publica(request)
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
    base_url = obtener_base_url_publica(request)
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
    <title>HaroldSound - Pruebas de Verificación PIN</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body { background:#121212; color:#fff; font-family:'Outfit', sans-serif; padding:2rem; max-width:650px; margin:0 auto; }
        h1 { color:#1DB954; font-size:2rem; text-align:center; }
        .card { background:#181818; border:1px solid #282828; border-radius:14px; padding:1.5rem; margin-bottom:1.5rem; }
        h3 { color:#38bdf8; margin-top:0; }
        label { display:block; font-size:0.85rem; color:#b3b3b3; margin-bottom:4px; }
        input { width:100%; padding:10px 12px; border-radius:8px; border:1px solid #333; background:#242424; color:#fff; box-sizing:border-box; margin-bottom:1rem; font-size:0.95rem; }
        .btn { width:100%; padding:12px; border:none; border-radius:99px; background:#1DB954; color:#fff; font-weight:bold; cursor:pointer; font-size:1rem; }
        .btn-sec { background:#0284c7; margin-top:0.5rem; }
        .res-box { background:#000; border:1px solid #333; padding:12px; border-radius:8px; font-family:monospace; color:#34d399; font-size:0.85rem; white-space:pre-wrap; margin-top:1rem; display:none; }
    </style>
</head>
<body>
    <h1>🎵 HaroldSound Testing Sandbox</h1>
    <p style="text-align:center; color:#b3b3b3;">Prueba el flujo de registro, verificación de PIN y aprobación en vivo:</p>

    <!-- PASO 1 -->
    <div class="card">
        <h3>Paso 1: Solicitar Código PIN</h3>
        <label>Nombre del Usuario:</label>
        <input type="text" id="nombre" value="Carlos Prueba">
        <label>Teléfono:</label>
        <input type="text" id="telefono" value="987654321">
        <label>ID del Dispositivo (deviceId):</label>
        <input type="text" id="deviceId" value="dev_demo_99">
        <button onclick="enviarCodigo()" class="btn">1. Enviar Registro y Generar PIN</button>
        <div id="res1" class="res-box"></div>
    </div>

    <!-- PASO 2 -->
    <div class="card">
        <h3>Paso 2: Confirmar Código PIN</h3>
        <label>Código PIN de 4 dígitos:</label>
        <input type="text" id="pinCode" placeholder="Ejemplo: 4829">
        <button onclick="verificarCodigo()" class="btn btn-sec">2. Confirmar Código PIN</button>
        <div id="res2" class="res-box"></div>
    </div>

    <!-- PASO 3 -->
    <div class="card">
        <h3>Paso 3: Aprobar desde el Panel Admin</h3>
        <p>Una vez verificado el PIN, entra al Panel de Control para hacer clic en <strong>✅ APROBAR</strong>:</p>
        <a href="/admin" target="_blank" class="btn" style="display:block; text-align:center; text-decoration:none;">👑 Abrir Panel Administrador /admin</a>
        <button onclick="consultarEstado()" class="btn btn-sec" style="margin-top:1rem;">3. Consultar Estado Actual (check-status)</button>
        <div id="res3" class="res-box"></div>
    </div>

    <script>
        async function enviarCodigo() {
            const data = {
                deviceId: document.getElementById('deviceId').value,
                nombre: document.getElementById('nombre').value,
                telefono: document.getElementById('telefono').value
            };
            const res = await fetch('/api/send-code', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            const json = await res.json();
            const box = document.getElementById('res1');
            box.style.display = 'block';
            box.innerText = JSON.stringify(json, null, 2);
            if(json.code) {
                document.getElementById('pinCode').value = json.code;
            }
        }

        async function verificarCodigo() {
            const data = {
                deviceId: document.getElementById('deviceId').value,
                code: document.getElementById('pinCode').value
            };
            const res = await fetch('/api/verify-code', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            const json = await res.json();
            const box = document.getElementById('res2');
            box.style.display = 'block';
            box.innerText = JSON.stringify(json, null, 2);
        }

        async function consultarEstado() {
            const devId = document.getElementById('deviceId').value;
            const res = await fetch('/api/check-status?deviceId=' + devId);
            const json = await res.json();
            const box = document.getElementById('res3');
            box.style.display = 'block';
            box.innerText = JSON.stringify(json, null, 2);
        }
    </script>
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
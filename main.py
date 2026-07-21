from fastapi import FastAPI, Request, HTTPException, Form, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import os
import json
import socket
from datetime import datetime
from urllib.parse import quote

app = FastAPI(title="HaroldSound API & Admin Panel")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DESCARGAS_DIR = "descargas"
METADATA_FILE = os.path.join(DESCARGAS_DIR, "metadata.json")
USERS_FILE = "users.json"
COOKIES_FILE = "cookies.txt"
ADMIN_PASSWORD = "harold_admin_2026"

if not os.path.exists(DESCARGAS_DIR):
    os.makedirs(DESCARGAS_DIR)

app.mount("/descargas", StaticFiles(directory=DESCARGAS_DIR), name="descargas")


class RegisterRequest(BaseModel):
    deviceId: str
    nombre: str
    telefono: str


def obtener_ip_local():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def cargar_usuarios_dict() -> dict:
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def guardar_usuarios_dict(users_dict: dict):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_dict, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error guardando usuarios: {e}")


def cargar_metadatos_dict() -> dict:
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def guardar_metadatos_dict(meta_dict: dict):
    try:
        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(meta_dict, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error guardando metadatos: {e}")


def obtener_nombre_archivo_real(nombre_final: str) -> str:
    if os.path.exists(nombre_final):
        return os.path.basename(nombre_final)
    
    base_sin_ext = os.path.splitext(os.path.basename(nombre_final))[0]
    if os.path.exists(DESCARGAS_DIR):
        for filename in os.listdir(DESCARGAS_DIR):
            if filename.endswith(".mp3"):
                if base_sin_ext.lower() in filename.lower() or filename.lower().startswith(base_sin_ext[:15].lower()):
                    return filename
    return os.path.basename(nombre_final)


# --- SISTEMA DE REGISTRO Y APROBACIÓN DE USUARIOS ---

@app.post("/api/register")
async def registrar_usuario(data: RegisterRequest):
    users = cargar_usuarios_dict()
    dev_id = data.deviceId.strip()

    if not dev_id or not data.nombre or not data.telefono:
        raise HTTPException(status_code=400, detail="Faltan datos de registro")

    if dev_id in users:
        return {
            "status": "success",
            "user_status": users[dev_id].get("status", "pending"),
            "message": "Dispositivo ya registrado"
        }

    users[dev_id] = {
        "deviceId": dev_id,
        "nombre": data.nombre.strip(),
        "telefono": data.telefono.strip(),
        "status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    guardar_usuarios_dict(users)

    return {
        "status": "success",
        "user_status": "pending",
        "message": "Registro recibido. Esperando aprobación del administrador."
    }


@app.get("/api/check-status")
async def verificar_estado_usuario(deviceId: str):
    users = cargar_usuarios_dict()
    dev_id = deviceId.strip()

    if dev_id not in users:
        return {"registered": False, "status": "unregistered"}

    user_info = users[dev_id]
    return {
        "registered": True,
        "status": user_info.get("status", "pending"),
        "nombre": user_info.get("nombre", ""),
        "telefono": user_info.get("telefono", "")
    }


# --- PANEL ADMINISTRADOR WEB EN /admin ---

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(passkey: str = ""):
    users = cargar_usuarios_dict()
    
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

    users = cargar_usuarios_dict()
    dev_id = deviceId.strip()

    if dev_id in users:
        if action == "approve":
            users[dev_id]["status"] = "approved"
        elif action == "block":
            users[dev_id]["status"] = "blocked"
        elif action == "delete":
            del users[dev_id]
        guardar_usuarios_dict(users)

    return RedirectResponse(url=f"/admin?passkey={passkey}", status_code=303)


# --- ENDPOINTS DE MÚSICA & DESCARGAS ---

@app.get("/descargar")
async def descargar_cancion(url: str, request: Request):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{DESCARGAS_DIR}/%(title)s.%(ext)s',
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            },
            {
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }
        ],
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        },
        'nocheckcertificate': True,
        'quiet': True,
        'noplaylist': True,
        'no_warnings': True,
    }
    
    if os.path.exists(COOKIES_FILE):
        ydl_opts['cookiefile'] = COOKIES_FILE
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info and 'entries' in info and len(info['entries']) > 0:
                info = info['entries'][0]
            
            nombre_archivo_original = ydl.prepare_filename(info)
            nombre_final = nombre_archivo_original.rsplit('.', 1)[0] + '.mp3'
            
            solo_nombre = obtener_nombre_archivo_real(nombre_final)
            titulo_cancion = info.get('title', solo_nombre.rsplit('.', 1)[0])
            thumbnail = info.get('thumbnail') or f"https://img.youtube.com/vi/{info.get('id', '')}/hqdefault.jpg"
            canal = info.get('uploader') or info.get('channel', 'Desconocido')
            
            duracion_sec = info.get('duration')
            duracion_str = ""
            if duracion_sec:
                mins = int(duracion_sec) // 60
                secs = int(duracion_sec) % 60
                duracion_str = f"{mins}:{secs:02d}"

            meta_dict = cargar_metadatos_dict()
            meta_dict[solo_nombre] = {
                "titulo": titulo_cancion,
                "thumbnail": thumbnail,
                "canal": canal,
                "duracion": duracion_str,
                "id": info.get('id', '')
            }
            guardar_metadatos_dict(meta_dict)

            base_url = str(request.base_url).rstrip('/')
            url_encoded = quote(solo_nombre)
            url_publica = f"{base_url}/descargas/{url_encoded}"
                
        return {
            "status": "success",
            "url": url_publica,
            "titulo": titulo_cancion,
            "archivo": solo_nombre,
            "thumbnail": thumbnail,
            "canal": canal,
            "duracion": duracion_str
        }
    except Exception as e:
        print(f"Error descargando {url}: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/buscar")
async def buscar_cancion(termino: str):
    ydl_opts = {
        'format': 'bestaudio/best',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        },
        'quiet': True,
        'extract_flat': True,
        'noplaylist': True,
        'no_warnings': True,
    }
    
    if os.path.exists(COOKIES_FILE):
        ydl_opts['cookiefile'] = COOKIES_FILE
    
    lista_canciones = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            resultados = ydl.extract_info(f"ytsearch20:{termino}", download=False)
            
            if resultados and 'entries' in resultados:
                for video in resultados['entries']:
                    if not video:
                        continue
                    
                    ie_key = video.get('ie_key', '')
                    url_video = video.get('url') or video.get('webpage_url') or ''
                    video_id = video.get('id', '')
                    
                    es_video = (ie_key == 'Youtube') or ('watch?v=' in url_video) or (len(video_id) == 11 and not video_id.startswith('UC'))
                    
                    if es_video:
                        if not url_video.startswith('http'):
                            url_video = f"https://www.youtube.com/watch?v={video_id}"
                        
                        duracion_sec = video.get('duration')
                        duracion_str = ""
                        if duracion_sec:
                            mins = int(duracion_sec) // 60
                            secs = int(duracion_sec) % 60
                            duracion_str = f"{mins}:{secs:02d}"
                        
                        thumbnail_url = video.get('thumbnail')
                        if not thumbnail_url and video_id:
                            thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

                        lista_canciones.append({
                            "id": video_id,
                            "titulo": video.get('title', 'Sin título'),
                            "url": url_video,
                            "duracion": duracion_str,
                            "canal": video.get('uploader') or video.get('channel', 'YouTube'),
                            "thumbnail": thumbnail_url
                        })
                        
                        if len(lista_canciones) >= 16:  
                            break
    except Exception as e:
        print(f"Error en búsqueda: {e}")
            
    return {"canciones": lista_canciones}


@app.get("/canciones")
async def listar_canciones(request: Request):
    base_url = str(request.base_url).rstrip('/')
    canciones = []
    meta_dict = cargar_metadatos_dict()
    
    if os.path.exists(DESCARGAS_DIR):
        for archivo in os.listdir(DESCARGAS_DIR):
            if archivo.endswith(".mp3"):
                url_encoded = quote(archivo)
                info_meta = meta_dict.get(archivo, {})
                
                titulo = info_meta.get("titulo", archivo.rsplit('.', 1)[0])
                thumbnail = info_meta.get("thumbnail", "")
                canal = info_meta.get("canal", "Colección")
                duracion = info_meta.get("duracion", "")

                canciones.append({
                    "titulo": titulo,
                    "archivo": archivo,
                    "url": f"{base_url}/descargas/{url_encoded}",
                    "thumbnail": thumbnail,
                    "canal": canal,
                    "duracion": duracion
                })
                
    return {"canciones": canciones}


@app.delete("/canciones/{archivo}")
async def eliminar_cancion(archivo: str):
    filepath = os.path.join(DESCARGAS_DIR, archivo)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            meta_dict = cargar_metadatos_dict()
            if archivo in meta_dict:
                del meta_dict[archivo]
                guardar_metadatos_dict(meta_dict)
            return {"status": "success", "message": f"Canción '{archivo}' eliminada correctamente."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al eliminar archivo: {str(e)}")
    else:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")


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
    print(f" 👑 Panel Admin Web: http://localhost:8000/admin")
    print(f"==========================================\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
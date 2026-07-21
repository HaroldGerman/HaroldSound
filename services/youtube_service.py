import os
import logging
from typing import List, Dict, Any, Optional
import yt_dlp

logger = logging.getLogger("youtube_service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class YtDlpNullLogger:
    """
    Logger nulo para evitar que yt-dlp escriba errores no capturados a sys.stderr
    durante las pruebas de estrategias secundarias.
    """
    def debug(self, msg: str):
        pass

    def warning(self, msg: str):
        pass

    def error(self, msg: str):
        pass


class YoutubeService:
    """
    Servicio centralizado e independiente para gestionar la interacción con YouTube mediante yt-dlp.
    Soporta reintentos automáticos, autenticación con cookies.txt, fallbacks de clientes móviles y procesamiento de audio con FFmpeg.
    """

    def __init__(self, cookies_file: str = "cookies.txt", downloads_dir: str = "descargas"):
        self.cookies_file = cookies_file
        self.downloads_dir = downloads_dir

        if not os.path.exists(self.downloads_dir):
            os.makedirs(self.downloads_dir, exist_ok=True)

    def _get_base_options(self, use_cookies: bool = True, client_strategy: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Construye la configuración centralizada y optimizada para yt-dlp.
        """
        opts: Dict[str, Any] = {
            'format': 'bestaudio/best',
            'nocheckcertificate': True,
            'quiet': True,
            'noplaylist': True,
            'no_warnings': True,
            'logger': YtDlpNullLogger(),
            'concurrent_fragment_downloads': 4,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            }
        }

        if client_strategy:
            opts['extractor_args'] = {
                'youtube': {
                    'player_client': client_strategy
                }
            }

        # Aplicar cookies si el archivo existe y no está vacío
        if use_cookies and os.path.exists(self.cookies_file) and os.path.getsize(self.cookies_file) > 0:
            opts['cookiefile'] = self.cookies_file

        return opts

    def search_songs(self, query: str, max_results: int = 16) -> List[Dict[str, Any]]:
        """
        Busca canciones en YouTube de forma robusta con múltiples estrategias de reintento.
        """
        strategies = [
            {'use_cookies': True, 'client_strategy': ['android', 'android_vr']},
            {'use_cookies': True, 'client_strategy': ['web', 'android']},
            {'use_cookies': False, 'client_strategy': ['android', 'android_vr']},
            {'use_cookies': False, 'client_strategy': ['android_music', 'android']},
        ]

        clean_query = query.strip()
        search_query = f"ytsearch20:{clean_query}"
        last_error: Optional[Exception] = None

        for idx, strat in enumerate(strategies, 1):
            opts = self._get_base_options(
                use_cookies=strat['use_cookies'],
                client_strategy=strat['client_strategy']
            )
            opts['extract_flat'] = True

            try:
                logger.info(f"Buscando '{clean_query}' (Estrategia {idx}/{len(strategies)})...")
                with yt_dlp.YoutubeDL(opts) as ydl:
                    results = ydl.extract_info(search_query, download=False)
                    songs = self._parse_search_results(results, max_results)
                    if songs:
                        logger.info(f"Búsqueda exitosa para '{clean_query}': {len(songs)} resultados.")
                        return songs
            except Exception as e:
                last_error = e
                logger.warning(f"Estrategia {idx} de búsqueda falló: {e}")

        logger.error(f"Todas las estrategias de búsqueda fallaron para '{clean_query}': {last_error}")
        return []

    def _parse_search_results(self, results: Dict[str, Any], max_results: int) -> List[Dict[str, Any]]:
        """
        Procesa y normaliza los resultados de búsqueda planos de YouTube.
        """
        songs: List[Dict[str, Any]] = []
        if not results or 'entries' not in results:
            return songs

        for video in results['entries']:
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

                songs.append({
                    "id": video_id,
                    "titulo": video.get('title', 'Sin título'),
                    "url": url_video,
                    "duracion": duracion_str,
                    "canal": video.get('uploader') or video.get('channel', 'YouTube'),
                    "thumbnail": thumbnail_url
                })

                if len(songs) >= max_results:
                    break

        return songs

    def download_audio(self, url: str) -> Dict[str, Any]:
        """
        Descarga el audio de una URL de YouTube en formato MP3 (192kbps)
        priorizando la autenticación con cookies.txt si está disponible.
        """
        has_cookies = os.path.exists(self.cookies_file) and os.path.getsize(self.cookies_file) > 0
        if has_cookies:
            logger.info(f"🍪 Archivo cookies.txt detectado ({os.path.getsize(self.cookies_file)} bytes). Se utilizará para autenticación en YouTube.")
        else:
            logger.warning(f"⚠️ No se encontró el archivo '{self.cookies_file}'. Si YouTube bloquea la IP por Anti-Bot, monta cookies.txt en el contenedor.")

        strategies = [
            {'use_cookies': True, 'client_strategy': ['android', 'android_vr']},
            {'use_cookies': True, 'client_strategy': ['web', 'android']},
            {'use_cookies': False, 'client_strategy': ['android', 'android_vr']},
            {'use_cookies': False, 'client_strategy': ['android_music', 'android']},
        ]

        out_template = os.path.join(self.downloads_dir, "%(title)s.%(ext)s")
        last_exception: Optional[Exception] = None

        for idx, strat in enumerate(strategies, 1):
            opts = self._get_base_options(
                use_cookies=strat['use_cookies'],
                client_strategy=strat['client_strategy']
            )
            opts['outtmpl'] = out_template
            opts['postprocessors'] = [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                },
                {
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                }
            ]

            try:
                logger.info(f"Iniciando descarga de '{url}' (Estrategia {idx}/{len(strategies)})...")
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if not info:
                        raise ValueError("No se obtuvieron metadatos del video")

                    if 'entries' in info and len(info['entries']) > 0:
                        info = info['entries'][0]

                    nombre_archivo_original = ydl.prepare_filename(info)
                    nombre_final = nombre_archivo_original.rsplit('.', 1)[0] + '.mp3'
                    solo_nombre = self._find_actual_file(nombre_final)

                    titulo_cancion = info.get('title', solo_nombre.rsplit('.', 1)[0])
                    thumbnail = info.get('thumbnail') or f"https://img.youtube.com/vi/{info.get('id', '')}/hqdefault.jpg"
                    canal = info.get('uploader') or info.get('channel', 'Desconocido')

                    duracion_sec = info.get('duration')
                    duracion_str = ""
                    if duracion_sec:
                        mins = int(duracion_sec) // 60
                        secs = int(duracion_sec) % 60
                        duracion_str = f"{mins}:{secs:02d}"

                    logger.info(f"Descarga exitosa: '{titulo_cancion}' -> '{solo_nombre}'")

                    return {
                        "status": "success",
                        "titulo": titulo_cancion,
                        "archivo": solo_nombre,
                        "thumbnail": thumbnail,
                        "canal": canal,
                        "duracion": duracion_str,
                        "id": info.get('id', '')
                    }
            except Exception as e:
                last_exception = e
                logger.warning(f"Estrategia {idx} de descarga falló para '{url}': {e}")

        logger.error(f"Fallo definitivo al descargar '{url}': {last_exception}")
        raise RuntimeError(f"No se pudo descargar la canción: {str(last_exception)}")

    def _find_actual_file(self, expected_path: str) -> str:
        """
        Resuelve el nombre de archivo real en el disco en caso de caracteres especiales o sanitización.
        """
        if os.path.exists(expected_path):
            return os.path.basename(expected_path)

        base_sin_ext = os.path.splitext(os.path.basename(expected_path))[0]
        if os.path.exists(self.downloads_dir):
            for filename in os.listdir(self.downloads_dir):
                if filename.endswith(".mp3"):
                    if base_sin_ext.lower() in filename.lower() or filename.lower().startswith(base_sin_ext[:15].lower()):
                        return filename
        return os.path.basename(expected_path)

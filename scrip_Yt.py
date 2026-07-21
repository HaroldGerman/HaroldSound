import yt_dlp

def descargar_audio(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'canciones/%(title)s.%(ext)s', # Carpeta donde se guardan
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

# Ejemplo de uso
# descargar_audio('URL_DE_TU_VIDEO_AQUI')
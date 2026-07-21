import os
import json
import logging
from typing import Dict, Any, List
from urllib.parse import quote

logger = logging.getLogger("storage_service")


class StorageService:
    """
    Servicio para la gestión de archivos MP3 descargados localmente y sus metadatos asociados.
    """

    def __init__(self, downloads_dir: str = "descargas"):
        self.downloads_dir = downloads_dir
        self.metadata_file = os.path.join(self.downloads_dir, "metadata.json")

        if not os.path.exists(self.downloads_dir):
            os.makedirs(self.downloads_dir, exist_ok=True)

    def cargar_metadatos(self) -> Dict[str, Dict[str, Any]]:
        """
        Carga la información de metadatos de las canciones en disco.
        """
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error cargando metadatos desde '{self.metadata_file}': {e}")
                return {}
        return {}

    def guardar_metadatos(self, meta_dict: Dict[str, Dict[str, Any]]) -> bool:
        """
        Guarda los metadatos actualizados en el archivo JSON.
        """
        try:
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(meta_dict, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error guardando metadatos en '{self.metadata_file}': {e}")
            return False

    def guardar_cancion_metadata(self, archivo: str, titulo: str, thumbnail: str, canal: str, duracion: str, video_id: str = ""):
        """
        Registra los metadatos de una nueva canción descargada.
        """
        meta_dict = self.cargar_metadatos()
        meta_dict[archivo] = {
            "titulo": titulo,
            "thumbnail": thumbnail,
            "canal": canal,
            "duracion": duracion,
            "id": video_id
        }
        self.guardar_metadatos(meta_dict)

    def listar_canciones(self, base_url: str) -> List[Dict[str, Any]]:
        """
        Retorna la lista de todas las canciones disponibles localmente con sus URLs públicas.
        """
        canciones: List[Dict[str, Any]] = []
        meta_dict = self.cargar_metadatos()

        if os.path.exists(self.downloads_dir):
            for archivo in os.listdir(self.downloads_dir):
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

        return canciones

    def eliminar_cancion(self, archivo: str) -> bool:
        """
        Elimina el archivo MP3 del disco y remueve sus metadatos.
        """
        filepath = os.path.join(self.downloads_dir, archivo)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                meta_dict = self.cargar_metadatos()
                if archivo in meta_dict:
                    del meta_dict[archivo]
                    self.guardar_metadatos(meta_dict)
                return True
            except Exception as e:
                logger.error(f"Error eliminando canción '{archivo}': {e}")
                raise e
        return False

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("user_service")


class UserService:
    """
    Servicio de gestión de usuarios y dispositivos registrados para HaroldSound.
    Almacena los datos en un archivo JSON persistente.
    """

    def __init__(self, users_file: str = "users.json"):
        self.users_file = users_file

    def cargar_usuarios(self) -> Dict[str, Dict[str, Any]]:
        """
        Carga el diccionario de usuarios desde el archivo JSON.
        """
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error al cargar usuarios desde '{self.users_file}': {e}")
                return {}
        return {}

    def guardar_usuarios(self, users_dict: Dict[str, Dict[str, Any]]) -> bool:
        """
        Guarda el diccionario de usuarios en el archivo JSON.
        """
        try:
            with open(self.users_file, "w", encoding="utf-8") as f:
                json.dump(users_dict, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error al guardar usuarios en '{self.users_file}': {e}")
            return False

    def registrar_usuario(self, device_id: str, nombre: str, telefono: str) -> Dict[str, Any]:
        """
        Registra una nueva solicitud de dispositivo o retorna el estado actual si ya existe.
        """
        dev_id = device_id.strip()
        users = self.cargar_usuarios()

        if dev_id in users:
            return {
                "status": "success",
                "user_status": users[dev_id].get("status", "pending"),
                "message": "Dispositivo ya registrado"
            }

        users[dev_id] = {
            "deviceId": dev_id,
            "nombre": nombre.strip(),
            "telefono": telefono.strip(),
            "status": "pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.guardar_usuarios(users)

        return {
            "status": "success",
            "user_status": "pending",
            "message": "Registro recibido. Esperando aprobación del administrador."
        }

    def verificar_estado(self, device_id: str) -> Dict[str, Any]:
        """
        Consulta el estado de registro de un dispositivo por su deviceId.
        """
        dev_id = device_id.strip()
        users = self.cargar_usuarios()

        if dev_id not in users:
            return {"registered": False, "status": "unregistered"}

        user_info = users[dev_id]
        return {
            "registered": True,
            "status": user_info.get("status", "pending"),
            "nombre": user_info.get("nombre", ""),
            "telefono": user_info.get("telefono", "")
        }

    def actualizar_estado(self, device_id: str, accion: str) -> bool:
        """
        Actualiza el estado de aprobación ('approve', 'block', 'delete') para un dispositivo.
        """
        dev_id = device_id.strip()
        users = self.cargar_usuarios()

        if dev_id not in users and accion != "delete":
            return False

        if accion == "approve":
            users[dev_id]["status"] = "approved"
        elif accion == "block":
            users[dev_id]["status"] = "blocked"
        elif accion == "delete":
            if dev_id in users:
                del users[dev_id]

        return self.guardar_usuarios(users)

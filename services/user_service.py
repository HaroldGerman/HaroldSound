import os
import re
import json
import random
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("user_service")


class UserService:
    """
    Servicio de gestión de usuarios, verificación por código PIN de 4 dígitos
    vía WhatsApp/SMS y validación de número de teléfono único para HaroldSound.
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

    def enviar_codigo_verificacion(self, device_id: str, nombre: str, telefono: str) -> Dict[str, Any]:
        """
        Genera un código PIN de 4 dígitos para un número de teléfono.
        Garantiza que cada número de teléfono solo pueda ser registrado 1 sola vez en el sistema.
        """
        dev_id = device_id.strip()
        nombre_clean = nombre.strip()
        tel_raw = telefono.strip()
        tel_digits = re.sub(r"\D", "", tel_raw)

        if not tel_digits or len(tel_digits) < 7:
            return {
                "status": "error",
                "message": "Por favor ingresa un número de celular válido."
            }

        users = self.cargar_usuarios()

        # 1. SEGURIDAD: Verificar si el NÚMERO DE TELÉFONO ya está registrado en el sistema
        for existing_id, u_info in users.items():
            existing_tel_digits = re.sub(r"\D", "", u_info.get("telefono", ""))
            if existing_tel_digits == tel_digits:
                existing_status = u_info.get("status", "unregistered")

                # Si es un dispositivo diferente intentando usar el mismo teléfono
                if existing_id != dev_id:
                    if existing_status == "approved":
                        logger.warning(f"Intento de duplicado: Teléfono {tel_raw} ya registrado en dispositivo {existing_id}")
                        return {
                            "status": "error",
                            "message": "⚠️ Este número de celular ya está registrado y activo en otro dispositivo."
                        }
                    elif existing_status == "blocked":
                        return {
                            "status": "error",
                            "message": "🚫 Este número de celular ha sido bloqueado por el administrador."
                        }

        # 2. Si el dispositivo ya tiene un registro previo en estado final
        if dev_id in users:
            user = users[dev_id]
            status = user.get("status", "unregistered")
            if status in ["approved", "blocked"]:
                return {
                    "status": "success",
                    "user_status": status,
                    "message": f"Dispositivo ya registrado en estado '{status}'."
                }

        # Generar PIN aleatorio de 4 dígitos
        pin_code = f"{random.randint(1000, 9999)}"

        users[dev_id] = {
            "deviceId": dev_id,
            "nombre": nombre_clean,
            "telefono": tel_raw,
            "status": "code_sent",
            "verification_code": pin_code,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.guardar_usuarios(users)

        logger.info(f"🔑 Código PIN {pin_code} generado para {nombre_clean} ({tel_raw}) [ID: {dev_id}]")

        return {
            "status": "success",
            "user_status": "code_sent",
            "message": "Solicitud recibida. Se enviará un código PIN de 4 dígitos a tu número de WhatsApp."
        }

    def verificar_codigo(self, device_id: str, code: str) -> Dict[str, Any]:
        """
        Valida el código PIN de 4 dígitos ingresado por el usuario en la app.
        """
        dev_id = device_id.strip()
        clean_code = code.strip()
        users = self.cargar_usuarios()

        if dev_id not in users:
            return {"status": "error", "message": "Dispositivo no registrado. Por favor inicia el registro."}

        user = users[dev_id]
        stored_code = user.get("verification_code")

        if stored_code and stored_code == clean_code:
            user["status"] = "pending"
            user["verified_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.guardar_usuarios(users)

            logger.info(f"✅ Código PIN verificado para {user.get('nombre')}. Solicitud lista para aprobación final.")

            return {
                "status": "success",
                "user_status": "pending",
                "message": "¡Número de celular verificado con éxito! Esperando aprobación del administrador."
            }
        else:
            return {
                "status": "error",
                "message": "Código de verificación incorrecto. Revisa el PIN enviado a tu WhatsApp e inténtalo de nuevo."
            }

    def verificar_estado(self, device_id: str) -> Dict[str, Any]:
        """
        Consulta el estado actual de registro de un dispositivo.
        """
        dev_id = device_id.strip()
        users = self.cargar_usuarios()

        if dev_id not in users:
            return {"registered": False, "status": "unregistered"}

        user_info = users[dev_id]
        return {
            "registered": True,
            "status": user_info.get("status", "unregistered"),
            "nombre": user_info.get("nombre", ""),
            "telefono": user_info.get("telefono", "")
        }

    def actualizar_estado(self, device_id: str, accion: str) -> bool:
        """
        Actualiza el estado de aprobación ('approve', 'block', 'delete') desde el panel /admin.
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

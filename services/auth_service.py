import os
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional
import jwt

logger = logging.getLogger("auth_service")


class AuthService:
    """
    Servicio de autenticación segura para el panel de administración.
    Utiliza Tokens JWT firmados enviados en Cookies HttpOnly.
    """

    def __init__(self, secret_key: Optional[str] = None, admin_password: Optional[str] = None):
        self.secret_key = secret_key or os.getenv("SECRET_KEY") or secrets.token_hex(32)
        self.admin_password = admin_password or os.getenv("ADMIN_PASSWORD")
        self.algorithm = "HS256"
        self.token_duration_hours = 24

        if not self.admin_password:
            logger.warning("⚠️ SECURITY WARNING: ADMIN_PASSWORD no está configurado. El acceso al panel /admin estará deshabilitado.")

    def verificar_password(self, password_ingresada: str) -> bool:
        """
        Verifica la contraseña ingresada de forma segura.
        """
        if not self.admin_password:
            return False
        return secrets.compare_digest(password_ingresada.strip(), self.admin_password.strip())

    def crear_token_acceso(self) -> str:
        """
        Genera un Token JWT firmado con fecha de expiración.
        """
        expiracion = datetime.utcnow() + timedelta(hours=self.token_duration_hours)
        payload = {
            "sub": "admin",
            "role": "administrator",
            "exp": expiracion
        }
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token

    def verificar_token(self, token: Optional[str]) -> bool:
        """
        Valida la firma y expiración del Token JWT de la Cookie.
        """
        if not token:
            return False
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload.get("sub") == "admin"
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
            logger.debug(f"Token inválido o expirado: {e}")
            return False

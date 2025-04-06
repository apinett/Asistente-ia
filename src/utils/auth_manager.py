import os
import json
import getpass
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
from ..utils.logger import get_logger

class AuthManager:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.credentials_file = os.path.join('config', 'credentials.enc')
        self.key_file = os.path.join('config', 'key.key')
        self._load_or_generate_key()
        
    def _load_or_generate_key(self):
        """Cargar o generar la clave de encriptación."""
        try:
            if os.path.exists(self.key_file):
                with open(self.key_file, 'rb') as f:
                    self.key = f.read()
            else:
                self.key = Fernet.generate_key()
                os.makedirs('config', exist_ok=True)
                with open(self.key_file, 'wb') as f:
                    f.write(self.key)
        except Exception as e:
            self.logger.error(f"Error al manejar la clave de encriptación: {e}")
            raise
    
    def _encrypt_data(self, data: Dict[str, str]) -> bytes:
        """Encriptar datos sensibles."""
        f = Fernet(self.key)
        return f.encrypt(json.dumps(data).encode())
    
    def _decrypt_data(self, encrypted_data: bytes) -> Dict[str, str]:
        """Desencriptar datos sensibles."""
        f = Fernet(self.key)
        return json.loads(f.decrypt(encrypted_data).decode())
    
    def save_credentials(self, credentials: Dict[str, str]):
        """Guardar credenciales encriptadas."""
        try:
            encrypted_data = self._encrypt_data(credentials)
            with open(self.credentials_file, 'wb') as f:
                f.write(encrypted_data)
            self.logger.info("Credenciales guardadas exitosamente")
        except Exception as e:
            self.logger.error(f"Error al guardar credenciales: {e}")
            raise
    
    def load_credentials(self) -> Optional[Dict[str, str]]:
        """Cargar credenciales encriptadas."""
        try:
            if os.path.exists(self.credentials_file):
                with open(self.credentials_file, 'rb') as f:
                    encrypted_data = f.read()
                return self._decrypt_data(encrypted_data)
            return None
        except Exception as e:
            self.logger.error(f"Error al cargar credenciales: {e}")
            return None
    
    def get_credentials(self) -> Dict[str, str]:
        """Obtener credenciales del usuario."""
        # Intentar cargar credenciales existentes
        credentials = self.load_credentials()
        if credentials:
            return credentials
        
        # Si no hay credenciales, solicitarlas al usuario
        print("\n=== Configuración de Credenciales ===")
        print("Por favor, ingresa tus credenciales:")
        
        # Credenciales de correo
        print("\n--- Credenciales de Correo ---")
        email = input("Correo electrónico: ").strip()
        email_password = getpass.getpass("Contraseña de correo: ").strip()
        
        # Credenciales de TMS
        print("\n--- Credenciales de TMS ---")
        tms_url = input("URL del sistema TMS: ").strip()
        tms_username = input("Usuario de TMS: ").strip()
        tms_password = getpass.getpass("Contraseña de TMS: ").strip()
        
        # Guardar credenciales
        credentials = {
            'EMAIL_USER': email,
            'EMAIL_PASSWORD': email_password,
            'TMS_URL': tms_url,
            'TMS_USERNAME': tms_username,
            'TMS_PASSWORD': tms_password
        }
        
        self.save_credentials(credentials)
        return credentials
    
    def update_credentials(self, service: str, new_credentials: Dict[str, str]):
        """Actualizar credenciales de un servicio específico."""
        current_credentials = self.load_credentials() or {}
        
        if service == 'email':
            current_credentials.update({
                'EMAIL_USER': new_credentials.get('email'),
                'EMAIL_PASSWORD': new_credentials.get('password')
            })
        elif service == 'tms':
            current_credentials.update({
                'TMS_URL': new_credentials.get('url'),
                'TMS_USERNAME': new_credentials.get('username'),
                'TMS_PASSWORD': new_credentials.get('password')
            })
        
        self.save_credentials(current_credentials)
        self.logger.info(f"Credenciales de {service} actualizadas exitosamente") 
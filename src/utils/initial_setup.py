import os
import json
import getpass
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from dotenv import load_dotenv, set_key
from src.utils.logger import Logger
from src.utils.email_utils import infer_email_config


class InitialSetup:
    def __init__(self):
        self.config_dir = "data"
        self.config_file = os.path.join(self.config_dir, "config.json")
        self.key_file = os.path.join(self.config_dir, "config.key")
        self.logger = Logger()
        self.fernet_key = None
        self.config = self.load_config()
        self.setup_directories()

    def setup_directories(self):
        """Crear directorios necesarios si no existen."""
        directories = ["data", "logs", "models", "temp"]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)

    def load_config(self) -> Dict[str, Any]:
        """Cargar configuración existente."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"Error al cargar configuración: {e}")
        return {
            "email": {},
            "whatsapp": {},
            "tms": {},
            "learning": {},
            "is_configured": False,
        }

    def save_config(self):
        """Guardar configuración."""
        try:
            os.makedirs("data", exist_ok=True)
            with open(self.config_file, "w") as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            self.logger.error(f"Error al guardar configuración: {e}")
            return False

    def setup_encryption(self):
        """Configurar encriptación."""
        try:
            if os.path.exists(self.key_file):
                with open(self.key_file, "rb") as key_file:
                    self.fernet_key = key_file.read()
            else:
                self.fernet_key = Fernet.generate_key()
                with open(self.key_file, "wb") as key_file:
                    key_file.write(self.fernet_key)
            return True
        except Exception as e:
            self.logger.error(f"Error al configurar encriptación: {e}")
            return False

    def encrypt_data(self, data: str) -> str:
        """Encriptar datos sensibles."""
        if not self.fernet_key:
            if not self.setup_encryption():
                return None
        try:
            f = Fernet(self.fernet_key)
            encrypted_data = f.encrypt(data.encode())
            return encrypted_data.decode()
        except Exception as e:
            self.logger.error(f"Error al encriptar datos: {e}")
            return None

    def decrypt_data(self, encrypted_data: str) -> Optional[str]:
        """Desencriptar datos usando la clave cargada."""
        if not self.fernet_key:
            self.logger.error("Intento de desencriptar sin clave cargada.")
            return None
        try:
            f = Fernet(self.fernet_key)
            decrypted_data = f.decrypt(encrypted_data.encode())
            return decrypted_data.decode()
        except Exception as e:
            self.logger.error(f"Error al desencriptar datos: {e}")
            return None

    def setup_email(self):
        """Configurar las credenciales de correo electrónico."""
        self.logger.info("Iniciando configuración de correo electrónico...")
        print("\n--- Configuración de Correo Electrónico ---")

        email = input("Correo electrónico: ").strip()
        password = getpass.getpass("Contraseña (se ocultará): ")

        inferred_config = infer_email_config(email)

        if inferred_config:
            self.logger.info(f"Configuración de servidor inferida para {email}.")
            print("Configuración de servidor detectada automáticamente.")
            email_config = {
                "email": email,
                "password": password,
                "server": inferred_config["server"],
                "port": inferred_config["port"],
                "use_ssl": inferred_config["use_ssl"],
                "smtp_server": inferred_config["smtp_server"],
                "smtp_port": inferred_config["smtp_port"],
            }
            # Aquí podrías añadir una verificación opcional de conexión
            # para asegurarte de que las credenciales y la config inferida funcionan
            # try:
            #     # Intenta conectar con EmailManager
            #     temp_manager = EmailManager(**email_config)
            #     temp_manager.connect() # Necesitarías un método connect simple
            #     print("Conexión de prueba exitosa.")
            # except Exception as e:
            #     self.logger.error(f"Error en prueba de conexión: {e}")
            #     print("Error al verificar la conexión. Verifica tus credenciales o configura manualmente.")
            #     # Podrías volver a pedir config manual aquí

        else:
            self.logger.warning(
                f"No se pudo inferir la configuración para {email}. Solicitando manualmente."
            )
            print("No se pudo detectar la configuración del servidor automáticamente.")
            print("Por favor, ingresa los detalles del servidor manualmente:")
            server = input("Servidor IMAP: ").strip()
            port_str = input("Puerto IMAP (ej. 993): ").strip()
            use_ssl_str = input("Usar SSL (s/n): ").lower()
            smtp_server = input("Servidor SMTP: ").strip()
            smtp_port_str = input("Puerto SMTP (ej. 587): ").strip()

            try:
                port = int(port_str)
                smtp_port = int(smtp_port_str)
                use_ssl = use_ssl_str == "s"
                email_config = {
                    "email": email,
                    "password": password,
                    "server": server,
                    "port": port,
                    "use_ssl": use_ssl,
                    "smtp_server": smtp_server,
                    "smtp_port": smtp_port,
                }
            except ValueError:
                self.logger.error("Puerto inválido ingresado.")
                print(
                    "Error: El puerto debe ser un número. No se guardó la configuración de email."
                )
                return None

        # Encriptar contraseña antes de guardar
        encrypted_password = self.encrypt_data(password)
        email_config["password"] = encrypted_password  # Guardar contraseña encriptada

        self.config["email"] = email_config
        print("Configuración de correo electrónico guardada.")
        return email_config

    def setup_whatsapp(self):
        """Configurar WhatsApp."""
        print("\n=== Configuración de WhatsApp ===")
        phone = input(
            "Número de teléfono (con código de país, ej: +54123456789): "
        ).strip()

        # Validar formato del número
        if not phone.startswith("+"):
            phone = "+" + phone

        self.config["whatsapp"] = {"phone": phone, "is_configured": True}

        print("Configuración de WhatsApp guardada.")
        print("\nPara usar WhatsApp, asegúrate de:")
        print("1. Tener WhatsApp Web abierto en tu navegador")
        print("2. Haber escaneado el código QR con tu teléfono")
        print("3. Mantener la sesión activa")

    def setup_tms(self):
        """Configurar TMS."""
        print("\n=== Configuración de TMS ===")
        tms_url = input("URL del sistema TMS: ").strip()
        username = input("Usuario TMS: ").strip()
        password = getpass.getpass("Contraseña TMS: ").strip()

        self.config["tms"] = {
            "url": tms_url,
            "username": username,
            "password": self.encrypt_data(password),
            "is_configured": True,
        }

        print("Configuración de TMS guardada.")
        print("\nPara usar el TMS, asegúrate de:")
        print("1. Tener acceso a la URL proporcionada")
        print("2. Usar credenciales válidas")
        print("3. Mantener la sesión activa")

    def setup_learning(self):
        """Configurar sistema de aprendizaje."""
        print("\n=== Configuración del Sistema de Aprendizaje ===")
        enable_learning = (
            input("¿Activar aprendizaje automático? (s/n): ").strip().lower() == "s"
        )
        save_actions = (
            input("¿Guardar acciones aprendidas? (s/n): ").strip().lower() == "s"
        )

        self.config["learning"] = {
            "enable_learning": enable_learning,
            "save_actions": save_actions,
        }

    def run_setup(self):
        """Ejecutar el proceso completo de configuración inicial si es necesario."""
        os.makedirs(self.config_dir, exist_ok=True)

        if not os.path.exists(self.key_file):
            self.setup_encryption()
        else:
            self.load_or_setup_encryption_key()

        if not self.config or not self.config.get("configured", False):
            print("Bienvenido al asistente de configuración inicial.")
            self.config = {"configured": False}  # Reset config

            # Setup de cada módulo
            self.setup_email()
            self.setup_whatsapp()
            self.setup_tms()
            self.setup_learning()

            self.config["configured"] = True
            self.save_config()
            print("\n¡Configuración inicial completada!")
        else:
            self.logger.info("Configuración ya existente encontrada.")
            # Asegurarse de que la config cargada tenga todas las claves esperadas
            # (Podrías añadir validación aquí)

        return self.config

    def get_config(self):
        """Devuelve la configuración cargada (y desencriptada si es necesario)."""
        # Desencriptar datos sensibles al devolver la config
        decrypted_config = self.config.copy()
        try:
            if decrypted_config.get("email") and decrypted_config["email"].get(
                "password"
            ):
                decrypted_config["email"]["password"] = self.decrypt_data(
                    decrypted_config["email"]["password"]
                )
            if decrypted_config.get("whatsapp") and decrypted_config["whatsapp"].get(
                "api_key"
            ):
                decrypted_config["whatsapp"]["api_key"] = self.decrypt_data(
                    decrypted_config["whatsapp"]["api_key"]
                )
            if decrypted_config.get("tms") and decrypted_config["tms"].get("password"):
                decrypted_config["tms"]["password"] = self.decrypt_data(
                    decrypted_config["tms"]["password"]
                )
            if decrypted_config.get("tms") and decrypted_config["tms"].get("api_key"):
                decrypted_config["tms"]["api_key"] = self.decrypt_data(
                    decrypted_config["tms"]["api_key"]
                )
        except Exception as e:
            self.logger.error(
                f"Error al desencriptar configuración para devolverla: {e}"
            )
            # Decide cómo manejar esto: devolver config parcialmente encriptada, None, o lanzar error?
            # Por seguridad, podríamos devolver None o una copia sin los campos sensibles
            # return None
        return decrypted_config

    def load_or_setup_encryption_key(self):
        """Carga la clave de encriptación o pide la contraseña maestra si la clave no se puede cargar."""
        try:
            with open(self.key_file, "rb") as f:
                key = f.read()
            # Intenta inicializar Fernet para validar la clave (implícitamente)
            self.fernet_key = Fernet(key)
            self.logger.info("Clave de encriptación cargada.")
        except Exception as e:
            self.logger.warning(
                f"No se pudo cargar la clave de encriptación ({e}). Solicitando contraseña maestra."
            )
            self.setup_encryption()  # Vuelve a pedir la contraseña maestra para generar/validar la clave

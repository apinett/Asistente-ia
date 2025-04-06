import pyttsx3
import keyboard
import time
import json
import os
from typing import Dict, Any
from ..tasks.email_manager import EmailManager
from ..tasks.whatsapp_manager import WhatsAppManager
from ..tasks.tms_manager import TMSManager
from ..learning.adaptive_learning import AdaptiveLearning
from ..utils.logger import get_logger
from ..utils.auth_manager import AuthManager


class Assistant:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.auth_manager = AuthManager()
        self.email_manager = None
        self.whatsapp_manager = None
        self.tms_manager = None
        self.engine = pyttsx3.init()
        self.setup_voice()
        self.learning_system = AdaptiveLearning()

        # Cargar configuración
        self.config = self._load_config()

    def setup_voice(self):
        """Configurar la voz del asistente."""
        voices = self.engine.getProperty("voices")
        # Buscar una voz en español si está disponible
        for voice in voices:
            if "spanish" in voice.name.lower():
                self.engine.setProperty("voice", voice.id)
                break
        self.engine.setProperty("rate", 150)  # Velocidad de habla

    def _load_config(self) -> Dict[str, Any]:
        """Cargar configuración del asistente."""
        config_path = os.path.join("config", "assistant_config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.warning(
                "Archivo de configuración no encontrado. Usando configuración por defecto."
            )
            return self._create_default_config()

    def _create_default_config(self) -> Dict[str, Any]:
        """Crear configuración por defecto."""
        default_config = {
            "voice_enabled": True,
            "language": "es-ES",
            "learning_rate": 0.1,
            "max_history": 1000,
            "tasks": {"email": True, "whatsapp": True, "tms": True},
        }
        os.makedirs("config", exist_ok=True)
        with open(
            os.path.join("config", "assistant_config.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(default_config, f, indent=4)
        return default_config

    def speak(self, text):
        """Reproducir texto como voz."""
        self.logger.log(f"Asistente: {text}")
        if self.config["voice_enabled"]:
            self.engine.say(text)
            self.engine.runAndWait()
        print(f"Asistente: {text}")

    def initialize_services(self):
        """Inicializar los servicios con las credenciales."""
        try:
            credentials = self.auth_manager.load_credentials()

            if credentials.get("email"):
                self.email_manager = EmailManager(
                    credentials["email"]["username"], credentials["email"]["password"]
                )

            if credentials.get("whatsapp"):
                self.whatsapp_manager = WhatsAppManager(
                    credentials["whatsapp"]["phone"]
                )

            if credentials.get("tms"):
                self.tms_manager = TMSManager(
                    credentials["tms"]["username"], credentials["tms"]["password"]
                )

            return True
        except Exception as e:
            self.logger.log(f"Error al inicializar servicios: {str(e)}", "ERROR")
            return False

    def handle_command(self, command):
        """Manejar comandos de voz."""
        command = command.lower()

        if "correo" in command or "email" in command:
            if self.email_manager:
                if "enviar" in command:
                    self.email_manager.send_email()
                elif "leer" in command:
                    self.email_manager.read_emails()
            else:
                self.speak("No se han configurado las credenciales de correo")

        elif "whatsapp" in command:
            if self.whatsapp_manager:
                if "enviar" in command:
                    self.whatsapp_manager.send_message()
                elif "leer" in command:
                    self.whatsapp_manager.read_messages()
            else:
                self.speak("No se han configurado las credenciales de WhatsApp")

        elif "tms" in command:
            if self.tms_manager:
                if "entrada" in command:
                    self.tms_manager.enter_data()
                elif "consultar" in command:
                    self.tms_manager.query_data()
            else:
                self.speak("No se han configurado las credenciales del TMS")

        elif "actualizar" in command and "credenciales" in command:
            self.auth_manager.update_credentials()
            self.initialize_services()
            self.speak("Credenciales actualizadas correctamente")

        else:
            self.speak("No entendí el comando. Por favor, intenta de nuevo.")

    def run(self):
        """Ejecutar el asistente."""
        self.speak("Inicializando asistente...")

        if not self.initialize_services():
            self.speak(
                "Error al inicializar los servicios. Por favor, verifica las credenciales."
            )
            return

        self.speak("Asistente listo. Presiona Ctrl+Alt+Espacio para activar.")

        while True:
            try:
                if keyboard.is_pressed("ctrl+alt+space"):
                    self.speak("¿En qué puedo ayudarte?")
                    command = input("Ingresa tu comando: ")

                    if command.lower() in ["adiós", "hasta luego", "salir"]:
                        self.speak("¡Hasta luego! Que tengas un excelente día.")
                        break

                    self.handle_command(command)
                    time.sleep(1)  # Evitar múltiples activaciones

                # Aprender de la interacción
                if command:
                    self.learning_system.learn_from_interaction(command)

            except KeyboardInterrupt:
                self.logger.info("Sesión terminada por el usuario")
                break
            except Exception as e:
                self.logger.error(f"Error en el bucle principal: {e}")
                self.speak(
                    "Lo siento, ha ocurrido un error. ¿Podrías repetir tu solicitud?"
                )

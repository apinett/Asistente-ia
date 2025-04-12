import pyttsx3
import keyboard
import time
from typing import Dict, Any
from src.utils.auth_manager import AuthManager
from src.tasks.email_manager import EmailManager
from src.tasks.whatsapp_manager import WhatsAppManager
from src.tasks.tms_manager import TMSManager
from src.utils.logger import Logger
from src.learning.action_learner import ActionLearner


class Assistant:
    def __init__(self, config: Dict[str, Any]):
        self.logger = Logger()
        self.config = config
        self.auth_manager = AuthManager()
        self.email_manager = None
        self.whatsapp_manager = None
        self.tms_manager = None
        self.engine = pyttsx3.init()
        self.setup_voice()
        self.learning_system = (
            ActionLearner() if config["learning"]["enable_learning"] else None
        )

    def setup_voice(self):
        """Configurar la voz del asistente."""
        voices = self.engine.getProperty("voices")
        # Buscar una voz en español si está disponible
        for voice in voices:
            if "spanish" in voice.name.lower():
                self.engine.setProperty("voice", voice.id)
                break
        self.engine.setProperty("rate", 150)  # Velocidad de habla

    def speak(self, text):
        """Reproducir texto como voz."""
        self.logger.log(f"Asistente: {text}")
        self.engine.say(text)
        self.engine.runAndWait()

    def initialize_services(self):
        """Inicializar los servicios con la configuración."""
        try:
            # Configurar email
            if self.config["email"]:
                self.email_manager = EmailManager(
                    self.config["email"]["email"],
                    self.config["email"]["password"],
                    self.config["email"]["server"],
                    self.config["email"]["port"],
                )

            # Configurar WhatsApp
            if self.config["whatsapp"]:
                self.whatsapp_manager = WhatsAppManager(
                    self.config["whatsapp"]["phone"], self.config["whatsapp"]["api_key"]
                )

            # Configurar TMS
            if self.config["tms"]:
                self.tms_manager = TMSManager(
                    self.config["tms"]["url"],
                    self.config["tms"]["username"],
                    self.config["tms"]["password"],
                    self.config["tms"]["api_key"],
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
            from src.utils.initial_setup import InitialSetup

            setup = InitialSetup()
            setup.run_setup()
            self.config = setup.get_config()
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

                # Aprender de la interacción si está activado
                if self.learning_system and command:
                    self.learning_system.learn_from_interaction(command)

            except KeyboardInterrupt:
                self.logger.info("Sesión terminada por el usuario")
                break
            except Exception as e:
                self.logger.error(f"Error en el bucle principal: {e}")
                self.speak(
                    "Lo siento, ha ocurrido un error. ¿Podrías repetir tu solicitud?"
                )

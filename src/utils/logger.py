import logging
import os
from datetime import datetime
from typing import Optional


class Logger:
    def __init__(self):
        # Crear directorio de logs si no existe
        os.makedirs("logs", exist_ok=True)

        # Configurar el logger
        self.logger = logging.getLogger("AssistantLogger")
        self.logger.setLevel(logging.DEBUG)

        # Crear manejador de archivo
        log_file = os.path.join(
            "logs", f"assistant_{datetime.now().strftime('%Y%m%d')}.log"
        )
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)

        # Crear manejador de consola
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Crear formato
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Agregar manejadores al logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def log(self, message: str, level: Optional[str] = "INFO"):
        """Registrar un mensaje con el nivel especificado."""
        level = level.upper()
        if level == "DEBUG":
            self.logger.debug(message)
        elif level == "INFO":
            self.logger.info(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "ERROR":
            self.logger.error(message)
        elif level == "CRITICAL":
            self.logger.critical(message)
        else:
            self.logger.info(message)  # Por defecto, usar INFO

    def debug(self, message: str):
        """Registrar un mensaje de depuración."""
        self.log(message, "DEBUG")

    def info(self, message: str):
        """Registrar un mensaje informativo."""
        self.log(message, "INFO")

    def warning(self, message: str):
        """Registrar un mensaje de advertencia."""
        self.log(message, "WARNING")

    def error(self, message: str):
        """Registrar un mensaje de error."""
        self.log(message, "ERROR")

    def critical(self, message: str):
        """Registrar un mensaje crítico."""
        self.log(message, "CRITICAL")


def get_logger(name: str) -> logging.Logger:
    """Obtener un logger específico para un módulo."""
    return logging.getLogger(f"assistant.{name}")

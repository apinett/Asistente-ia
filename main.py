import os
from dotenv import load_dotenv
from src.assistant.core import Assistant
from src.assistant.gui import AssistantGUI


def main():
    # Cargar variables de entorno
    load_dotenv()

    # Crear directorios necesarios
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("assets", exist_ok=True)

    # Inicializar asistente
    assistant = Assistant()

    # Inicializar interfaz gráfica
    gui = AssistantGUI(assistant)

    # Ejecutar interfaz
    gui.run()


if __name__ == "__main__":
    main()

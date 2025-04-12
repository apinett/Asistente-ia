import os
from dotenv import load_dotenv
from src.assistant.core import Assistant
from src.assistant.gui import AssistantGUI
from src.utils.initial_setup import InitialSetup


def main():
    # Cargar variables de entorno
    load_dotenv()

    # Crear directorios necesarios
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("assets", exist_ok=True)

    # Ejecutar configuración inicial
    setup = InitialSetup()
    setup.run_setup()

    # Inicializar asistente con la configuración
    assistant = Assistant(setup.get_config())

    # Inicializar interfaz gráfica
    gui = AssistantGUI(assistant)

    # Ejecutar interfaz
    gui.run()


if __name__ == "__main__":
    main()

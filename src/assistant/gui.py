import tkinter as tk
from tkinter import ttk, scrolledtext
import pyautogui
import keyboard
import time
from PIL import Image, ImageTk
import os


class AssistantGUI:
    def __init__(self, assistant):
        self.assistant = assistant
        self.root = tk.Tk()
        self.root.title("Asistente IA")
        self.root.geometry("400x600")
        self.root.attributes("-alpha", 0.9)  # Hacer la ventana semi-transparente
        self.root.attributes("-topmost", True)  # Mantener la ventana siempre visible

        # Estilo
        style = ttk.Style()
        style.configure("TButton", padding=6, relief="flat", background="#2196F3")
        style.configure("TLabel", padding=6)

        self.create_widgets()
        self.setup_hotkeys()

    def create_widgets(self):
        # Frame principal
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Logo/Icono
        try:
            image = Image.open("assets/icon.png")
            image = image.resize((100, 100), Image.Resampling.LANCZOS)
            self.icon = ImageTk.PhotoImage(image)
            icon_label = ttk.Label(main_frame, image=self.icon)
            icon_label.pack(pady=10)
        except:
            pass

        # Estado del asistente
        self.status_label = ttk.Label(
            main_frame, text="Asistente en espera", font=("Helvetica", 12)
        )
        self.status_label.pack(pady=5)

        # Área de chat
        self.chat_area = scrolledtext.ScrolledText(
            main_frame, wrap=tk.WORD, width=40, height=20
        )
        self.chat_area.pack(pady=10, fill="both", expand=True)
        self.chat_area.config(state="disabled")

        # Botones de acción
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        self.record_button = ttk.Button(
            button_frame, text="Grabar Acción", command=self.start_recording
        )
        self.record_button.pack(side="left", padx=5)

        self.learn_button = ttk.Button(
            button_frame, text="Aprender", command=self.start_learning
        )
        self.learn_button.pack(side="left", padx=5)

        # Barra de progreso
        self.progress = ttk.Progressbar(
            main_frame, orient="horizontal", length=300, mode="determinate"
        )
        self.progress.pack(pady=5)

        # Configurar eventos
        self.root.bind("<Button-1>", self.on_click)
        self.root.bind("<B1-Motion>", self.on_drag)

    def setup_hotkeys(self):
        keyboard.add_hotkey("ctrl+alt+space", self.activate_assistant)

    def on_click(self, event):
        """Manejar clic en la ventana."""
        self.x = event.x
        self.y = event.y

    def on_drag(self, event):
        """Manejar arrastre de la ventana."""
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def activate_assistant(self):
        """Activar el asistente."""
        self.status_label.config(text="Asistente activo")
        self.assistant.speak("¿En qué puedo ayudarte?")

    def start_recording(self):
        """Iniciar grabación de acciones."""
        self.status_label.config(text="Grabando acciones...")
        self.record_button.config(text="Detener Grabación")
        self.record_button.config(command=self.stop_recording)

        # Aquí implementar la lógica de grabación de acciones
        # usando pyautogui para capturar movimientos y clics

    def stop_recording(self):
        """Detener grabación de acciones."""
        self.status_label.config(text="Asistente en espera")
        self.record_button.config(text="Grabar Acción")
        self.record_button.config(command=self.start_recording)

    def start_learning(self):
        """Iniciar modo de aprendizaje."""
        self.status_label.config(text="Modo aprendizaje activo")
        self.learn_button.config(text="Detener Aprendizaje")
        self.learn_button.config(command=self.stop_learning)

        # Aquí implementar la lógica de aprendizaje
        # usando el sistema de aprendizaje del asistente

    def stop_learning(self):
        """Detener modo de aprendizaje."""
        self.status_label.config(text="Asistente en espera")
        self.learn_button.config(text="Aprender")
        self.learn_button.config(command=self.start_learning)

    def update_chat(self, message, is_user=False):
        """Actualizar área de chat."""
        self.chat_area.config(state="normal")
        prefix = "Usuario: " if is_user else "Asistente: "
        self.chat_area.insert("end", f"{prefix}{message}\n")
        self.chat_area.see("end")
        self.chat_area.config(state="disabled")

    def update_progress(self, value):
        """Actualizar barra de progreso."""
        self.progress["value"] = value

    def run(self):
        """Ejecutar la interfaz."""
        self.root.mainloop()

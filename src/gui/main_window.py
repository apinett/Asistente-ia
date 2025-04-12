import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from PIL import Image, ImageTk
import os


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configuración de la ventana principal
        self.title("Asistente IA - Logística y Transporte")
        self.geometry("1200x800")
        self.minsize(1000, 700)

        # Configuración de tema y colores
        self.setup_theme()

        # Crear estructura principal
        self.create_main_structure()

        # Cargar recursos
        self.load_resources()

    def setup_theme(self):
        """Configurar el tema y colores de la aplicación."""
        # Colores principales
        self.colors = {
            "primary": "#1E2A38",  # Azul oscuro
            "secondary": "#2D2F33",  # Gris grafito
            "background": "#121212",  # Negro carbón
            "accent": "#00E676",  # Verde neón
            "warning": "#FF9800",  # Naranja
            "text": "#FFFFFF",  # Blanco
            "text_secondary": "#B0B0B0",  # Gris claro
        }

        # Configurar tema de customtkinter
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

    def create_main_structure(self):
        """Crear la estructura principal de la interfaz."""
        # Frame principal
        self.main_frame = ctk.CTkFrame(self, fg_color=self.colors["background"])
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Barra lateral
        self.create_sidebar()

        # Área de contenido principal
        self.create_main_content()

    def create_sidebar(self):
        """Crear la barra lateral de navegación."""
        self.sidebar = ctk.CTkFrame(
            self.main_frame, width=250, fg_color=self.colors["primary"]
        )
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        # Logo y título
        self.logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.logo_frame.pack(pady=20)

        # Botones de navegación
        self.nav_buttons = {
            "Dashboard": self.create_nav_button("Dashboard", "dashboard_icon.png"),
            "TMS": self.create_nav_button("TMS", "tms_icon.png"),
            "Email": self.create_nav_button("Email", "email_icon.png"),
            "WhatsApp": self.create_nav_button("WhatsApp", "whatsapp_icon.png"),
            "Configuración": self.create_nav_button(
                "Configuración", "settings_icon.png"
            ),
        }

        # Separador
        ttk.Separator(self.sidebar, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Botón de modo oscuro/claro
        self.theme_switch = ctk.CTkSwitch(
            self.sidebar, text="Modo Oscuro", command=self.toggle_theme
        )
        self.theme_switch.pack(pady=10)

    def create_nav_button(self, text, icon_path):
        """Crear un botón de navegación con icono."""
        button = ctk.CTkButton(
            self.sidebar,
            text=text,
            image=self.load_icon(icon_path),
            compound=tk.LEFT,
            fg_color="transparent",
            hover_color=self.colors["secondary"],
            anchor="w",
            command=lambda: self.navigate_to(text),
        )
        button.pack(fill=tk.X, padx=10, pady=5)
        return button

    def create_main_content(self):
        """Crear el área de contenido principal."""
        self.content_frame = ctk.CTkFrame(
            self.main_frame, fg_color=self.colors["background"]
        )
        self.content_frame.pack(
            side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5
        )

        # Barra superior
        self.create_top_bar()

        # Área de contenido
        self.content_area = ctk.CTkFrame(
            self.content_frame, fg_color=self.colors["background"]
        )
        self.content_area.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    def create_top_bar(self):
        """Crear la barra superior con información y controles."""
        top_bar = ctk.CTkFrame(
            self.content_frame, height=60, fg_color=self.colors["primary"]
        )
        top_bar.pack(fill=tk.X, padx=5, pady=5)

        # Título de la sección actual
        self.section_title = ctk.CTkLabel(
            top_bar, text="Dashboard", font=("Roboto", 20, "bold")
        )
        self.section_title.pack(side=tk.LEFT, padx=20)

        # Widgets de la derecha
        right_widgets = ctk.CTkFrame(top_bar, fg_color="transparent")
        right_widgets.pack(side=tk.RIGHT, padx=20)

        # Notificaciones
        self.notification_btn = ctk.CTkButton(
            right_widgets,
            text="",
            image=self.load_icon("notification_icon.png"),
            width=30,
            height=30,
            fg_color="transparent",
            hover_color=self.colors["secondary"],
        )
        self.notification_btn.pack(side=tk.LEFT, padx=5)

        # Perfil de usuario
        self.profile_btn = ctk.CTkButton(
            right_widgets,
            text="",
            image=self.load_icon("profile_icon.png"),
            width=30,
            height=30,
            fg_color="transparent",
            hover_color=self.colors["secondary"],
        )
        self.profile_btn.pack(side=tk.LEFT, padx=5)

    def load_resources(self):
        """Cargar recursos gráficos."""
        self.icons = {}
        icon_paths = {
            "dashboard_icon.png": "assets/icons/dashboard.png",
            "tms_icon.png": "assets/icons/tms.png",
            "email_icon.png": "assets/icons/email.png",
            "whatsapp_icon.png": "assets/icons/whatsapp.png",
            "settings_icon.png": "assets/icons/settings.png",
            "notification_icon.png": "assets/icons/notification.png",
            "profile_icon.png": "assets/icons/profile.png",
        }

        for icon_name, path in icon_paths.items():
            self.icons[icon_name] = self.load_icon(path)

    def load_icon(self, path):
        """Cargar un icono desde archivo."""
        try:
            image = Image.open(path)
            image = image.resize((24, 24))
            return ImageTk.PhotoImage(image)
        except:
            return None

    def navigate_to(self, section):
        """Navegar a una sección específica."""
        self.section_title.configure(text=section)
        # Aquí se actualizará el contenido según la sección

    def toggle_theme(self):
        """Cambiar entre modo claro y oscuro."""
        current_mode = ctk.get_appearance_mode()
        new_mode = "light" if current_mode == "dark" else "dark"
        ctk.set_appearance_mode(new_mode)

    def run(self):
        """Iniciar la aplicación."""
        self.mainloop()

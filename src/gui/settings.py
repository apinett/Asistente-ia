import customtkinter as ctk
from tkinter import ttk
import tkinter as tk
from src.utils.auth_manager import AuthManager
from src.utils.email_utils import infer_email_config
from tkinter import messagebox
import os
import json


class SettingsPanel(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.parent = parent
        self.auth_manager = AuthManager()
        self.create_widgets()

    def create_widgets(self):
        """Crear los widgets del panel de configuración."""
        # Notebook para pestañas
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Crear pestañas
        self.create_general_tab()
        self.create_email_tab()
        self.create_whatsapp_tab()
        self.create_tms_tab()
        self.create_notifications_tab()

    def create_general_tab(self):
        """Crear pestaña de configuración general."""
        general_frame = ctk.CTkFrame(self.notebook)
        self.notebook.add(general_frame, text="General")

        # Título
        title_label = ctk.CTkLabel(
            general_frame, text="Configuración General", font=("Roboto", 16, "bold")
        )
        title_label.pack(pady=10)

        # Idioma
        language_frame = ctk.CTkFrame(general_frame, fg_color="transparent")
        language_frame.pack(fill=tk.X, padx=20, pady=10)

        language_label = ctk.CTkLabel(
            language_frame, text="Idioma:", font=("Roboto", 12)
        )
        language_label.pack(side=tk.LEFT)

        self.language_var = tk.StringVar(value="es")
        language_options = ["Español", "English"]
        language_dropdown = ctk.CTkOptionMenu(
            language_frame, values=language_options, variable=self.language_var
        )
        language_dropdown.pack(side=tk.LEFT, padx=10)

        # Tema
        theme_frame = ctk.CTkFrame(general_frame, fg_color="transparent")
        theme_frame.pack(fill=tk.X, padx=20, pady=10)

        theme_label = ctk.CTkLabel(theme_frame, text="Tema:", font=("Roboto", 12))
        theme_label.pack(side=tk.LEFT)

        self.theme_var = tk.StringVar(value="dark")
        theme_dropdown = ctk.CTkOptionMenu(
            theme_frame,
            values=["Oscuro", "Claro"],
            variable=self.theme_var,
            command=self.change_theme,
        )
        theme_dropdown.pack(side=tk.LEFT, padx=10)

    def create_email_tab(self):
        """Crear pestaña de configuración de email simplificada."""
        email_frame = ctk.CTkFrame(self.notebook)
        self.notebook.add(email_frame, text="Email")

        # Título
        title_label = ctk.CTkLabel(
            email_frame, text="Configuración de Email", font=("Roboto", 16, "bold")
        )
        title_label.pack(pady=10)

        # Formulario de configuración
        form_frame = ctk.CTkFrame(email_frame, fg_color="transparent")
        form_frame.pack(fill=tk.X, padx=20, pady=10)

        # --- Campo Correo ---
        email_field_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        email_field_frame.pack(fill=tk.X, pady=5)
        email_label = ctk.CTkLabel(
            email_field_frame, text="Correo electrónico:", font=("Roboto", 12)
        )
        email_label.pack(side=tk.LEFT, padx=(0, 10))
        self.email_var = tk.StringVar()
        email_entry = ctk.CTkEntry(email_field_frame, textvariable=self.email_var)
        email_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # --- Campo Contraseña ---
        pass_field_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        pass_field_frame.pack(fill=tk.X, pady=5)
        pass_label = ctk.CTkLabel(
            pass_field_frame, text="Contraseña:", font=("Roboto", 12)
        )
        pass_label.pack(side=tk.LEFT, padx=(0, 45))  # Ajustar padding para alinear
        self.email_password_var = tk.StringVar()
        pass_entry = ctk.CTkEntry(
            pass_field_frame, textvariable=self.email_password_var, show="*"
        )
        pass_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # --- Mensaje informativo ---
        info_label = ctk.CTkLabel(
            email_frame,
            text="La configuración del servidor (IMAP/SMTP) se detectará automáticamente\npara proveedores comunes (Gmail, Outlook, etc.).",
            font=("Roboto", 10),
            text_color="gray",
        )
        info_label.pack(pady=(10, 5))
        advanced_label = ctk.CTkLabel(
            email_frame,
            text="Si usas un proveedor diferente, configura manualmente desde el archivo config.json.",
            font=("Roboto", 10),
            text_color="gray",
        )
        advanced_label.pack(pady=(0, 20))

        # Botón de guardar
        save_button = ctk.CTkButton(
            email_frame,
            text="Guardar Configuración de Email",
            command=self.save_email_config_simplified,
        )
        save_button.pack(pady=10)

        # Cargar configuración existente si la hay
        self.load_existing_email_config()

    def load_existing_email_config(self):
        """Carga el correo existente en el campo, si está configurado."""
        try:
            # Usamos auth_manager para leer la config actual (puede estar encriptada)
            # Necesitamos un método en auth_manager o initial_setup para obtener solo la config de email
            # Por simplicidad ahora, asumimos que podemos leer el json directamente (requiere mejora)
            config_path = os.path.join("data", "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config_data = json.load(f)
                if config_data.get("email") and config_data["email"].get("email"):
                    # Necesitamos desencriptar para mostrar, pero aquí solo mostramos el email
                    # La contraseña no se muestra por seguridad.
                    self.email_var.set(config_data["email"].get("email", ""))
                    # self.email_password_var no se setea por seguridad
        except Exception as e:
            print(
                f"Error al cargar config de email existente: {e}"
            )  # Usar logger sería mejor

    def save_email_config_simplified(self):
        """Guarda la configuración de email (correo y contraseña) e infiere el resto."""
        email = self.email_var.get().strip()
        password = self.email_password_var.get()  # No hacer strip a la contraseña

        if not email or "@" not in email:
            messagebox.showerror(
                "Error", "Por favor, ingresa una dirección de correo válida."
            )
            return

        if not password:
            messagebox.showwarning(
                "Advertencia", "La contraseña está vacía. ¿Estás seguro?"
            )
            # No retornamos, permitimos guardar contraseña vacía si el usuario insiste

        inferred_config = infer_email_config(email)

        if inferred_config:
            full_config = {
                "email": email,
                "password": password,  # La contraseña se encriptará en auth_manager
                "server": inferred_config["server"],
                "port": inferred_config["port"],
                "use_ssl": inferred_config["use_ssl"],
                "smtp_server": inferred_config["smtp_server"],
                "smtp_port": inferred_config["smtp_port"],
            }

            try:
                # Llama a auth_manager para guardar (necesitaría un método update_service_config)
                # Suponiendo que tenemos acceso a initial_setup o similar para guardar:
                from src.utils.initial_setup import InitialSetup

                setup = InitialSetup()
                setup.load_or_setup_encryption_key()  # Asegurar que la clave esté cargada

                # Encriptar la contraseña antes de guardarla en el objeto config
                encrypted_password = setup.encrypt_data(password)
                if encrypted_password:
                    full_config["password"] = encrypted_password
                else:
                    messagebox.showerror(
                        "Error de Encriptación", "No se pudo encriptar la contraseña."
                    )
                    return

                # Actualizar la configuración completa del email
                setup.config["email"] = full_config
                setup.save_config()  # Guardar el archivo JSON
                messagebox.showinfo(
                    "Éxito", "Configuración de email guardada correctamente."
                )

            except Exception as e:
                messagebox.showerror(
                    "Error al Guardar", f"No se pudo guardar la configuración: {e}"
                )

        else:
            messagebox.showerror(
                "Error",
                f"No se pudo detectar automáticamente la configuración para {email}.\n"
                + "Por favor, configura manualmente editando el archivo 'data/config.json'.",
            )

    def create_whatsapp_tab(self):
        """Crear pestaña de configuración de WhatsApp."""
        whatsapp_frame = ctk.CTkFrame(self.notebook)
        self.notebook.add(whatsapp_frame, text="WhatsApp")

        # Título
        title_label = ctk.CTkLabel(
            whatsapp_frame,
            text="Configuración de WhatsApp",
            font=("Roboto", 16, "bold"),
        )
        title_label.pack(pady=10)

        # Formulario de configuración
        form_frame = ctk.CTkFrame(whatsapp_frame, fg_color="transparent")
        form_frame.pack(fill=tk.X, padx=20, pady=10)

        # Campos del formulario
        fields = [("Número de teléfono:", "phone"), ("API Key:", "api_key")]

        self.whatsapp_vars = {}
        for label_text, field_name in fields:
            field_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
            field_frame.pack(fill=tk.X, pady=5)

            label = ctk.CTkLabel(field_frame, text=label_text, font=("Roboto", 12))
            label.pack(side=tk.LEFT)

            var = tk.StringVar()
            self.whatsapp_vars[field_name] = var

            if field_name == "api_key":
                entry = ctk.CTkEntry(field_frame, textvariable=var, show="*")
            else:
                entry = ctk.CTkEntry(field_frame, textvariable=var)
            entry.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

        # Botón de guardar
        save_button = ctk.CTkButton(
            whatsapp_frame,
            text="Guardar Configuración",
            command=self.save_whatsapp_config,
        )
        save_button.pack(pady=20)

    def create_tms_tab(self):
        """Crear pestaña de configuración de TMS."""
        tms_frame = ctk.CTkFrame(self.notebook)
        self.notebook.add(tms_frame, text="TMS")

        # Título
        title_label = ctk.CTkLabel(
            tms_frame, text="Configuración de TMS", font=("Roboto", 16, "bold")
        )
        title_label.pack(pady=10)

        # Formulario de configuración
        form_frame = ctk.CTkFrame(tms_frame, fg_color="transparent")
        form_frame.pack(fill=tk.X, padx=20, pady=10)

        # Campos del formulario
        fields = [
            ("URL del TMS:", "url"),
            ("Usuario:", "username"),
            ("Contraseña:", "password"),
            ("API Key:", "api_key"),
        ]

        self.tms_vars = {}
        for label_text, field_name in fields:
            field_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
            field_frame.pack(fill=tk.X, pady=5)

            label = ctk.CTkLabel(field_frame, text=label_text, font=("Roboto", 12))
            label.pack(side=tk.LEFT)

            var = tk.StringVar()
            self.tms_vars[field_name] = var

            if field_name in ["password", "api_key"]:
                entry = ctk.CTkEntry(field_frame, textvariable=var, show="*")
            else:
                entry = ctk.CTkEntry(field_frame, textvariable=var)
            entry.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

        # Botón de guardar
        save_button = ctk.CTkButton(
            tms_frame, text="Guardar Configuración", command=self.save_tms_config
        )
        save_button.pack(pady=20)

    def create_notifications_tab(self):
        """Crear pestaña de configuración de notificaciones."""
        notifications_frame = ctk.CTkFrame(self.notebook)
        self.notebook.add(notifications_frame, text="Notificaciones")

        # Título
        title_label = ctk.CTkLabel(
            notifications_frame,
            text="Configuración de Notificaciones",
            font=("Roboto", 16, "bold"),
        )
        title_label.pack(pady=10)

        # Opciones de notificación
        options_frame = ctk.CTkFrame(notifications_frame, fg_color="transparent")
        options_frame.pack(fill=tk.X, padx=20, pady=10)

        # Variables de control
        self.notification_vars = {
            "email": tk.BooleanVar(value=True),
            "whatsapp": tk.BooleanVar(value=True),
            "desktop": tk.BooleanVar(value=True),
            "sound": tk.BooleanVar(value=True),
        }

        # Checkboxes
        for label_text, var in self.notification_vars.items():
            checkbox = ctk.CTkCheckBox(
                options_frame, text=label_text.capitalize(), variable=var
            )
            checkbox.pack(pady=5, anchor="w")

        # Botón de guardar
        save_button = ctk.CTkButton(
            notifications_frame,
            text="Guardar Configuración",
            command=self.save_notifications_config,
        )
        save_button.pack(pady=20)

    def change_theme(self, theme):
        """Cambiar el tema de la aplicación."""
        theme = theme.lower()
        ctk.set_appearance_mode(theme)

    def save_whatsapp_config(self):
        """Guardar la configuración de WhatsApp."""
        config = {
            "phone": self.whatsapp_vars["phone"].get(),
            "api_key": self.whatsapp_vars["api_key"].get(),
        }
        self.auth_manager.update_credentials("whatsapp", config)

    def save_tms_config(self):
        """Guardar la configuración de TMS."""
        config = {
            "url": self.tms_vars["url"].get(),
            "username": self.tms_vars["username"].get(),
            "password": self.tms_vars["password"].get(),
            "api_key": self.tms_vars["api_key"].get(),
        }
        self.auth_manager.update_credentials("tms", config)

    def save_notifications_config(self):
        """Guardar la configuración de notificaciones."""
        config = {
            "email": self.notification_vars["email"].get(),
            "whatsapp": self.notification_vars["whatsapp"].get(),
            "desktop": self.notification_vars["desktop"].get(),
            "sound": self.notification_vars["sound"].get(),
        }
        # Guardar configuración en archivo
        with open("config/notifications.json", "w") as f:
            import json

            json.dump(config, f)

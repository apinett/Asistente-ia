import customtkinter as ctk
from tkinter import ttk
import tkinter as tk
from datetime import datetime, timedelta


class Dashboard(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.parent = parent
        self.create_widgets()

    def create_widgets(self):
        """Crear los widgets del dashboard."""
        # Grid principal
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Widgets principales
        self.create_status_cards()
        self.create_shipment_timeline()
        self.create_metrics_chart()
        self.create_alerts_panel()

    def create_status_cards(self):
        """Crear tarjetas de estado."""
        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.grid(
            row=0, column=0, columnspan=2, padx=10, pady=10, sticky="nsew"
        )

        # Configurar grid para las tarjetas
        status_frame.grid_columnconfigure(0, weight=1)
        status_frame.grid_columnconfigure(1, weight=1)
        status_frame.grid_columnconfigure(2, weight=1)
        status_frame.grid_columnconfigure(3, weight=1)

        # Tarjetas de estado
        self.status_cards = {
            "En Ruta": self.create_status_card(status_frame, "En Ruta", "12", 0),
            "En Almacén": self.create_status_card(status_frame, "En Almacén", "8", 1),
            "Entregado": self.create_status_card(status_frame, "Entregado", "15", 2),
            "Retrasado": self.create_status_card(status_frame, "Retrasado", "3", 3),
        }

    def create_status_card(self, parent, title, value, column):
        """Crear una tarjeta de estado individual."""
        card = ctk.CTkFrame(parent, height=120)
        card.grid(row=0, column=column, padx=5, pady=5, sticky="nsew")

        # Título
        title_label = ctk.CTkLabel(card, text=title, font=("Roboto", 14, "bold"))
        title_label.pack(pady=(10, 5))

        # Valor
        value_label = ctk.CTkLabel(card, text=value, font=("Roboto", 24, "bold"))
        value_label.pack(pady=5)

        return card

    def create_shipment_timeline(self):
        """Crear línea de tiempo de envíos."""
        timeline_frame = ctk.CTkFrame(self)
        timeline_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # Título
        timeline_title = ctk.CTkLabel(
            timeline_frame,
            text="Línea de Tiempo de Envíos",
            font=("Roboto", 16, "bold"),
        )
        timeline_title.pack(pady=10)

        # Lista de envíos
        self.shipment_list = ttk.Treeview(
            timeline_frame,
            columns=("ID", "Origen", "Destino", "Estado", "ETA"),
            show="headings",
            height=8,
        )

        # Configurar columnas
        self.shipment_list.heading("ID", text="ID")
        self.shipment_list.heading("Origen", text="Origen")
        self.shipment_list.heading("Destino", text="Destino")
        self.shipment_list.heading("Estado", text="Estado")
        self.shipment_list.heading("ETA", text="ETA")

        # Ajustar anchos
        self.shipment_list.column("ID", width=80)
        self.shipment_list.column("Origen", width=150)
        self.shipment_list.column("Destino", width=150)
        self.shipment_list.column("Estado", width=100)
        self.shipment_list.column("ETA", width=120)

        self.shipment_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Agregar datos de ejemplo
        self.add_sample_shipments()

    def create_metrics_chart(self):
        """Crear gráfico de métricas."""
        metrics_frame = ctk.CTkFrame(self)
        metrics_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

        # Título
        metrics_title = ctk.CTkLabel(
            metrics_frame, text="Métricas de Rendimiento", font=("Roboto", 16, "bold")
        )
        metrics_title.pack(pady=10)

        # Gráfico (placeholder)
        chart_placeholder = ctk.CTkLabel(
            metrics_frame, text="Gráfico de Métricas", font=("Roboto", 14)
        )
        chart_placeholder.pack(expand=True)

    def create_alerts_panel(self):
        """Crear panel de alertas."""
        alerts_frame = ctk.CTkFrame(self)
        alerts_frame.grid(
            row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew"
        )

        # Título
        alerts_title = ctk.CTkLabel(
            alerts_frame, text="Alertas y Notificaciones", font=("Roboto", 16, "bold")
        )
        alerts_title.pack(pady=10)

        # Lista de alertas
        self.alerts_list = ttk.Treeview(
            alerts_frame,
            columns=("Tipo", "Mensaje", "Fecha"),
            show="headings",
            height=4,
        )

        # Configurar columnas
        self.alerts_list.heading("Tipo", text="Tipo")
        self.alerts_list.heading("Mensaje", text="Mensaje")
        self.alerts_list.heading("Fecha", text="Fecha")

        # Ajustar anchos
        self.alerts_list.column("Tipo", width=100)
        self.alerts_list.column("Mensaje", width=300)
        self.alerts_list.column("Fecha", width=150)

        self.alerts_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Agregar alertas de ejemplo
        self.add_sample_alerts()

    def add_sample_shipments(self):
        """Agregar envíos de ejemplo a la lista."""
        sample_shipments = [
            ("TRK001", "CDMX", "Monterrey", "En Ruta", "2024-03-15 14:00"),
            ("TRK002", "Guadalajara", "Tijuana", "En Almacén", "2024-03-16 09:00"),
            ("TRK003", "Mérida", "Cancún", "Entregado", "2024-03-14 16:30"),
            ("TRK004", "Puebla", "Querétaro", "Retrasado", "2024-03-15 18:00"),
        ]

        for shipment in sample_shipments:
            self.shipment_list.insert("", tk.END, values=shipment)

    def add_sample_alerts(self):
        """Agregar alertas de ejemplo a la lista."""
        sample_alerts = [
            (
                "Retraso",
                "Envío TRK004 retrasado por condiciones climáticas",
                "2024-03-14 15:30",
            ),
            (
                "Alerta",
                "Bajo nivel de combustible en unidad TRK001",
                "2024-03-14 16:45",
            ),
            ("Información", "Nuevo envío programado para mañana", "2024-03-14 17:20"),
        ]

        for alert in sample_alerts:
            self.alerts_list.insert("", tk.END, values=alert)

import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import winreg
from pathlib import Path

class InstallerGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Instalador de Asistente IA")
        self.root.geometry("600x400")
        self.root.resizable(False, False)
        
        # Estilo
        style = ttk.Style()
        style.configure("TButton", padding=6, relief="flat", background="#2196F3")
        style.configure("TLabel", padding=6)
        
        self.create_widgets()
        
    def create_widgets(self):
        # Título
        title = ttk.Label(
            self.root,
            text="Instalador de Asistente IA",
            font=("Helvetica", 16, "bold")
        )
        title.pack(pady=20)
        
        # Descripción
        description = ttk.Label(
            self.root,
            text="Este asistente te ayudará a configurar el Asistente IA en tu computadora.",
            wraplength=500
        )
        description.pack(pady=10)
        
        # Frame para los pasos
        steps_frame = ttk.Frame(self.root)
        steps_frame.pack(pady=20, padx=20, fill="x")
        
        # Pasos de instalación
        self.steps = [
            "1. Verificar requisitos del sistema",
            "2. Instalar dependencias",
            "3. Configurar credenciales",
            "4. Crear acceso directo",
            "5. Finalizar instalación"
        ]
        
        self.current_step = 0
        self.step_labels = []
        
        for i, step in enumerate(self.steps):
            label = ttk.Label(
                steps_frame,
                text=step,
                font=("Helvetica", 10)
            )
            label.pack(anchor="w", pady=5)
            self.step_labels.append(label)
        
        # Botones
        button_frame = ttk.Frame(self.root)
        button_frame.pack(side="bottom", pady=20)
        
        self.back_button = ttk.Button(
            button_frame,
            text="Atrás",
            command=self.previous_step,
            state="disabled"
        )
        self.back_button.pack(side="left", padx=5)
        
        self.next_button = ttk.Button(
            button_frame,
            text="Siguiente",
            command=self.next_step
        )
        self.next_button.pack(side="left", padx=5)
        
        self.cancel_button = ttk.Button(
            button_frame,
            text="Cancelar",
            command=self.cancel_installation
        )
        self.cancel_button.pack(side="left", padx=5)
        
        # Barra de progreso
        self.progress = ttk.Progressbar(
            self.root,
            orient="horizontal",
            length=400,
            mode="determinate"
        )
        self.progress.pack(pady=20)
        
        # Etiqueta de estado
        self.status_label = ttk.Label(
            self.root,
            text="",
            wraplength=500
        )
        self.status_label.pack(pady=5)
        
        self.update_progress()
        
    def update_progress(self):
        progress = (self.current_step / (len(self.steps) - 1)) * 100
        self.progress["value"] = progress
        
        # Actualizar estado de los pasos
        for i, label in enumerate(self.step_labels):
            if i < self.current_step:
                label.configure(text=f"✓ {self.steps[i]}")
            elif i == self.current_step:
                label.configure(text=f"→ {self.steps[i]}")
            else:
                label.configure(text=self.steps[i])
    
    def check_system_requirements(self):
        """Verificar requisitos del sistema."""
        try:
            # Verificar versión de Python
            python_version = sys.version_info
            if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
                messagebox.showerror(
                    "Error",
                    "Se requiere Python 3.8 o superior"
                )
                return False
            
            # Verificar espacio en disco
            free_space = self.get_free_space()
            if free_space < 500:  # 500 MB mínimo
                messagebox.showerror(
                    "Error",
                    "Se requiere al menos 500 MB de espacio libre"
                )
                return False
            
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Error al verificar requisitos: {str(e)}")
            return False
    
    def install_dependencies(self):
        """Instalar dependencias desde requirements.txt."""
        try:
            self.status_label.configure(text="Actualizando pip...")
            self.root.update()
            
            # Actualizar pip primero
            subprocess.check_call([
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "pip"
            ])
            
            # Instalar setuptools y wheel primero
            self.status_label.configure(text="Instalando setuptools y wheel...")
            self.root.update()
            
            subprocess.check_call([
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "setuptools",
                "wheel"
            ])
            
            self.status_label.configure(text="Instalando dependencias...")
            self.root.update()
            
            # Instalar dependencias una por una
            with open("requirements.txt", "r") as f:
                dependencies = f.readlines()
            
            for dep in dependencies:
                dep = dep.strip()
                if dep and not dep.startswith("#"):
                    self.status_label.configure(text=f"Instalando {dep}...")
                    self.root.update()
                    
                    try:
                        # Usar --no-deps para evitar conflictos de dependencias
                        subprocess.check_call([
                            sys.executable,
                            "-m",
                            "pip",
                            "install",
                            "--no-cache-dir",
                            "--no-deps",
                            dep
                        ])
                    except subprocess.CalledProcessError as e:
                        messagebox.showerror(
                            "Error",
                            f"Error al instalar {dep}: {str(e)}\n"
                            "Por favor, intenta instalar manualmente las dependencias."
                        )
                        return False
            
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Error al instalar dependencias: {str(e)}")
            return False
    
    def create_shortcut(self):
        """Crear acceso directo en el escritorio."""
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            shortcut_path = os.path.join(desktop, "Asistente IA.lnk")
            
            # Crear acceso directo usando PowerShell
            ps_script = f'''
            $WshShell = New-Object -comObject WScript.Shell
            $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
            $Shortcut.TargetPath = "{os.path.abspath("main.exe")}"
            $Shortcut.WorkingDirectory = "{os.path.dirname(os.path.abspath("main.exe"))}"
            $Shortcut.Save()
            '''
            
            subprocess.run(["powershell", "-Command", ps_script], check=True)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Error al crear acceso directo: {str(e)}")
            return False
    
    def get_free_space(self):
        """Obtener espacio libre en disco en MB."""
        path = os.path.abspath(os.sep)
        free_bytes = os.statvfs(path).f_bfree * os.statvfs(path).f_bsize
        return free_bytes / (1024 * 1024)  # Convertir a MB
    
    def next_step(self):
        """Avanzar al siguiente paso de la instalación."""
        if self.current_step == 0:
            if not self.check_system_requirements():
                return
        elif self.current_step == 1:
            if not self.install_dependencies():
                return
        elif self.current_step == 3:
            if not self.create_shortcut():
                return
        
        self.current_step += 1
        self.update_progress()
        
        if self.current_step >= len(self.steps) - 1:
            self.next_button.configure(text="Finalizar")
        elif self.current_step > 0:
            self.back_button.configure(state="normal")
        
        if self.current_step >= len(self.steps):
            self.finish_installation()
    
    def previous_step(self):
        """Retroceder al paso anterior."""
        if self.current_step > 0:
            self.current_step -= 1
            self.update_progress()
            
            if self.current_step == 0:
                self.back_button.configure(state="disabled")
            if self.current_step < len(self.steps) - 1:
                self.next_button.configure(text="Siguiente")
    
    def cancel_installation(self):
        """Cancelar la instalación."""
        if messagebox.askyesno("Confirmar", "¿Estás seguro de que deseas cancelar la instalación?"):
            self.root.quit()
    
    def finish_installation(self):
        """Finalizar la instalación."""
        messagebox.showinfo(
            "Instalación Completada",
            "El Asistente IA ha sido instalado exitosamente.\n"
            "Puedes encontrarlo en el escritorio como 'Asistente IA'."
        )
        self.root.quit()
    
    def run(self):
        """Ejecutar el instalador."""
        self.root.mainloop()

if __name__ == "__main__":
    installer = InstallerGUI()
    installer.run() 
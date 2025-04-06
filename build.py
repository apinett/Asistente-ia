import os
import sys
import shutil
import subprocess
from pathlib import Path

def build_executable():
    """Generar el ejecutable del asistente."""
    print("Iniciando proceso de construcción...")
    
    # Verificar que PyInstaller está instalado
    try:
        import PyInstaller
    except ImportError:
        print("Instalando PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Crear directorio de distribución si no existe
    dist_dir = Path("dist")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir()
    
    # Configurar opciones de PyInstaller
    options = [
        "pyinstaller",
        "--name=AsistenteIA",
        "--onefile",
        "--windowed",
        "--icon=assets/icon.ico",  # Asegúrate de tener un ícono
        "--add-data=requirements.txt;.",
        "--add-data=README.md;.",
        "--add-data=config;config",
        "--add-data=src;src",
        "--hidden-import=sklearn.utils._cython_blas",
        "--hidden-import=sklearn.neighbors.typedefs",
        "--hidden-import=sklearn.neighbors.quad_tree",
        "--hidden-import=sklearn.tree._utils",
        "--hidden-import=sklearn.tree._splitter",
        "--hidden-import=sklearn.utils._typedefs",
        "main.py"
    ]
    
    # Ejecutar PyInstaller
    print("Generando ejecutable...")
    subprocess.check_call(options)
    
    # Copiar archivos adicionales
    print("Copiando archivos adicionales...")
    shutil.copy("requirements.txt", dist_dir / "AsistenteIA")
    shutil.copy("README.md", dist_dir / "AsistenteIA")
    
    # Crear directorio de configuración
    config_dir = dist_dir / "AsistenteIA" / "config"
    config_dir.mkdir(exist_ok=True)
    
    # Crear archivo de configuración inicial
    initial_config = {
        "voice_enabled": True,
        "language": "es-ES",
        "learning_rate": 0.1,
        "max_history": 1000,
        "tasks": {
            "email": True,
            "whatsapp": True,
            "tms": True
        }
    }
    
    import json
    with open(config_dir / "assistant_config.json", "w", encoding="utf-8") as f:
        json.dump(initial_config, f, indent=4)
    
    print("\n¡Construcción completada!")
    print(f"El ejecutable se encuentra en: {dist_dir / 'AsistenteIA' / 'AsistenteIA.exe'}")

if __name__ == "__main__":
    build_executable() 
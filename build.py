import os
import sys
import shutil
import time
from pathlib import Path

# Verificar e instalar PyInstaller si es necesario
try:
    import PyInstaller.__main__
except ImportError:
    print("PyInstaller no está instalado. Instalando...")
    os.system(f"{sys.executable} -m pip install pyinstaller")
    import PyInstaller.__main__

def clean_dist():
    """Limpiar directorios de construcción anteriores."""
    dirs_to_clean = ['build', 'dist']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            try:
                # Intentar eliminar el directorio
                shutil.rmtree(dir_name)
            except PermissionError:
                print(f"\nAdvertencia: No se pudo eliminar {dir_name} debido a permisos.")
                print("Intentando forzar la eliminación...")
                
                # Intentar cambiar permisos
                try:
                    import stat
                    def remove_readonly(func, path, _):
                        os.chmod(path, stat.S_IWRITE)
                        func(path)
                    
                    shutil.rmtree(dir_name, onerror=remove_readonly)
                    print(f"Directorio {dir_name} eliminado exitosamente.")
                except Exception as e:
                    print(f"Error al forzar la eliminación de {dir_name}: {e}")
                    print("\nPor favor, sigue estos pasos:")
                    print("1. Cierra todos los programas que puedan estar usando estos archivos")
                    print("2. Abre el Administrador de tareas (Ctrl+Shift+Esc)")
                    print("3. Busca y cierra cualquier proceso de Python")
                    print("4. Intenta eliminar manualmente los directorios:")
                    print("   - build")
                    print("   - dist")
                    print("5. Vuelve a ejecutar el script")
                    sys.exit(1)
            except Exception as e:
                print(f"Error al eliminar {dir_name}: {e}")
                sys.exit(1)
    
    # Eliminar archivo spec si existe
    spec_file = 'main.spec'
    if os.path.exists(spec_file):
        try:
            os.remove(spec_file)
        except PermissionError:
            print(f"\nAdvertencia: No se pudo eliminar {spec_file} debido a permisos.")
            try:
                import stat
                os.chmod(spec_file, stat.S_IWRITE)
                os.remove(spec_file)
                print(f"Archivo {spec_file} eliminado exitosamente.")
            except Exception as e:
                print(f"Error al forzar la eliminación de {spec_file}: {e}")
                print("\nPor favor, elimina manualmente el archivo main.spec y vuelve a intentarlo.")
                sys.exit(1)
        except Exception as e:
            print(f"Error al eliminar {spec_file}: {e}")
            sys.exit(1)

def create_version_file():
    """Crear archivo de versión para el ejecutable."""
    try:
        version_info = '''
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'Tu Empresa'),
         StringStruct(u'FileDescription', u'Asistente IA Local'),
         StringStruct(u'FileVersion', u'1.0.0'),
         StringStruct(u'InternalName', u'assistant'),
         StringStruct(u'LegalCopyright', u'(c) 2024 Tu Empresa. Todos los derechos reservados.'),
         StringStruct(u'OriginalFilename', u'AsistenteIA.exe'),
         StringStruct(u'ProductName', u'Asistente IA Local'),
         StringStruct(u'ProductVersion', u'1.0.0')])
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
'''
        # Guardar el archivo con codificación UTF-8
        with open('version_info.txt', 'w', encoding='utf-8') as f:
            f.write(version_info)
    except Exception as e:
        print(f"Error al crear archivo de versión: {e}")
        sys.exit(1)

def build_executable():
    """Construir el ejecutable con configuraciones optimizadas."""
    try:
        # Verificar que las dependencias estén instaladas
        required_packages = [
            'webdriver_manager',
            'numpy',
            'pandas',
            'scikit-learn',
            'pyttsx3',
            'SpeechRecognition',
            'python-dotenv',
            'openai',
            'selenium',
            'cryptography',
            'pillow',
            'keyboard',
            'imap-tools',
            'pyautogui'
        ]
        
        print("Verificando dependencias...")
        for package in required_packages:
            try:
                if package == 'python-dotenv':
                    __import__('dotenv')
                elif package == 'imap-tools':
                    __import__('imap_tools')
                else:
                    __import__(package)
                print(f"✓ {package} encontrado")
            except ImportError:
                print(f"Instalando {package}...")
                os.system(f"{sys.executable} -m pip install {package}")
        
        # Configurar la codificación para PyInstaller
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        
        # Verificar si existe el directorio assets
        if not os.path.exists('assets'):
            os.makedirs('assets')
        
        # Verificar si existe el icono
        icon_path = 'assets/icon.ico'
        if not os.path.exists(icon_path):
            print("Icono no encontrado. Creando icono por defecto...")
            try:
                from PIL import Image, ImageDraw
                # Crear una imagen simple
                img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                # Dibujar un círculo
                draw.ellipse([(50, 50), (206, 206)], fill=(0, 120, 212))
                # Guardar como .ico
                img.save(icon_path, format='ICO')
                print("Icono creado exitosamente.")
            except ImportError:
                print("Pillow no está instalado. Instalando...")
                os.system(f"{sys.executable} -m pip install pillow")
                from PIL import Image, ImageDraw
                img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                draw.ellipse([(50, 50), (206, 206)], fill=(0, 120, 212))
                img.save(icon_path, format='ICO')
                print("Icono creado exitosamente.")
            except Exception as e:
                print(f"Error al crear el icono: {e}")
                print("Continuando sin icono...")
                icon_path = None
        
        # Construir el ejecutable
        pyinstaller_args = [
            'main.py',
            '--name=AsistenteIA',
            '--onefile',
            '--windowed',
            '--clean',
            '--uac-admin',
            '--version-file=version_info.txt',
            '--add-binary=data;data',
            '--hidden-import=selenium',
            '--hidden-import=webdriver_manager',
            '--hidden-import=cryptography',
            '--hidden-import=numpy',
            '--hidden-import=pandas',
            '--hidden-import=scikit-learn',
            '--hidden-import=pyttsx3',
            '--hidden-import=SpeechRecognition',
            '--hidden-import=dotenv',
            '--hidden-import=openai',
            '--hidden-import=keyboard',
            '--hidden-import=imap_tools',
            '--hidden-import=pyautogui',
            '--exclude-module=matplotlib',
            '--exclude-module=jupyter',
            '--exclude-module=tkinter',
            '--exclude-module=qt5',
            '--exclude-module=sqlite3',
            '--noupx',
            '--log-level=DEBUG'
        ]
        
        if icon_path and os.path.exists(icon_path):
            pyinstaller_args.append(f'--icon={icon_path}')
        
        PyInstaller.__main__.run(pyinstaller_args)
    except Exception as e:
        print(f"Error al construir el ejecutable: {e}")
        print("\nSugerencias para resolver el problema:")
        print("1. Asegúrate de que todas las dependencias estén instaladas:")
        print("   pip install webdriver_manager numpy pandas scikit-learn pillow pyttsx3 SpeechRecognition python-dotenv openai selenium cryptography keyboard imap-tools pyautogui")
        print("2. Verifica que no haya caracteres especiales en los nombres de archivo")
        print("3. Intenta ejecutar el script como administrador")
        print("4. Si el problema persiste, intenta:")
        print("   - Eliminar manualmente los directorios build y dist")
        print("   - Reiniciar tu computadora")
        print("   - Volver a instalar Python y las dependencias")
        sys.exit(1)

def sign_executable():
    """Firmar el ejecutable (requiere certificado)."""
    try:
        import win32api
        cert_path = os.environ.get('CODE_SIGNING_CERT')
        if cert_path and os.path.exists(cert_path):
            win32api.SignFile(
                'dist/AsistenteIA.exe',
                cert_path,
                os.environ.get('CERT_PASSWORD', ''),
                'sha256'
            )
    except ImportError:
        print("La firma del ejecutable requiere pywin32")
    except Exception as e:
        print(f"Error al firmar el ejecutable: {e}")

def main():
    """Proceso principal de construcción."""
    print("Iniciando proceso de construcción...")
    
    # Verificar procesos de Python
    try:
        import psutil
        current_pid = os.getpid()  # Obtener el PID del proceso actual
        python_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Verificar si es un proceso de Python
                if 'python' in proc.info['name'].lower():
                    # Obtener la línea de comandos del proceso
                    cmdline = proc.info['cmdline']
                    if cmdline:  # Asegurarse de que cmdline no sea None
                        # Ignorar el proceso actual y los procesos del sistema
                        if proc.info['pid'] != current_pid and not any(x in cmdline[0] for x in ['pythonw.exe', 'python.exe']):
                            python_processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        if python_processes:
            print("\nProcesos de Python encontrados:")
            for proc in python_processes:
                try:
                    print(f"- PID: {proc.info['pid']}, Comando: {' '.join(proc.info['cmdline'])}")
                except:
                    print(f"- PID: {proc.info['pid']}")
            print("\nPor favor, cierra estos procesos y vuelve a intentarlo.")
            sys.exit(1)
    except ImportError:
        print("Instalando psutil...")
        os.system(f"{sys.executable} -m pip install psutil")
        import psutil
    
    # Limpiar construcciones anteriores
    print("Limpiando directorios anteriores...")
    clean_dist()
    
    # Crear archivo de versión
    print("Creando archivo de versión...")
    create_version_file()
    
    # Construir ejecutable
    print("Construyendo ejecutable...")
    build_executable()
    
    # Intentar firmar el ejecutable
    print("Intentando firmar el ejecutable...")
    sign_executable()
    
    # Limpiar archivos temporales
    if os.path.exists('version_info.txt'):
        try:
            os.remove('version_info.txt')
        except Exception as e:
            print(f"Error al eliminar archivo de versión: {e}")
    
    print("Construcción completada.")
    print("El ejecutable se encuentra en: dist/AsistenteIA.exe")

if __name__ == '__main__':
    main() 
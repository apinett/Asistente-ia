# Instalación del Asistente IA

## Requisitos del Sistema

- Windows 10 o superior
- Python 3.8 o superior (si se instala desde el código fuente)
- Mínimo 500 MB de espacio libre en disco
- Conexión a Internet para la instalación de dependencias

## Instalación desde el Ejecutable

1. Descarga el archivo `AsistenteIA_Setup.exe` desde el repositorio
2. Ejecuta el instalador haciendo doble clic
3. Sigue los pasos del asistente de instalación:
   - Verificación de requisitos del sistema
   - Instalación de dependencias
   - Configuración de credenciales
   - Creación de acceso directo
4. Al finalizar, encontrarás un acceso directo en el escritorio

## Instalación desde el Código Fuente

1. Clona el repositorio:

```bash
git clone https://github.com/tu-usuario/AsistenteIA.git
cd AsistenteIA
```

2. Instala las dependencias:

```bash
pip install -r requirements.txt
```

3. Ejecuta el instalador:

```bash
python installer.py
```

4. Sigue los pasos del asistente de instalación

## Generación del Ejecutable

Para generar el ejecutable desde el código fuente:

1. Asegúrate de tener todas las dependencias instaladas
2. Ejecuta el script de construcción:

```bash
python build.py
```

3. El ejecutable se generará en la carpeta `dist/AsistenteIA/`

## Solución de Problemas

### Problemas Comunes

1. **Error de permisos**

   - Ejecuta el instalador como administrador
   - Asegúrate de tener permisos de escritura en la carpeta de instalación

2. **Error de dependencias**

   - Verifica tu conexión a Internet
   - Intenta ejecutar `pip install --upgrade pip` antes de la instalación

3. **Error de Python**
   - Asegúrate de tener Python 3.8 o superior instalado
   - Verifica que Python está en el PATH del sistema

### Soporte

Si encuentras algún problema durante la instalación, por favor:

1. Revisa el archivo de log en `logs/installer.log`
2. Abre un issue en el repositorio con los detalles del error
3. Incluye la información de tu sistema operativo y versión de Python

## Desinstalación

1. Cierra el Asistente IA si está en ejecución
2. Elimina la carpeta de instalación (por defecto en `C:\Program Files\AsistenteIA`)
3. Elimina el acceso directo del escritorio
4. Elimina la carpeta de configuración en `%APPDATA%\AsistenteIA`

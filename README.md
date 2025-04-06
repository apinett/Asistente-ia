# Asistente IA Local

Un asistente de inteligencia artificial local que aprende de tus acciones y te ayuda con tareas repetitivas.

## Características

- Interfaz gráfica semi-transparente
- Aprendizaje automático de acciones
- Gestión de correos electrónicos
- Envío de mensajes por WhatsApp
- Integración con sistemas TMS
- Almacenamiento local de datos
- Aprendizaje adaptativo

## Requisitos del Sistema

- Python 3.8 o superior
- Windows 10/11
- 4GB de RAM mínimo
- 500MB de espacio en disco
- Conexión a internet para algunas funcionalidades

## Instalación

1. Clona el repositorio:

```bash
git clone https://github.com/tu-usuario/asistente-ia.git
cd asistente-ia
```

2. Crea un entorno virtual (opcional pero recomendado):

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. Instala las dependencias:

```bash
pip install -r requirements.txt
```

4. Ejecuta el asistente:

```bash
python main.py
```

## Uso

1. La ventana del asistente aparecerá en tu pantalla
2. Puedes arrastrarla a cualquier posición
3. Usa los botones para:
   - Grabar acciones (el asistente aprenderá lo que haces)
   - Activar el modo aprendizaje
   - Ver el historial de conversación

## Comandos Disponibles

- "enviar correo" o "enviar email"
- "leer correo" o "leer email"
- "enviar whatsapp"
- "leer whatsapp"
- "entrada tms"
- "consultar tms"
- "actualizar credenciales"
- "adiós", "hasta luego" o "salir" para terminar

## Seguridad

- Todas las credenciales se almacenan localmente y encriptadas
- No se envían datos a servidores externos
- El aprendizaje se realiza localmente

## Contribución

Las contribuciones son bienvenidas. Por favor, lee las [guías de contribución](CONTRIBUTING.md) para más detalles.

## Licencia

Este proyecto está licenciado bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para más detalles.

## Soporte

Si encuentras algún problema o tienes alguna pregunta, por favor abre un [issue](https://github.com/tu-usuario/asistente-ia/issues) en el repositorio.

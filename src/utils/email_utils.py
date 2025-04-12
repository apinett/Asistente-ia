import re
from typing import Dict, Optional

# Mapeo de dominios a configuraciones comunes (IMAP_Server, IMAP_Port, IMAP_SSL, SMTP_Server, SMTP_Port)
# Usamos puertos estándar: IMAP SSL 993, SMTP STARTTLS 587
COMMON_EMAIL_PROVIDERS = {
    "gmail.com": ("imap.gmail.com", 993, True, "smtp.gmail.com", 587),
    "googlemail.com": (
        "imap.gmail.com",
        993,
        True,
        "smtp.gmail.com",
        587,
    ),  # Alias de Gmail
    "outlook.com": ("outlook.office365.com", 993, True, "smtp.office365.com", 587),
    "hotmail.com": (
        "outlook.office365.com",
        993,
        True,
        "smtp.office365.com",
        587,
    ),  # Alias de Outlook
    "live.com": (
        "outlook.office365.com",
        993,
        True,
        "smtp.office365.com",
        587,
    ),  # Alias de Outlook
    "yahoo.com": ("imap.mail.yahoo.com", 993, True, "smtp.mail.yahoo.com", 587),
    "aol.com": ("imap.aol.com", 993, True, "smtp.aol.com", 587),
    "icloud.com": ("imap.mail.me.com", 993, True, "smtp.mail.me.com", 587),
    "mail.com": ("imap.mail.com", 993, True, "smtp.mail.com", 587),
    # Agrega más proveedores si es necesario
}


def infer_email_config(email: str) -> Optional[Dict[str, any]]:
    """
    Infiere la configuración del servidor IMAP y SMTP basado en el dominio
    del correo electrónico para proveedores comunes.
    Devuelve un diccionario con 'server', 'port', 'use_ssl', 'smtp_server', 'smtp_port' o None.
    """
    if not email or "@" not in email:
        return None  # Correo inválido

    match = re.search(r"@([\w.-]+)$", email)
    if not match:
        return None  # No se pudo extraer el dominio

    domain = match.group(1).lower()

    # Buscar en proveedores comunes
    if domain in COMMON_EMAIL_PROVIDERS:
        imap_server, imap_port, use_ssl, smtp_server, smtp_port = (
            COMMON_EMAIL_PROVIDERS[domain]
        )
        return {
            "server": imap_server,  # IMAP server
            "port": imap_port,  # IMAP port
            "use_ssl": use_ssl,  # Usar SSL para IMAP
            "smtp_server": smtp_server,  # SMTP server
            "smtp_port": smtp_port,  # SMTP port
        }

    # Si no es un proveedor conocido, devolvemos None
    return None


# Ejemplo de uso:
# config = infer_email_config("usuario@gmail.com")
# if config:
#     print(f"Configuración inferida: {config}")
# else:
#     print("No se pudo inferir la configuración para este proveedor.")

# config_fail = infer_email_config("usuario@dominio-raro.com")
# if not config_fail:
#     print("Correcto, no se pudo inferir para dominio-raro.com")

import os
import smtplib
import ssl
import re
from email.message import EmailMessage
from typing import List, Dict, Any, Optional
from imap_tools import MailBox, AND
from src.utils.logger import Logger


class EmailManager:
    def __init__(self, config: Dict[str, Any], logger: Optional[Logger] = None):
        """Inicializa el EmailManager con la configuración proporcionada."""
        self.config = config
        self.logger = logger if logger else Logger()
        self.mailbox = None

        # Extraer configuración necesaria
        self.email = self.config.get("email")
        self.password = self.config.get("password")
        self.imap_server = self.config.get("server")
        self.imap_port = self.config.get("port")
        self.imap_ssl = self.config.get("use_ssl", True)
        self.smtp_server = self.config.get("smtp_server")
        self.smtp_port = self.config.get("smtp_port")

        if not all(
            [
                self.email,
                self.password,
                self.imap_server,
                self.imap_port,
                self.smtp_server,
                self.smtp_port,
            ]
        ):
            self.logger.warning(
                "Configuración de correo incompleta. Faltan datos necesarios."
            )

    def connect(self) -> bool:
        """Conectar al servidor IMAP usando la configuración proporcionada."""
        if not self.email or not self.password or not self.imap_server:
            self.logger.error("Credenciales o servidor IMAP no configurados.")
            return False
        try:
            self.mailbox = MailBox(self.imap_server, self.imap_port)
            self.mailbox.login(self.email, self.password, initial_folder="INBOX")
            self.logger.info(
                f"Conexión IMAP exitosa a {self.imap_server} para {self.email}"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Error al conectar al servidor IMAP {self.imap_server}: {e}"
            )
            self.mailbox = None
            return False

    def disconnect(self):
        """Desconectar del servidor IMAP."""
        if self.mailbox:
            try:
                self.mailbox.logout()
                self.logger.info("Desconectado del servidor IMAP.")
            except Exception as e:
                self.logger.error(f"Error al desconectar del servidor IMAP: {e}")
            finally:
                self.mailbox = None

    def get_unread_emails(
        self, folder: str = "INBOX", limit: Optional[int] = 10
    ) -> List[Dict[str, Any]]:
        """Obtener correos no leídos de una carpeta específica."""
        if not self.mailbox:
            if not self.connect():
                return []

        emails_data = []
        try:
            self.mailbox.folder.set(folder)
            messages = self.mailbox.fetch(AND(seen=False), limit=limit, reverse=True)
            for msg in messages:
                emails_data.append(
                    {
                        "uid": msg.uid,
                        "subject": msg.subject,
                        "from": msg.from_,
                        "to": msg.to,
                        "date": msg.date,
                        "text": msg.text or msg.html,
                        "attachments": [att.filename for att in msg.attachments],
                    }
                )
            self.logger.info(
                f"Recuperados {len(emails_data)} correos no leídos de {folder}."
            )
        except Exception as e:
            self.logger.error(f"Error al obtener correos no leídos de {folder}: {e}")
        finally:
            pass
        return emails_data

    def search_emails(
        self, query: str, folder: str = "INBOX", limit: Optional[int] = 20
    ) -> List[Dict[str, Any]]:
        """Buscar correos por criterio (asunto, remitente, etc.)."""
        if not self.mailbox:
            if not self.connect():
                return []

        emails_data = []
        try:
            self.mailbox.folder.set(folder)
            criteria = f'(OR (FROM "{query}") (SUBJECT "{query}") (TEXT "{query}"))'
            messages = self.mailbox.fetch(query, limit=limit, reverse=True)
            for msg in messages:
                emails_data.append(
                    {
                        "uid": msg.uid,
                        "subject": msg.subject,
                        "from": msg.from_,
                        "to": msg.to,
                        "date": msg.date,
                        "text": msg.text or msg.html,
                        "attachments": [att.filename for att in msg.attachments],
                    }
                )
            self.logger.info(
                f"Encontrados {len(emails_data)} correos para la búsqueda '{query}' en {folder}."
            )
        except Exception as e:
            self.logger.error(f"Error al buscar correos en {folder}: {e}")
        finally:
            pass
        return emails_data

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Enviar un correo electrónico usando la configuración SMTP."""
        if not all([self.email, self.password, self.smtp_server, self.smtp_port]):
            self.logger.error(
                "Configuración SMTP incompleta. No se puede enviar correo."
            )
            return False

        message = EmailMessage()
        message["From"] = self.email
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        context = ssl.create_default_context()

        try:
            self.logger.info(
                f"Conectando al servidor SMTP {self.smtp_server}:{self.smtp_port}"
            )
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                self.logger.info(f"Iniciando sesión SMTP como {self.email}")
                server.login(self.email, self.password)
                self.logger.info(f"Enviando correo a {to_email}")
                server.send_message(message)
                self.logger.info("Correo enviado exitosamente.")
                return True
        except smtplib.SMTPAuthenticationError:
            self.logger.error(
                f"Error de autenticación SMTP para {self.email}. Verifica la contraseña o la configuración de 'apps menos seguras'."
            )
            return False
        except smtplib.SMTPServerDisconnected:
            self.logger.error(
                f"Servidor SMTP {self.smtp_server} desconectado inesperadamente."
            )
            return False
        except smtplib.SMTPConnectError as e:
            self.logger.error(
                f"Error al conectar al servidor SMTP {self.smtp_server}:{self.smtp_port}. {e}"
            )
            return False
        except ConnectionRefusedError:
            self.logger.error(
                f"Conexión rechazada por el servidor SMTP {self.smtp_server}:{self.smtp_port}."
            )
            return False
        except Exception as e:
            self.logger.error(f"Error inesperado al enviar correo: {e}")
            return False

    def handle_command(self, command: str) -> Optional[str]:
        """Procesar comandos relacionados con correo."""
        command = command.lower()
        response = None

        if "leer" in command and ("correo" in command or "email" in command):
            if "no leídos" in command:
                emails = self.get_unread_emails()
                if emails:
                    response = f"Tienes {len(emails)} correos no leídos. El más reciente es de {emails[0]['from']} con asunto: {emails[0]['subject']}."
                else:
                    response = "No tienes correos no leídos."
            else:
                response = "Función para leer todos los correos aún no implementada."

        elif ("buscar" in command or "encuentra" in command) and (
            "correo" in command or "email" in command
        ):
            try:
                parts = re.split(
                    r"buscar correo de |buscar correo sobre |buscar correo |buscar email de |buscar email sobre |buscar email ",
                    command,
                    maxsplit=1,
                )
                if len(parts) > 1 and parts[1]:
                    search_term = parts[1].strip()
                    emails = self.search_emails(search_term)
                    if emails:
                        response = f"Encontré {len(emails)} correos relacionados con '{search_term}'. El más reciente es de {emails[0]['from']} con asunto: {emails[0]['subject']}."
                    else:
                        response = (
                            f"No encontré correos relacionados con '{search_term}'."
                        )
                else:
                    response = "Por favor, especifica qué quieres buscar en el correo."
            except Exception as e:
                self.logger.error(
                    f"Error procesando comando de búsqueda de correo: {e}"
                )
                response = "Hubo un error al intentar buscar el correo."

        elif ("enviar" in command or "mandar" in command) and (
            "correo" in command or "email" in command
        ):
            try:
                to_match = re.search(r" a ([\w\.-]+@[\w\.-]+)", command)
                subject_match = re.search(r" asunto (.+?)(?: cuerpo |$)", command)
                body_match = re.search(r" cuerpo (.+)", command)

                if to_match and subject_match and body_match:
                    to_email = to_match.group(1)
                    subject = subject_match.group(1).strip()
                    body = body_match.group(1).strip()

                    self.logger.info(
                        f"Intentando enviar correo a {to_email} con asunto '{subject}'"
                    )
                    if self.send_email(to_email, subject, body):
                        response = f"Correo enviado a {to_email}."
                    else:
                        response = (
                            "Hubo un problema al enviar el correo. Revisa los logs."
                        )
                else:
                    response = "No pude entender todos los detalles para enviar el correo. Necesito destinatario, asunto y cuerpo."
            except Exception as e:
                self.logger.error(f"Error procesando comando de envío de correo: {e}")
                response = "Hubo un error al intentar enviar el correo."

        else:
            pass

        return response

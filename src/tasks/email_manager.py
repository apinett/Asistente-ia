import os
from typing import List, Dict, Any
from imap_tools import MailBox, AND
from ..utils.logger import get_logger

class EmailManager:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.mailbox = None
        self._load_credentials()
        
    def _load_credentials(self):
        """Cargar credenciales de correo desde variables de entorno."""
        self.email = os.getenv('EMAIL_USER')
        self.password = os.getenv('EMAIL_PASSWORD')
        self.imap_server = os.getenv('EMAIL_IMAP_SERVER', 'imap.gmail.com')
        
        if not all([self.email, self.password]):
            self.logger.warning("Credenciales de correo no encontradas")
    
    def connect(self) -> bool:
        """Conectar al servidor de correo."""
        try:
            self.mailbox = MailBox(self.imap_server).login(self.email, self.password)
            self.logger.info("Conexión exitosa al servidor de correo")
            return True
        except Exception as e:
            self.logger.error(f"Error al conectar al servidor de correo: {e}")
            return False
    
    def get_unread_emails(self, folder: str = 'INBOX') -> List[Dict[str, Any]]:
        """Obtener correos no leídos."""
        if not self.mailbox:
            if not self.connect():
                return []
                
        try:
            self.mailbox.folder.set(folder)
            messages = self.mailbox.fetch(AND(seen=False))
            return [{
                'subject': msg.subject,
                'from': msg.from_,
                'date': msg.date,
                'text': msg.text,
                'html': msg.html,
                'attachments': [att.filename for att in msg.attachments]
            } for msg in messages]
        except Exception as e:
            self.logger.error(f"Error al obtener correos no leídos: {e}")
            return []
    
    def search_emails(self, query: str, folder: str = 'INBOX') -> List[Dict[str, Any]]:
        """Buscar correos por criterio."""
        if not self.mailbox:
            if not self.connect():
                return []
                
        try:
            self.mailbox.folder.set(folder)
            messages = self.mailbox.fetch(AND(subject=query))
            return [{
                'subject': msg.subject,
                'from': msg.from_,
                'date': msg.date,
                'text': msg.text,
                'html': msg.html
            } for msg in messages]
        except Exception as e:
            self.logger.error(f"Error al buscar correos: {e}")
            return []
    
    def handle_command(self, command: str):
        """Procesar comandos relacionados con correo."""
        command = command.lower()
        
        if "correos no leídos" in command or "emails no leídos" in command:
            emails = self.get_unread_emails()
            if emails:
                return f"Tienes {len(emails)} correos no leídos"
            return "No tienes correos no leídos"
            
        elif "buscar correo" in command or "buscar email" in command:
            # Extraer término de búsqueda del comando
            search_term = command.split("buscar")[-1].strip()
            emails = self.search_emails(search_term)
            if emails:
                return f"Encontré {len(emails)} correos relacionados con '{search_term}'"
            return f"No encontré correos relacionados con '{search_term}'"
            
        else:
            return "No entiendo ese comando relacionado con correo" 
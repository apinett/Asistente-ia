import os
from typing import List, Dict, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from ..utils.logger import get_logger

class WhatsAppManager:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.driver = None
        self.wait = None
        self._setup_driver()
        
    def _setup_driver(self):
        """Configurar el driver de Selenium para WhatsApp Web."""
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--user-data-dir=./whatsapp_data')
            self.driver = webdriver.Chrome(options=options)
            self.wait = WebDriverWait(self.driver, 20)
            self.logger.info("Driver de WhatsApp configurado correctamente")
        except Exception as e:
            self.logger.error(f"Error al configurar el driver de WhatsApp: {e}")
    
    def connect(self) -> bool:
        """Conectar a WhatsApp Web."""
        try:
            self.driver.get('https://web.whatsapp.com')
            # Esperar a que el usuario escanee el código QR
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="chat-list"]')))
            self.logger.info("Conexión exitosa a WhatsApp Web")
            return True
        except Exception as e:
            self.logger.error(f"Error al conectar a WhatsApp Web: {e}")
            return False
    
    def get_unread_messages(self) -> List[Dict[str, Any]]:
        """Obtener mensajes no leídos."""
        if not self.driver:
            if not self.connect():
                return []
                
        try:
            # Encontrar chats no leídos
            unread_chats = self.driver.find_elements(By.CSS_SELECTOR, 'span[data-testid="icon-unread"]')
            messages = []
            
            for chat in unread_chats:
                chat.click()
                # Esperar a que se carguen los mensajes
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="msg-container"]')))
                
                # Obtener mensajes
                message_elements = self.driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="msg-container"]')
                for msg in message_elements:
                    try:
                        sender = msg.find_element(By.CSS_SELECTOR, 'span[data-testid="author"]').text
                        text = msg.find_element(By.CSS_SELECTOR, 'span[data-testid="conversation-info"]').text
                        messages.append({
                            'sender': sender,
                            'text': text
                        })
                    except:
                        continue
                        
            return messages
        except Exception as e:
            self.logger.error(f"Error al obtener mensajes no leídos: {e}")
            return []
    
    def send_message(self, contact: str, message: str) -> bool:
        """Enviar mensaje a un contacto."""
        if not self.driver:
            if not self.connect():
                return False
                
        try:
            # Buscar contacto
            search_box = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="search"]')))
            search_box.click()
            search_box.send_keys(contact)
            
            # Seleccionar contacto
            contact_element = self.wait.until(EC.presence_of_element_located((By.XPATH, f"//span[@title='{contact}']")))
            contact_element.click()
            
            # Enviar mensaje
            message_box = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="conversation-compose-box-input"]')))
            message_box.send_keys(message)
            message_box.send_keys('\n')
            
            self.logger.info(f"Mensaje enviado a {contact}")
            return True
        except Exception as e:
            self.logger.error(f"Error al enviar mensaje: {e}")
            return False
    
    def handle_command(self, command: str):
        """Procesar comandos relacionados con WhatsApp."""
        command = command.lower()
        
        if "mensajes no leídos" in command or "whatsapp no leídos" in command:
            messages = self.get_unread_messages()
            if messages:
                return f"Tienes {len(messages)} mensajes no leídos en WhatsApp"
            return "No tienes mensajes no leídos en WhatsApp"
            
        elif "enviar mensaje" in command:
            # Extraer contacto y mensaje del comando
            parts = command.split("a")[-1].split("diciendo")
            if len(parts) == 2:
                contact = parts[0].strip()
                message = parts[1].strip()
                if self.send_message(contact, message):
                    return f"Mensaje enviado a {contact}"
                return f"No se pudo enviar el mensaje a {contact}"
            return "Por favor, especifica el contacto y el mensaje"
            
        else:
            return "No entiendo ese comando relacionado con WhatsApp" 
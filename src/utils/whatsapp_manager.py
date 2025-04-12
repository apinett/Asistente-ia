import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from src.utils.logger import Logger


class WhatsAppManager:
    def __init__(self):
        self.logger = Logger()
        self.driver = None
        self.is_connected = False
        self.last_message_time = None
        self.wait = None
        self.setup_driver()

    def setup_driver(self):
        """Configurar el driver de Chrome para Selenium."""
        try:
            chrome_options = Options()
            # chrome_options.add_argument("--headless")  # Descomentar para modo sin interfaz
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.wait = WebDriverWait(self.driver, 30)
            self.logger.info("Driver de Chrome configurado correctamente")
        except Exception as e:
            self.logger.error(f"Error al configurar el driver: {e}")
            raise

    def connect(self) -> bool:
        """Conectar con WhatsApp Web."""
        try:
            self.driver.get("https://web.whatsapp.com")
            # Esperar a que aparezca el código QR
            qr_code = self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "canvas[aria-label='Scan me!']")
                )
            )
            self.logger.info("Código QR detectado. Por favor, escanea con tu teléfono.")

            # Esperar a que el usuario escanee el código QR
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[title='Menu']"))
            )

            self.is_connected = True
            self.logger.info("Conectado a WhatsApp Web")
            return True
        except Exception as e:
            self.logger.error(f"Error al conectar con WhatsApp: {e}")
            return False

    def send_message(self, phone: str, message: str) -> bool:
        """Enviar mensaje a un número de teléfono."""
        try:
            if not self.is_connected:
                if not self.connect():
                    return False

            # Asegurarse de que el número tenga el formato correcto
            if not phone.startswith("+"):
                phone = "+" + phone

            # Abrir chat con el número
            chat_url = f"https://web.whatsapp.com/send?phone={phone[1:]}"
            self.driver.get(chat_url)

            # Esperar a que se cargue el chat
            message_box = self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div[title='Type a message']")
                )
            )

            # Enviar el mensaje
            message_box.send_keys(message)
            send_button = self.driver.find_element(
                By.CSS_SELECTOR, "span[data-icon='send']"
            )
            send_button.click()

            self.last_message_time = datetime.now()
            self.logger.info(f"Mensaje enviado a {phone}")
            return True
        except Exception as e:
            self.logger.error(f"Error al enviar mensaje: {e}")
            return False

    def read_last_messages(self, phone: str, count: int = 5) -> List[str]:
        """Leer los últimos mensajes de un chat específico."""
        try:
            if not self.is_connected:
                if not self.connect():
                    return []

            # Abrir chat con el número
            chat_url = f"https://web.whatsapp.com/send?phone={phone[1:]}"
            self.driver.get(chat_url)

            # Esperar a que se cargue el chat
            self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div[title='Type a message']")
                )
            )

            # Obtener los mensajes
            messages = []
            message_elements = self.driver.find_elements(
                By.CSS_SELECTOR, "div[class*='message-in']"
            )

            for element in message_elements[-count:]:
                try:
                    message_text = element.find_element(
                        By.CSS_SELECTOR, "span[class*='selectable-text']"
                    ).text
                    messages.append(message_text)
                except:
                    continue

            return messages
        except Exception as e:
            self.logger.error(f"Error al leer mensajes: {e}")
            return []

    def is_online(self) -> bool:
        """Verificar si la conexión está activa."""
        try:
            if not self.driver:
                return False
            # Verificar si el menú principal está visible
            menu = self.driver.find_elements(By.CSS_SELECTOR, "div[title='Menu']")
            return len(menu) > 0
        except:
            return False

    def disconnect(self):
        """Desconectar de WhatsApp Web."""
        try:
            if self.driver:
                self.driver.quit()
            self.is_connected = False
            self.logger.info("Desconectado de WhatsApp Web")
        except Exception as e:
            self.logger.error(f"Error al desconectar: {e}")

    def __del__(self):
        """Destructor para asegurar que el driver se cierre correctamente."""
        self.disconnect()

import os
import json
from typing import Dict, Any, List
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from ..utils.logger import get_logger

class TMSManager:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.driver = None
        self.wait = None
        self._load_config()
        self._setup_driver()
        
    def _load_config(self):
        """Cargar configuración del TMS."""
        config_path = os.path.join('config', 'tms_config.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.logger.warning("Archivo de configuración TMS no encontrado")
            self.config = {
                'url': os.getenv('TMS_URL', ''),
                'username': os.getenv('TMS_USERNAME', ''),
                'password': os.getenv('TMS_PASSWORD', ''),
                'templates': {}
            }
    
    def _setup_driver(self):
        """Configurar el driver de Selenium para el TMS."""
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--user-data-dir=./tms_data')
            self.driver = webdriver.Chrome(options=options)
            self.wait = WebDriverWait(self.driver, 20)
            self.logger.info("Driver de TMS configurado correctamente")
        except Exception as e:
            self.logger.error(f"Error al configurar el driver de TMS: {e}")
    
    def connect(self) -> bool:
        """Conectar al sistema TMS."""
        try:
            self.driver.get(self.config['url'])
            
            # Login
            username_field = self.wait.until(EC.presence_of_element_located((By.ID, 'username')))
            password_field = self.driver.find_element(By.ID, 'password')
            
            username_field.send_keys(self.config['username'])
            password_field.send_keys(self.config['password'])
            
            # Click en botón de login
            login_button = self.driver.find_element(By.ID, 'login-button')
            login_button.click()
            
            # Esperar a que se cargue el dashboard
            self.wait.until(EC.presence_of_element_located((By.ID, 'dashboard')))
            self.logger.info("Conexión exitosa al sistema TMS")
            return True
        except Exception as e:
            self.logger.error(f"Error al conectar al sistema TMS: {e}")
            return False
    
    def load_trip(self, trip_data: Dict[str, Any]) -> bool:
        """Cargar un viaje en el sistema TMS."""
        if not self.driver:
            if not self.connect():
                return False
                
        try:
            # Navegar a la página de carga de viajes
            self.driver.get(f"{self.config['url']}/trips/new")
            
            # Esperar a que se cargue el formulario
            form = self.wait.until(EC.presence_of_element_located((By.ID, 'trip-form')))
            
            # Llenar campos del formulario
            for field, value in trip_data.items():
                try:
                    input_field = form.find_element(By.NAME, field)
                    input_field.send_keys(value)
                except:
                    self.logger.warning(f"No se encontró el campo {field}")
            
            # Enviar formulario
            submit_button = form.find_element(By.ID, 'submit-trip')
            submit_button.click()
            
            # Esperar confirmación
            self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'success-message')))
            self.logger.info("Viaje cargado exitosamente")
            return True
        except Exception as e:
            self.logger.error(f"Error al cargar viaje: {e}")
            return False
    
    def extract_trip_data(self, template_path: str) -> Dict[str, Any]:
        """Extraer datos de viaje desde una plantilla."""
        try:
            # Aquí se implementaría la lógica para extraer datos de la plantilla
            # Por ejemplo, usando pandas para archivos Excel o procesamiento de PDF
            # Por ahora retornamos datos de ejemplo
            return {
                'origin': 'Ciudad A',
                'destination': 'Ciudad B',
                'date': '2024-03-15',
                'driver': 'Juan Pérez',
                'vehicle': 'ABC123'
            }
        except Exception as e:
            self.logger.error(f"Error al extraer datos de la plantilla: {e}")
            return {}
    
    def handle_command(self, command: str):
        """Procesar comandos relacionados con el TMS."""
        command = command.lower()
        
        if "cargar viaje" in command:
            # Extraer ruta de la plantilla del comando
            template_path = command.split("desde")[-1].strip()
            if os.path.exists(template_path):
                trip_data = self.extract_trip_data(template_path)
                if trip_data:
                    if self.load_trip(trip_data):
                        return "Viaje cargado exitosamente en el sistema TMS"
                    return "No se pudo cargar el viaje en el sistema TMS"
                return "No se pudieron extraer los datos del viaje"
            return "No se encontró el archivo de plantilla especificado"
            
        else:
            return "No entiendo ese comando relacionado con el TMS" 
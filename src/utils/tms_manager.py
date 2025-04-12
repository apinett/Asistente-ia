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


class TMSManager:
    def __init__(self):
        self.logger = Logger()
        self.driver = None
        self.is_connected = False
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

    def connect(self, tms_url: str, username: str, password: str) -> bool:
        """Conectar con el sistema TMS."""
        try:
            # Navegar a la URL del TMS
            self.driver.get(tms_url)

            # Esperar a que aparezca el formulario de login
            username_field = self.wait.until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            password_field = self.driver.find_element(By.NAME, "password")

            # Ingresar credenciales
            username_field.send_keys(username)
            password_field.send_keys(password)

            # Enviar formulario
            login_button = self.driver.find_element(
                By.CSS_SELECTOR, "button[type='submit']"
            )
            login_button.click()

            # Esperar a que se complete el login
            self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div[class*='dashboard']")
                )
            )

            self.is_connected = True
            self.logger.info("Conectado al sistema TMS")
            return True
        except Exception as e:
            self.logger.error(f"Error al conectar con TMS: {e}")
            return False

    def enter_data(self, data: Dict[str, Any]) -> bool:
        """Ingresar datos en el sistema TMS."""
        try:
            if not self.is_connected:
                self.logger.error("No hay conexión con el sistema TMS")
                return False

            # Navegar a la página de ingreso de datos
            self.driver.get(f"{self.driver.current_url}/data-entry")

            # Esperar a que se cargue el formulario
            form = self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "form[class*='data-entry']")
                )
            )

            # Ingresar datos en los campos correspondientes
            for field, value in data.items():
                try:
                    input_field = form.find_element(By.NAME, field)
                    input_field.clear()
                    input_field.send_keys(str(value))
                except:
                    self.logger.warning(f"Campo {field} no encontrado, saltando...")

            # Enviar formulario
            submit_button = form.find_element(By.CSS_SELECTOR, "button[type='submit']")
            submit_button.click()

            # Esperar confirmación
            self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div[class*='success-message']")
                )
            )

            self.logger.info("Datos ingresados correctamente")
            return True
        except Exception as e:
            self.logger.error(f"Error al ingresar datos: {e}")
            return False

    def get_data(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Obtener datos del sistema TMS."""
        try:
            if not self.is_connected:
                self.logger.error("No hay conexión con el sistema TMS")
                return []

            # Navegar a la página de consulta
            self.driver.get(f"{self.driver.current_url}/data-query")

            # Aplicar filtros si se proporcionan
            if filters:
                filter_form = self.wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "form[class*='filter']")
                    )
                )
                for field, value in filters.items():
                    try:
                        filter_field = filter_form.find_element(By.NAME, field)
                        filter_field.clear()
                        filter_field.send_keys(str(value))
                    except:
                        self.logger.warning(
                            f"Filtro {field} no encontrado, saltando..."
                        )

                # Aplicar filtros
                apply_button = filter_form.find_element(
                    By.CSS_SELECTOR, "button[type='submit']"
                )
                apply_button.click()

            # Esperar a que se carguen los resultados
            results_table = self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "table[class*='results']")
                )
            )

            # Extraer datos de la tabla
            data = []
            rows = results_table.find_elements(By.TAG_NAME, "tr")
            headers = [th.text for th in rows[0].find_elements(By.TAG_NAME, "th")]

            for row in rows[1:]:
                cells = row.find_elements(By.TAG_NAME, "td")
                row_data = {headers[i]: cell.text for i, cell in enumerate(cells)}
                data.append(row_data)

            return data
        except Exception as e:
            self.logger.error(f"Error al obtener datos: {e}")
            return []

    def is_online(self) -> bool:
        """Verificar si la conexión está activa."""
        try:
            if not self.driver:
                return False
            # Verificar si el dashboard está visible
            dashboard = self.driver.find_elements(
                By.CSS_SELECTOR, "div[class*='dashboard']"
            )
            return len(dashboard) > 0
        except:
            return False

    def disconnect(self):
        """Desconectar del sistema TMS."""
        try:
            if self.driver:
                self.driver.quit()
            self.is_connected = False
            self.logger.info("Desconectado del sistema TMS")
        except Exception as e:
            self.logger.error(f"Error al desconectar: {e}")

    def __del__(self):
        """Destructor para asegurar que el driver se cierre correctamente."""
        self.disconnect()

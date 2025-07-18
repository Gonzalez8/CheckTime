import logging
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import tempfile
import shutil

from checktime.shared.config import get_selenium_timeout, get_chrome_options_args, get_simulation_mode, get_chrome_bin, get_chromedriver_bin

SIMULATION_MODE = get_simulation_mode()

logger = logging.getLogger(__name__)

class CheckJCClient:
    """Cliente para interactuar con CheckJC."""
    
    def __init__(self, username, password, subdomain):
        if not username or not password or not subdomain:
            raise ValueError("CheckJC username, password, and subdomain must be provided.")

        self.username = username
        self.password = password
        self.subdomain = subdomain
        self.driver = None
        self.wait = None
        self.timeout = get_selenium_timeout()
        self.login_url = f"https://{self.subdomain}.checkjc.com/login"
    
    def __enter__(self):
        if SIMULATION_MODE:
            logger.info(f"Simulation mode enabled for {self.username}")
            return self

        options = webdriver.ChromeOptions()
        options.binary_location = get_chrome_bin()
        for arg in get_chrome_options_args():
            options.add_argument(arg)
        # Aislar perfil temporal único por usuario
        self._tmp_profile = tempfile.mkdtemp(prefix=f"chrome_{self.username}_")
        options.add_argument(f"--user-data-dir={self._tmp_profile}")

        service = Service(executable_path=get_chromedriver_bin())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, self.timeout)
        logger.info(f"Driver de Chrome inicializado correctamente para {self.username}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.quit()
            logger.info(f"Driver de Chrome cerrado para {self.username}")
        # Limpia el perfil temporal
        if hasattr(self, "_tmp_profile"):
            shutil.rmtree(self._tmp_profile, ignore_errors=True)
    
    def login(self):
        """Realiza el login en CheckJC."""
        if SIMULATION_MODE:
            logger.info(f"Simulation: Login successful for {self.username}")
            time.sleep(1)
            return True

        try:
            logger.info(f"Navigating to login page: {self.login_url}")
            self.driver.get(self.login_url)
            
            username_field = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='username'], input#username, input[type='text'], input[type='email']"))
            )
            username_field.clear()
            username_field.send_keys(self.username)
            logger.info(f"Username entered for {self.username}")
            
            password_field = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='password'], input#password, input[type='password']"))
            )
            password_field.clear()
            password_field.send_keys(self.password)
            logger.info("Password entered")
            
            login_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#btn-login, button[type='submit'], input[type='submit']"))
            )
            login_button.click()
            logger.info("Login button clicked")
            
            self.wait.until(
                EC.any_of(
                    EC.invisibility_of_element_located((By.CSS_SELECTOR, "#btn-login, button[type='submit'], input[type='submit']")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".dashboard, .main-content, #btn-check")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.alert-danger"))
                )
            )
            try:
                error_div = self.driver.find_element(By.CSS_SELECTOR, "div.alert-danger")
                error_text = error_div.text.strip()

                if error_text:
                    raise Exception(f"Error during login for {self.username}: {error_text}")

            except NoSuchElementException:
                logger.info(f"Login successful for {self.username}")
                
            return True
        
        except Exception as e:
            error_msg = f"❌ Error during login for {self.username}: {e}"
            raise

    def perform_check(self, check_type: str):
        """Check in or check out, robust version."""
        if SIMULATION_MODE:
            time.sleep(1)
            now = datetime.now().strftime("%H:%M:%S")
            logger.info(f"Simulation: Check {check_type} completed at {now} for {self.username}")
            return True

        try:
            logger.info(f"Searching for Check {check_type} button")
            btn_fichar = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#btn-check, button.btn-check, button[id*='check'], button[class*='check']"))
            )
            self.driver.execute_script("arguments[0].click();", btn_fichar)

            # Espera a que aparezca el mensaje de éxito
            try:
                success = WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".alert-success, .bubble.alert-success"))
                )
                if "Resultado del fichaje" in self.driver.page_source:
                    logger.info(f"Check {check_type} completed for {self.username} successfully")
                    return True
                else:
                    logger.error(f"Check {check_type} for {self.username} - Success message not found. HTML: {self.driver.page_source[:1000]}")
                    raise Exception("Success message not found after check")
            except TimeoutException:
                logger.error(f"Check {check_type} for {self.username} - Timeout waiting for success message. HTML: {self.driver.page_source[:1000]}")
                raise Exception("Timeout waiting for success message after check")

        except Exception as e:
            error_msg = f"❌ Error during Check {check_type} for {self.username}: {e}"
            logger.error(error_msg)
            raise

    def check_in(self):
        """Perform check in."""
        return self.perform_check("in")
    
    def check_out(self):
        """Perform check out."""
        return self.perform_check("out")


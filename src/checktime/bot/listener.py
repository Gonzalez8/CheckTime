import time
from typing import Optional, Dict, Any
from ..utils.logger import bot_logger, error_logger
from ..utils.telegram import TelegramClient
from ..fichaje.holidays import HolidayManager

class TelegramBotListener:
    """Cliente para escuchar y procesar comandos de Telegram."""
    
    def __init__(self, telegram_client: Optional[TelegramClient] = None, holiday_manager: Optional[HolidayManager] = None):
        """
        Inicializa el listener de Telegram.
        
        Args:
            telegram_client (Optional[TelegramClient]): Cliente de Telegram
            holiday_manager (Optional[HolidayManager]): Gestor de festivos
        """
        self.telegram = telegram_client or TelegramClient()
        self.holiday_manager = holiday_manager or HolidayManager()
        self.last_update_id = None
    
    def process_command(self, message: Dict[str, Any]) -> None:
        """
        Procesa un comando recibido.
        
        Args:
            message (Dict[str, Any]): Mensaje recibido
        """
        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()
        
        if str(chat_id) != self.telegram.chat_id:
            bot_logger.warning(f"Mensaje ignorado de chat no autorizado: {chat_id}")
            return
        
        bot_logger.info(f"Comando recibido: {text}")
        
        if text.startswith("/addfestivo"):
            parts = text.split(None, 2)  # Split into command, date, and description (if present)
            if len(parts) >= 2:
                date = parts[1]
                description = parts[2] if len(parts) > 2 else None
                self.add_holiday(date, description)
            else:
                self.telegram.send_message("❌ Usa: `/addfestivo YYYY-MM-DD [descripción]`")
        
        elif text.startswith("/delfestivo"):
            parts = text.split()
            if len(parts) == 2:
                self.remove_holiday(parts[1])
            else:
                self.telegram.send_message("❌ Usa: `/delfestivo YYYY-MM-DD`")
        
        elif text == "/listfestivos":
            self.list_holidays()
        
        else:
            bot_logger.warning(f"Comando no reconocido: {text}")
            self.telegram.send_message("❓ Comando no reconocido. Usa `/addfestivo`, `/delfestivo` o `/listfestivos`.")
    
    def add_holiday(self, date: str, description: Optional[str] = None) -> None:
        """
        Añade un día festivo.
        
        Args:
            date (str): Fecha en formato YYYY-MM-DD
            description (Optional[str]): Descripción del festivo
        """
        try:
            # Validar el formato de la fecha
            from datetime import datetime
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                self.telegram.send_message("❌ Formato inválido. Usa: `/addfestivo YYYY-MM-DD [descripción]`")
                return
            
            # Conectar a la base de datos
            import sqlite3
            import os
            
            # Obtener la ruta de la base de datos
            db_path = os.getenv('DATABASE_URL', 'sqlite:////data/checktime.db')
            if db_path.startswith('sqlite:///'):
                db_path = db_path[10:]  # Remove the sqlite:/// prefix
            
            if not os.path.exists(db_path):
                self.telegram.send_message("❌ No se pudo encontrar la base de datos")
                return
            
            # Insertar el festivo directamente con SQLite
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Comprobar si el festivo ya existe
            cursor.execute("SELECT id FROM holiday WHERE date = ?", (date,))
            if cursor.fetchone():
                self.telegram.send_message(f"⚠️ El festivo {date} ya está registrado.")
                conn.close()
                return
            
            # Insertar el nuevo festivo
            if description:
                holiday_description = f"{description}"
            else:
                holiday_description = f"Added via Telegram bot on {datetime.now()}"
            
            cursor.execute("INSERT INTO holiday (date, description, created_at) VALUES (?, ?, ?)", 
                          (date, holiday_description, datetime.now()))
            conn.commit()
            conn.close()
            
            self.telegram.send_message(f"✅ Festivo añadido: {date}")
            
        except Exception as e:
            error_msg = f"Error al añadir festivo: {e}"
            error_logger.error(error_msg)
            self.telegram.send_message(f"❌ {error_msg}")
    
    def remove_holiday(self, date: str) -> None:
        """
        Elimina un día festivo.
        
        Args:
            date (str): Fecha en formato YYYY-MM-DD
        """
        try:
            # Validar el formato de la fecha
            from datetime import datetime
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                self.telegram.send_message("❌ Formato inválido. Usa: `/delfestivo YYYY-MM-DD`")
                return
            
            # Conectar a la base de datos
            import sqlite3
            import os
            
            # Obtener la ruta de la base de datos
            db_path = os.getenv('DATABASE_URL', 'sqlite:////data/checktime.db')
            if db_path.startswith('sqlite:///'):
                db_path = db_path[10:]  # Remove the sqlite:/// prefix
            
            if not os.path.exists(db_path):
                self.telegram.send_message("❌ No se pudo encontrar la base de datos")
                return
            
            # Eliminar el festivo directamente con SQLite
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Comprobar si el festivo existe
            cursor.execute("SELECT id FROM holiday WHERE date = ?", (date,))
            if not cursor.fetchone():
                self.telegram.send_message(f"⚠️ No existe el festivo {date}")
                conn.close()
                return
            
            # Eliminar el festivo
            cursor.execute("DELETE FROM holiday WHERE date = ?", (date,))
            conn.commit()
            conn.close()
            
            self.telegram.send_message(f"✅ Festivo eliminado: {date}")
            
        except Exception as e:
            error_msg = f"Error al eliminar festivo: {e}"
            error_logger.error(error_msg)
            self.telegram.send_message(f"❌ {error_msg}")
    
    def list_holidays(self) -> None:
        """Lista los próximos días festivos del año."""
        try:
            from datetime import datetime
            import sqlite3
            import os
            
            current_date = datetime.now().date()
            current_year = current_date.year
            
            # Use the configured database from environment
            import os
            db_path = os.getenv('DATABASE_URL', 'sqlite:////data/checktime.db')
            if db_path.startswith('sqlite:///'):
                db_path = db_path[10:]  # Remove the sqlite:/// prefix
            
            if not os.path.exists(db_path):
                self.telegram.send_message("❌ No se pudo encontrar la base de datos")
                return
            
            # Acceder directamente a SQLite
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Obtener todos los festivos
            cursor.execute("SELECT date, description FROM holiday")
            all_holidays = cursor.fetchall()
            
            if not all_holidays:
                self.telegram.send_message("📅 No hay festivos guardados.")
                conn.close()
                return
            
            # Filtrar para mostrar solo los próximos festivos del año actual
            upcoming_holidays = []
            for date_str, desc in all_holidays:
                holiday_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if holiday_date >= current_date and holiday_date.year == current_year:
                    upcoming_holidays.append((date_str, desc))
            
            if not upcoming_holidays:
                self.telegram.send_message("📅 No hay festivos próximos para este año.")
                conn.close()
                return
            
            # Crear el mensaje
            message = f"📅 *Próximos festivos del año {current_year}:*\n"
            for date_str, desc in sorted(upcoming_holidays, key=lambda x: datetime.strptime(x[0], "%Y-%m-%d")):
                holiday_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                days_remaining = (holiday_date - current_date).days
                day_text = "hoy" if days_remaining == 0 else f"en {days_remaining} día{'s' if days_remaining != 1 else ''}"
                message += f"- {date_str} ({desc}): {day_text}\n"
            
            conn.close()
            self.telegram.send_message(message)
        except Exception as e:
            error_msg = f"Error al listar festivos: {e}"
            error_logger.error(error_msg)
            self.telegram.send_message(f"❌ {error_msg}")
    
    def listen(self) -> None:
        """Inicia el bucle de escucha de comandos."""
        bot_logger.info("Iniciando bot de Telegram")
        
        while True:
            try:
                updates = self.telegram.get_updates(
                    offset=(self.last_update_id + 1) if self.last_update_id else None
                )
                
                if "result" in updates:
                    for update in updates["result"]:
                        self.last_update_id = update["update_id"]
                        
                        if "message" in update:
                            self.process_command(update["message"])
            
            except Exception as e:
                error_msg = f"Error en loop principal: {e}"
                error_logger.error(error_msg, exc_info=True)
                bot_logger.error(error_msg)
            
            time.sleep(5)

def main():
    """Función principal para ejecutar el bot."""
    listener = TelegramBotListener()
    listener.listen()

if __name__ == "__main__":
    main() 
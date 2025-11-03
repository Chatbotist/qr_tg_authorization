"""
Менеджер авторизации через QR-код
"""
import time
import uuid
import asyncio
import threading
from pathlib import Path
from typing import Optional, Dict, List
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import qrcode
import io
import base64
from PIL import Image, ImageDraw
import config


class AuthManager:
    """
    Класс для управления авторизацией через QR-код
    Однопользовательская система - одна сессия для всего приложения
    """
    
    def __init__(self):
        # Словарь для хранения активных QR-кодов
        self.active_qr_codes: Dict[str, dict] = {}
        # Глобальный event loop для всех Telethon операций
        self._global_loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._loop_lock = threading.Lock()
        # Постоянный путь к единственной сессии (одна сессия на весь проект)
        self.session_path = config.SESSIONS_DIR / "user.session"
        # Данные текущего пользователя
        self._user_data: Optional[Dict] = None
        self._start_global_loop()
    
    def _start_global_loop(self):
        """Запускает глобальный event loop в отдельном потоке"""
        def run_loop():
            """Запуск event loop"""
            self._global_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._global_loop)
            self._global_loop.run_forever()
        
        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()
        print("[AUTH] Глобальный event loop запущен в отдельном потоке")
    
    def _get_loop(self):
        """Получает глобальный event loop"""
        with self._loop_lock:
            while self._global_loop is None:
                time.sleep(0.01)
            return self._global_loop
    
    def _run_async(self, coro):
        """
        Запускает async функцию в глобальном event loop
        
        Args:
            coro: Корутина для выполнения
            
        Returns:
            Результат выполнения корутины
        """
        loop = self._get_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()
    
    def is_authorized(self) -> bool:
        """
        Проверяет, авторизован ли пользователь
        
        Returns:
            bool: True если авторизован
        """
        return self._user_data is not None
    
    def get_user_data(self) -> Optional[Dict]:
        """
        Возвращает данные текущего пользователя
        
        Returns:
            Dict или None
        """
        return self._user_data
        
    def generate_qr_code_url(self) -> tuple[str, str]:
        """
        Генерирует новый QR-код для авторизации и сохраняет как файл
        
        Returns:
            tuple: (qr_id, qr_url) - ID QR-кода и URL на изображение
        """
        # Если уже авторизован, не генерируем новый QR
        if self.is_authorized():
            raise Exception("Already authorized")
        
        # Удаляем все старые temp файлы перед генерацией нового QR
        self.cleanup_temp_files()
        
        try:
            # Генерируем уникальный ID для QR-кода
            qr_id = str(uuid.uuid4())
            
            # Создаем временную сессию для этого QR-кода
            temp_session = config.SESSIONS_DIR / f"temp_{qr_id}.session"
            
            # Создаем клиент для QR авторизации
            qr_client = TelegramClient(str(temp_session), config.API_ID, config.API_HASH)
            
            # Получаем QR-код для авторизации
            async def get_qr_login():
                await qr_client.connect()
                if not await qr_client.is_user_authorized():
                    qr_login = await qr_client.qr_login()
                    return qr_login
                else:
                    await qr_client.disconnect()
                    raise Exception("Client already authorized")
            
            qr_login = self._run_async(get_qr_login())
            qr_url = qr_login.url
            
            # Сохраняем информацию о QR-коде
            self.active_qr_codes[qr_id] = {
                "qr_login": qr_login,
                "qr_client": qr_client,
                "expires_at": time.time() + config.QR_CODE_TIMEOUT,
                "temp_session": str(temp_session),
            }
            
            # Генерируем QR-код
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_url)
            qr.make(fit=True)
            
            # Создаем изображение в RGB режиме для четких квадратов
            img = qr.make_image(fill_color="black", back_color="white")
            # Конвертируем в RGB если изображение в другом режиме (например, '1' для монохромного)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Добавляем логотип в центр QR-кода
            width, height = img.size
            
            # Загружаем логотип
            logo_path = Path(config.SESSIONS_DIR.parent) / 'static' / 'img' / 'tg_icon.png'
            if logo_path.exists():
                logo = Image.open(str(logo_path))
                
                # Конвертируем в RGBA для сохранения прозрачности
                if logo.mode != 'RGBA':
                    if logo.mode == 'P' and 'transparency' in logo.info:
                        logo = logo.convert('RGBA')
                    else:
                        logo = logo.convert('RGBA')
                
                # Размер логотипа: примерно 15% от размера QR-кода
                logo_size = int(min(width, height) * 0.15)
                logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
                
                # Вычисляем центр QR-кода
                center_x = width // 2
                center_y = height // 2
                
                # Вычисляем радиус белой круглой зоны: логотип + 5px с каждой стороны (итого +10px диаметра)
                # Радиус = (логотип + 10px) / 2
                white_zone_radius = (logo_size + 10) // 2
                
                # Создаем белую круглую зону в центре QR-кода
                draw = ImageDraw.Draw(img)
                # Рисуем белый круг
                draw.ellipse(
                    [
                        center_x - white_zone_radius,
                        center_y - white_zone_radius,
                        center_x + white_zone_radius,
                        center_y + white_zone_radius
                    ],
                    fill='white'
                )
                
                # Вычисляем позицию для размещения логотипа (по центру белой зоны)
                logo_position_x = center_x - logo_size // 2
                logo_position_y = center_y - logo_size // 2
                
                # Вставляем логотип с сохранением прозрачности
                img.paste(logo, (logo_position_x, logo_position_y), logo)
            
            # Создаем директорию для QR-кодов если её нет
            qr_dir = Path(config.SESSIONS_DIR.parent) / 'static' / 'qr'
            qr_dir.mkdir(parents=True, exist_ok=True)
            
            # Сохраняем QR-код как файл
            qr_filename = f"{qr_id}.png"
            qr_filepath = qr_dir / qr_filename
            img.save(qr_filepath, 'PNG')
            
            # Сохраняем путь к файлу в данных QR-кода
            self.active_qr_codes[qr_id]['qr_file'] = str(qr_filepath)
            
            # Возвращаем URL
            qr_url_path = f"/static/qr/{qr_filename}"
            
            return qr_id, qr_url_path
            
        except Exception as e:
            print(f"[AUTH] Ошибка при генерации QR-кода: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def generate_qr_code(self) -> tuple[str, str]:
        """
        Генерирует новый QR-код для авторизации
        
        Returns:
            tuple: (qr_id, base64_image) - ID QR-кода и изображение в base64
        """
        # Если уже авторизован, не генерируем новый QR
        if self.is_authorized():
            raise Exception("Already authorized. Logout first.")
        
        # Удаляем все старые temp файлы перед генерацией нового QR
        self.cleanup_temp_files()
        
        # Очищаем старые QR-коды из памяти
        for qr_id, qr_data in list(self.active_qr_codes.items()):
            # Отключаем клиентов старых QR-кодов
            client = qr_data.get("qr_client")
            if client:
                try:
                    async def disconnect():
                        await client.disconnect()
                    self._run_async(disconnect())
                except Exception as e:
                    print(f"[AUTH] Ошибка при отключении клиента {qr_id}: {e}")
            # Удаляем temp сессии
            temp_session = qr_data.get("temp_session")
            if temp_session:
                temp_session_file = Path(temp_session)
                if temp_session_file.exists():
                    try:
                        temp_session_file.unlink()
                        print(f"[AUTH] Удален старый temp файл: {temp_session}")
                    except Exception as e:
                        print(f"[AUTH] Ошибка при удалении {temp_session}: {e}")
        
        self.active_qr_codes.clear()
        
        # Создаем уникальный ID для QR-кода
        qr_id = str(uuid.uuid4())
        
        # Создаем временную сессию для QR
        temp_session = config.SESSIONS_DIR / f"temp_{qr_id}.session"
        
        async def create_qr_login():
            """Внутренняя async функция для создания QR-логина"""
            # Используем временную сессию для QR
            client = TelegramClient(str(temp_session), config.API_ID, config.API_HASH)
            try:
                await client.connect()
                # Используем встроенный метод qr_login
                qr_login = await client.qr_login()
                return qr_login, client  # Возвращаем и клиента тоже
            except:
                # В случае ошибки пытаемся отключиться
                try:
                    await client.disconnect()
                except:
                    pass
                raise
        
        try:
            # Создаем QR-логин
            qr_login, qr_client = self._run_async(create_qr_login())
            
            # Получаем URL для QR-кода
            qr_url = qr_login.url
            
            # Сохраняем информацию о QR-коде
            self.active_qr_codes[qr_id] = {
                "qr_login": qr_login,
                "qr_client": qr_client,  # Сохраняем клиента чтобы использовать wait()
                "expires_at": time.time() + config.QR_CODE_TIMEOUT,
                "temp_session": str(temp_session),
            }
            
            # Генерируем QR-код
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_url)
            qr.make(fit=True)
            
            # Создаем изображение в RGB режиме для четких квадратов
            img = qr.make_image(fill_color="black", back_color="white")
            # Конвертируем в RGB если изображение в другом режиме (например, '1' для монохромного)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Добавляем логотип в центр QR-кода
            width, height = img.size
            
            # Загружаем логотип
            logo_path = Path(config.SESSIONS_DIR.parent) / 'static' / 'img' / 'tg_icon.png'
            if logo_path.exists():
                logo = Image.open(str(logo_path))
                
                # Конвертируем в RGBA для сохранения прозрачности
                if logo.mode != 'RGBA':
                    if logo.mode == 'P' and 'transparency' in logo.info:
                        logo = logo.convert('RGBA')
                    else:
                        logo = logo.convert('RGBA')
                
                # Размер логотипа: примерно 15% от размера QR-кода
                logo_size = int(min(width, height) * 0.15)
                logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
                
                # Вычисляем центр QR-кода
                center_x = width // 2
                center_y = height // 2
                
                # Вычисляем радиус белой круглой зоны: логотип + 5px с каждой стороны (итого +10px диаметра)
                # Радиус = (логотип + 10px) / 2
                white_zone_radius = (logo_size + 10) // 2
                
                # Создаем белую круглую зону в центре QR-кода
                draw = ImageDraw.Draw(img)
                # Рисуем белый круг
                draw.ellipse(
                    [
                        center_x - white_zone_radius,
                        center_y - white_zone_radius,
                        center_x + white_zone_radius,
                        center_y + white_zone_radius
                    ],
                    fill='white'
                )
                
                # Вычисляем позицию для размещения логотипа (по центру белой зоны)
                logo_position_x = center_x - logo_size // 2
                logo_position_y = center_y - logo_size // 2
                
                # Вставляем логотип с сохранением прозрачности
                img.paste(logo, (logo_position_x, logo_position_y), logo)
            
            # Конвертируем в base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            return qr_id, img_str
            
        except Exception as e:
            print(f"[AUTH] Ошибка при генерации QR-кода: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def is_qr_valid(self, qr_id: str) -> bool:
        """
        Проверяет, действителен ли QR-код
        
        Args:
            qr_id: ID QR-кода
            
        Returns:
            bool: True если QR-код действителен
        """
        if qr_id not in self.active_qr_codes:
            return False
        
        # Проверяем время истечения
        expires_at = self.active_qr_codes[qr_id].get("expires_at", 0)
        return time.time() < expires_at
    
    def check_authorization_status(self, qr_id: str) -> Optional[Dict]:
        """
        Проверяет статус авторизации по QR-коду
        
        Args:
            qr_id: ID QR-кода
            
        Returns:
            Dict или None: Данные пользователя если авторизован, иначе None
        """
        print(f"[AUTH] check_authorization_status для qr_id: {qr_id}")
        
        # Если уже авторизован, возвращаем данные
        if self.is_authorized():
            print(f"[AUTH] check_authorization_status: уже авторизован")
            return self._user_data
        
        if not self.is_qr_valid(qr_id):
            print(f"[AUTH] check_authorization_status: QR невалиден")
            return None
        
        qr_data = self.active_qr_codes[qr_id]
        temp_session = qr_data.get("temp_session")
        
        # Пытаемся завершить авторизацию через wait()
        print(f"[AUTH] check_authorization_status: проверяем wait()")
        try:
            qr_login = qr_data.get("qr_login")
            
            async def check_auth():
                print(f"[AUTH] check_auth: используем сохраненного клиента")
                # Используем сохраненного клиента
                client = qr_data.get("qr_client")
                
                try:
                    # Ожидаем завершения авторизации через wait() с небольшим таймаутом
                    try:
                        print(f"[AUTH] check_auth: вызываем wait()")
                        await asyncio.wait_for(qr_login.wait(), timeout=2)
                        print(f"[AUTH] check_auth: wait() завершен")
                    except asyncio.TimeoutError:
                        print(f"[AUTH] check_auth: таймаут wait()")
                        return None
                    except SessionPasswordNeededError as e:
                        print(f"[AUTH] Password needed: {type(e).__name__}")
                        return {"needs_password": True}
                    except Exception as e:
                        print(f"[AUTH] Ошибка при wait(): {type(e).__name__}: {e}")
                        return None
                    
                    # Проверяем авторизацию
                    if await client.is_user_authorized():
                        user = await client.get_me()
                        print(f"[AUTH] check_auth: пользователь авторизован: {user.first_name}")
                        
                        user_data = {
                            "id": user.id,
                            "first_name": user.first_name,
                            "last_name": user.last_name or "",
                            "username": user.username or "",
                            "phone": user.phone or "",
                        }
                        
                        # Копируем temp сессию в постоянную
                        import shutil
                        shutil.copy(str(temp_session), str(self.session_path))
                        print(f"[AUTH] check_auth: сессия скопирована в постоянную")
                        
                        # Удаляем файл QR-кода если он есть
                        qr_file = qr_data.get("qr_file")
                        if qr_file:
                            qr_file_path = Path(qr_file)
                            if qr_file_path.exists():
                                try:
                                    qr_file_path.unlink()
                                    print(f"[AUTH] Удален файл QR-кода после авторизации: {qr_file}")
                                except Exception as e:
                                    print(f"[AUTH] Ошибка при удалении файла QR-кода {qr_file}: {e}")
                        
                        # НЕ отключаем клиента - он нужен боту
                        return user_data
                    
                    print(f"[AUTH] check_auth: пользователь не авторизован")
                    return None
                except Exception as e:
                    print(f"[AUTH] check_auth: ошибка: {e}")
                    raise
            
            user_data = self._run_async(check_auth())
            
            if user_data:
                # Проверяем, требуется ли пароль
                if user_data.get("needs_password"):
                    return {"needs_password": True}
                
                # Удаляем temp сессию
                temp_session_file = Path(temp_session)
                if temp_session_file.exists():
                    try:
                        temp_session_file.unlink()
                        print(f"[AUTH] Удален temp файл: {temp_session}")
                    except Exception as e:
                        print(f"[AUTH] Ошибка при удалении temp файла: {e}")
                
                # Сохраняем данные пользователя
                self._user_data = user_data
                # НЕ очищаем QR-коды и НЕ отключаем клиент - он будет передан боту
                # self.active_qr_codes.clear() - оставляем клиент для бота
                print(f"[AUTH] check_authorization_status: успешно завершен, клиент сохранен для бота")
                return user_data
                
        except Exception as e:
            print(f"[AUTH] Ошибка при проверке авторизации: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        
        return None
    
    def submit_password(self, qr_id: str, password: str) -> Optional[Dict]:
        """
        Отправляет пароль 2FA для завершения авторизации
        
        Args:
            qr_id: ID QR-кода
            password: Пароль 2FA
            
        Returns:
            Dict или None: Данные пользователя если успешно
        """
        print(f"[AUTH] submit_password вызван для qr_id: {qr_id}")
        
        # Если уже авторизован, возвращаем данные
        if self.is_authorized():
            print(f"[AUTH] submit_password: уже авторизован")
            return self._user_data
        
        if qr_id not in self.active_qr_codes:
            print(f"[AUTH] submit_password: qr_id не найден")
            return None
        
        try:
            qr_data = self.active_qr_codes[qr_id]
            temp_session = qr_data.get("temp_session")
            
            async def sign_in_with_password():
                print(f"[AUTH] submit_password: используем сохраненного клиента")
                # Используем сохраненного клиента
                client = qr_data.get("qr_client")
                try:
                    print(f"[AUTH] submit_password: отправляем пароль")
                    await client.sign_in(password=password)
                    print(f"[AUTH] submit_password: пароль принят")
                    
                    if await client.is_user_authorized():
                        user = await client.get_me()
                        print(f"[AUTH] submit_password: пользователь авторизован: {user.first_name}")
                        
                        user_data = {
                            "id": user.id,
                            "first_name": user.first_name,
                            "last_name": user.last_name or "",
                            "username": user.username or "",
                            "phone": user.phone or "",
                        }
                        
                        # Копируем temp сессию в постоянную
                        import shutil
                        shutil.copy(str(temp_session), str(self.session_path))
                        print(f"[AUTH] submit_password: сессия скопирована в постоянную")
                        
                        # Удаляем файл QR-кода если он есть
                        qr_file = qr_data.get("qr_file")
                        if qr_file:
                            qr_file_path = Path(qr_file)
                            if qr_file_path.exists():
                                try:
                                    qr_file_path.unlink()
                                    print(f"[AUTH] Удален файл QR-кода после авторизации через пароль: {qr_file}")
                                except Exception as e:
                                    print(f"[AUTH] Ошибка при удалении файла QR-кода {qr_file}: {e}")
                        
                        # НЕ отключаем клиента - он нужен боту
                        return user_data
                    
                    print(f"[AUTH] submit_password: пользователь не авторизован")
                    return None
                except Exception as e:
                    print(f"[AUTH] submit_password: ошибка в sign_in_with_password: {e}")
                    raise
            
            user_data = self._run_async(sign_in_with_password())
            
            if user_data:
                # Удаляем temp сессию
                temp_session_file = Path(temp_session)
                if temp_session_file.exists():
                    try:
                        temp_session_file.unlink()
                        print(f"[AUTH] Удален temp файл: {temp_session}")
                    except Exception as e:
                        print(f"[AUTH] Ошибка при удалении temp файла: {e}")
                
                # Сохраняем данные пользователя
                self._user_data = user_data
                # НЕ очищаем QR-коды и НЕ отключаем клиент - он будет передан боту
                # self.active_qr_codes.clear() - оставляем клиент для бота
                print(f"[AUTH] submit_password: успешно завершен, клиент сохранен для бота")
                return user_data
            
            print(f"[AUTH] submit_password: не удалось получить данные пользователя")
                
        except Exception as e:
            print(f"[AUTH] Ошибка при вводе пароля: {e}")
            import traceback
            traceback.print_exc()
        
        return None
    
    def logout(self) -> bool:
        """
        Выход из аккаунта и очистка сессии
        
        Returns:
            bool: True если успешно
        """
        try:
            print(f"[AUTH] logout вызван")
            
            # Бот отключается сам через userbot_manager
            
            # Удаляем все файлы сессии (включая journal и другие)
            import glob
            session_files = list(config.SESSIONS_DIR.glob("user.session*"))
            print(f"[AUTH] Найдено файлов сессии для удаления: {len(session_files)}")
            for session_file in session_files:
                try:
                    session_file.unlink()
                    print(f"[AUTH] Удален файл сессии: {session_file.name}")
                except Exception as e:
                    print(f"[AUTH] Ошибка при удалении файла сессии {session_file.name}: {e}")
            
            # Очищаем данные
            self._user_data = None
            self.active_qr_codes.clear()
            
            print(f"[AUTH] logout успешен")
            return True
            
        except Exception as e:
            print(f"[AUTH] Ошибка при выходе: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_session_path(self) -> str:
        """
        Получает путь к файлу сессии
        
        Returns:
            str: Путь к сессии
        """
        return str(self.session_path)
    
    def get_client(self) -> Optional[TelegramClient]:
        """
        Получает активный клиент (deprecated - бот работает через userbot_manager)
        
        Returns:
            None
        """
        return None
    
    def get_user_photo(self, client=None) -> Optional[bytes]:
        """
        Получает фото профиля пользователя
        
        Args:
            client: Опциональный клиент для использования (если None - создает новый)
        
        Returns:
            bytes или None
        """
        print(f"[AUTH] get_user_photo вызван")
        
        if not self.is_authorized():
            print(f"[AUTH] get_user_photo: пользователь не авторизован")
            return None
        
        async def download_photo(provided_client):
            # Используем переданного клиента или создаем временного
            use_provided_client = provided_client is not None
            if not use_provided_client:
                provided_client = TelegramClient(str(self.session_path), config.API_ID, config.API_HASH)
                await provided_client.connect()
            
            try:
                user = await provided_client.get_me()
                if user is None:
                    print(f"[AUTH] get_user_photo: get_me() вернул None - клиент не авторизован")
                    if not use_provided_client:
                        await provided_client.disconnect()
                    return None
                if user.photo:
                    photo_data = await provided_client.download_profile_photo(user, file=bytes)
                    if not use_provided_client:
                        await provided_client.disconnect()
                    return photo_data
                if not use_provided_client:
                    await provided_client.disconnect()
                return None
            except Exception as e:
                print(f"[AUTH] get_user_photo: ошибка при загрузке: {e}")
                if not use_provided_client:
                    try:
                        await provided_client.disconnect()
                    except:
                        pass
                return None
        
        try:
            photo_data = self._run_async(download_photo(client))
            return photo_data
        except Exception as e:
            print(f"[AUTH] get_user_photo: ошибка: {e}")
            return None
    
    def get_active_sessions(self) -> List[Dict]:
        """
        Возвращает список активных сессий (для однопользовательской системы - один пользователь)
        
        Returns:
            List[Dict]: Список с данными текущего пользователя
        """
        if self.is_authorized():
            return [{"user_data": self._user_data}]
        return []
    
    def restore_sessions(self):
        """
        Восстанавливает активную сессию из файла при запуске сервера
        """
        print(f"[AUTH] restore_sessions вызван, путь: {self.session_path}")
        if not self.session_path.exists():
            print("[AUTH] restore_sessions: файл сессии не найден")
            return
        print(f"[AUTH] restore_sessions: файл сессии найден, начинаем восстановление")
        
        async def restore_session():
            print(f"[AUTH] restore_session: создаем клиента")
            await asyncio.sleep(0.5)  # Даем время БД разблокироваться
            client = TelegramClient(str(self.session_path), config.API_ID, config.API_HASH)
            try:
                print(f"[AUTH] restore_session: подключаемся к клиенту")
                await asyncio.wait_for(client.connect(), timeout=10)
                print(f"[AUTH] restore_session: клиент подключен, проверяем авторизацию")
                
                if await client.is_user_authorized():
                    user = await client.get_me()
                    print(f"[AUTH] restore_sessions: восстановлена сессия для {user.first_name}")
                    
                    user_data = {
                        "id": user.id,
                        "first_name": user.first_name,
                        "last_name": user.last_name or "",
                        "username": user.username or "",
                        "phone": user.phone or "",
                    }
                    
                    # Сохраняем данные
                    self._user_data = user_data
                    print(f"[AUTH] restore_session: отключаем клиента")
                    await client.disconnect()  # Отключаем, бот подключится сам
                    print(f"[AUTH] restore_session: клиент отключен")
                    return True
                else:
                    print(f"[AUTH] restore_session: пользователь не авторизован")
                    await client.disconnect()
                    return False
            except asyncio.TimeoutError:
                print(f"[AUTH] restore_session: таймаут подключения")
                try:
                    await client.disconnect()
                except:
                    pass
                return False
            except Exception as e:
                print(f"[AUTH] restore_sessions: ошибка: {e}")
                import traceback
                traceback.print_exc()
                try:
                    await client.disconnect()
                except:
                    pass
                return False
        
        try:
            self._run_async(restore_session())
        except Exception as e:
            print(f"[AUTH] restore_sessions: ошибка при восстановлении: {e}")
    
    def cleanup_expired_qr(self):
        """
        Очищает истекшие QR-коды из памяти и отключает их клиентов
        """
        current_time = time.time()
        expired_qr_ids = []
        
        for qr_id, qr_data in self.active_qr_codes.items():
            expires_at = qr_data.get("expires_at", 0)
            if current_time > expires_at:
                expired_qr_ids.append(qr_id)
        
        for qr_id in expired_qr_ids:
            print(f"[AUTH] Очистка истекшего QR: {qr_id}")
            qr_data = self.active_qr_codes[qr_id]
            # Отключаем клиента если он есть
            client = qr_data.get("qr_client")
            if client:
                try:
                    async def disconnect():
                        await client.disconnect()
                    self._run_async(disconnect())
                    print(f"[AUTH] Клиент для {qr_id} отключен")
                except Exception as e:
                    print(f"[AUTH] Ошибка при отключении клиента {qr_id}: {e}")
            # Удаляем temp сессии
            temp_session = qr_data.get("temp_session")
            if temp_session:
                temp_session_file = Path(temp_session)
                if temp_session_file.exists():
                    try:
                        temp_session_file.unlink()
                        print(f"[AUTH] Удален temp файл: {temp_session}")
                    except Exception as e:
                        print(f"[AUTH] Ошибка при удалении {temp_session}: {e}")
            # Удаляем файл QR-кода если он есть
            qr_file = qr_data.get("qr_file")
            if qr_file:
                qr_file_path = Path(qr_file)
                if qr_file_path.exists():
                    try:
                        qr_file_path.unlink()
                        print(f"[AUTH] Удален файл QR-кода: {qr_file}")
                    except Exception as e:
                        print(f"[AUTH] Ошибка при удалении файла QR-кода {qr_file}: {e}")
            # Удаляем из словаря
            del self.active_qr_codes[qr_id]
    
    def get_qr_client_and_clear(self, qr_id: str) -> Optional[TelegramClient]:
        """
        Получает клиент из QR-данных и очищает их
        
        Args:
            qr_id: ID QR-кода
            
        Returns:
            TelegramClient или None
        """
        if qr_id not in self.active_qr_codes:
            return None
        qr_data = self.active_qr_codes[qr_id]
        client = qr_data.get("qr_client")
        # Очищаем QR-данные
        del self.active_qr_codes[qr_id]
        return client
    
    def cleanup_temp_files(self):
        """
        Очищает все temp файлы сессий (вызывается при старте сервера и при генерации нового QR)
        Удаляет все файлы начинающиеся с temp_* включая .session, .session.journal и другие
        """
        print("[AUTH] cleanup_temp_files вызван")
        # Ищем все файлы начинающиеся с temp_
        temp_files = []
        # Ищем .session файлы
        temp_files.extend(config.SESSIONS_DIR.glob("temp_*.session"))
        # Ищем .session.journal файлы
        temp_files.extend(config.SESSIONS_DIR.glob("temp_*.session.journal"))
        # Ищем любые другие файлы начинающиеся с temp_
        temp_files.extend([f for f in config.SESSIONS_DIR.iterdir() 
                          if f.is_file() and f.name.startswith("temp_")])
        
        # Убираем дубликаты
        temp_files = list(set(temp_files))
        
        print(f"[AUTH] Найдено temp файлов: {len(temp_files)}")
        deleted_count = 0
        for temp_file in temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    deleted_count += 1
                    print(f"[AUTH] Удален temp файл: {temp_file.name}")
            except Exception as e:
                print(f"[AUTH] Ошибка при удалении {temp_file.name}: {e}")
        print(f"[AUTH] Удалено temp файлов: {deleted_count} из {len(temp_files)}")


# Глобальный экземпляр менеджера авторизации
auth_manager = AuthManager()


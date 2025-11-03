"""
Flask веб-приложение для авторизации через QR-код
"""
from flask import Flask, render_template, jsonify, request, send_file
import asyncio
import threading
import time
import os
from auth_manager import auth_manager
from userbot_manager import userbot_manager
from pathlib import Path
import config

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = config.SECRET_KEY


@app.route('/')
def index():
    """
    Главная страница с QR-кодом
    """
    return render_template('index.html')


@app.route('/inactive')
def inactive():
    """
    Страница заглушки для неактивных вкладок
    """
    try:
        return render_template('inactive.html')
    except Exception as e:
        print(f"[APP] Ошибка при рендеринге inactive.html: {e}")
        import traceback
        traceback.print_exc()
        # Возвращаем простую заглушку если шаблон не найден
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Inactive Tab</title></head>
        <body style="text-align: center; padding: 50px; font-family: Arial;">
            <h1>Такая ошибка, много вкладок</h1>
            <p>Telegram поддерживает только одну активную вкладку с приложением.</p>
            <p>Пожалуйста, перезагрузите эту страницу, чтобы продолжить использование в этой вкладке, или закройте её.</p>
            <button onclick="window.location.href='/'" style="padding: 10px 20px; font-size: 16px; cursor: pointer;">ПЕРЕЗАГРУЗИТЬ</button>
        </body>
        </html>
        """, 200


@app.route('/health', methods=['GET'])
def health():
    """
    Проверка здоровья сервиса для предотвращения остановки на бесплатном тарифе
    """
    return jsonify({
        'status': 'ok',
        'timestamp': time.time()
    }), 200


@app.route('/api/generate_qr', methods=['POST'])
def generate_qr():
    """
    Генерирует новый QR-код для авторизации
    
    Returns:
        JSON с qr_id и base64 изображением QR-кода
    """
    print("[API] generate_qr: запрос получен")
    try:
        # Проверяем переменные окружения ПЕРЕД началом работы
        print(f"[API] generate_qr: проверка переменных окружения:")
        print(f"[API] generate_qr: API_ID={config.API_ID} (тип: {type(config.API_ID)})")
        print(f"[API] generate_qr: API_HASH установлен={bool(config.API_HASH)}, длина={len(config.API_HASH) if config.API_HASH else 0}")
        
        if not config.API_ID or config.API_ID == 0 or not config.API_HASH or config.API_HASH == "":
            error_msg = "API_ID или API_HASH не установлены в переменных окружения Render!"
            print(f"[API] generate_qr: ОШИБКА КОНФИГУРАЦИИ - {error_msg}")
            print(f"[API] generate_qr: API_ID={config.API_ID}, API_HASH установлен={bool(config.API_HASH)}")
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500
        
        print(f"[API] generate_qr: переменные окружения валидны!")
        
        # Если уже авторизован, возвращаем сообщение
        if auth_manager.is_authorized():
            print("[API] generate_qr: пользователь уже авторизован")
            return jsonify({
                'success': False,
                'error': 'Already authorized'
            }), 400
        
        print("[API] generate_qr: начинаем генерацию QR-кода")
        print(f"[API] generate_qr: переменные окружения OK, API_ID={config.API_ID}")
        
        # Генерируем QR-код с таймаутом на уровне приложения
        import signal
        
        qr_id, qr_image = auth_manager.generate_qr_code()
        print(f"[API] generate_qr: QR-код успешно сгенерирован, qr_id: {qr_id}")
        return jsonify({
            'success': True,
            'qr_id': qr_id,
            'qr_image': qr_image
        })
    except TimeoutError as e:
        error_msg = f"Таймаут при генерации QR-кода: {e}"
        print(f"[API] generate_qr: ТАЙМАУТ - {error_msg}")
        return jsonify({
            'success': False,
            'error': error_msg
        }), 504  # Gateway Timeout
    except Exception as e:
        print(f"[API] generate_qr: ошибка: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/generate_qr_url', methods=['POST'])
def generate_qr_url():
    """
    Генерирует новый QR-код для авторизации и возвращает URL на изображение
    
    Returns:
        JSON с qr_id и URL на изображение QR-кода
    """
    try:
        # Если уже авторизован, возвращаем сообщение
        if auth_manager.is_authorized():
            return jsonify({
                'success': False,
                'error': 'Already authorized'
            }), 400
        
        qr_id, qr_url = auth_manager.generate_qr_code_url()
        return jsonify({
            'success': True,
            'qr_id': qr_id,
            'qr_url': qr_url
        })
    except Exception as e:
        print(f"[API] generate_qr_url: ошибка: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/check_status/<qr_id>')
def check_status(qr_id):
    """
    Проверяет статус авторизации
    
    Args:
        qr_id: ID QR-кода
        
    Returns:
        JSON с информацией о статусе авторизации
    """
    try:
        print(f"[API] check_status вызван для qr_id: {qr_id}")
        
        # Проверяем, авторизован ли пользователь
        if auth_manager.is_authorized():
            print(f"[API] check_status: уже авторизован")
            user_data = auth_manager.get_user_data()
            bot_active = userbot_manager.is_bot_active('main')
            return jsonify({
                'success': True,
                'authorized': True,
                'user_data': user_data,
                'bot_active': bot_active
            })
        
        # Проверяем валидность QR-кода
        if not auth_manager.is_qr_valid(qr_id):
            print(f"[API] check_status: QR-код невалиден или истек")
            return jsonify({
                'success': False,
                'qr_expired': True
            })
        
        # Проверяем статус авторизации
        user_data = auth_manager.check_authorization_status(qr_id)
        
        if user_data:
            # Проверяем, требуется ли пароль
            if user_data.get("needs_password"):
                print(f"[API] check_status: требуется пароль")
                return jsonify({
                    'success': True,
                    'needs_password': True
                })
            
            # Если авторизация прошла успешно, запускаем юзербота в отдельном потоке
            print(f"[API] check_status: авторизован, запускаем бота")
            if not userbot_manager.is_bot_active("main"):
                print(f"[API] check_status: запускаем бота в потоке")
                def start_bot_thread():
                    try:
                        print(f"[BOT] Запускаем бота в потоке {threading.current_thread().name}")
                        loop = auth_manager._get_loop()
                        # Получаем клиент из QR
                        client = auth_manager.get_qr_client_and_clear(qr_id)
                        if not client:
                            print(f"[BOT] Ошибка: клиент из QR не найден")
                            return
                        print(f"[BOT] Получили клиент из QR, регистрируем бота")
                        async def init_bot():
                            try:
                                # Клиент уже подключен из QR
                                print(f"[BOT] init_bot: регистрируем бота")
                                await userbot_manager.start_bot("main", client)
                                print(f"[BOT] init_bot: бот зарегистрирован")
                                return client
                            except Exception as e:
                                print(f"[BOT] init_bot: ошибка: {e}")
                                import traceback
                                traceback.print_exc()
                                raise
                        future = asyncio.run_coroutine_threadsafe(init_bot(), loop)
                        print(f"[BOT] Ждем завершения запуска бота")
                        future.result(timeout=10)  # Таймаут 10 секунд
                        print(f"[BOT] Бот запущен")
                    except Exception as e:
                        print(f"[BOT] Ошибка в потоке бота: {e}")
                        import traceback
                        traceback.print_exc()
                threading.Thread(target=start_bot_thread, daemon=True).start()
                # Небольшая задержка чтобы бот успел запуститься
                import time
                time.sleep(0.5)
            
            bot_active = userbot_manager.is_bot_active('main')
            return jsonify({
                'success': True,
                'authorized': True,
                'user_data': user_data,
                'bot_active': bot_active
            })
        else:
            print(f"[API] check_status: не авторизован")
            return jsonify({
                'success': True,
                'authorized': False
            })
            
    except Exception as e:
        print(f"[API] check_status: ошибка: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/user_photo')
def user_photo():
    """
    Отдает фото пользователя из Telegram
    
    Returns:
        Файл изображения
    """
    try:
        print(f"[API] user_photo вызван")
        
        if not auth_manager.is_authorized():
            print(f"[API] user_photo: пользователь не авторизован")
            return '', 404
        
        # Получаем клиента из активного бота, если он есть
        bot_client = None
        if userbot_manager.is_bot_active("main"):
            bot_client = userbot_manager.get_client("main")
            print(f"[API] user_photo: используем клиента из активного бота")
        
        photo_data = auth_manager.get_user_photo(client=bot_client)
        
        if photo_data:
            from io import BytesIO
            print(f"[API] user_photo: отправляем фото, размер: {len(photo_data)}")
            return send_file(BytesIO(photo_data), mimetype='image/jpeg')
        
        print(f"[API] user_photo: фото не найдено")
        return '', 404
            
    except Exception as e:
        print(f"[API] user_photo: ошибка: {e}")
        import traceback
        traceback.print_exc()
        return '', 404


@app.route('/api/submit_password/<qr_id>', methods=['POST'])
def submit_password(qr_id):
    """
    Отправляет пароль 2FA
    
    Args:
        qr_id: ID сессии
        
    Returns:
        JSON с результатом операции
    """
    try:
        print(f"[API] submit_password вызван для qr_id: {qr_id}")
        data = request.get_json()
        password = data.get('password')
        
        if not password:
            print(f"[API] submit_password: пароль не указан")
            return jsonify({
                'success': False,
                'error': 'Password required'
            }), 400
        
        print(f"[API] submit_password: отправляем пароль в auth_manager")
        user_data = auth_manager.submit_password(qr_id, password)
        
        if user_data:
            print(f"[API] submit_password: пользователь авторизован: {user_data}")
            
            # Запускаем юзербота используя клиент из QR в отдельном потоке
            if not userbot_manager.is_bot_active("main"):
                print(f"[API] submit_password: запускаем бота в потоке")
                def start_bot_thread():
                    try:
                        print(f"[BOT] Запускаем бота в потоке {threading.current_thread().name}")
                        loop = auth_manager._get_loop()
                        # Получаем клиент из QR
                        client = auth_manager.get_qr_client_and_clear(qr_id)
                        if not client:
                            print(f"[BOT] Ошибка: клиент из QR не найден")
                            return
                        print(f"[BOT] Получили клиент из QR, регистрируем бота")
                        async def init_bot():
                            try:
                                # Клиент уже подключен из QR
                                print(f"[BOT] init_bot: регистрируем бота")
                                await userbot_manager.start_bot("main", client)
                                print(f"[BOT] init_bot: бот зарегистрирован")
                                return client
                            except Exception as e:
                                print(f"[BOT] init_bot: ошибка: {e}")
                                import traceback
                                traceback.print_exc()
                                raise
                        future = asyncio.run_coroutine_threadsafe(init_bot(), loop)
                        print(f"[BOT] Ждем завершения запуска бота")
                        future.result(timeout=10)  # Таймаут 10 секунд
                        print(f"[BOT] Бот запущен")
                    except Exception as e:
                        print(f"[BOT] Ошибка в потоке бота: {e}")
                        import traceback
                        traceback.print_exc()
                threading.Thread(target=start_bot_thread, daemon=True).start()
                # Небольшая задержка чтобы бот успел запуститься
                import time
                time.sleep(0.5)
            
            bot_active = userbot_manager.is_bot_active('main')
            return jsonify({
                'success': True,
                'authorized': True,
                'user_data': user_data,
                'bot_active': bot_active
            })
        else:
            print(f"[API] submit_password: неверный пароль")
            return jsonify({
                'success': False,
                'error': 'Invalid password'
            }), 401
            
    except Exception as e:
        print(f"[API] submit_password: ошибка: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/active_sessions')
def active_sessions():
    """
    Возвращает список активных сессий
    
    Returns:
        JSON со списком активных сессий и статусом бота
    """
    try:
        sessions = auth_manager.get_active_sessions()
        bot_active = userbot_manager.is_bot_active('main')
        print(f"[API] active_sessions: sessions={sessions}, bot_active={bot_active}")
        # НЕ запускаем бота автоматически в active_sessions - только при явной авторизации
        return jsonify({
            'success': True,
            'sessions': sessions,
            'bot_active': bot_active
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/check_session_status')
def check_session_status():
    """
    Проверяет статус активной сессии и возвращает её валидность
    """
    try:
        print(f"[API] check_session_status вызван")
        # Проверяем, есть ли данные пользователя
        if auth_manager.is_authorized():
            # Проверяем, активен ли бот
            bot_active = userbot_manager.is_bot_active('main')
            # Проверяем валидность сессии независимо от статуса бота
            session_path = auth_manager.get_session_path()
            if Path(session_path).exists():
                # Пытаемся подключиться и проверить
                from telethon import TelegramClient
                from telethon.errors import AuthKeyUnregisteredError, SessionRevokedError, UnauthorizedError
                async def check_session():
                    # Получаем клиента из активного бота если есть
                    bot_client = None
                    if bot_active:
                        bot_client = userbot_manager.get_client('main')
                    
                    if bot_client:
                        # Используем клиента бота для проверки
                        try:
                            user = await bot_client.get_me()
                            if user is None:
                                return False
                            return True
                        except (AuthKeyUnregisteredError, SessionRevokedError, UnauthorizedError) as e:
                            print(f"[API] check_session_status: сессия невалидна через бота - {type(e).__name__}")
                            return False
                        except Exception as e:
                            print(f"[API] check_session_status: ошибка при проверке через бота: {type(e).__name__}")
                            return False
                    else:
                        # Создаем временного клиента для проверки
                        client = TelegramClient(str(session_path), config.API_ID, config.API_HASH)
                        try:
                            await client.connect()
                            is_authorized = await client.is_user_authorized()
                            await client.disconnect()
                            return is_authorized
                        except (AuthKeyUnregisteredError, SessionRevokedError, UnauthorizedError) as e:
                            print(f"[API] check_session_status: сессия невалидна - {type(e).__name__}")
                            try:
                                await client.disconnect()
                            except:
                                pass
                            return False
                        except Exception as e:
                            print(f"[API] check_session_status: ошибка при проверке: {type(e).__name__}")
                            try:
                                await client.disconnect()
                            except:
                                pass
                            return False
                is_valid = auth_manager._run_async(check_session())
                if is_valid:
                    print(f"[API] check_session_status: сессия валидна")
                    return jsonify({
                        'success': True,
                        'session_valid': True
                    })
                else:
                    print(f"[API] check_session_status: сессия невалидна")
                    return jsonify({
                        'success': True,
                        'session_valid': False
                    })
            else:
                print(f"[API] check_session_status: файл сессии не существует")
                return jsonify({
                    'success': True,
                    'session_valid': False
                })
        else:
            print(f"[API] check_session_status: сессия не найдена")
            return jsonify({
                'success': True,
                'session_valid': False
            })
    except Exception as e:
        print(f"[API] check_session_status: ошибка: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/logout', methods=['POST'])
def logout():
    """
    Выход из аккаунта и остановка юзербота
    
    Returns:
        JSON с результатом операции
    """
    try:
        print(f"[API] logout вызван")
        # Останавливаем юзербота
        if userbot_manager.is_bot_active("main"):
            print(f"[API] logout: останавливаем бота")
            loop = auth_manager._get_loop()
            async def stop_bot():
                await userbot_manager.stop_bot("main")
            future = asyncio.run_coroutine_threadsafe(stop_bot(), loop)
            future.result(timeout=5)  # Таймаут 5 секунд
            print(f"[API] logout: бот остановлен")
        else:
            print(f"[API] logout: бот не был активен")
        
        # Выходим из аккаунта
        auth_manager.logout()
        print(f"[API] logout: успешно завершен")
        
        return jsonify({
            'success': True
        })
        
    except Exception as e:
        print(f"[API] logout: ошибка: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/toggle_bot', methods=['POST'])
def toggle_bot():
    """
    Включает/выключает работу бота
    
    Returns:
        JSON с результатом операции
    """
    try:
        print(f"[API] toggle_bot вызван")
        
        if not auth_manager.is_authorized():
            print(f"[API] toggle_bot: пользователь не авторизован")
            return jsonify({
                'success': False,
                'error': 'Not authorized'
            }), 401
        
        data = request.get_json()
        enabled = data.get('enabled', False)
        
        loop = auth_manager._get_loop()
        
        if enabled:
            # Включаем бота (если еще не активен)
            if not userbot_manager.is_bot_active("main"):
                print(f"[API] toggle_bot: запускаем бота")
                def start_bot_thread():
                    try:
                        print(f"[BOT] Запускаем бота в потоке {threading.current_thread().name}")
                        async def init_bot():
                            try:
                                await asyncio.sleep(1)
                                print(f"[BOT] init_bot: получаем путь к сессии")
                                session_path = auth_manager.get_session_path()
                                print(f"[BOT] init_bot: создаем клиента")
                                from telethon import TelegramClient
                                client = TelegramClient(str(session_path), config.API_ID, config.API_HASH)
                                print(f"[BOT] init_bot: подключаемся к клиенту")
                                await client.connect()
                                print(f"[BOT] init_bot: клиент подключен, регистрируем бота")
                                await userbot_manager.start_bot("main", client)
                                print(f"[BOT] init_bot: бот зарегистрирован")
                                return client
                            except Exception as e:
                                print(f"[BOT] init_bot: ошибка: {e}")
                                import traceback
                                traceback.print_exc()
                                raise
                        future = asyncio.run_coroutine_threadsafe(init_bot(), loop)
                        print(f"[BOT] Ждем завершения запуска бота")
                        future.result(timeout=10)  # Таймаут 10 секунд
                        print(f"[BOT] Бот запущен")
                    except Exception as e:
                        print(f"[BOT] Ошибка в потоке бота: {e}")
                        import traceback
                        traceback.print_exc()
                threading.Thread(target=start_bot_thread, daemon=True).start()
            else:
                print(f"[API] toggle_bot: бот уже активен")
        else:
            # Выключаем бота
            if userbot_manager.is_bot_active("main"):
                print(f"[API] toggle_bot: останавливаем бота")
                async def stop_bot():
                    await userbot_manager.stop_bot("main")
                future = asyncio.run_coroutine_threadsafe(stop_bot(), loop)
                future.result()
                print(f"[API] toggle_bot: бот остановлен")
            else:
                print(f"[API] toggle_bot: бот не был активен")
        
        return jsonify({
            'success': True
        })
        
    except Exception as e:
        print(f"[API] toggle_bot: ошибка: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def cleanup_expired_qr_periodically():
    """Периодически очищает истекшие QR-коды"""
    print("[APP] Поток очистки QR-кодов запущен")
    while True:
        time.sleep(60)  # Проверка каждую минуту
        try:
            print("[APP] Запуск очистки истекших QR-кодов")
            auth_manager.cleanup_expired_qr()
        except Exception as e:
            print(f"[APP] Ошибка при очистке истекших QR: {e}")


def setup_keepalive():
    """Настраивает периодические запросы для поддержания сервиса активным (только для разработки)"""
    try:
        import requests
    except ImportError:
        print("[KEEPALIVE] requests не установлен, keepalive отключен")
        return
    
    def ping_health():
        """Отправляет запрос к /health каждые 50 секунд"""
        try:
            port = os.getenv('PORT', '5000')
            url = f'http://localhost:{port}/health'
            requests.get(url, timeout=5)
            print("[KEEPALIVE] Health check sent")
        except Exception as e:
            print(f"[KEEPALIVE] Error: {e}")
    
    # Запускаем ping каждые 50 секунд (меньше чем таймаут бездействия Render ~60 секунд)
    def keepalive_loop():
        while True:
            time.sleep(50)
            ping_health()
    
    threading.Thread(target=keepalive_loop, daemon=True).start()
    print("[KEEPALIVE] Keepalive thread started (only for local development)")


def handle_user_logout():
    """
    Callback для вызова когда пользователь завершает сессию в Telegram
    """
    print(f"[APP] handle_user_logout вызван - пользователь завершил сессию в Telegram")
    # Выполняем logout через auth_manager
    auth_manager.logout()
    print(f"[APP] handle_user_logout: данные очищены")


if __name__ == '__main__':
    # Создаем директорию для шаблонов если её нет
    Path('templates').mkdir(exist_ok=True)
    Path('static').mkdir(exist_ok=True)
    
    # Устанавливаем callback для logout
    userbot_manager.set_logout_callback(handle_user_logout)
    
    # Очищаем temp файлы при старте
    auth_manager.cleanup_temp_files()
    
    # Восстанавливаем сессии при запуске в отдельном потоке
    threading.Thread(target=auth_manager.restore_sessions, daemon=True).start()
    
    # Запускаем периодическую очистку истекших QR
    threading.Thread(target=cleanup_expired_qr_periodically, daemon=True).start()
    
    # Запускаем keepalive для бесплатного тарифа Render (только если не в production через gunicorn)
    if os.getenv('GUNICORN_WORKERS') is None:  # Значит запущен через python app.py
        setup_keepalive()
    
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.DEBUG,
        threaded=True,
        use_reloader=False  # Отключаем reloader чтобы потоки не убивались
    )


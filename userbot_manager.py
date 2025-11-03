"""
Менеджер юзербота для обработки сообщений
"""
import asyncio
import time
from typing import Optional, Callable
from telethon import TelegramClient, events
from telethon.errors import AuthKeyUnregisteredError, SessionRevokedError, UnauthorizedError
import config


class UserbotManager:
    """
    Класс для управления юзерботом
    """
    
    def __init__(self):
        # Словарь активных ботов: {session_id: client}
        self.active_bots: dict = {}
        # Словарь event loops для ботов: {session_id: event_loop}
        self.bot_loops: dict = {}
        # Callback для вызова при отключении пользователем
        self.logout_callback: Optional[Callable] = None
    
    def set_logout_callback(self, callback: Callable):
        """
        Устанавливает callback для вызова при logout
        
        Args:
            callback: Функция для вызова
        """
        self.logout_callback = callback
        
    async def start_bot(self, session_id: str, client: TelegramClient) -> bool:
        """
        Запускает юзербота для отправки эхо-сообщений
        
        Args:
            session_id: ID сессии
            client: TelegramClient с активной сессией
            
        Returns:
            bool: True если бот успешно запущен
        """
        try:
            print(f"[BOT] start_bot вызван для session_id: {session_id}")
            
            # Если бот уже запущен - останавливаем его сначала
            if session_id in self.active_bots:
                print(f"[BOT] start_bot: бот уже запущен для {session_id}, останавливаем старый")
                old_client = self.active_bots[session_id]
                try:
                    await old_client.disconnect()
                    print(f"[BOT] Старый клиент отключен")
                except Exception as e:
                    print(f"[BOT] Ошибка при отключении старого клиента: {e}")
                del self.active_bots[session_id]
            
            # Используем уже авторизованного клиента для работы юзербота
            userbot_client = client
            print(f"[BOT] start_bot: клиент получен, регистрируем обработчики")
            
            # Функция для обработки отключения сессии
            async def handle_session_logout(error=None):
                """
                Обрабатывает отключение сессии (удаление в Telegram)
                """
                try:
                    error_type = type(error).__name__ if error else "Unknown"
                    print(f"[BOT] Обнаружено отключение сессии: {error_type}")
                    
                    # Удаляем бота из активных
                    if session_id in self.active_bots:
                        del self.active_bots[session_id]
                        print(f"[BOT] Бот удален из активных")
                    
                    # Вызываем callback если он установлен
                    if self.logout_callback:
                        print(f"[BOT] Вызываем logout_callback для отключения сессии")
                        self.logout_callback()
                except Exception as callback_error:
                    print(f"[BOT] Ошибка в handle_session_logout: {callback_error}")
                    import traceback
                    traceback.print_exc()
            
            # Регистрируем обработчик для всех входящих сообщений
            @userbot_client.on(events.NewMessage(incoming=True))
            async def echo_handler(event):
                """
                Обработчик для эхо-ответов на все входящие сообщения
                """
                # Проверяем, что сообщение не от самого себя
                if event.is_private:
                    try:
                        print(f"[BOT] Получено сообщение: {event.message.text if event.message.text else 'медиа'}")
                        # Получаем текст сообщения или информацию о медиа
                        if event.message.text:
                            response_text = event.message.text
                        elif event.message.media:
                            response_text = "Получено медиа"
                        else:
                            response_text = "Получено неизвестное сообщение"
                        
                        # Отправляем эхо-ответ
                        await event.reply(response_text)
                        print(f"[BOT] Эхо-ответ отправлен")
                        
                    except (AuthKeyUnregisteredError, SessionRevokedError, UnauthorizedError) as e:
                        print(f"[BOT] Сессия стала невалидной при отправке ответа: {type(e).__name__}")
                        await handle_session_logout(e)
                    except Exception as e:
                        print(f"[BOT] Ошибка при отправке эхо-ответа: {e}")
            
            # Также добавляем периодическую проверку валидности сессии (каждые 20 секунд)
            async def periodic_session_check():
                """
                Периодически проверяет валидность сессии через простой API вызов
                """
                while session_id in self.active_bots:
                    try:
                        await asyncio.sleep(20)  # Проверка каждые 20 секунд
                        
                        # Проверяем что клиент все еще в активных ботах
                        if session_id not in self.active_bots:
                            print(f"[BOT] Периодическая проверка: бот больше не активен, прекращаем проверку")
                            break
                        
                        # Проверяем валидность сессии через вызов get_me()
                        # Используем тот же client, который уже работает в текущем event loop
                        # Это предотвращает ошибку "The asyncio event loop must not change after connection"
                        try:
                            # Проверяем что клиент подключен перед вызовом get_me()
                            if not userbot_client.is_connected():
                                print(f"[BOT] Периодическая проверка: клиент не подключен, сессия невалидна")
                                await handle_session_logout()
                                break
                            
                            user = await asyncio.wait_for(userbot_client.get_me(), timeout=5)
                            if user is None:
                                print(f"[BOT] Периодическая проверка: get_me() вернул None - сессия невалидна")
                                await handle_session_logout()
                                break
                        except (AuthKeyUnregisteredError, SessionRevokedError, UnauthorizedError) as e:
                            print(f"[BOT] Периодическая проверка: сессия отозвана: {type(e).__name__}")
                            await handle_session_logout(e)
                            break
                        except asyncio.TimeoutError:
                            print(f"[BOT] Периодическая проверка: таймаут при get_me()")
                            # Таймаут - не критично, продолжаем проверку
                            continue
                        except RuntimeError as e:
                            error_msg = str(e)
                            if "asyncio event loop must not change" in error_msg.lower():
                                print(f"[BOT] Периодическая проверка: RuntimeError (event loop changed) - пропускаем эту проверку")
                                # Эта ошибка возникает если клиент используется в другом loop
                                # Не критично, просто пропускаем эту проверку
                                continue
                            else:
                                # Другие RuntimeError - критичны
                                raise
                    except Exception as e:
                        error_name = type(e).__name__
                        # Для критических ошибок авторизации прерываем цикл
                        if isinstance(e, (AuthKeyUnregisteredError, SessionRevokedError, UnauthorizedError)):
                            print(f"[BOT] Периодическая проверка: критическая ошибка авторизации: {error_name}")
                            await handle_session_logout(e)
                            break
                        print(f"[BOT] Ошибка при периодической проверке сессии: {error_name}: {e}")
                        # Не прерываем цикл при обычных ошибках
                        continue
            
            # Запускаем периодическую проверку в фоне
            asyncio.create_task(periodic_session_check())
            
            print(f"[BOT] start_bot: обработчик зарегистрирован, сохраняем бота")
            # Сохраняем бота
            self.active_bots[session_id] = userbot_client
            # Event loop будет сохранен в start_bot_with_client или в restore_and_start_bot
            # Не пытаемся получить его здесь, так как он может быть не установлен или клиент может быть из другого loop
            
            print(f"[BOT] Юзербот для сессии {session_id} успешно запущен")
            return True
            
        except Exception as e:
            print(f"[BOT] Ошибка при запуске юзербота: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def stop_bot(self, session_id: str) -> bool:
        """
        Останавливает юзербота
        
        Args:
            session_id: ID сессии
            
        Returns:
            bool: True если бот успешно остановлен
        """
        try:
            if session_id in self.active_bots:
                # Отключаем клиента перед удалением
                client = self.active_bots[session_id]
                try:
                    await client.disconnect()
                    print(f"[BOT] Клиент для сессии {session_id} отключен")
                except Exception as e:
                    print(f"[BOT] Ошибка при отключении клиента: {e}")
                
                # Закрываем event loop если он есть
                if session_id in self.bot_loops:
                    bot_loop = self.bot_loops[session_id]
                    try:
                        # Останавливаем loop если он запущен в другом потоке
                        if bot_loop.is_running():
                            # Останавливаем loop через call_soon_threadsafe
                            bot_loop.call_soon_threadsafe(bot_loop.stop)
                            print(f"[BOT] Отправлен сигнал остановки event loop для сессии {session_id}")
                            # Ждем немного чтобы loop остановился
                            time.sleep(0.5)
                        else:
                            # Loop не запущен - можем закрыть сразу
                            if not bot_loop.is_closed():
                                bot_loop.close()
                                print(f"[BOT] Event loop для сессии {session_id} закрыт")
                    except Exception as e:
                        print(f"[BOT] Ошибка при закрытии event loop: {e}")
                        import traceback
                        traceback.print_exc()
                    finally:
                        # Удаляем loop из словаря
                        if session_id in self.bot_loops:
                            del self.bot_loops[session_id]
                
                # Удаляем из активных ботов
                del self.active_bots[session_id]
                print(f"[BOT] Юзербот для сессии {session_id} остановлен")
                return True
            
            return False
            
        except Exception as e:
            print(f"[BOT] Ошибка при остановке юзербота: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def is_bot_active(self, session_id: str) -> bool:
        """
        Проверяет, активен ли бот для данной сессии
        
        Args:
            session_id: ID сессии
            
        Returns:
            bool: True если бот активен
        """
        return session_id in self.active_bots
    
    def get_client(self, session_id: str) -> Optional[TelegramClient]:
        """
        Получает клиента активного бота
        
        Args:
            session_id: ID сессии
            
        Returns:
            TelegramClient или None
        """
        return self.active_bots.get(session_id)


# Глобальный экземпляр менеджера юзербота
userbot_manager = UserbotManager()


# API Документация

Документация REST API для веб-приложения авторизации Telegram через QR-код.

## Базовый URL

```
http://localhost:5000
```

## Формат ответов

Все API эндпоинты возвращают JSON объекты. В случае успеха поле `success` равно `true`, при ошибке - `false` и добавляется поле `error`.

## Эндпоинты

### Страницы

#### GET `/`
Главная страница приложения с интерфейсом авторизации через QR-код.

**Ответ:** HTML страница

---

#### GET `/inactive`
Страница-заглушка для неактивных вкладок браузера.

**Ответ:** HTML страница

---

### Авторизация

#### POST `/api/generate_qr`
Генерирует новый QR-код для авторизации в Telegram.

**Метод:** `POST`

**Заголовки:**
```
Content-Type: application/json
```

**Тело запроса:** Отсутствует

**Успешный ответ (200):**
```json
{
  "success": true,
  "qr_id": "uuid-string",
  "qr_image": "data:image/png;base64,iVBORw0KGgoAAAANS..."
}
```

**Ошибки:**
- `400` - Пользователь уже авторизован
  ```json
  {
    "success": false,
    "error": "Already authorized"
  }
  ```
- `500` - Внутренняя ошибка сервера
  ```json
  {
    "success": false,
    "error": "Error message"
  }
  ```

**Пример использования:**
```javascript
const response = await fetch('/api/generate_qr', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  }
});
const data = await response.json();
console.log(data.qr_id, data.qr_image);
```

---

#### GET `/api/check_status/<qr_id>`
Проверяет статус авторизации по QR-коду.

**Метод:** `GET`

**Параметры URL:**
- `qr_id` (string) - ID QR-кода, полученный из `/api/generate_qr`

**Успешный ответ (200):**

**Если не авторизован:**
```json
{
  "success": true,
  "authorized": false
}
```

**Если требуется пароль 2FA:**
```json
{
  "success": true,
  "needs_password": true
}
```

**Если авторизован:**
```json
{
  "success": true,
  "authorized": true,
  "user_data": {
    "id": 123456789,
    "first_name": "Имя",
    "last_name": "Фамилия",
    "username": "username",
    "phone": "1234567890"
  },
  "bot_active": true
}
```

**Ошибки:**
- `500` - Внутренняя ошибка сервера
  ```json
  {
    "success": false,
    "error": "Error message"
  }
  ```

**Пример использования:**
```javascript
const qrId = "uuid-string";
const response = await fetch(`/api/check_status/${qrId}`);
const data = await response.json();

if (data.authorized) {
  console.log("Пользователь авторизован:", data.user_data);
} else if (data.needs_password) {
  console.log("Требуется пароль 2FA");
} else {
  console.log("Ожидание авторизации...");
}
```

**Примечания:**
- Эндпоинт должен вызываться периодически (рекомендуется каждые 2 секунды) для проверки статуса авторизации
- После успешной авторизации автоматически запускается юзербот (если еще не запущен)
- QR-код истекает через 10 минут, после чего нужно генерировать новый

---

#### POST `/api/submit_password/<qr_id>`
Отправляет пароль двухфакторной аутентификации (2FA) для завершения авторизации.

**Метод:** `POST`

**Параметры URL:**
- `qr_id` (string) - ID QR-кода или сессии

**Заголовки:**
```
Content-Type: application/json
```

**Тело запроса:**
```json
{
  "password": "your_2fa_password"
}
```

**Успешный ответ (200):**
```json
{
  "success": true,
  "authorized": true,
  "user_data": {
    "id": 123456789,
    "first_name": "Имя",
    "last_name": "Фамилия",
    "username": "username",
    "phone": "1234567890"
  },
  "bot_active": true
}
```

**Ошибки:**
- `400` - Пароль не указан
  ```json
  {
    "success": false,
    "error": "Password required"
  }
  ```
- `401` - Неверный пароль
  ```json
  {
    "success": false,
    "error": "Invalid password"
  }
  ```
- `500` - Внутренняя ошибка сервера
  ```json
  {
    "success": false,
    "error": "Error message"
  }
  ```

**Пример использования:**
```javascript
const qrId = "uuid-string";
const password = "your_2fa_password";

const response = await fetch(`/api/submit_password/${qrId}`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ password })
});

const data = await response.json();

if (data.success && data.authorized) {
  console.log("Авторизация успешна:", data.user_data);
} else {
  console.error("Ошибка:", data.error);
}
```

---

### Профиль пользователя

#### GET `/api/user_photo`
Получает фотографию профиля авторизованного пользователя.

**Метод:** `GET`

**Успешный ответ (200):**
- Изображение JPEG

**Ошибки:**
- `404` - Пользователь не авторизован или фото отсутствует

**Пример использования:**
```javascript
const response = await fetch('/api/user_photo');
if (response.ok) {
  const blob = await response.blob();
  const imageUrl = URL.createObjectURL(blob);
  // Использовать imageUrl для отображения
}
```

---

### Управление сессиями

#### GET `/api/active_sessions`
Возвращает список активных сессий авторизованного пользователя.

**Метод:** `GET`

**Успешный ответ (200):**
```json
{
  "success": true,
  "sessions": [
    {
      "user_data": {
        "id": 123456789,
        "first_name": "Имя",
        "last_name": "Фамилия",
        "username": "username",
        "phone": "1234567890"
      }
    }
  ],
  "bot_active": true
}
```

**Ошибки:**
- `500` - Внутренняя ошибка сервера
  ```json
  {
    "success": false,
    "error": "Error message"
  }
  ```

**Пример использования:**
```javascript
const response = await fetch('/api/active_sessions');
const data = await response.json();

if (data.success && data.sessions.length > 0) {
  console.log("Активные сессии:", data.sessions);
  console.log("Бот активен:", data.bot_active);
}
```

---

#### GET `/api/check_session_status`
Проверяет валидность текущей активной сессии.

**Метод:** `GET`

**Успешный ответ (200):**

**Если сессия валидна:**
```json
{
  "success": true,
  "session_valid": true
}
```

**Если сессия невалидна:**
```json
{
  "success": true,
  "session_valid": false
}
```

**Ошибки:**
- `500` - Внутренняя ошибка сервера
  ```json
  {
    "success": false,
    "error": "Error message"
  }
  ```

**Пример использования:**
```javascript
const response = await fetch('/api/check_session_status');
const data = await response.json();

if (data.success) {
  if (data.session_valid) {
    console.log("Сессия валидна");
  } else {
    console.log("Сессия невалидна - требуется повторная авторизация");
  }
}
```

**Примечания:**
- Эндпоинт проверяет не только наличие сессии, но и её действительность в Telegram
- Если сессия была отозвана в Telegram, вернется `session_valid: false`
- Рекомендуется периодически проверять статус сессии (каждые 5-10 секунд)

---

#### POST `/api/logout`
Выполняет выход из аккаунта, останавливает юзербота и очищает сессию.

**Метод:** `POST`

**Заголовки:**
```
Content-Type: application/json
```

**Тело запроса:** Отсутствует (можно отправить пустой объект `{}`)

**Успешный ответ (200):**
```json
{
  "success": true
}
```

**Ошибки:**
- `500` - Внутренняя ошибка сервера
  ```json
  {
    "success": false,
    "error": "Error message"
  }
  ```

**Пример использования:**
```javascript
const response = await fetch('/api/logout', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  }
});

const data = await response.json();

if (data.success) {
  console.log("Выход выполнен успешно");
  // Перенаправить на страницу авторизации
} else {
  console.error("Ошибка при выходе:", data.error);
}
```

**Примечания:**
- После вызова эндпоинта все данные сессии удаляются
- Юзербот автоматически останавливается
- Для повторной авторизации необходимо заново сгенерировать QR-код

---

### Управление ботом

#### POST `/api/toggle_bot`
Включает или выключает работу юзербота.

**Метод:** `POST`

**Заголовки:**
```
Content-Type: application/json
```

**Тело запроса:**
```json
{
  "enabled": true
}
```

**Параметры:**
- `enabled` (boolean, обязательный) - `true` для включения бота, `false` для выключения

**Успешный ответ (200):**
```json
{
  "success": true
}
```

**Ошибки:**
- `401` - Пользователь не авторизован
  ```json
  {
    "success": false,
    "error": "Not authorized"
  }
  ```
- `500` - Внутренняя ошибка сервера
  ```json
  {
    "success": false,
    "error": "Error message"
  }
  ```

**Пример использования:**
```javascript
// Включить бота
const response = await fetch('/api/toggle_bot', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ enabled: true })
});

const data = await response.json();

if (data.success) {
  console.log("Бот включен");
} else {
  console.error("Ошибка:", data.error);
}

// Выключить бота
const response2 = await fetch('/api/toggle_bot', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ enabled: false })
});
```

**Примечания:**
- Бот работает только при авторизованном пользователе
- Бот автоматически отвечает на все входящие сообщения эхом
- При включении бота, если он еще не запущен, создается новое подключение к Telegram

---

## Коды состояния HTTP

| Код | Описание |
|-----|----------|
| 200 | Успешный запрос |
| 400 | Неверный запрос (неправильные параметры) |
| 401 | Не авторизован |
| 404 | Ресурс не найден |
| 500 | Внутренняя ошибка сервера |

## Обработка ошибок

Все ошибки возвращаются в формате JSON с полями:
- `success` (boolean) - всегда `false` при ошибке
- `error` (string) - описание ошибки

Пример:
```json
{
  "success": false,
  "error": "Error message description"
}
```

## Примеры использования

### Полный цикл авторизации

```javascript
// 1. Генерируем QR-код
const generateResponse = await fetch('/api/generate_qr', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' }
});
const qrData = await generateResponse.json();
const qrId = qrData.qr_id;

// 2. Периодически проверяем статус
const checkInterval = setInterval(async () => {
  const statusResponse = await fetch(`/api/check_status/${qrId}`);
  const statusData = await statusResponse.json();
  
  if (statusData.authorized) {
    clearInterval(checkInterval);
    console.log("Авторизация успешна:", statusData.user_data);
  } else if (statusData.needs_password) {
    clearInterval(checkInterval);
    // Показать форму для ввода пароля
    showPasswordForm(qrId);
  } else if (!statusData.success && statusData.qr_expired) {
    clearInterval(checkInterval);
    // QR-код истек, генерируем новый
    generateNewQR();
  }
}, 2000); // Проверка каждые 2 секунды

// 3. Если требуется пароль 2FA
async function submitPassword(qrId, password) {
  const response = await fetch(`/api/submit_password/${qrId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password })
  });
  const data = await response.json();
  return data;
}

// 4. Выход из аккаунта
async function logout() {
  const response = await fetch('/api/logout', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });
  const data = await response.json();
  return data;
}
```

## Лимиты и ограничения

- QR-код действителен **10 минут** с момента генерации
- После истечения QR-кода необходимо генерировать новый
- Одновременно может быть активна только **одна сессия** на пользователя
- Бот работает только при активной авторизованной сессии

## Безопасность

- Все сессии хранятся локально в папке `sessions/`
- API не использует токены аутентификации - проверка происходит через сессии Telegram
- Рекомендуется запускать приложение только на `localhost` или за защищенным прокси
- Для продакшена рекомендуется использовать HTTPS

## Поддержка

При возникновении проблем проверьте:
1. Логи сервера в консоли
2. Валидность API credentials (`API_ID`, `API_HASH`)
3. Статус подключения к интернету
4. Доступность Telegram API


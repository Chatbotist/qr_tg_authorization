// Управление состоянием приложения
let currentQrId = null;
let statusCheckInterval = null;
let qrTimerInterval = null;
let sessionCheckInterval = null; // Интервал для проверки сессии
let qrTimeLeft = 25; // Таймаут QR кода
let isSubmittingPassword = false; // Флаг для предотвращения двойной отправки пароля

// BroadcastChannel для отслеживания активной вкладки
const CHANNEL_NAME = 'tg_qr_auth_tab_control';
let tabChannel = null;
let isActiveTab = false;
let tabId = null;

// Инициализация отслеживания вкладок
function initTabTracking() {
    // Проверяем поддержку BroadcastChannel
    if (typeof BroadcastChannel === 'undefined') {
        console.warn('BroadcastChannel не поддерживается, используем localStorage fallback');
        initTabTrackingFallback();
        return;
    }
    
    // Генерируем уникальный ID для этой вкладки
    tabId = 'tab_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    
    // Создаем канал для связи между вкладками
    tabChannel = new BroadcastChannel(CHANNEL_NAME);
    
    // Инициализируем время активации
    window.lastActivation = Date.now();
    
    // Проверяем, в фокусе ли мы - если да, то мы активная вкладка
    // Если нет - ждем события focus чтобы стать активной
    if (document.hasFocus() && document.visibilityState === 'visible') {
        isActiveTab = true;
        const initialTimestamp = Date.now();
        tabChannel.postMessage({ type: 'tab_activated', tabId: tabId, timestamp: initialTimestamp });
        window.lastActivation = initialTimestamp;
        console.log('[TAB] Вкладка в фокусе при загрузке, помечаем как активную');
    } else {
        // Вкладка не в фокусе - ждем когда получит фокус
        isActiveTab = false;
        console.log('[TAB] Вкладка не в фокусе при загрузке, ждем фокуса');
    }
    
    // Слушаем сообщения от других вкладок
    tabChannel.onmessage = (event) => {
        const data = event.data;
        
        if (data.type === 'tab_activated') {
            // Другая вкладка стала активной
            if (data.tabId !== tabId) {
                const ourLastActivation = window.lastActivation || 0;
                // Если другая вкладка активировалась позже, чем мы в последний раз, проверяем
                // Добавляем небольшую задержку (100ms) чтобы избежать конфликтов при одновременном открытии
                if (data.timestamp > (ourLastActivation + 100)) {
                    // Перенаправляем на /inactive только если:
                    // 1. Мы на главной странице (не на /inactive)
                    // 2. Мы НЕ в фокусе (не активная вкладка)
                    // 3. Страница не видна или мы не взаимодействуем с ней
                    if (window.location.pathname === '/' && !document.hasFocus()) {
                        console.log('[TAB] Другая вкладка активна, эта вкладка не в фокусе - перенаправляем на заглушку');
                        isActiveTab = false;
                        window.location.href = '/inactive';
                    }
                }
            } else {
                // Это наше сообщение, обновляем время активации
                window.lastActivation = data.timestamp;
            }
        }
    };
    
    // Не нужно проверять другие вкладки - мы сами объявляем активность при фокусе
    
    // Отслеживаем фокус окна - при получении фокуса становимся активными (только на главной странице)
    window.addEventListener('focus', () => {
        // Активность отслеживаем только на главной странице, не на /inactive
        if (document.visibilityState === 'visible' && window.location.pathname === '/') {
            isActiveTab = true;
            const now = Date.now();
            tabChannel.postMessage({ type: 'tab_activated', tabId: tabId, timestamp: now });
            window.lastActivation = now;
            console.log('[TAB] Вкладка получила фокус на главной, активируем, timestamp:', now);
        }
    });
    
    // Отслеживаем потерю фокуса - если потеряли фокус, можем стать неактивной
    window.addEventListener('blur', () => {
        // При потере фокуса не сразу перенаправляем, но отмечаем что мы не активны
        // Если другая вкладка активируется, мы получим сообщение и перенаправимся
        console.log('[TAB] Вкладка потеряла фокус');
    });
    
    // Отслеживаем клики - при клике становимся активными (только на главной странице)
    document.addEventListener('click', () => {
        if (document.visibilityState === 'visible' && !document.hidden && window.location.pathname === '/') {
            isActiveTab = true;
            const now = Date.now();
            tabChannel.postMessage({ type: 'tab_activated', tabId: tabId, timestamp: now });
            window.lastActivation = now;
        }
    });
    
    // Отслеживаем движение мыши - показывает что пользователь активен (только на главной странице)
    document.addEventListener('mousemove', () => {
        if (document.visibilityState === 'visible' && isActiveTab && document.hasFocus() && window.location.pathname === '/') {
            const now = Date.now();
            // Обновляем только если прошло более 200ms с последней активации
            if (now - (window.lastActivation || 0) > 200) {
                tabChannel.postMessage({ type: 'tab_activated', tabId: tabId, timestamp: now });
                window.lastActivation = now;
            }
        }
    });
    
    // Отслеживаем видимость страницы
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            // Вкладка не видна, но не обязательно неактивна
            return;
        } else {
            // Вкладка снова видна - проверяем, должна ли быть активной
            const lastActivation = window.lastActivation || 0;
            const now = Date.now();
            // Если последняя активация была более 1 секунды назад, становимся активными
            if (now - lastActivation > 1000) {
                isActiveTab = true;
                tabChannel.postMessage({ type: 'tab_activated', tabId: tabId, timestamp: now });
                window.lastActivation = now;
            }
        }
    });
    
    // Периодически подтверждаем активность (каждые 500ms для более быстрой реакции)
    // Только на главной странице, не на /inactive
    // Подтверждаем активность только если вкладка в фокусе
    setInterval(() => {
        if (isActiveTab && document.visibilityState === 'visible' && window.location.pathname === '/') {
            // Подтверждаем активность только если вкладка действительно в фокусе
            if (document.hasFocus()) {
                const now = Date.now();
                tabChannel.postMessage({ type: 'tab_activated', tabId: tabId, timestamp: now });
                window.lastActivation = now;
            }
        }
    }, 500);
    
    console.log('[TAB] Отслеживание вкладок инициализировано, ID:', tabId);
}

// Fallback для браузеров без BroadcastChannel (используем localStorage)
function initTabTrackingFallback() {
    tabId = 'tab_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    isActiveTab = true;
    
    const now = Date.now();
    // Сохраняем активную вкладку только если мы на главной странице
    if (window.location.pathname === '/') {
        localStorage.setItem('activeTabId', tabId);
        localStorage.setItem('activeTabTimestamp', now.toString());
        window.lastActivation = now;
    }
    
    // Проверяем каждые 200ms для быстрой реакции
    setInterval(() => {
        if (!isActiveTab) return;
        
        // Проверяем только на главной странице
        if (window.location.pathname !== '/') return;
        
        const activeTabId = localStorage.getItem('activeTabId');
        const activeTimestamp = parseInt(localStorage.getItem('activeTabTimestamp') || '0');
        const now = Date.now();
        
        // Если другая вкладка активна и это было недавно (менее 2 секунд), перенаправляем
        if (activeTabId !== tabId && (now - activeTimestamp) < 2000) {
            console.log('[TAB] Другая вкладка активна (fallback), перенаправляем');
            isActiveTab = false;
            window.location.href = '/inactive';
        } else if (document.visibilityState === 'visible' && document.hasFocus() && isActiveTab) {
            // Обновляем активность если мы видимы и в фокусе
            const newTimestamp = Date.now();
            localStorage.setItem('activeTabId', tabId);
            localStorage.setItem('activeTabTimestamp', newTimestamp.toString());
            window.lastActivation = newTimestamp;
        }
    }, 200);
    
    window.addEventListener('focus', () => {
        // Только на главной странице
        if (window.location.pathname === '/') {
            isActiveTab = true;
            const now = Date.now();
            localStorage.setItem('activeTabId', tabId);
            localStorage.setItem('activeTabTimestamp', now.toString());
            window.lastActivation = now;
        }
    });
    
    // Отслеживаем клики только на главной странице
    document.addEventListener('click', () => {
        if (document.visibilityState === 'visible' && document.hasFocus() && window.location.pathname === '/') {
            isActiveTab = true;
            const now = Date.now();
            localStorage.setItem('activeTabId', tabId);
            localStorage.setItem('activeTabTimestamp', now.toString());
            window.lastActivation = now;
        }
    });
}

// Элементы DOM (объявляем после DOMContentLoaded для надежности)
let qrScreen, passwordScreen, profileScreen, qrContainer, userPhoto, userName, userUsername, userPhone;
let logoutBtn, passwordForm, passwordInput, passwordError, botToggle;
let logoutModal, logoutModalCancel, logoutModalConfirm;

// Проверка на активную вкладку при загрузке (до DOMContentLoaded)
// Новая вкладка не должна сразу перенаправляться - только если она не в фокусе
(function checkActiveTabOnLoad() {
    // Если вкладка в фокусе при загрузке - она активная, не перенаправляем
    if (document.hasFocus()) {
        console.log('[TAB] При загрузке вкладка в фокусе - она активная');
        return;
    }
    
    // Если не в фокусе - проверяем есть ли другие активные вкладки
    const CHANNEL_NAME = 'tg_qr_auth_tab_control';
    
    // Проверяем через BroadcastChannel если доступен
    if (typeof BroadcastChannel !== 'undefined') {
        const checkChannel = new BroadcastChannel(CHANNEL_NAME);
        let lastMessageTime = 0;
        
        checkChannel.onmessage = (event) => {
            const data = event.data;
            if (data.type === 'tab_activated') {
                lastMessageTime = data.timestamp;
            }
        };
        
        // Если через 1000ms получили сообщение от другой активной вкладки И мы не в фокусе - перенаправляем
        // Но только если страница действительно не в фокусе после загрузки
        // УВЕЛИЧИВАЕМ задержку чтобы дать время DOMContentLoaded выполниться и сгенерировать QR
        setTimeout(() => {
            // Проверяем еще раз - возможно страница получила фокус за это время
            // Перенаправляем только если:
            // 1. Есть сообщение от другой вкладки (lastMessageTime > 0)
            // 2. Страница НЕ в фокусе
            // 3. Страница не видна
            // 4. Мы на главной странице (не на /inactive)
            // 5. QR еще НЕ был сгенерирован (currentQrId все еще null) - это значит что мы точно не успели инициализироваться
            if (lastMessageTime > 0 && 
                !document.hasFocus() && 
                document.visibilityState !== 'visible' &&
                window.location.pathname === '/' &&
                currentQrId === null) {
                console.log('[TAB] При загрузке обнаружена другая активная вкладка и QR не сгенерирован, перенаправляем');
                window.location.href = '/inactive';
            } else {
                console.log('[TAB] Остаемся на главной:', {
                    lastMessageTime: lastMessageTime,
                    hasFocus: document.hasFocus(),
                    visibilityState: document.visibilityState,
                    pathname: window.location.pathname,
                    currentQrId: currentQrId
                });
            }
            checkChannel.close();
        }, 1500); // Увеличиваем задержку до 1500ms чтобы дать время генерации QR
    }
})();

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', async () => {
    // Инициализируем элементы DOM
    qrScreen = document.getElementById('qr-screen');
    passwordScreen = document.getElementById('password-screen');
    profileScreen = document.getElementById('profile-screen');
    qrContainer = document.getElementById('qr-container');
    userPhoto = document.getElementById('user-photo');
    userName = document.getElementById('user-name');
    userUsername = document.getElementById('user-username');
    userPhone = document.getElementById('user-phone');
    logoutBtn = document.getElementById('logout-btn');
    passwordForm = document.getElementById('password-form');
    passwordInput = document.getElementById('password-input');
    passwordError = document.getElementById('password-error');
    botToggle = document.getElementById('bot-toggle');
    logoutModal = document.getElementById('logout-modal');
    logoutModalCancel = document.getElementById('logout-modal-cancel');
    logoutModalConfirm = document.getElementById('logout-modal-confirm');
    
    // Проверяем что элементы найдены
    if (!qrContainer) {
        console.error('[ERROR] Элемент qr-container не найден!');
        return;
    }
    
    // Инициализируем отслеживание активной вкладки ПЕРЕД всем остальным
    initTabTracking();
    
    // Небольшая задержка чтобы дать время отслеживанию вкладок проверить другие вкладки
    await new Promise(resolve => setTimeout(resolve, 200));
    
    // Проверяем активные сессии
    console.log('[INIT] Начинаем проверку активных сессий...');
    let hasActiveSession = await checkActiveSessions();
    console.log('[INIT] Результат checkActiveSessions:', hasActiveSession, 'currentQrId:', currentQrId);
    
    // Если checkActiveSessions вернул false, но check_session_status показал валидную сессию
    // Попробуем восстановить через restore_session
    if (!hasActiveSession && !currentQrId) {
        console.log('[INIT] Проверяем check_session_status перед генерацией QR...');
        try {
            const statusResponse = await fetch('/api/check_session_status');
            if (statusResponse.ok) {
                const statusData = await statusResponse.json();
                if (statusData.success && statusData.session_valid === true) {
                    console.log('[INIT] Сессия валидна по check_session_status, восстанавливаем через restore_session...');
                    const restoreResponse = await fetch('/api/restore_session');
                    if (restoreResponse.ok) {
                        const restoreData = await restoreResponse.json();
                        if (restoreData.success && restoreData.user_data) {
                            console.log('[INIT] Сессия успешно восстановлена через restore_session');
                            showProfile(restoreData.user_data);
                            if (botToggle) botToggle.checked = restoreData.bot_active || false;
                            currentQrId = 'active_session';
                            hasActiveSession = true;
                        }
                    }
                }
            }
        } catch (error) {
            console.error('[INIT] Ошибка при проверке check_session_status:', error);
        }
    }
    
    // Если нет активных сессий, генерируем новый QR
    // При генерации нового QR старые temp файлы удалятся автоматически
    if (!hasActiveSession && !currentQrId) {
        console.log('[INIT] Нет активной сессии и нет QR, запускаем генерацию QR-кода...');
        await generateNewQR();
    } else {
        console.log('[INIT] Пропускаем генерацию QR:', {
            hasActiveSession: hasActiveSession,
            currentQrId: currentQrId,
            reason: hasActiveSession ? 'есть активная сессия' : 'QR уже установлен'
        });
    }
    
    // Запускаем периодическую проверку сессии
    startSessionCheck();
    
    // Обработчики событий
    if (logoutBtn) logoutBtn.addEventListener('click', showLogoutModal);
    if (passwordForm) passwordForm.addEventListener('submit', handlePasswordSubmit);
    if (botToggle) botToggle.addEventListener('change', handleBotToggle);
    if (logoutModalCancel) logoutModalCancel.addEventListener('click', hideLogoutModal);
    if (logoutModalConfirm) logoutModalConfirm.addEventListener('click', handleLogout);
});

/**
 * Генерирует новый QR-код
 * @param {boolean} showSpinner - показывать ли спиннер загрузки (только при первой генерации)
 */
async function generateNewQR(showSpinner = true) {
    try {
        // Показываем спиннер только при первой генерации
        if (showSpinner) {
            qrContainer.innerHTML = '<div class="loading-spinner"></div>';
        }
        
        console.log('[QR] Запрос на генерацию QR-кода...');
        
        // Добавляем таймаут для запроса (60 секунд)
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 60000);
        
        try {
            const response = await fetch('/api/generate_qr', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            console.log('[QR] Ответ получен, статус:', response.status);
            
            if (!response.ok) {
                console.error('[QR] Ошибка HTTP:', response.status, response.statusText);
                const errorText = await response.text();
                console.error('[QR] Текст ошибки:', errorText);
                qrContainer.innerHTML = '<div class="error-message">Ошибка загрузки QR-кода (HTTP ' + response.status + '). Проверьте консоль.</div>';
                return;
            }
        
        const data = await response.json();
        console.log('[QR] Ответ сервера:', data);
        
        if (data.success) {
            currentQrId = data.qr_id;
            // Если это не первая генерация, делаем мгновенную замену без спиннера
            const isFirstGeneration = showSpinner;
            
            const imgElement = document.createElement('img');
            imgElement.src = `data:image/png;base64,${data.qr_image}`;
            imgElement.alt = 'QR Code';
            
            // При первой генерации - плавное появление, при смене - мгновенная замена
            if (!isFirstGeneration) {
                imgElement.classList.add('qr-instant');
                // Мгновенная замена - очищаем контейнер и сразу добавляем новый QR
                qrContainer.innerHTML = '';
                qrContainer.appendChild(imgElement);
            } else {
                // Плавное появление при первой генерации - очищаем спиннер и добавляем QR с анимацией
                qrContainer.innerHTML = '';
                qrContainer.appendChild(imgElement);
            }
            
            // Логотип теперь встроен в сам QR-код на сервере, не нужно добавлять поверх
            
            // Начинаем проверку статуса
            startStatusCheck();
        } else {
            console.error('[QR] Ошибка генерации QR-кода:', data.error || 'Неизвестная ошибка');
            qrContainer.innerHTML = '<div class="error-message">Ошибка генерации QR-кода: ' + (data.error || 'Неизвестная ошибка') + '</div>';
        }
        } catch (error) {
            clearTimeout(timeoutId);
            
            if (error.name === 'AbortError') {
                console.error('[QR] Таймаут запроса (60 секунд)');
                qrContainer.innerHTML = '<div class="error-message">Таймаут при генерации QR-кода. Сервер не отвечает. Возможно, это холодный старт на бесплатном тарифе Render. Попробуйте еще раз через несколько секунд.</div>';
            } else {
                console.error('[QR] Ошибка при генерации QR-кода:', error);
                console.error('[QR] Тип ошибки:', error.name);
                console.error('[QR] Сообщение:', error.message);
                qrContainer.innerHTML = '<div class="error-message">Ошибка соединения с сервером: ' + error.message + '. Проверьте интернет-соединение.</div>';
            }
        }
    } catch (error) {
        console.error('[QR] Критическая ошибка при генерации QR-кода:', error);
        qrContainer.innerHTML = '<div class="error-message">Критическая ошибка. Проверьте консоль браузера.</div>';
    }
}

/**
 * Начинает периодическую проверку статуса авторизации
 */
function startStatusCheck() {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
    }
    
    statusCheckInterval = setInterval(checkAuthorizationStatus, 2000); // Проверка каждые 2 секунды
}

/**
 * Останавливает проверку статуса
 */
function stopStatusCheck() {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
        statusCheckInterval = null;
    }
}

/**
 * Проверяет статус авторизации
 */
async function checkAuthorizationStatus() {
    if (!currentQrId) return;
    
    try {
        const response = await fetch(`/api/check_status/${currentQrId}`);
        const data = await response.json();
        
        if (!data.success) {
            if (data.qr_expired) {
                stopStatusCheck();
                
                // Генерируем новый QR-код мгновенно, без спиннера
                generateNewQR(false);
            }
            return;
        }
        
        if (data.needs_password) {
            // Требуется пароль 2FA
            stopStatusCheck();
            showPasswordScreen();
        } else if (data.authorized && data.user_data) {
            // Авторизация успешна!
            stopStatusCheck();
            showProfile(data.user_data);
            // Устанавливаем состояние переключателя бота в соответствии с реальным статусом
            if (data.bot_active !== undefined) {
                botToggle.checked = data.bot_active;
                console.log('[BOT] Toggle установлен из check_status:', data.bot_active);
            }
            // Устанавливаем active_session для проверки сессии
            currentQrId = 'active_session';
            
            // Дополнительная синхронизация через небольшую задержку (бот может еще запускаться)
            setTimeout(async () => {
                await syncBotToggleState();
            }, 2000);
        }
    } catch (error) {
        console.error('Ошибка при проверке статуса:', error);
    }
}

/**
 * Показывает экран профиля
 */
function showProfile(userData) {
    // Очищаем старое фото перед загрузкой нового
    userPhoto.src = '';
    
    // Заполняем данные пользователя
    userPhoto.src = `/api/user_photo?t=${Date.now()}`; // Добавляем timestamp для обновления
    userPhoto.onerror = function() {
        this.src = 'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22%3E%3Ccircle cx=%2250%22 cy=%2250%22 r=%2250%22 fill=%22%23667eea%22/%3E%3Ctext x=%2250%22 y=%2250%22 text-anchor=%22middle%22 dy=%22.3em%22 fill=%22white%22 font-size=%2240%22%3E' + 
                   userData.first_name.charAt(0).toUpperCase() + '%3C/text%3E%3C/svg%3E';
    };
    
    userName.textContent = `${userData.first_name} ${userData.last_name}`.trim();
    
    if (userData.username && userData.username.trim()) {
        userUsername.textContent = `@${userData.username}`;
        userUsername.style.display = 'block';
    } else {
        userUsername.style.display = 'none';
    }
    
    if (userData.phone) {
        userPhone.textContent = `+${userData.phone}`;
        userPhone.style.display = 'block';
    } else {
        userPhone.style.display = 'none';
    }
    
    // Переключаем экраны
    qrScreen.classList.remove('active');
    passwordScreen.classList.remove('active');
    profileScreen.classList.add('active');
    
    // Синхронизируем состояние toggle бота с сервером сразу после показа профиля
    setTimeout(async () => {
        await syncBotToggleState();
    }, 500);
}

/**
 * Показывает экран ввода пароля
 */
function showPasswordScreen() {
    passwordError.style.display = 'none';
    qrScreen.classList.remove('active');
    profileScreen.classList.remove('active');
    passwordScreen.classList.add('active');
}

/**
 * Обработка отправки пароля
 */
async function handlePasswordSubmit(event) {
    event.preventDefault();
    
    if (!currentQrId || isSubmittingPassword) return;
    
    passwordError.style.display = 'none';
    
    const password = passwordInput.value;
    if (!password) return;
    
    isSubmittingPassword = true;
    try {
        const response = await fetch(`/api/submit_password/${currentQrId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ password })
        });
        
        const data = await response.json();
        
        if (data.success && data.user_data) {
            passwordInput.value = '';
            showProfile(data.user_data);
            // Устанавливаем состояние переключателя бота в соответствии с реальным статусом
            if (data.bot_active !== undefined) {
                botToggle.checked = data.bot_active;
                console.log('[BOT] Toggle установлен из submit_password:', data.bot_active);
            }
            // Устанавливаем active_session для проверки сессии
            currentQrId = 'active_session';
            
            // Дополнительная синхронизация через небольшую задержку (бот может еще запускаться)
            setTimeout(async () => {
                await syncBotToggleState();
            }, 2000);
        } else {
            passwordError.style.display = 'block';
            passwordInput.value = '';
        }
    } catch (error) {
        console.error('Ошибка при отправке пароля:', error);
        passwordError.textContent = 'Ошибка соединения с сервером';
        passwordError.style.display = 'block';
    } finally {
        isSubmittingPassword = false;
    }
}

/**
 * Показываем модальное окно подтверждения выхода
 */
function showLogoutModal() {
    logoutModal.style.display = 'flex';
}

/**
 * Скрываем модальное окно подтверждения выхода
 */
function hideLogoutModal() {
    logoutModal.style.display = 'none';
}

/**
 * Обработка выхода
 */
async function handleLogout() {
    // Скрываем модальное окно
    hideLogoutModal();
    
    try {
        const response = await fetch('/api/logout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Очищаем текущий QR ID
            currentQrId = null;
            
            // Очищаем фото и данные пользователя
            userPhoto.src = '';
            userName.textContent = '';
            userUsername.textContent = '';
            userUsername.style.display = 'none';
            userPhone.textContent = '';
            userPhone.style.display = 'none';
            
            // Возвращаемся к экрану QR-кода
            passwordScreen.classList.remove('active');
            profileScreen.classList.remove('active');
            qrScreen.classList.add('active');
            
            // Небольшая задержка перед генерацией нового QR, чтобы сервер успел очистить данные
            setTimeout(async () => {
                try {
                    await generateNewQR();
                } catch (error) {
                    console.error('[LOGOUT] Ошибка при генерации QR после выхода:', error);
                    // Если не удалось сгенерировать QR, показываем сообщение об ошибке
                    if (qrContainer) {
                        qrContainer.innerHTML = '<div class="error-message">Ошибка загрузки QR-кода. Пожалуйста, обновите страницу.</div>';
                    }
                }
            }, 500);
        } else {
            alert('Ошибка при выходе');
        }
    } catch (error) {
        console.error('Ошибка при выходе:', error);
        alert('Ошибка соединения с сервером');
    }
}

/**
 * Обработка переключения бота
 */
async function handleBotToggle(event) {
    const isChecked = event.target.checked;
    const previousState = !isChecked; // Сохраняем предыдущее состояние
    
    try {
        console.log('[BOT] Переключение бота:', isChecked ? 'включить' : 'выключить');
        
        const response = await fetch('/api/toggle_bot', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ enabled: isChecked })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            // Если не получилось, откатываем переключатель к предыдущему состоянию
            console.error('[BOT] Ошибка при переключении:', data.error);
            botToggle.checked = previousState;
            alert(data.error || 'Ошибка при переключении бота');
            return;
        }
        
        // Синхронизируем toggle с реальным состоянием бота из ответа сервера
        if (data.bot_active !== undefined) {
            console.log('[BOT] Реальное состояние бота после операции:', data.bot_active);
            botToggle.checked = data.bot_active;
            // Обновляем lastSyncedBotState после успешной операции
            lastSyncedBotState = data.bot_active;
            
            // Если состояние не совпадает с запрошенным - это нормально для некоторых случаев
            // (например, бот уже был включен или выключен)
            if (data.bot_active !== isChecked) {
                console.log('[BOT] Состояние бота не совпадает с запрошенным (возможно, уже было установлено)');
            }
        } else {
            // Если сервер не вернул состояние, делаем повторную проверку через небольшую задержку
            console.log('[BOT] Сервер не вернул состояние бота, проверяем через 2 секунды...');
            setTimeout(async () => {
                await syncBotToggleState(true); // force = true, так как это после операции
            }, 2000);
        }
    } catch (error) {
        console.error('[BOT] Ошибка при переключении бота:', error);
        botToggle.checked = previousState;
        alert('Ошибка соединения с сервером');
    }
}

// Переменная для отслеживания последнего состояния toggle (для debounce)
let lastSyncedBotState = null;
let syncBotToggleTimeout = null;

/**
 * Синхронизирует состояние toggle с реальным состоянием бота на сервере
 */
async function syncBotToggleState(force = false) {
    try {
        // Проверяем только если мы на странице профиля
        if (currentQrId !== 'active_session' || !profileScreen.classList.contains('active')) {
            return;
        }
        
        // Debounce: не синхронизируем слишком часто (минимум 3 секунды между синхронизациями)
        if (!force && syncBotToggleTimeout) {
            console.log('[BOT] Синхронизация уже запланирована, пропускаем');
            return;
        }
        
        // Очищаем предыдущий timeout если есть
        if (syncBotToggleTimeout) {
            clearTimeout(syncBotToggleTimeout);
        }
        
        // Устанавливаем новый timeout для следующей синхронизации (защита от частых вызовов)
        syncBotToggleTimeout = setTimeout(() => {
            syncBotToggleTimeout = null;
        }, 3000);
        
        console.log('[BOT] Синхронизация состояния toggle с сервером...');
        const response = await fetch('/api/active_sessions');
        
        if (response.ok) {
            const data = await response.json();
            if (data.bot_active !== undefined && botToggle) {
                const serverState = data.bot_active;
                const currentToggleState = botToggle.checked;
                
                // Обновляем toggle только если:
                // 1. Состояние действительно изменилось
                // 2. И это не то же состояние, что мы синхронизировали в последний раз (защита от колебаний)
                if (serverState !== currentToggleState && (force || serverState !== lastSyncedBotState)) {
                    console.log(`[BOT] Состояние toggle не совпадает с сервером. Сервер: ${serverState}, Toggle: ${currentToggleState}. Синхронизируем...`);
                    
                    // Обновляем toggle и сохраняем последнее синхронизированное состояние
                    botToggle.checked = serverState;
                    lastSyncedBotState = serverState;
                } else if (serverState === currentToggleState) {
                    // Состояния совпадают - обновляем lastSyncedBotState
                    lastSyncedBotState = serverState;
                } else {
                    // Состояния не совпадают, но мы только что синхронизировали с таким же значением
                    // Это может быть временное колебание - не обновляем toggle
                    console.log(`[BOT] Состояние сервера: ${serverState}, но мы недавно синхронизировали такое же. Пропускаем (защита от колебаний)`);
                }
            }
        }
    } catch (error) {
        console.error('[BOT] Ошибка при синхронизации состояния toggle:', error);
    }
}

/**
 * Проверяет активные сессии при загрузке страницы
 */
async function checkActiveSessions() {
    try {
        console.log('[INIT] Проверка активных сессий...');
        
        // Сначала проверяем check_session_status - он проверяет файл сессии даже если _user_data потерян
        const statusResponse = await fetch('/api/check_session_status');
        let sessionValid = false;
        
        if (statusResponse.ok) {
            const statusData = await statusResponse.json();
            console.log('[INIT] Ответ check_session_status:', JSON.stringify(statusData));
            sessionValid = statusData.success && statusData.session_valid === true;
        }
        
        // Затем проверяем active_sessions для получения user_data
        const response = await fetch('/api/active_sessions');
        
        if (!response.ok) {
            console.error('[INIT] Ошибка HTTP при запросе active_sessions:', response.status);
            // Если check_session_status показал валидную сессию, но active_sessions не работает - все равно считаем сессию валидной
            if (sessionValid) {
                console.log('[INIT] Сессия валидна по check_session_status, но active_sessions недоступен - загружаем профиль через check_status');
                // Пытаемся загрузить данные через восстановление сессии на сервере
                return false; // Вернем false, чтобы сгенерировать QR, но сервер восстановит сессию
            }
            return false;
        }
        
        const data = await response.json();
        console.log('[INIT] Ответ active_sessions:', JSON.stringify(data));
        
        // Если check_session_status показал валидную сессию, но active_sessions пуст (например, после перезапуска Render)
        // Восстанавливаем данные через специальный запрос
        if (sessionValid && (!data.sessions || data.sessions.length === 0)) {
            console.log('[INIT] Сессия валидна по check_session_status, но active_sessions пуст - восстанавливаем сессию');
            // Отправляем запрос для восстановления данных пользователя
            try {
                const restoreResponse = await fetch('/api/restore_session');
                if (restoreResponse.ok) {
                    const restoreData = await restoreResponse.json();
                    if (restoreData.success && restoreData.user_data) {
                        console.log('[INIT] Сессия восстановлена, показываем профиль');
                        showProfile(restoreData.user_data);
                        if (botToggle) botToggle.checked = restoreData.bot_active || false;
                        currentQrId = 'active_session';
                        return true;
                    }
                }
            } catch (restoreError) {
                console.error('[INIT] Ошибка при восстановлении сессии:', restoreError);
            }
        }
        
        if (data.success && data.sessions && Array.isArray(data.sessions) && data.sessions.length > 0) {
            // Есть активная сессия - показываем профиль
            console.log('[INIT] Найдена активная сессия, показываем профиль');
            const session = data.sessions[0];
            if (session && session.user_data) {
                showProfile(session.user_data);
                // Устанавливаем состояние переключателя бота в соответствии с реальным статусом
                if (botToggle) botToggle.checked = data.bot_active || false;
                currentQrId = 'active_session'; // Помечаем что сессия активна
                return true; // Сессия найдена
            } else {
                console.warn('[INIT] Сессия найдена, но нет user_data');
                // Если check_session_status показал валидную сессию - все равно считаем сессию валидной
                if (sessionValid) {
                    console.log('[INIT] Сессия валидна, но нет user_data - пытаемся восстановить');
                    return false; // Вернем false, но попробуем восстановить через restore_session
                }
                return false;
            }
        } else {
            // Если check_session_status показал валидную сессию - все равно считаем сессию валидной
            if (sessionValid) {
                console.log('[INIT] Сессия валидна по check_session_status, но active_sessions пуст - восстанавливаем');
                return false; // Вернем false, но попробуем восстановить через restore_session
            }
            
            console.log('[INIT] Активных сессий не найдено (sessions пустой или не массив), будет сгенерирован QR-код');
            console.log('[INIT] Детали:', {
                success: data.success,
                sessionsType: typeof data.sessions,
                sessionsLength: data.sessions ? data.sessions.length : 'null/undefined'
            });
            return false; // Сессии нет
        }
    } catch (error) {
        console.error('[INIT] Ошибка при проверке активных сессий:', error);
        console.error('[INIT] Stack trace:', error.stack);
        return false; // При ошибке считаем что сессии нет
    }
}

/**
 * Запускает периодическую проверку сессии
 */
function startSessionCheck() {
    // Очищаем предыдущий интервал если есть
    if (sessionCheckInterval) {
        clearInterval(sessionCheckInterval);
    }
    
    console.log('[SESSION] Запущена периодическая проверка сессии каждые 5 секунд');
    
    // Проверяем каждые 5 секунд
    sessionCheckInterval = setInterval(async () => {
        // Проверяем только если сессия активна
        if (currentQrId === 'active_session') {
            console.log('[SESSION] Проверка валидности сессии...');
            await checkSessionValidity();
            
            // Также синхронизируем состояние toggle бота
            await syncBotToggleState();
        }
    }, 5000);
}

/**
 * Проверяет валидность текущей сессии
 */
async function checkSessionValidity() {
    try {
        console.log('[SESSION] Отправка запроса check_session_status');
        const response = await fetch('/api/check_session_status');
        const data = await response.json();
        console.log('[SESSION] Ответ check_session_status:', data);
        
        if (data.success) {
            if (!data.session_valid) {
                // Сессия невалидна - выполняем logout через сервер
                console.log('[SESSION] Сессия стала невалидной, выполняем logout');
                try {
                    await fetch('/api/logout', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                } catch (error) {
                    console.error('[SESSION] Ошибка при logout:', error);
                }
                
                // Очищаем текущий QR ID
                currentQrId = null;
                
                // Очищаем фото и данные пользователя
                userPhoto.src = '';
                userName.textContent = '';
                userUsername.textContent = '';
                userUsername.style.display = 'none';
                userPhone.textContent = '';
                userPhone.style.display = 'none';
                
                // Скрываем профиль и показываем QR
                passwordScreen.classList.remove('active');
                profileScreen.classList.remove('active');
                qrScreen.classList.add('active');
                
                // Генерируем новый QR
                generateNewQR();
            } else {
                console.log('[SESSION] Сессия валидна');
            }
        }
    } catch (error) {
        console.error('[SESSION] Ошибка при проверке валидности сессии:', error);
    }
}


// Управление состоянием приложения
let currentQrId = null;
let statusCheckInterval = null;
let qrTimerInterval = null;
let sessionCheckInterval = null; // Интервал для проверки сессии
let qrTimeLeft = 25; // Таймаут QR кода
let isSubmittingPassword = false; // Флаг для предотвращения двойной отправки пароля

// Элементы DOM
const qrScreen = document.getElementById('qr-screen');
const passwordScreen = document.getElementById('password-screen');
const profileScreen = document.getElementById('profile-screen');
const qrContainer = document.getElementById('qr-container');
const userPhoto = document.getElementById('user-photo');
const userName = document.getElementById('user-name');
const userUsername = document.getElementById('user-username');
const userPhone = document.getElementById('user-phone');
const logoutBtn = document.getElementById('logout-btn');
const passwordForm = document.getElementById('password-form');
const passwordInput = document.getElementById('password-input');
const passwordError = document.getElementById('password-error');
const botToggle = document.getElementById('bot-toggle');
const logoutModal = document.getElementById('logout-modal');
const logoutModalCancel = document.getElementById('logout-modal-cancel');
const logoutModalConfirm = document.getElementById('logout-modal-confirm');

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', async () => {
    // Проверяем активные сессии
    await checkActiveSessions();
    
    // Если нет активных сессий, генерируем новый QR
    if (!currentQrId) {
        generateNewQR();
    }
    
    // Запускаем периодическую проверку сессии
    startSessionCheck();
    
    // Обработчики событий
    logoutBtn.addEventListener('click', showLogoutModal);
    passwordForm.addEventListener('submit', handlePasswordSubmit);
    botToggle.addEventListener('change', handleBotToggle);
    logoutModalCancel.addEventListener('click', hideLogoutModal);
    logoutModalConfirm.addEventListener('click', handleLogout);
});

/**
 * Генерирует новый QR-код
 */
async function generateNewQR() {
    try {
        qrContainer.innerHTML = '<div class="loading-spinner"></div>';
        
        const response = await fetch('/api/generate_qr', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentQrId = data.qr_id;
            qrContainer.innerHTML = `<img src="data:image/png;base64,${data.qr_image}" alt="QR Code">`;
            
            // Начинаем проверку статуса
            startStatusCheck();
        } else {
            console.error('Ошибка генерации QR-кода');
        }
    } catch (error) {
        console.error('Ошибка при генерации QR-кода:', error);
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
                
                // Генерируем новый QR-код через 1 секунду
                setTimeout(() => {
                    generateNewQR();
                }, 1000);
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
            }
            // Устанавливаем active_session для проверки сессии
            currentQrId = 'active_session';
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
    
    if (userData.username) {
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
            }
            // Устанавливаем active_session для проверки сессии
            currentQrId = 'active_session';
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
            
            // Генерируем новый QR-код
            generateNewQR();
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
    try {
        const response = await fetch('/api/toggle_bot', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ enabled: isChecked })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            // Если не получилось, откатываем переключатель
            botToggle.checked = !isChecked;
            alert(data.error || 'Ошибка при переключении бота');
        }
    } catch (error) {
        console.error('Ошибка при переключении бота:', error);
        botToggle.checked = !isChecked;
        alert('Ошибка соединения с сервером');
    }
}

/**
 * Проверяет активные сессии при загрузке страницы
 */
async function checkActiveSessions() {
    try {
        const response = await fetch('/api/active_sessions');
        const data = await response.json();
        
        if (data.success && data.sessions && data.sessions.length > 0) {
            // Есть активная сессия - показываем профиль
            const session = data.sessions[0];
            showProfile(session.user_data);
            // Устанавливаем состояние переключателя бота в соответствии с реальным статусом
            botToggle.checked = data.bot_active || false;
            currentQrId = 'active_session'; // Помечаем что сессия активна
        }
    } catch (error) {
        console.error('Ошибка при проверке активных сессий:', error);
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


# Скрипт для управления Render через API
# Использование: .\render_manage.ps1 <command> [options]

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('logs', 'deploy', 'restart', 'status', 'env', 'help')]
    [string]$Command,
    
    [string]$ServiceId = 'srv-d43v6auuk2gs739hi7v0',
    [string]$ApiToken = 'rnd_vYdkJPfQ8Y02VwGyItmXyaTSIDJX'
)

$headers = @{
    'Authorization' = "Bearer $ApiToken"
    'Accept' = 'application/json'
    'Content-Type' = 'application/json'
}

$baseUrl = "https://api.render.com/v1/services/$ServiceId"

switch ($Command) {
    'status' {
        Write-Host "Проверка статуса сервиса..." -ForegroundColor Cyan
        $service = Invoke-RestMethod -Uri $baseUrl -Headers $headers -Method Get
        $serviceDetails = $service.service.serviceDetails
        Write-Host "`nСервис: $($service.service.name)" -ForegroundColor Green
        Write-Host "URL: $($serviceDetails.url)"
        Write-Host "Статус: $($service.service.suspended)"
        Write-Host "План: $($serviceDetails.plan)"
        Write-Host "Регион: $($serviceDetails.region)"
        
        # Последний деплой
        $deploys = Invoke-RestMethod -Uri "$baseUrl/deploys?limit=1" -Headers $headers -Method Get
        if ($deploys) {
            $lastDeploy = $deploys[0].deploy
            Write-Host "`nПоследний деплой:" -ForegroundColor Yellow
            Write-Host "  Статус: $($lastDeploy.status)"
            Write-Host "  Коммит: $($lastDeploy.commit.message)"
            Write-Host "  Время: $($lastDeploy.createdAt)"
        }
    }
    
    'deploy' {
        Write-Host "Запуск нового деплоя..." -ForegroundColor Cyan
        $result = Invoke-RestMethod -Uri "$baseUrl/deploys" -Headers $headers -Method Post -Body '{}'
        Write-Host "Деплой запущен! ID: $($result.id)" -ForegroundColor Green
        Write-Host "Статус: $($result.status)"
    }
    
    'restart' {
        Write-Host "Перезапуск сервиса (создание нового деплоя)..." -ForegroundColor Cyan
        $result = Invoke-RestMethod -Uri "$baseUrl/deploys" -Headers $headers -Method Post -Body '{}'
        Write-Host "Перезапуск инициирован! ID деплоя: $($result.id)" -ForegroundColor Green
    }
    
    'logs' {
        Write-Host "Получение логов..." -ForegroundColor Cyan
        Write-Host "Примечание: Для просмотра логов в реальном времени используйте Render Dashboard" -ForegroundColor Yellow
        Write-Host "Dashboard: https://dashboard.render.com/web/$ServiceId" -ForegroundColor Yellow
    }
    
    'env' {
        Write-Host "Проверка переменных окружения..." -ForegroundColor Cyan
        Write-Host "Примечание: Для просмотра/изменения переменных окружения используйте Render Dashboard" -ForegroundColor Yellow
        Write-Host "Dashboard: https://dashboard.render.com/web/$ServiceId/environment-variables" -ForegroundColor Yellow
    }
    
    'help' {
        Write-Host "Управление Render через API" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Использование:" -ForegroundColor Yellow
        Write-Host "  .\render_manage.ps1 <command>"
        Write-Host ""
        Write-Host "Команды:" -ForegroundColor Yellow
        Write-Host "  status   - Проверить статус сервиса и последний деплой"
        Write-Host "  deploy   - Запустить новый деплой"
        Write-Host "  restart  - Перезапустить сервис (создать новый деплой)"
        Write-Host "  logs     - Показать ссылку на логи в Dashboard"
        Write-Host "  env      - Показать ссылку на переменные окружения в Dashboard"
        Write-Host "  help     - Показать эту справку"
        Write-Host ""
        Write-Host "Примеры:" -ForegroundColor Yellow
        Write-Host "  .\render_manage.ps1 status"
        Write-Host "  .\render_manage.ps1 restart"
    }
}


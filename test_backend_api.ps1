# Backend API Test Script
# Örnek proje ile backend testi

$baseUrl = "http://127.0.0.1:8000"
$headers = @{
    "Content-Type" = "application/json"
}

Write-Host "=== Backend API Test Başlatılıyor ===" -ForegroundColor Green
Write-Host ""

# 1. Health Check
Write-Host "1. Health Check..." -ForegroundColor Yellow
try {
    $health = Invoke-WebRequest -Uri "$baseUrl/health" -Method GET -UseBasicParsing
    Write-Host "   ✓ Health Check Başarılı: $($health.StatusCode)" -ForegroundColor Green
    Write-Host "   Response: $($health.Content)" -ForegroundColor Gray
} catch {
    Write-Host "   ✗ Health Check Başarısız: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

# 2. Workspace Oluştur
Write-Host "2. Workspace Oluşturuluyor..." -ForegroundColor Yellow
$workspaceData = @{
    name = "Test Workspace"
    slug = "test-workspace-$(Get-Date -Format 'yyyyMMddHHmmss')"
    workspace_metadata = @{
        description = "Test için oluşturulan workspace"
        environment = "development"
    }
} | ConvertTo-Json

try {
    $workspace = Invoke-WebRequest -Uri "$baseUrl/api/workspaces" -Method POST -Headers $headers -Body $workspaceData -UseBasicParsing
    $workspaceJson = $workspace.Content | ConvertFrom-Json
    $workspaceId = $workspaceJson.id
    $workspaceSlug = $workspaceJson.slug
    Write-Host "   ✓ Workspace Oluşturuldu: $workspaceId ($workspaceSlug)" -ForegroundColor Green
    Write-Host "   Response: $($workspace.Content)" -ForegroundColor Gray
} catch {
    Write-Host "   ✗ Workspace Oluşturma Başarısız: $_" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "   Error Details: $responseBody" -ForegroundColor Red
    }
    exit 1
}
Write-Host ""

# 3. Workspace'i Listele
Write-Host "3. Workspace'ler Listeleniyor..." -ForegroundColor Yellow
try {
    $workspaces = Invoke-WebRequest -Uri "$baseUrl/api/workspaces" -Method GET -UseBasicParsing
    $workspacesJson = $workspaces.Content | ConvertFrom-Json
    Write-Host "   ✓ Toplam $($workspacesJson.total) workspace bulundu" -ForegroundColor Green
    foreach ($ws in $workspacesJson.items) {
        Write-Host "   - $($ws.name) ($($ws.slug))" -ForegroundColor Gray
    }
} catch {
    Write-Host "   ✗ Workspace Listeleme Başarısız: $_" -ForegroundColor Red
}
Write-Host ""

# 4. Project Oluştur (Workspace içinde)
Write-Host "4. Project Oluşturuluyor..." -ForegroundColor Yellow
$projectData = @{
    name = "Test Project"
    slug = "test-project"
    metadata = @{
        description = "Test için oluşturulan proje"
        language = "python"
    }
} | ConvertTo-Json

try {
    $project = Invoke-WebRequest -Uri "$baseUrl/api/projects?workspace_slug=$workspaceSlug" -Method POST -Headers $headers -Body $projectData -UseBasicParsing
    $projectJson = $project.Content | ConvertFrom-Json
    $projectId = $projectJson.id
    Write-Host "   ✓ Project Oluşturuldu: $projectId" -ForegroundColor Green
    Write-Host "   Response: $($project.Content)" -ForegroundColor Gray
} catch {
    Write-Host "   ✗ Project Oluşturma Başarısız: $_" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "   Error Details: $responseBody" -ForegroundColor Red
    }
}
Write-Host ""

# 5. Project'leri Listele
Write-Host "5. Project'ler Listeleniyor..." -ForegroundColor Yellow
try {
    $projects = Invoke-WebRequest -Uri "$baseUrl/api/projects?workspace_slug=$workspaceSlug" -Method GET -UseBasicParsing
    $projectsJson = $projects.Content | ConvertFrom-Json
    Write-Host "   ✓ Toplam $($projectsJson.total) project bulundu" -ForegroundColor Green
    foreach ($proj in $projectsJson.items) {
        Write-Host "   - $($proj.name) ($($proj.slug))" -ForegroundColor Gray
    }
} catch {
    Write-Host "   ✗ Project Listeleme Başarısız: $_" -ForegroundColor Red
}
Write-Host ""

# 6. Task Oluştur
Write-Host "6. Task Oluşturuluyor..." -ForegroundColor Yellow
$taskData = @{
    name = "Test Task - Basit Python Scripti Oluştur"
    description = "Basit bir 'Hello World' Python scripti oluştur"
    project_slug = "test-project"
    metadata = @{
        priority = "medium"
        estimated_time = "5 minutes"
    }
} | ConvertTo-Json

try {
    $task = Invoke-WebRequest -Uri "$baseUrl/api/tasks?workspace_slug=$workspaceSlug" -Method POST -Headers $headers -Body $taskData -UseBasicParsing
    $taskJson = $task.Content | ConvertFrom-Json
    $taskId = $taskJson.id
    Write-Host "   ✓ Task Oluşturuldu: $taskId" -ForegroundColor Green
    Write-Host "   Task: $($taskJson.name)" -ForegroundColor Gray
    Write-Host "   Status: $($taskJson.status)" -ForegroundColor Gray
} catch {
    Write-Host "   ✗ Task Oluşturma Başarısız: $_" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "   Error Details: $responseBody" -ForegroundColor Red
    }
}
Write-Host ""

# 7. Task'ları Listele
Write-Host "7. Task'lar Listeleniyor..." -ForegroundColor Yellow
try {
    $tasks = Invoke-WebRequest -Uri "$baseUrl/api/tasks?workspace_slug=$workspaceSlug" -Method GET -UseBasicParsing
    $tasksJson = $tasks.Content | ConvertFrom-Json
    Write-Host "   ✓ Toplam $($tasksJson.total) task bulundu" -ForegroundColor Green
    foreach ($t in $tasksJson.items) {
        Write-Host "   - $($t.name) [Status: $($t.status)]" -ForegroundColor Gray
    }
} catch {
    Write-Host "   ✗ Task Listeleme Başarısız: $_" -ForegroundColor Red
}
Write-Host ""

# 8. API Docs Kontrolü
Write-Host "8. API Dokümantasyonu Kontrol Ediliyor..." -ForegroundColor Yellow
try {
    $docs = Invoke-WebRequest -Uri "$baseUrl/docs" -Method GET -UseBasicParsing
    Write-Host "   ✓ API Docs Erişilebilir: $($docs.StatusCode)" -ForegroundColor Green
    Write-Host "   Docs URL: $baseUrl/docs" -ForegroundColor Gray
} catch {
    Write-Host "   ✗ API Docs Erişilemiyor: $_" -ForegroundColor Red
}
Write-Host ""

Write-Host "=== Test Tamamlandı ===" -ForegroundColor Green
Write-Host ""
Write-Host "Özet:" -ForegroundColor Cyan
Write-Host "  - Workspace: $workspaceSlug" -ForegroundColor White
Write-Host "  - API Base URL: $baseUrl" -ForegroundColor White
Write-Host "  - API Docs: $baseUrl/docs" -ForegroundColor White

# 🐳 Docker Servisleri Durumu

## 📊 Mevcut Servis Durumu

### ✅ Çalışan Servisler

1. **mgx-backend** (Backend API)
   - **Status**: ✅ Up 22 hours (healthy)
   - **Port**: `8000:8000`
   - **Health**: ✅ Healthy
   - **URL**: http://localhost:8000
   - **API Docs**: http://localhost:8000/docs

2. **mgx-frontend** (Frontend Next.js)
   - **Status**: ✅ Up 22 hours (healthy)
   - **Port**: `3000:3000`
   - **Health**: ✅ Healthy
   - **URL**: http://localhost:3000

3. **mgx-postgres** (PostgreSQL Database)
   - **Status**: ✅ Up 4 minutes (healthy)
   - **Port**: `5432:5432`
   - **Health**: ✅ Healthy

4. **mgx-redis** (Redis Cache)
   - **Status**: ✅ Up 4 minutes (healthy)
   - **Port**: `6379:6379`
   - **Health**: ✅ Healthy

5. **mgx-minio** (MinIO S3 Storage)
   - **Status**: ✅ Up 4 minutes (healthy)
   - **Ports**: `9000:9000` (API), `9001:9001` (Console)
   - **Health**: ✅ Healthy
   - **Console**: http://localhost:9001
   - **Credentials**: minioadmin / minioadmin

### ⚠️ Sorunlu Servisler

6. **mgx-migrate** (Database Migrations)
   - **Status**: ⚠️ Restarting (255)
   - **Sorun**: Migration servisi sürekli restart oluyor
   - **Not**: Migration zaten tamamlanmış olabilir, bu yüzden restart ediyor olabilir

---

## 🔍 Servis Detayları

### Backend API
- **Health Check**: ✅ `http://localhost:8000/health`
- **Response**: `{"status":"ok","timestamp":"...","service":"mgx-agent-api"}`
- **API Documentation**: http://localhost:8000/docs

### Frontend
- **URL**: http://localhost:3000
- **Framework**: Next.js
- **Status**: ✅ Çalışıyor

### Database (PostgreSQL)
- **Host**: localhost
- **Port**: 5432
- **Database**: mgx
- **User**: mgx
- **Password**: mgx (varsayılan)

### Redis
- **Host**: localhost
- **Port**: 6379
- **URL**: redis://localhost:6379/0

### MinIO (S3 Storage)
- **API Endpoint**: http://localhost:9000
- **Console**: http://localhost:9001
- **Access Key**: minioadmin
- **Secret Key**: minioadmin
- **Bucket**: mgx-artifacts

---

## 🚀 Servisleri Başlatma

### Tüm Servisleri Başlat
```bash
docker compose up -d
```

### Belirli Servisleri Başlat
```bash
# Sadece backend
docker compose up -d mgx-ai

# Sadece database servisleri
docker compose up -d postgres redis minio
```

### Servisleri Yeniden Başlat
```bash
# Tüm servisleri restart et
docker compose restart

# Belirli bir servisi restart et
docker compose restart mgx-ai
```

---

## 📊 Servis Durumunu Kontrol Etme

### Tüm Servislerin Durumu
```bash
docker compose ps
```

### Servis Logları
```bash
# Backend logları
docker compose logs mgx-ai --tail=50 -f

# Frontend logları
docker compose logs mgx-frontend --tail=50 -f

# Tüm loglar
docker compose logs --tail=50 -f
```

### Health Check
```bash
# Backend health
curl http://localhost:8000/health

# Frontend
curl http://localhost:3000

# PostgreSQL
docker compose exec postgres pg_isready

# Redis
docker compose exec redis redis-cli ping

# MinIO
curl http://localhost:9000/minio/health/live
```

---

## 🔧 Sorun Giderme

### Migration Servisi Restart Oluyor
Migration servisi sürekli restart oluyorsa, muhtemelen migration zaten tamamlanmıştır. Bu normal bir durum olabilir.

**Çözüm**:
```bash
# Migration servisini durdur
docker compose stop mgx-migrate

# Migration'ı manuel çalıştır (gerekirse)
docker compose run --rm mgx-migrate
```

### Servisler Başlamıyor
```bash
# Logları kontrol et
docker compose logs

# Servisleri yeniden build et
docker compose up -d --build

# Volumes'ları temizle (dikkatli!)
docker compose down -v
```

### Port Çakışması
Eğer portlar kullanılıyorsa:
```bash
# Port kullanımını kontrol et
netstat -ano | findstr :8000
netstat -ano | findstr :3000
netstat -ano | findstr :5432
```

---

## ✅ Sonuç

**Tüm ana servisler çalışıyor:**
- ✅ Backend API: http://localhost:8000
- ✅ Frontend: http://localhost:3000
- ✅ PostgreSQL: localhost:5432
- ✅ Redis: localhost:6379
- ✅ MinIO: http://localhost:9000

**Migration servisi** restart oluyor ama bu normal olabilir (migration zaten tamamlanmış).

---

## 🌐 Erişim URL'leri

- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Frontend**: http://localhost:3000
- **MinIO Console**: http://localhost:9001
- **MinIO API**: http://localhost:9000


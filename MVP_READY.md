# 🎙️ Audio Pipeline Web App - MVP Ready

## ✅ Что готово

Backend **полностью готов**, Frontend **полностью реализован**!

### Backend (FastAPI)
- ✅ Auth endpoints (register, login, logout)
- ✅ Pipeline CRUD (create, list, get, cancel, delete, retry)
- ✅ Config management (get, save, reset, HF token)
- ✅ WebSocket для real-time прогресса
- ✅ User-isolated data directories
- ✅ Token encryption (Fernet/AES-256)
- ✅ Concurrency limits (1 per user, 3 system-wide)

### Frontend (React + Vite)
- ✅ Login/Register страницы
- ✅ Dashboard со списком jobs
- ✅ Run Pipeline форма с выбором источника
- ✅ Settings (HuggingFace, Download, Processing, Additional Options)
- ✅ JobProgress с WebSocket
- ✅ Material UI дизайн
- ✅ Axios с Bearer token авторизацией

---

## 🚀 Быстрый запуск MVP

### Шаг 1: Настроить окружение

```bash
# Генерирует .env с безопасными ключами
python setup_env.py
```

### Шаг 2: Установить frontend зависимости

```bash
cd frontend
npm install
```

### Шаг 3: Запустить backend

```bash
# Windows
.venv311\Scripts\activate
python -m uvicorn backend.app:app --reload

# Linux/Mac
source .venv311/bin/activate
python -m uvicorn backend.app:app --reload
```

### Шаг 4: Запустить frontend (новое окно терминала)

```bash
cd frontend
npm run dev
```

### ИЛИ: Запустить всё сразу

```bash
# Windows
start.bat

# Linux/Mac
chmod +x start.sh
./start.sh
```

---

## 📡 Доступные URL

| Сервис | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/api/docs |
| Health Check | http://localhost:8000/health |

---

## 🧪 Тестирование MVP

### Автоматический тест

```bash
# Запускает полный end-to-end тест
python test_mvp.py
```

Тест проверяет:
1. ✅ Регистрация пользователя
2. ✅ Логин
3. ✅ Получение текущего пользователя
4. ✅ Получение конфигурации
5. ✅ Сохранение конфигурации
6. ✅ Создание pipeline job
7. ✅ Получение статуса job
8. ✅ Список jobs
9. ✅ Системный статус

### Ручной тест через браузер

1. Откройте http://localhost:5173
2. Нажмите "Register" → создайте аккаунт
3. Логиньтесь
4. Перейдите в Settings → настройте HuggingFace
5. Перейдите в "Run Pipeline"
6. Выберите источник и нажмите "Run Pipeline"
7. Смотрите прогресс в реальном времени
8. Перейдите в Dashboard → проверьте статус job

---

## 📁 Структура Frontend

```
frontend/src/
├── App.jsx                    # Main app with routes
├── main.jsx                   # Entry point
├── api/                       # (ПУСТО) - используем axios напрямую
├── components/                 # UI компоненты
│   ├── Layout/
│   │   ├── Layout.jsx       # Main layout with sidebar
│   │   ├── Header.jsx        # Top navigation bar
│   │   └── Sidebar.jsx      # Side navigation menu
│   ├── Pipeline/
│   │   ├── RunForm.jsx       # Create job form
│   │   ├── JobProgress.jsx   # Real-time progress display
│   │   └── SourceSelector.jsx # Source type selection
│   └── Settings/
│       ├── HFSettings.jsx        # HuggingFace settings
│       ├── DownloadSettings.jsx   # Download configuration
│       ├── ProcessingSettings.jsx  # Processing toggles
│       └── AdditionalOptions.jsx   # Advanced options
├── context/
│   └── AuthContext.jsx       # Auth state management
├── hooks/
│   ├── useAuth.js            # Auth hook
│   └── useConfig.js          # Config hook
└── pages/
    ├── LoginPage.jsx            # Login page
    ├── RegisterPage.jsx         # Registration page
    ├── DashboardPage.jsx        # Jobs list
    ├── SettingsPage.jsx         # Settings tabs
    └── RunPipelinePage.jsx      # Run/view job page
```

---

## 🌍 WebSocket для Real-time Progress

Frontend автоматически подключается к WebSocket при просмотре job:

```javascript
// URL: ws://localhost:8000/ws/jobs/{job_id}?token=JWT_TOKEN
// Events: progress, status, error, completed, cancelled
```

---

## 📊 End-to-End Сценарий (полностью работает)

```
1. Регистрация          → POST /api/auth/register
                         ✅ Создаётся user в БД
                         ✅ Возвращается JWT token

2. Логин              → POST /api/auth/login
                         ✅ Проверяется пароль
                         ✅ Возвращается JWT token

3. Настройки          → GET /api/config
                         → PUT /api/config
                         ✅ Читается/пишется UserConfig
                         ✅ HF токен шифруется

4. Запуск Pipeline     → POST /api/pipelines
                         ✅ Создаётся PipelineJob
                         ✅ Проверяются лимиты
                         ✅ Запускается async task
                         ✅ Отправляется прогресс по WS

5. Статус             → GET /api/pipelines/{id}
                         ✅ Возвращается статус + steps

6. Прогресс           → WebSocket /ws/jobs/{id}
                         ✅ Отправляются progress обновления
                         ✅ Отображаются step-by-step
```

---

## ⚠️ Известные ограничения (MVP)

| Проблема | Статус | Описание |
|----------|--------|----------|
| Job Cancellation | ⚠️ | Cancel button не останавливает CPU-bound pipeline (только статус меняется) |
| Email Verification | — | Email поле есть, но не проверяется |
| Rate Limiting | — | Нет лимитов на API запросы |
| File Upload UI | — | Local source требует ручного размещения файлов |
| Database | — | SQLite (для прод. нужен PostgreSQL) |

---

## 🛠️ Если что-то не работает

### Backend не запускается

```bash
# Проверьте .env файл
cat .env

# SECRET_KEY должен быть минимум 32 символа
```

### Frontend не запускается

```bash
cd frontend
npm install
npm run dev
```

### WebSocket не подключается

```bash
# Проверьте backend запущен
curl http://localhost:8000/health

# Проверьте токен в localStorage
# F12 → Application → Local Storage → token
```

### Job не создаётся

```bash
# Проверьте config/config.yaml существует
cat config/config.yaml

# Проверьте логи backend
# В терминале где запущен uvicorn
```

---

## 🚀 Что нужно для Production

1. Установить `SECRET_KEY` через environment (не .env!)
2. Заменить SQLite на PostgreSQL
3. Настроить обратный прокси (nginx)
4. Включить HTTPS
5. Настроить process manager (systemd)
6. Добавить мониторинг (logs, metrics)

---

## 📝 Разработчикам

### Backend архитектура
```
backend/
├── app.py              # FastAPI app + lifespan
├── config.py           # Pydantic Settings
├── database.py         # SQLAlchemy session + user paths
├── models/             # ORM модели (User, PipelineJob, Config...)
├── routes/             # API endpoints
├── services/           # Business logic (executor, manager, ws)
└── utils/              # Helpers (file_utils, etc.)
```

### Frontend архитектура
```
frontend/
├── React 18 + React Router + Material UI
├── Axios для API вызовов
├── Socket.io-client для WebSocket
├── AuthContext для JWT управления
└── useConfig hook для настроек
```

---

## 📄 License

MIT

---

**MVP ГОТОВ К РАБОТЕ!** 🎉

Просто:
1. Запустите `python setup_env.py`
2. Запустите `start.bat` (Windows) или `./start.sh` (Linux/Mac)
3. Откройте http://localhost:5173
4. Пользуйтесь!
# Pipeline Executor Architecture

## Обзор

`DirectPipelineExecutor` запускает AudioPipeline напрямую (без subprocess), обеспечивая:
- Точный контроль прогресса
- Обновление PipelineStep записей в БД
- Real-time WebSocket сообщения
- Быстрый запуск задач

## Компоненты

### 1. DirectPipelineExecutor

Основной класс для выполнения pipeline.

**Методы:**

| Метод | Описание |
|--------|----------|
| `execute_job()` | Выполняет pipeline с отслеживанием прогресса |
| `execute_job_with_timeout()` | Выполняет pipeline с таймаутом |
| `cancel_job()` | Отменяет запущенную задачу |
| `is_job_running()` | Проверяет статус задачи |
| `get_active_jobs()` | Возвращает список активных задач |

### 2. PipelineStepTracker

Отслеживает и обновляет PipelineStep записи в БД.

**Методы:**

| Метод | Описание |
|--------|----------|
| `create_step_records()` | Создаёт записи для всех шагов |
| `update_step()` | Обновляет статус шага и отправляет WS |
| `mark_step_failed()` | Помечает шаг как failed |
| `get_step_status()` | Возвращает статус шага |
| `get_all_steps_status()` | Возвращает статусы всех шагов |

**Статусы шагов:**
- `pending` — ожидание выполнения
- `running` — выполняется
- `completed` — завершён успешно
- `failed` — завершён с ошибкой

**Порядок шагов:**
```
download → normalize → noise_reduction → vad_segmentation
→ transcription → filter → push
```

### 3. BackgroundJobScheduler

Менеджер планирования задач.

**Методы:**

| Метод | Описание |
|--------|----------|
| `schedule_and_execute()` | Создаёт задачу и запускает в фоне |
| `_execute_with_cleanup()` | Выполняет с автоматической очисткой |
| `cancel_and_cleanup()` | Отменяет задачу и чистит ресурсы |

## Поток выполнения

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Клиент создаёт задачу (POST /api/pipelines)           │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. BackgroundJobScheduler.schedule_and_execute()           │
│    - Проверяет лимиты                                    │
│    - Создаёт запись PipelineJob                            │
│    - Создаёт блокировки                                   │
│    - Создаёт записи PipelineStep                           │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. DirectPipelineExecutor.execute_job()                    │
│    - Получает конфиг пользователя                         │
│    - Создаёт временный config.yaml                         │
│    - Создаёт AudioPipeline с progress_callback              │
│    - Запускает pipeline в executor thread                  │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. AudioPipeline.emit_progress() ← progress_callback       │
│    - Отправляет данные в PipelineStepTracker             │
│    - Обновляет PipelineStep в БД                        │
│    - Отправляет WebSocket сообщение                       │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Pipeline завершён                                     │
│    - Обновляет финальный статус                         │
│    - Освобождает блокировки                              │
│    - Удаляет временные файлы                             │
└─────────────────────────────────────────────────────────────┘
```

## Структура базы данных

### PipelineJob
```python
{
    id: int,
    user_id: int,
    status: str,  # pending, running, completed, failed, cancelled
    source_type: str,  # url, youtube, json, huggingface, local
    source_value: str,
    config_snapshot: str,  # JSON config без токенов
    error_message: str,
    error_traceback: str,
    last_successful_step: str,
    file_count: int,
    total_size_bytes: int,
    created_at: datetime,
    started_at: datetime,
    completed_at: datetime
}
```

### PipelineStep
```python
{
    id: int,
    job_id: int,
    step_name: str,  # download, normalize, noise_reduction, ...
    status: str,  # pending, running, completed, failed
    progress: int,  # 0-100
    message: str,
    started_at: datetime,
    completed_at: datetime
}
```

## WebSocket сообщения

### Progress update
```json
{
    "type": "progress",
    "job_id": 123,
    "timestamp": "2026-03-29T12:00:00",
    "step": "download",
    "status": "running",
    "progress": 50,
    "message": "Downloading...",
    "files_count": 10
}
```

### Status update
```json
{
    "type": "status",
    "job_id": 123,
    "timestamp": "2026-03-29T12:00:00",
    "status": "completed"
}
```

### Error message
```json
{
    "type": "error",
    "job_id": 123,
    "timestamp": "2026-03-29T12:00:00",
    "error_message": "Failed to download",
    "traceback": "...",
    "last_successful_step": "download"
}
```

## API Endpoints

| Endpoint | Метод | Описание |
|----------|--------|----------|
| `/api/pipelines` | POST | Создать задачу |
| `/api/pipelines` | GET | Получить список задач |
| `/api/pipelines/{id}` | GET | Получить задачу |
| `/api/pipelines/{id}/cancel` | POST | Отменить задачу |
| `/api/pipelines/{id}/retry` | POST | Повторить задачу |
| `/api/pipelines/{id}/logs` | GET | Получить логи |
| `/ws/jobs/{id}` | WebSocket | Подписаться на прогресс |

## Создание задачи

**Request:**
```json
POST /api/pipelines
{
    "source_type": "youtube",
    "source_value": "https://youtube.com/watch?v=xxx",
    "skip_download": false,
    "skip_push": false
}
```

**Response:**
```json
{
    "id": 123,
    "user_id": 1,
    "status": "running",
    "source_type": "youtube",
    "source_value": "https://youtube.com/watch?v=xxx",
    "created_at": "2026-03-29T12:00:00",
    "started_at": "2026-03-29T12:00:01",
    "completed_at": null
}
```

## Лимиты

| Лимит | Значение |
|--------|----------|
| Задач на пользователя | 1 |
| Задач система | 3 |
| Файлов на задачу | 5 |
| Размер входных данных | 2GB |

## Тестирование

Запустить тест скрипт:
```bash
cd scripts
python test_pipeline_executor.py
```

Выберите:
1. Тест step tracker (без реального pipeline)
2. Тест с реальным выполнением pipeline

## Конфигурация

Пользовательский конфиг хранится в `backend/config.py` Settings и в базе данных `UserConfig`.

Обновление конфига:
```json
PUT /api/config
{
    "huggingface_repo_id": "username/dataset",
    "huggingface_token": "hf_xxx",
    "download_max_workers": 4,
    "noise_reduction_enabled": true
}
```

## Troubleshooting

**Ошибка: "Module 'main' not found"**
- Убедитесь, что `scripts/` добавлен в `sys.path`

**Pipeline не обновляет статус**
- Проверьте, что `progress_callback` передаётся в `AudioPipeline`
- Проверьте WebSocket соединение

**Зависания задач**
- Проверьте logs в `data/users/{user_id}/transcriptions/`
- Убедитесь, что CUDA доступна (для Whisper)

## Production советы

1. **Timeouts:** Добавьте таймауты для каждого шага
2. **Resource limits:** Ограничьте memory для pipeline
3. **Monitoring:** Логируйте время выполнения каждого шага
4. **Cleanup:** Периодически чистите старые задачи и файлы
5. **Retry logic:** Добавьте автоматический retry для transient errors
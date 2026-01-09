<div align="center">

# Современное REST API для управления задачами и пользователями с поддержкой версионирования

</div>

# Установка
```git clone https://github.com/EchoMessenger/tasktracker.git```

```python -m venv venv```

```pip install -r requirements.txt```

# Настройка базы данных
```sudo -u postgres psql -c "CREATE DATABASE tasktracker;"```

```sudo -u postgres psql -c "CREATE USER taskuser WITH PASSWORD 'securepassword';"```

```sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE tasktracker TO taskuser;"```

# Настройка подключения к БД
Отредактируйте database.py

```DATABASE_URL = "postgresql://taskuser:securepassword@localhost:5432/tasktracker"```
# Запуск приложения
```uvicorn main:app --reload --host 0.0.0.0 --port 8000```

После запуска откройте: http://localhost:8000/docs


# API документация

https://echomessenger.github.io/tasktracker/


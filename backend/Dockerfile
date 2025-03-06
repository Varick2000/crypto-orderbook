FROM python:3.11-slim

WORKDIR /app

# Встановлення залежностей
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Копіювання коду
COPY . .

# Відкриття порту
EXPOSE 8000

# Запуск сервера
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
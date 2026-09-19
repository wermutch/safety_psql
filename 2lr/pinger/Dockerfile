FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# config.yaml кладём прямо в образ — это несекретные настройки подключения (п.1.8)
COPY pinger.py config.yaml ./

CMD ["python", "pinger.py"]

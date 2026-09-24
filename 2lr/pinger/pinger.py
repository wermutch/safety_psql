import logging
import os
import sys
import time

import psycopg2
import yaml

# host/port/dbname берём из файла, как в первой лабе — это не секреты.
CONFIG_KEYS = {"host", "port", "dbname", "sslmode", "connect_timeout"}


def load_db_config(path="config.yaml"):
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    params = {k: raw[k] for k in CONFIG_KEYS if k in raw}
    # логин/пароль по п.1.6 — только из переменных среды, в файле их нет и не будет
    params["user"] = os.environ["DB_USER"]
    params["password"] = os.environ["DB_PASSWORD"]
    return params


def build_logger():
    logger = logging.getLogger("pinger")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    # успех и предупреждения — в stdout (п.1.2, п.1.3)
    out = logging.StreamHandler(sys.stdout)
    out.setLevel(logging.DEBUG)
    out.addFilter(lambda record: record.levelno < logging.ERROR)
    out.setFormatter(fmt)
    logger.addHandler(out)

    # ошибки подключения — отдельно, в stderr (п.1.2)
    err = logging.StreamHandler(sys.stderr)
    err.setLevel(logging.ERROR)
    err.setFormatter(fmt)
    logger.addHandler(err)

    # если задан путь — дублируем всё то же самое в файл (п.1.7)
    log_file = os.environ.get("LOG_FILE")
    if log_file:
        log_dir = os.path.dirname(log_file)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    return logger


def check_once(logger, db_params):
    # connect_timeout из config.yaml
    conn = psycopg2.connect(**db_params)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT VERSION();")
            (version,) = cur.fetchone()
    finally:
        conn.close()

    if "PostgreSQL" in version:
        logger.info("Подключение успешно. Версия: %s", version)
    else:
        # ответ пришёл, ошибки не было, но выглядит не как обычный ответ Postgres
        logger.warning("Нетипичный ответ от БД: %s", version)


def main():
    interval = int(os.environ.get("PING_INTERVAL_SECONDS", "300"))
    logger = build_logger()
    db_params = load_db_config()

    logger.info("Pinger запущен, интервал опроса: %s сек.", interval)

    while True:
        try:
            check_once(logger, db_params)
        except Exception as exc:
            # любая ошибка подключения — в stderr, но цикл не прерываем (п.1.4)
            logger.error("Не удалось подключиться к БД: %s", exc)
        time.sleep(interval)


if __name__ == "__main__":
    main()
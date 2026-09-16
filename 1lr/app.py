import argparse
import getpass
import sys

import psycopg2
import yaml

# Белый список ключей, которые допустимо брать из файла конфигурации.
ALLOWED_CONFIG_KEYS = {"host", "port", "dbname", "sslmode", "connect_timeout"}


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    if not isinstance(raw, dict):
        raise ValueError("config.yaml: ожидается словарь параметров")

    return {k: raw[k] for k in ALLOWED_CONFIG_KEYS if k in raw}


def get_credentials_console() -> tuple[str, str]:
    login = input("Логин: ").strip()
    password = getpass.getpass("Пароль: ")
    return login, password


def get_credentials_gui() -> tuple[str, str]:
    import tkinter as tk
    from tkinter import simpledialog

    root = tk.Tk()
    root.withdraw()
    login = simpledialog.askstring("Подключение к БД", "Логин:", parent=root)
    password = simpledialog.askstring(
        "Подключение к БД", "Пароль:", show="*", parent=root
    )
    root.destroy()

    if login is None or password is None:
        sys.exit("Ввод отменён пользователем")
    return login, password


def main() -> None:
    parser = argparse.ArgumentParser(description="Лабораторная: подключение к PostgreSQL")
    parser.add_argument("--config", default="config.yaml", help="файл параметров подключения")
    parser.add_argument("--gui", action="store_true", help="запросить логин/пароль через GUI")
    args = parser.parse_args()

    conn_params = load_config(args.config)

    login, password = get_credentials_gui() if args.gui else get_credentials_console()

    #    Безопасное объединение: login/password кладутся в словарь под ФИКСИРОВАННЫМИ
    #    ключами "user"/"password" и передаются psycopg2.connect(**conn_params) как
    #    отдельные именованные параметры driver'а — НЕ подставляются в строку DSN/conninfo.
    #    Поэтому ввод вида "x dbname=other_db" или "x sslmode=disable" не будет
    #    распарсен как дополнительные опции подключения, а останется буквальным
    #    значением логина/пароля. Ключи из ALLOWED_CONFIG_KEYS пользователь переопределить
    #    не может в принципе — они читаются только из файла и не связаны с вводом.
    conn_params["user"] = login
    conn_params["password"] = password

    conn = psycopg2.connect(**conn_params)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT VERSION();")
            (version,) = cur.fetchone()
            print(version)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

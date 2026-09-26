import argparse
import getpass
import os
import sys

import psycopg2
import yaml
from psycopg2 import sql

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
    password = simpledialog.askstring("Подключение к БД", "Пароль:", show="*", parent=root)
    root.destroy()
    if login is None or password is None:
        sys.exit("Ввод отменён пользователем")
    return login, password


# --- схема предметной области: единственный источник допустимых таблиц/колонок ---
# п.7: пользователь никогда не вводит имя таблицы/колонки текстом — только выбирает
# номер из этого списка, поэтому подставить произвольный идентификатор в SQL нельзя.
SCHEMA = {
    "authors": {"columns": ["id", "name", "country"], "pk": "id"},
    "books": {"columns": ["id", "title", "author_id", "price", "year"], "pk": "id"},
    "customers": {"columns": ["id", "name", "email"], "pk": "id"},
    "orders": {"columns": ["id", "customer_id", "created_at"], "pk": "id"},
    "order_items": {"columns": ["id", "order_id", "book_id", "quantity", "price"], "pk": "id"},
}

LOG_FILE = os.environ.get("LOG_FILE")


def log_raw(text: str) -> None:
    # п.6.7 — сырой текст ошибки дублируется в файл без обработки, пользователю не показывается
    if LOG_FILE:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def choose(options: list[str], prompt: str) -> str:
    for i, opt in enumerate(options, 1):
        print(f"{i}. {opt}")
    while True:
        raw = input(prompt).strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("Некорректный выбор, попробуйте снова.")


def choose_table() -> str:
    return choose(list(SCHEMA.keys()), "Выберите таблицу (номер): ")


def choose_column(table: str, exclude_pk: bool = False) -> str:
    cols = SCHEMA[table]["columns"]
    if exclude_pk:
        cols = [c for c in cols if c != SCHEMA[table]["pk"]]
    return choose(cols, "Выберите колонку (номер): ")


def yes(prompt: str) -> bool:
    return input(prompt).strip().lower() == "y"


# --- п.6.5: успех/ошибка — в stdout/stderr, пользователю — дружественный текст ---
def execute_read(conn, query, params=None):
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            colnames = [d.name for d in cur.description]
        print(f"OK: найдено строк — {len(rows)}.")
        print(colnames)
        for row in rows:
            print(row)
    except Exception as exc:
        conn.rollback()
        log_raw(repr(exc))
        print("Ошибка: не удалось выполнить запрос на чтение.", file=sys.stderr)


def execute_write(conn, query, params, ok_message="OK: изменения применены."):
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
        conn.commit()
        print(ok_message)
    except Exception as exc:
        conn.rollback()
        log_raw(repr(exc))
        print("Ошибка: не удалось выполнить изменение данных.", file=sys.stderr)


# --- п.6.1.1 ---
def view_all(conn):
    table = choose_table()
    query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(table))
    execute_read(conn, query)


# --- п.6.1.2 ---
def view_filtered_one(conn):
    table = choose_table()
    col = choose_column(table)
    value = input(f"Значение для {col}: ")
    query = sql.SQL("SELECT * FROM {} WHERE {} = %s").format(sql.Identifier(table), sql.Identifier(col))
    execute_read(conn, query, (value,))


# --- п.6.1.3 ---
def view_filtered_many(conn):
    table = choose_table()
    conds, values = [], []
    while True:
        col = choose_column(table)
        values.append(input(f"Значение для {col}: "))
        conds.append(sql.SQL("{} = %s").format(sql.Identifier(col)))
        if not yes("Добавить ещё условие? (y/n): "):
            break
    query = sql.SQL("SELECT * FROM {} WHERE {}").format(sql.Identifier(table), sql.SQL(" AND ").join(conds))
    execute_read(conn, query, values)


# --- п.6.2.1 ---
def update_one(conn):
    table = choose_table()
    pk = SCHEMA[table]["pk"]
    pk_value = input(f"Значение {pk} записи для обновления: ")
    set_cols, set_values = [], []
    while True:
        col = choose_column(table, exclude_pk=True)
        set_values.append(input(f"Новое значение для {col}: "))
        set_cols.append(sql.SQL("{} = %s").format(sql.Identifier(col)))
        if not yes("Изменить ещё одну колонку? (y/n): "):
            break
    query = sql.SQL("UPDATE {} SET {} WHERE {} = %s").format(
        sql.Identifier(table), sql.SQL(", ").join(set_cols), sql.Identifier(pk)
    )
    execute_write(conn, query, set_values + [pk_value])


# --- п.6.2.2 ---
def update_many(conn):
    table = choose_table()
    set_col = choose_column(table, exclude_pk=True)
    set_value = input(f"Новое значение для {set_col}: ")
    filter_col = choose_column(table)
    values = []
    while True:
        values.append(input(f"Значение {filter_col} (для отбора): "))
        if not yes("Добавить ещё значение? (y/n): "):
            break
    placeholders = sql.SQL(", ").join(sql.Placeholder() * len(values))
    query = sql.SQL("UPDATE {} SET {} = %s WHERE {} IN ({})").format(
        sql.Identifier(table), sql.Identifier(set_col), sql.Identifier(filter_col), placeholders
    )
    execute_write(conn, query, [set_value] + values)


# --- п.6.3.1 ---
def insert_one(conn):
    table = choose_table()
    columns = [c for c in SCHEMA[table]["columns"] if c != SCHEMA[table]["pk"]]
    values = [input(f"Значение для {c}: ") for c in columns]
    cols_ident = sql.SQL(", ").join(map(sql.Identifier, columns))
    placeholders = sql.SQL(", ").join(sql.Placeholder() * len(columns))
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(sql.Identifier(table), cols_ident, placeholders)
    execute_write(conn, query, values, "OK: строка добавлена.")


# --- п.6.4.1 ---
def insert_many_one_table(conn):
    table = choose_table()
    columns = [c for c in SCHEMA[table]["columns"] if c != SCHEMA[table]["pk"]]
    rows = []
    while True:
        rows.append(tuple(input(f"Значение для {c}: ") for c in columns))
        if not yes("Добавить ещё строку? (y/n): "):
            break
    cols_ident = sql.SQL(", ").join(map(sql.Identifier, columns))
    placeholders = sql.SQL(", ").join(sql.Placeholder() * len(columns))
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(sql.Identifier(table), cols_ident, placeholders)
    try:
        with conn.cursor() as cur:
            cur.executemany(query, rows)
        conn.commit()
        print(f"OK: добавлено строк — {len(rows)}.")
    except Exception as exc:
        conn.rollback()
        log_raw(repr(exc))
        print("Ошибка: не удалось вставить данные.", file=sys.stderr)


# --- п.6.3.2: одна строка в две связанные таблицы (заказ + одна позиция) ---
def insert_order_with_one_item(conn):
    customer_id = input("ID клиента: ")
    book_id = input("ID книги: ")
    quantity = input("Количество: ")
    price = input("Цена позиции: ")
    try:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("INSERT INTO {} (customer_id) VALUES (%s) RETURNING id").format(sql.Identifier("orders")),
                (customer_id,),
            )
            order_id = cur.fetchone()[0]
            cur.execute(
                sql.SQL(
                    "INSERT INTO {} (order_id, book_id, quantity, price) VALUES (%s, %s, %s, %s)"
                ).format(sql.Identifier("order_items")),
                (order_id, book_id, quantity, price),
            )
        conn.commit()
        print(f"OK: заказ №{order_id} создан.")
    except Exception as exc:
        conn.rollback()
        log_raw(repr(exc))
        print("Ошибка: не удалось создать заказ.", file=sys.stderr)


# --- п.6.4.2 (повышенная сложность): несколько строк в несколько связанных таблиц ---
def insert_order_with_many_items(conn):
    customer_id = input("ID клиента: ")
    items = []
    while True:
        book_id = input("ID книги: ")
        quantity = input("Количество: ")
        price = input("Цена позиции: ")
        items.append((book_id, quantity, price))
        if not yes("Добавить ещё позицию? (y/n): "):
            break
    try:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("INSERT INTO {} (customer_id) VALUES (%s) RETURNING id").format(sql.Identifier("orders")),
                (customer_id,),
            )
            order_id = cur.fetchone()[0]
            rows = [(order_id, b, q, p) for b, q, p in items]
            cur.executemany(
                sql.SQL(
                    "INSERT INTO {} (order_id, book_id, quantity, price) VALUES (%s, %s, %s, %s)"
                ).format(sql.Identifier("order_items")),
                rows,
            )
        conn.commit()
        print(f"OK: заказ №{order_id} создан, позиций — {len(rows)}.")
    except Exception as exc:
        conn.rollback()
        log_raw(repr(exc))
        print("Ошибка: не удалось создать заказ с позициями.", file=sys.stderr)


MENU = [
    ("Просмотр таблицы без фильтра", view_all),
    ("Просмотр с фильтром по одному значению", view_filtered_one),
    ("Просмотр с фильтром по нескольким значениям", view_filtered_many),
    ("Обновить одну запись", update_one),
    ("Обновить несколько записей", update_many),
    ("Вставить одну строку", insert_one),
    ("Вставить заказ + одну позицию (2 связанные таблицы)", insert_order_with_one_item),
    ("Вставить несколько строк в одну таблицу", insert_many_one_table),
    ("Вставить заказ с несколькими позициями (неск. таблиц)", insert_order_with_many_items),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Лабораторная 3: CLI для книжного магазина")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args()

    conn_params = load_config(args.config)
    # п.6.6 — логин/пароль только от пользователя
    login, password = get_credentials_gui() if args.gui else get_credentials_console()
    conn_params["user"] = login
    conn_params["password"] = password

    try:
        conn = psycopg2.connect(**conn_params)
    except Exception as exc:
        log_raw(repr(exc))
        sys.exit("Ошибка: не удалось подключиться к базе данных.")

    print("Подключение установлено.")

    try:
        while True:
            print("\n0. Выход")
            for i, (title, _) in enumerate(MENU, 1):
                print(f"{i}. {title}")
            choice = input("Выберите действие: ").strip()
            if choice == "0":
                break
            if choice.isdigit() and 1 <= int(choice) <= len(MENU):
                MENU[int(choice) - 1][1](conn)
            else:
                print("Некорректный выбор.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

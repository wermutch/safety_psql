INSERT INTO authors (name, country) VALUES
    ('Лев Толстой', 'Россия'),
    ('Джордж Оруэлл', 'Великобритания');

INSERT INTO books (title, author_id, price, year) VALUES
    ('Война и мир', 1, 890.00, 1869),
    ('Анна Каренина', 1, 650.00, 1877),
    ('1984', 2, 450.00, 1949);

INSERT INTO customers (name, email) VALUES
    ('Иван Петров', 'ivan@example.com'),
    ('Мария Смирнова', 'maria@example.com');

INSERT INTO orders (customer_id) VALUES (1);

INSERT INTO order_items (order_id, book_id, quantity, price) VALUES
    (1, 1, 1, 890.00),
    (1, 3, 2, 450.00);

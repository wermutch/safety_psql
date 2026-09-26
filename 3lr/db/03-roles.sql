-- обычный пользователь, не суперюзер: SELECT/INSERT/UPDATE, без DELETE и DDL
CREATE USER nerush WITH PASSWORD 'nerush';

GRANT CONNECT ON DATABASE shopdb TO nerush;
GRANT USAGE ON SCHEMA public TO nerush;
GRANT SELECT, INSERT, UPDATE ON authors, books, customers, orders, order_items TO nerush;

-- нужно, чтобы INSERT в SERIAL-колонки id работал под этим пользователем
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nerush;

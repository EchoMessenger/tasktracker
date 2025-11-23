import argparse
import sys
import os
from sqlalchemy import text

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import engine, Base


def check_tables_exist():
    """Проверить существование таблиц в PostgreSQL"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
            """))
            tables = [row[0] for row in result]
            return tables
    except Exception as e:
        print(f"Ошибка при проверке таблиц: {e}")
        return []


def drop_tables():
    """Удалить все таблицы через прямые SQL запросы"""
    try:
        with engine.begin() as conn:
            # Получаем список всех таблиц
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
            """))
            tables = [row[0] for row in result]

            if not tables:
                print("Нет таблиц для удаления")
                return True
            conn.execute(text("SET session_replication_role = 'replica';"))
            for table in tables:
                conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
                print(f"Удалена таблица: {table}")
            conn.execute(text("SET session_replication_role = 'origin';"))

        print("Все таблицы успешно удалены")
        return True

    except Exception as e:
        print(f"Ошибка при удалении таблиц: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Управление базой данных PostgreSQL')
    parser.add_argument('--drop', action='store_true', help='Удалить все таблицы')
    parser.add_argument('--force', action='store_true', help='Не запрашивать подтверждение')

    args = parser.parse_args()

    if args.drop:
        print("Операция: УДАЛЕНИЕ ВСЕХ ТАБЛИЦ")
        print("=" * 40)

        tables = check_tables_exist()
        if not tables:
            print("Нет таблиц для удаления")
            return

        print(f"Найдено таблиц: {len(tables)}")
        for table in tables:
            print(f"  - {table}")

        if not args.force:
            confirm = input("\nВы уверены, что хотите удалить ВСЕ таблицы? (y/N): ")
            if confirm.lower() not in ['y', 'yes']:
                print("Операция отменена")
                return

        success = drop_tables()
        if not success:
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
import os
from logging.config import fileConfig
from urllib.parse import quote_plus

from sqlalchemy import create_engine, engine_from_config, pool
from alembic import context

config = context.config

db_user = os.environ.get("DB_USER")
db_password = os.environ.get("DB_PASSWORD")
db_host = os.environ.get("DB_HOST")
db_port = os.environ.get("DB_PORT")
db_name = os.environ.get("DB_NAME")

database_url = None
if db_user and db_password and db_host and db_port and db_name:
    user_enc = quote_plus(db_user)
    password_enc = quote_plus(db_password)
    database_url = f"postgresql://{user_enc}:{password_enc}@{db_host}:{db_port}/{db_name}"

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None

def run_migrations_offline() -> None:
    url = database_url or config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    if database_url:
        connectable = create_engine(
            database_url,
            poolclass=pool.NullPool
        )
    else:
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

from kirana.db.models import Base
from kirana.config import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_DIRECT)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    from sqlalchemy import create_engine
    connectable = create_engine(settings.DATABASE_URL_DIRECT)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

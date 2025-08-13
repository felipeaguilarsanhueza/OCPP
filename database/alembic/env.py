import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Añade la raíz del proyecto al path para que pueda importar `database.models`
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

# Importa la metadata de tus modelos
from database.models import Base

# Este es el objeto Config de Alembic, que lee alembic.ini
config = context.config

# Si quieres sobreescribir la URL con una variable de entorno (.env), podrías:
# from config.settings import settings
# config.set_main_option('sqlalchemy.url', settings.DATABASE_URL)

# Configura el logging según alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata que usará Alembic para autogenerar
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Ejecuta migraciones en modo offline (genera SQL)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecuta migraciones en modo online (conexión real)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,             # detectar cambios de tipo
            compare_server_default=True,   # detectar cambios en default
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

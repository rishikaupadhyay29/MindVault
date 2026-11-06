from alembic import context
from sqlalchemy import create_engine, pool

from app import models  # noqa: F401  (register tables)
from app.config import settings
from app.db import Base

engine = create_engine(settings.database_url, poolclass=pool.NullPool)
with engine.connect() as conn:
    context.configure(connection=conn, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()

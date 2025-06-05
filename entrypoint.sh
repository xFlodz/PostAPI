#!/bin/bash

until PGPASSWORD=q1w2e3 psql -h db -U postgres -p 5432 -d posts_db  -c '\q'; do
  >&2 echo "PostgreSQL не доступен - ждём..."
  sleep 1
done

>&2 echo "PostgreSQL готов - выполняем миграции"

flask db init || true

flask db migrate -m "Auto migration"

flask db upgrade

exec "$@"
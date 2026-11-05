#!/bin/sh
# Writes PgBouncer's settings from the environment and starts it (pgbouncer.Dockerfile). Nothing secret is baked
# into the image: the password arrives from .env.api at start and is written, readable by this user only, to
# /run/pgbouncer, which lives as long as the container.
#
# Transaction pooling: a server connection belongs to a client for one transaction only. That is safe for the API
# because everything it sets per request is transaction-local (eos_core.db: set_config(..., true) for the
# organisation and the row-level security bypass), and it holds no session state: no LISTEN, no session advisory
# locks, no session SET. max_prepared_statements lets psycopg 3 keep its automatic prepared statements across the
# pool (PgBouncer 1.21 and later).
set -eu

: "${EOS_APP_DB_PASSWORD:?set EOS_APP_DB_PASSWORD}"
dir=/run/pgbouncer
umask 077

# userlist.txt quotes the password; a double quote inside it is written twice.
password=$(printf '%s' "$EOS_APP_DB_PASSWORD" | sed 's/"/""/g')
printf '"eos_app" "%s"\n' "$password" > "$dir/userlist.txt"

cat > "$dir/pgbouncer.ini" <<EOF
[databases]
eos = host=${PGBOUNCER_DB_HOST:-db} port=${PGBOUNCER_DB_PORT:-5432} dbname=eos

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
unix_socket_dir =
auth_type = scram-sha-256
auth_file = $dir/userlist.txt
pool_mode = transaction
default_pool_size = ${PGBOUNCER_POOL_SIZE:-20}
max_client_conn = ${PGBOUNCER_MAX_CLIENT_CONN:-200}
max_prepared_statements = 200
ignore_startup_parameters = extra_float_digits
log_connections = 0
log_disconnections = 0
EOF

exec pgbouncer "$dir/pgbouncer.ini"

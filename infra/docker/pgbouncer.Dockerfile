# PgBouncer, the connection pooler between the API processes and Postgres (#96; README, "Connection pooler").
# Alpine's own package, not a third-party image: the version follows the Alpine release pinned here, and it is at
# least 1.21 (1.22.1 in Alpine 3.20), which `max_prepared_statements` (psycopg 3's automatic prepared statements) needs.
FROM alpine:3.20

# PgBouncer refuses to run as root, and the package creates no user of its own.
RUN apk add --no-cache pgbouncer \
    && adduser -S -D -H -h /run/pgbouncer pgbouncer \
    && mkdir -p /run/pgbouncer \
    && chown pgbouncer /run/pgbouncer

COPY pgbouncer-entrypoint.sh /usr/local/bin/pgbouncer-entrypoint.sh

USER pgbouncer
EXPOSE 6432
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD nc -z 127.0.0.1 6432 || exit 1
ENTRYPOINT ["sh", "/usr/local/bin/pgbouncer-entrypoint.sh"]

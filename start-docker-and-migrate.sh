set -euo pipefail

cd "$(dirname "$0")"

docker-compose up -d postgres

count=0
limit=30
until docker-compose exec -T postgres pg_isready -q -U postgres; do
    sleep 2
    count=$((count + 1))
    if [ $count -ge $limit ]; then
        echo "Postgres not ready" >&2
        exit 1
    fi
done

docker-compose run --rm pin-api alembic -c alembic.ini upgrade head

docker-compose up -d pin-api
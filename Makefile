PROJECT := pin-api
.DEFAULT_GOAL := docker-up
ALEMBIC_INI ?= alembic.ini

docker-build:
	@docker build \
		-t pin-api \
		--build-arg PACKAGE_NAME=pin-api \
		--build-arg BUILD_REF=`git rev-parse --short HEAD` \
		--build-arg BUILD_DATE=`date -u +”%Y-%m-%dT%H:%M:%SZ”` \
		.
		
pin-api: 
	@go run ./cmd/api/main.go

docker-up:
	@docker-compose up --build --remove-orphans

docker-down:
	@docker-compose down

migrate-up:
	alembic -c $(ALEMBIC_INI) upgrade head

migrate-down:
	alembic -c $(ALEMBIC_INI) downgrade -1
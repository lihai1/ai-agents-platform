.PHONY: build run test migrate-up migrate-down lint fmt clean dev

# Variables
BINARY_NAME=control-plane
GO_FILES=$(shell find . -name '*.go' -type f)
MIGRATION_DIR=./migrations
DATABASE_URL=postgres://agentic:agentic@localhost:5432/agentic?sslmode=disable

build:
	go build -o bin/$(BINARY_NAME) ./cmd/server

run:
	go run ./cmd/server

test:
	ginkgo -r ./...

migrate-up:
	migrate -path $(MIGRATION_DIR) -database "$(DATABASE_URL)" up

migrate-down:
	migrate -path $(MIGRATION_DIR) -database "$(DATABASE_URL)" down

lint:
	golangci-lint run

fmt:
	go fmt ./...

clean:
	rm -rf bin/

dev: migrate-up
	docker-compose up -d postgres
	@sleep 3
	$(MAKE) run

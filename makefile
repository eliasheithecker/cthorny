.DEFAULT_GOAL := run

run:
	(cd ./cmd/ && go run .)

run-dev:
	(cd ./cmd/ && go run . --config=dev-config.yaml)

build:
	(cd ./cmd/ && go build .)

br:
	cd ./cmd/
	go build .
	./thorny $(ARGS)

t:
	rsync -av --delete . [user@host:/path]
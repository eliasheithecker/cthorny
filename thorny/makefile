.DEFAULT_GOAL := run

run:
	(cd ./cmd/ && go run .)

run-dev:
	(cd ./cmd/ && go run . --config=dev-config.yaml)

build:
	(cd ./cmd/ && go build .)

test:
	go test ./...

# Static linux binaries for the cloud sensors (deploy/startup.sh downloads them
# from the GitHub release). gopacket is used without pcap, so no cgo is needed.
release:
	mkdir -p dist
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -o dist/thorny-linux-amd64 ./cmd
	CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -trimpath -o dist/thorny-linux-arm64 ./cmd
	cp cmd/aws-config.yaml dist/aws-config.yaml

br:
	cd ./cmd/
	go build .
	./thorny $(ARGS)

t:
	rsync -av --delete . [user@host:/path]

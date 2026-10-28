FROM golang:1.24.3-alpine AS build
WORKDIR /build
COPY go.mod main.go ./
RUN go mod tidy && CGO_ENABLED=0 go build -o /badger-maintenance .

FROM python:3.12-slim
COPY --from=build /badger-maintenance /usr/local/bin/badger-maintenance
ENTRYPOINT ["/usr/local/bin/badger-maintenance"]

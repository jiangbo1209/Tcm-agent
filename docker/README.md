# TCM Agent Docker Deployment

## Services

- frontend: Vue production build + Nginx
- backend: FastAPI + Uvicorn + in-process Agent

## Ports

- Frontend: http://localhost:5500
- Backend: http://localhost:8011
- Backend API docs: http://localhost:8011/docs

## Build and start

Run from project root:

docker compose -f docker/docker-compose.app.yml up -d --build

## Status

docker compose -f docker/docker-compose.app.yml ps

## Logs

docker compose -f docker/docker-compose.app.yml logs -f --tail=200

## Stop

docker compose -f docker/docker-compose.app.yml down

## Rebuild

docker compose -f docker/docker-compose.app.yml up -d --build

## External service addresses

The backend runs inside a Docker container. Therefore `localhost` and
`127.0.0.1` refer to the backend container itself, not the Docker host.

If PostgreSQL and RAGFlow are exposed on the Docker host, configure:

POSTGRES_HOST=host.docker.internal
RAGFLOW_BASE_URL=http://host.docker.internal:9380

`docker-compose.app.yml` defines the following host mapping:

    extra_hosts:
      - "host.docker.internal:host-gateway"

If PostgreSQL or RAGFlow runs on another server, replace these values with
the actual service address.

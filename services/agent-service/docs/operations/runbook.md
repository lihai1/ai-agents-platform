# Operations Runbook

This runbook provides operational guidance for running and maintaining the agentic engineering platform.

## Starting the Platform

### Development Mode

```bash
# Start all services
docker-compose up

# Or use make
make dev
```

### Production Mode

```bash
# Build and start with production configuration
docker-compose -f docker-compose.prod.yml up -d
```

## Service Health Checks

### Control Plane (Go)

```bash
curl http://localhost:8080/healthz
curl http://localhost:8080/readyz
```

### Agent Service (Python)

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

### Angular UI

```bash
curl http://localhost:4200
```

## Troubleshooting

### Agent Run Stuck in Phase

1. Check run status:
   ```bash
   curl http://localhost:8000/agent/v1/runs/{run_id}
   ```

2. Check events:
   ```bash
   curl http://localhost:8000/agent/v1/runs/{run_id}/events
   ```

3. Cancel if needed:
   ```bash
   curl -X POST http://localhost:8000/agent/v1/runs/{run_id}/cancel
   ```

### Workspace Cleanup

If workspaces fail to clean up:

```bash
# Manually clean up Docker containers
docker ps -a | grep workspace- | awk '{print $1}' | xargs docker rm -f

# Clean up volumes
docker volume ls | grep workspace-volume- | awk '{print $2}' | xargs docker volume rm
```

### Database Issues

```bash
# Reset database (WARNING: deletes all data)
docker-compose exec postgres psql -U postgres -c "DROP DATABASE IF EXISTS agent; CREATE DATABASE agent;"
docker-compose exec agent-service alembic upgrade head
```

## Monitoring

### Key Metrics

- Active runs per user
- Average run duration
- Token usage per run
- Cost per run
- Success/failure rate
- Workspace utilization

### Logs

```bash
# Control plane logs
docker-compose logs -f control-plane

# Agent service logs
docker-compose logs -f agent-service

# Worker logs
docker-compose logs -f agent-worker
```

## Backup and Recovery

### Database Backup

```bash
docker-compose exec postgres pg_dump -U postgres agent > backup.sql
```

### Database Restore

```bash
docker-compose exec -T postgres psql -U postgres agent < backup.sql
```

## Security

### Secrets Management

- Never commit secrets to git
- Use environment variables for sensitive configuration
- Rotate API keys regularly
- Review access logs for suspicious activity

### Rate Limiting

Configure rate limits in the control plane:

```yaml
# config/rate-limits.yaml
per_user:
  requests_per_minute: 60
  concurrent_runs: 5

per_organization:
  requests_per_minute: 600
  concurrent_runs: 50
```

## Scaling

### Horizontal Scaling

To scale the agent service:

```bash
docker-compose up --scale agent-service=3
```

To scale workers:

```bash
docker-compose up --scale agent-worker=5
```

### NATS Clustering

For high availability, deploy NATS in cluster mode:

```yaml
nats:
  image: nats:latest
  command: "-cluster nats://0.0.0.0:6222 -routes nats://nats-1:6222,nats://nats-2:6222"
```

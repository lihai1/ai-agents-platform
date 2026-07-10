# Rate Limiter Implementation for Agent Service

Implement a distributed rate limiter using fixed window with leaky bucket algorithm to protect agent-service from DDOS and API abuse, limiting requests by chat_id (20/min) and user_id (100/min).

## Redis Usage and Benefits

### Why Redis for Rate Limiting

**Redis provides the ideal backend for distributed rate limiting:**

- **In-memory performance**: Sub-millisecond latency for rate limit checks, critical for high-throughput API endpoints
- **Atomic operations**: Built-in atomic INCR/EXPIRE commands prevent race conditions in distributed environments
- **TTL (Time-To-Live)**: Automatic key expiration simplifies window management - no manual cleanup needed
- **Distributed state**: Shared state across multiple agent-service instances ensures consistent limits
- **Persistence options**: RDB/AOF for durability if needed, though rate limit data is typically ephemeral
- **Data structures**: Sorted sets, hashes, and strings support various rate limiting algorithms

### Redis Implementation for Leaky Bucket

**Key Schema:**
```
rate_limit:{scope}:{identifier} = {
  "tokens": 20,           # Current token count
  "last_refill": 1234567890,  # Unix timestamp of last refill
  "window_start": 1234567890  # Window start timestamp
}
TTL: 60 seconds (1 minute window)
```

**Scope Examples:**
- `rate_limit:chat:thread-abc123` - Per-chat limit (20/min)
- `rate_limit:user:user-xyz789` - Per-user limit (100/min)

**User Identification:**
- Users are managed in control-plane service (`internal/models/user.go`, `internal/repository/user.go`)
- Agent-service receives user ID via `X-User-Subject` header (`internal/chatkit/context.py`)
- Default: `user:local-dev` if header not present (dev mode)
- Rate limiter will extract `user_subject` from request context for per-user limits

**Operations:**
1. **Check limit**: Lua script atomically checks token count and refills if needed
2. **Consume token**: Decrement token count if available, return 429 if empty
3. **Refill**: Add tokens at constant rate (leaky bucket) or reset on window boundary (fixed window)

**Benefits over alternatives:**
- **vs In-memory**: Works across multiple service instances, survives restarts
- **vs PostgreSQL**: 10-100x faster, automatic expiration, no query overhead
- **vs NATS KV**: Redis has mature rate limiting patterns and better tooling

**Fallback strategy:**
If Redis is unavailable, fall back to in-memory per-instance limiting (degraded but functional) or fail-open (log warnings but allow requests) based on configuration.

## Skill execution plan

**Request:** Implement distributed rate limiter for agent-service using fixed window with leaky bucket algorithm, limiting 20 requests/minute per chat_id or 100 requests/minute per user_id across all endpoints, returning HTTP 429 when exceeded.
**Complexity:** architectural
**Assumptions:** Redis will be added to the infrastructure stack (not currently present); rate limiting applies to all HTTP endpoints; chat_id and user_id extracted from request context/JWT; leaky bucket allows burst traffic within limits.

1. `@skills:repo-scout Explore agent-service structure for rate limiter integration points`
   - Goal: Identify existing middleware patterns, authentication/user context extraction, and configuration management
   - Exit evidence: Documented middleware structure in app/main.py, request context extraction in internal/chatkit/context.py, and configuration pattern in internal/config.py

2. `@skills:architecture-designer Design rate limiter architecture with Redis integration`
   - Goal: Define rate limiter architecture, Redis data structures, and integration points with FastAPI middleware
   - Exit evidence: Architecture document describing leaky bucket algorithm implementation, Redis key schema, middleware placement, and fallback strategy if Redis unavailable

3. `@skills:solution-planner Create implementation plan for rate limiter components`
   - Goal: Break down implementation into rate limiter module, FastAPI middleware, configuration, Docker Compose changes, and tests
   - Exit evidence: File-level implementation plan with module structure, API design, and migration steps

4. `@skills:devops-developer Add Redis to docker-compose-dev.yml and docker-compose.yml`
   - Goal: Add Redis service to both development and production Docker Compose files with appropriate networking
   - Exit evidence: Updated docker-compose-dev.yml and docker-compose.yml with Redis service, health checks, and environment variables

5. `@skills:python-developer Implement rate limiter module with Redis backend`
   - Goal: Create internal/rate_limiter/ module with leaky bucket algorithm, Redis client, and rate limit checking logic
   - Exit evidence: New internal/rate_limiter/__init__.py, limiter.py, and redis_client.py files with working implementation

6. `@skills:python-developer Implement FastAPI middleware for rate limiting`
   - Goal: Create rate limiting middleware that extracts chat_id/user_id from requests and applies rate limits
   - Exit evidence: New internal/middleware/rate_limit.py with FastAPI middleware integrated into app/main.py

7. `@skills:python-developer Add rate limiter configuration to settings`
   - Goal: Add rate limit configuration (limits, window size, Redis URL) to internal/config.py
   - Exit evidence: Updated internal/config.py with rate limit settings and .env.example documentation

8. `@skills:test-engineer Write unit and integration tests for rate limiter`
   - Goal: Create comprehensive tests for rate limiter logic, middleware, and Redis integration
   - Exit evidence: New tests/unit/test_rate_limiter.py and tests/integration/test_rate_limit_middleware.py with passing tests

9. `@skills:code-reviewer Review rate limiter implementation for correctness and security`
   - Goal: Review rate limiter algorithm, Redis integration, error handling, and security considerations
   - Exit evidence: Code review feedback addressing any issues found in the implementation

10. `@skills:completion-verifier Verify rate limiter works end-to-end`
    - Goal: Verify rate limiter is correctly limiting requests and returning 429 responses
    - Exit evidence: Successful test run showing rate limits enforced and HTTP 429 responses returned when limits exceeded

## Done when
- Rate limiter middleware is active on all agent-service endpoints
- Requests exceeding 20/min per chat_id return HTTP 429 with retry-after header
- Requests exceeding 100/min per user_id return HTTP 429 with retry-after header
- Redis is integrated into the Docker Compose setup
- Unit and integration tests pass
- Implementation follows existing code patterns and conventions

# Go REST Feature Fixture Repository

This is a fixture repository for testing the agent's ability to add a REST endpoint to a Go application.

## Task

Add a new REST endpoint `/api/v1/users/{id}` that:
- Returns user information by ID
- Validates that the ID is a valid UUID
- Returns 404 if user not found
- Returns 400 for invalid UUID format

## Expected Changes

- `internal/handlers/user.go` - Add new handler function
- `internal/service/user.go` - Add service method
- `internal/repository/user.go` - Add repository query
- `internal/handlers/user_test.go` - Add tests

## Acceptance Criteria

1. Endpoint returns 200 on success with user data
2. Endpoint validates UUID format (400 for invalid)
3. Endpoint returns 404 for non-existent user
4. Tests pass for all cases
5. No breaking changes to existing endpoints

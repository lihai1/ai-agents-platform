# User Authentication Implementation

Implement complete user authentication flow with login/register UI components, route guards, and integration with existing control-plane auth endpoints across 5 stages.

## 5-Stage Implementation Plan

### Stage 1: Backend Verification & Enhancement
**Goal:** Verify control-plane auth endpoints work correctly and add user data retrieval endpoint.

**Tasks:**
- Test existing `/auth/login` and `/auth/register` endpoints
- Add `/auth/me` endpoint to retrieve current user data from JWT
- Ensure JWT includes user_id in claims for agent-service X-User-Subject header
- Add database migration if needed for users table
- Write integration tests for auth endpoints

**Exit evidence:** Control-plane auth endpoints tested and working, new `/auth/me` endpoint returns user data.

### Stage 2: Angular Auth Components
**Goal:** Create separate LoginPage and RegisterPage components with form validation.

**Tasks:**
- Create `login.component.ts/html/css` with email/password form
- Create `register.component.ts/html/css` with name/email/password/confirm_password form
- Implement form validation (email format, password min length, password confirmation)
- Add error handling and loading states
- Style components with modern UI (using existing design patterns)
- Add navigation links between login and register pages

**Exit evidence:** Login and register components created with validation and styling.

### Stage 3: Angular Auth Service Enhancement
**Goal:** Enhance AuthService to handle user data storage and token management.

**Tasks:**
- Add `getCurrentUser()` method to fetch user data from `/auth/me`
- Add `setUser(user)` and `getUser()` methods for localStorage management
- Update `login()` to store both token and user data
- Update `logout()` to clear token and user data
- Add token refresh logic if needed (optional for now)
- Add error handling for API calls

**Exit evidence:** AuthService enhanced with user data management and tested.

### Stage 4: Route Guards & Routing
**Goal:** Implement route guards to protect authenticated routes and configure routing.

**Tasks:**
- Create `auth.guard.ts` to check authentication status
- Apply guard to `/projects` and `/chat` routes
- Update routing to include `/login` and `/register` routes
- Configure default route to redirect to login if not authenticated
- Add redirect URL preservation (return to intended page after login)
- Update AppComponent to show user info/logout button in header

**Exit evidence:** Route guards protecting authenticated routes, routing configured.

### Stage 5: Integration & Testing
**Goal:** Integrate auth flow end-to-end and test complete user journey.

**Tasks:**
- Connect login form to AuthService.login()
- Connect register form to AuthService.register()
- Add logout button in header connected to AuthService.logout()
- Update HttpClientService to include JWT in Authorization header
- Test complete flow: register → login → access projects → logout
- Test unauthenticated access redirects to login
- Write E2E tests with Playwright for auth flow
- Update agent-service to use X-User-Subject header from stored user_id

**Exit evidence:** Complete auth flow working, E2E tests passing, agent-service integration verified.

## Skill execution plan

**Request:** Implement user authentication with separate login/register components, route guards, form validation, localStorage JWT storage, and user data persistence across 5 stages.
**Complexity:** moderate
**Assumptions:** Control-plane auth endpoints exist and work; Angular standalone components; existing UI design patterns to follow; localStorage for JWT storage is acceptable.

1. `@skills:repo-scout Explore control-plane auth implementation and Angular structure`
   - Goal: Verify existing auth endpoints, understand Angular routing, and identify UI patterns
   - Exit evidence: Documented control-plane auth handlers, Angular routing structure, and existing component patterns

2. `@skills:go-developer Add /auth/me endpoint to control-plane`
   - Goal: Add endpoint to retrieve current user from JWT token
   - Exit evidence: New handler in internal/handlers/auth.go with /auth/me route returning user data

3. `@skills:angular-developer Create login and register components`
   - Goal: Build LoginPage and RegisterPage with form validation
   - Exit evidence: New login.component.ts and register.component.ts with templates, validation, and styling

4. `@skills:angular-developer Enhance AuthService with user data management`
   - Goal: Add user data storage, getCurrentUser(), and improved token management
   - Exit evidence: Updated auth.service.ts with new methods and localStorage handling

5. `@skills:angular-developer Implement route guards and routing configuration`
   - Goal: Create auth guard, protect routes, and configure login/register routes
   - Exit evidence: New auth.guard.ts, updated app.routes.ts with guards and auth routes

6. `@skills:angular-developer Integrate auth flow and add UI elements`
   - Goal: Connect forms to AuthService, add logout button, update header with user info
   - Exit evidence: Working login/register forms, logout functionality, and user display in header

7. `@skills:angular-developer Update HttpClientService for JWT authorization`
   - Goal: Include JWT token in Authorization header for API requests
   - Exit evidence: Updated http-client.service.ts with token injection

8. `@skills:angular-test-engineer Write unit tests for auth components and service`
   - Goal: Test login/register components, AuthService, and auth guard
   - Exit evidence: Unit tests for auth components and service with good coverage

9. `@skills:angular-test-engineer Write E2E tests for auth flow`
   - Goal: Test complete user journey from register to logout
   - Exit evidence: Playwright E2E tests covering registration, login, protected routes, and logout

10. `@skills:completion-verifier Verify complete auth flow end-to-end`
    - Goal: Verify registration, login, route protection, and agent-service integration
    - Exit evidence: Successful manual test of complete auth flow and automated test results

## Done when
- Users can register via UI and are created in control-plane database
- Users can login via UI and receive JWT token stored in localStorage
- Unauthenticated users are redirected to login when accessing protected routes
- User data (name, email) is stored in localStorage and displayed in UI
- Logout clears localStorage and redirects to login
- JWT token is included in Authorization header for API requests
- agent-service receives user_id via X-User-Subject header from stored token
- Unit and E2E tests pass

# Quality Assurance & Testing Guide

## 1. Test Architecture

The testing suite spans three distinct tiers:

1. **Unit Testing**: Tests domain business logic, password hashing, JWT generation, phone/email normalizations, and condition evaluation.
2. **Integration Testing**: Tests REST API endpoints, session handling, database transactions, and two-layer RBAC permissions.
3. **End-to-End Testing (Playwright)**: Tests full browser journeys covering login, lead assignment, call logging, task completion, and manager reporting.

## 2. Running Test Suites

### Backend Unit & Integration Tests
```bash
cd backend
pytest tests/ -v --cov=app
```

### End-to-End Playwright Tests
```bash
npx playwright test
```

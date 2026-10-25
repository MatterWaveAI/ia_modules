# E2E Tests for IA Modules Showcase App

End-to-end tests using Playwright for the IA Modules Showcase application.

## Overview

These tests validate the full application stack, including:
- **Home page** - Navigation, feature cards, responsiveness
- **Pipeline execution** - Running pipelines, viewing results, error handling
- **Metrics dashboard** - Charts, metric values, time range filters
- **Navigation & routing** - Page transitions, direct URL access
- **API integration** - Backend health checks, endpoint availability

## Quick Start

### 1. Install Dependencies

From the `showcase_app` directory:

```bash
# Install Playwright and browsers
cd tests/e2e
npm install
npx playwright install --with-deps
```

Or from the frontend directory:
```bash
cd frontend
npm run e2e:install
```

### 2. Run Tests

```bash
# Run all tests (headless - default)
npx playwright test

# Run with UI mode
npx playwright test --ui

# Run in headed mode (see browser)
npx playwright test --headed

# Run in debug mode
npx playwright test --debug

# Run specific test file
npx playwright test test-home.spec.js

# Run specific browser
npx playwright test --project=chromium

# Run with custom grep pattern
npx playwright test --grep "navigation"
```

## Test Structure

```
tests/e2e/
├── pages/                  # Page Object Models
│   ├── BasePage.js        # Base page with common methods
│   ├── HomePage.js        # Home page objects
│   ├── PipelinesPage.js   # Pipelines page objects
│   └── MetricsPage.js     # Metrics page objects
├── test-home.spec.js      # Home page tests
├── test-pipelines.spec.js # Pipeline execution tests
├── test-metrics.spec.js   # Metrics dashboard tests
├── test-navigation.spec.js # Navigation & routing tests
└── test-api.spec.js       # API integration tests
```

## Running Tests

### Headless Mode (Default)

Tests run without a visible browser - ideal for CI/CD:

```bash
npx playwright test
```

### Headed Mode

Opens a visible browser window - useful for debugging:

```bash
npx playwright test --headed
```

### UI Mode

Interactive test runner with time travel:

```bash
npx playwright test --ui
```

### Debug Mode

Step through tests with browser DevTools:

```bash
npx playwright test --debug
```

## Test Reports

After running tests, view the HTML report:

```bash
npx playwright show-report
```

This opens a detailed report with:
- Test results (pass/fail)
- Screenshots (on failure)
- Video recordings (on failure)
- Trace viewer for debugging

## CI/CD Integration

Tests automatically run in GitHub Actions on:
- Push to main/master
- Pull requests
- Manual trigger (workflow_dispatch)

### GitHub Actions Workflow

The `showcase-e2e` job in `.github/workflows/test.yml`:
1. Sets up Node.js and Python environments
2. Installs frontend and backend dependencies
3. Starts both backend (FastAPI) and frontend (Vite) servers
4. Runs tests with Chromium
5. Uploads test reports and screenshots as artifacts

### Running Locally with Production-like Setup

```bash
# Terminal 1 - Start backend
cd showcase_app/backend
python main.py

# Terminal 2 - Start frontend
cd showcase_app/frontend
npm run dev

# Terminal 3 - Run tests
cd showcase_app/tests/e2e
npx playwright test
```

## Page Object Model

Tests use the Page Object Model pattern for better maintainability:

```javascript
const { HomePage } = require('./pages/HomePage');

test('example test', async ({ page }) => {
  const homePage = new HomePage(page);
  await homePage.goto();
  await homePage.expectLoaded();
});
```

### Benefits:
- **Single source of truth** for selectors
- **Easy to update** when UI changes
- **Reusable** across multiple tests
- **Clean test code** focused on behavior

## Configuration

See `playwright.config.js` for:
- **Browser configurations** (Chromium, Firefox, WebKit)
- **Base URL** (default: http://localhost:5174)
- **Timeouts** and retry settings
- **Artifacts** (screenshots, videos, traces)
- **Web server** auto-start configuration

## Adding New Tests

1. Create a new test file: `test-<feature>.spec.js`
2. Create a page object if needed: `pages/<Feature>Page.js`
3. Use `test.describe()` to group related tests
4. Use `test.beforeEach()` for setup
5. Use assertions from `@playwright/test`

Example:
```javascript
const { test, expect } = require('@playwright/test');

test.describe('New Feature', () => {
  test('should do something', async ({ page }) => {
    await page.goto('http://localhost:5174/feature');
    await expect(page.getByText('Expected Text')).toBeVisible();
  });
});
```

## Best Practices

1. **Use Page Object Models** - Keep selectors in page objects
2. **Test user behavior** - Focus on what users do, not implementation details
3. **Use meaningful test names** - Describe the scenario being tested
4. **Add screenshots on failure** - Already configured in playwright.config.js
5. **Keep tests independent** - Each test should be able to run in isolation
6. **Use appropriate timeouts** - Pipeline execution may take time
7. **Test across browsers** - Ensure cross-browser compatibility

## Troubleshooting

### Tests fail to connect to backend
- Ensure backend is running on port 5555
- Check `.env` file in backend directory
- Verify database is initialized

### Tests timeout
- Increase timeout in test: `await expect(element).toBeVisible({ timeout: 30000 })`
- Check if servers are starting properly
- Verify network requests in headed mode

### Flaky tests
- Add explicit waits: `await page.waitForLoadState('networkidle')`
- Use `retries: 2` in CI (already configured)
- Check for race conditions in the application

## Tags

Use tags to categorize tests:

```javascript
test('should load @smoke', async ({ page }) => { ... });
```

Run only smoke tests:
```bash
npx playwright test --grep @smoke
```

## Resources

- [Playwright Documentation](https://playwright.dev)
- [Playwright Test](https://playwright.dev/docs/intro)
- [Page Object Model](https://playwright.dev/docs/pom)
- [Test Fixtures](https://playwright.dev/docs/test-fixtures)
- [Assertions](https://playwright.dev/docs/test-assertions)

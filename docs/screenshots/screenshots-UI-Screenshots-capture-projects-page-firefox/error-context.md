# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: screenshots.spec.ts >> UI Screenshots >> capture projects page
- Location: tests/e2e/screenshots.spec.ts:57:7

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: page.fill: Test timeout of 30000ms exceeded.
Call log:
  - waiting for locator('#email')

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - banner [ref=e4]:
    - generic [ref=e5]:
      - heading "Agentic Engineering Platform" [level=1] [ref=e6]
      - generic [ref=e7]:
        - generic [ref=e8]: Test User
        - button "Logout" [ref=e9] [cursor=pointer]
  - generic [ref=e11]:
    - banner [ref=e12]:
      - heading "Agentic Engineering Platform" [level=1] [ref=e13]
      - paragraph [ref=e14]: AI-powered software development automation
    - button "+ New Project" [ref=e16] [cursor=pointer]
    - paragraph [ref=e18]: Loading projects...
    - generic [ref=e19]:
      - generic [ref=e20]: 🚀
      - heading "No projects yet" [level=2] [ref=e21]
      - paragraph [ref=e22]: Create your first project to start building with AI agents
      - button "Create Project" [ref=e23] [cursor=pointer]
```

# Test source

```ts
  1   | import { test, expect } from '@playwright/test';
  2   | 
  3   | // Generate random user credentials
  4   | const randomEmail = `test-${Math.random().toString(36).substring(7)}@example.com`;
  5   | const randomPassword = 'TestPassword123!';
  6   | 
  7   | // Helper function to register and login
  8   | async function registerAndLogin(page: any) {
  9   |   // Register new user
  10  |   await page.goto('/register');
  11  |   await page.waitForLoadState('networkidle');
  12  |   
  13  |   await page.fill('#name', 'Test User');
  14  |   await page.fill('#email', randomEmail);
  15  |   await page.fill('#password', randomPassword);
  16  |   await page.fill('#confirmPassword', randomPassword);
  17  |   
  18  |   await page.click('button[type="submit"]');
  19  |   await page.waitForLoadState('networkidle');
  20  |   await page.waitForTimeout(2000); // Wait for registration and redirect
  21  |   
  22  |   // Check if registration succeeded by checking current URL
  23  |   const currentUrl = page.url();
  24  |   console.log('After registration, current URL:', currentUrl);
  25  |   
  26  |   // If still on register page, try login directly
  27  |   if (currentUrl.includes('/register')) {
  28  |     console.log('Registration may have failed, trying login directly');
  29  |     await page.goto('/login');
  30  |     await page.waitForLoadState('networkidle');
  31  |   }
  32  |   
  33  |   // Login with the registered user
> 34  |   await page.fill('#email', randomEmail);
      |              ^ Error: page.fill: Test timeout of 30000ms exceeded.
  35  |   await page.fill('#password', randomPassword);
  36  |   
  37  |   await page.click('button[type="submit"]');
  38  |   await page.waitForLoadState('networkidle');
  39  |   await page.waitForTimeout(2000); // Wait for login and redirect
  40  |   
  41  |   // Verify we're logged in by checking URL
  42  |   const loginUrl = page.url();
  43  |   console.log('After login, current URL:', loginUrl);
  44  |   
  45  |   // If still on login page, the login failed
  46  |   if (loginUrl.includes('/login')) {
  47  |     console.log('Login failed, checking for error messages');
  48  |     const errorElement = await page.locator('.error-message').first();
  49  |     if (await errorElement.isVisible()) {
  50  |       const errorText = await errorElement.textContent();
  51  |       console.log('Error message:', errorText);
  52  |     }
  53  |   }
  54  | }
  55  | 
  56  | test.describe('UI Screenshots', () => {
  57  |   test('capture projects page', async ({ page }) => {
  58  |     await registerAndLogin(page);
  59  |     
  60  |     // Navigate to projects
  61  |     await page.goto('/projects');
  62  |     await page.waitForLoadState('networkidle');
  63  |     await page.waitForTimeout(2000); // Wait for content to render
  64  |     await page.screenshot({ 
  65  |       path: '../../docs/screenshots/projects.png',
  66  |       fullPage: true 
  67  |     });
  68  |   });
  69  | 
  70  |   test('capture chat page', async ({ page }) => {
  71  |     await registerAndLogin(page);
  72  |     
  73  |     // Navigate to chat
  74  |     await page.goto('/chat');
  75  |     await page.waitForLoadState('networkidle');
  76  |     await page.waitForTimeout(2000); // Wait for content to render
  77  |     
  78  |     // Click create project button if it exists
  79  |     try {
  80  |       const createProjectButton = page.locator('button:has-text("Create Project")');
  81  |       if (await createProjectButton.isVisible({ timeout: 2000 })) {
  82  |         await createProjectButton.click();
  83  |         await page.waitForTimeout(1000);
  84  |         
  85  |         // Click skip GitHub option if it exists
  86  |         try {
  87  |           const skipGithubButton = page.locator('button:has-text("Skip GitHub")');
  88  |           if (await skipGithubButton.isVisible({ timeout: 2000 })) {
  89  |             await skipGithubButton.click();
  90  |             await page.waitForTimeout(1000);
  91  |           }
  92  |         } catch (e) {
  93  |           console.log('Skip GitHub button not found or not visible');
  94  |         }
  95  |       }
  96  |     } catch (e) {
  97  |       console.log('Create Project button not found or not visible');
  98  |     }
  99  |     
  100 |     await page.waitForTimeout(2000); // Wait for content to render
  101 |     await page.screenshot({ 
  102 |       path: '../../docs/screenshots/chat.png',
  103 |       fullPage: true 
  104 |     });
  105 |   });
  106 | });
  107 | 
```
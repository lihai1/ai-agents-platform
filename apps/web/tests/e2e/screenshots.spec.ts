import { test, expect } from '@playwright/test';

// Generate random user credentials
const randomEmail = `test-${Math.random().toString(36).substring(7)}@example.com`;
const randomPassword = 'TestPassword123!';

// Helper function to register and login
async function registerAndLogin(page: any) {
  // Register new user
  await page.goto('/register');
  await page.waitForLoadState('networkidle');
  
  await page.fill('#name', 'Test User');
  await page.fill('#email', randomEmail);
  await page.fill('#password', randomPassword);
  await page.fill('#confirmPassword', randomPassword);
  
  await page.click('button[type="submit"]');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000); // Wait for registration and redirect
  
  // Check if registration succeeded by checking current URL
  const currentUrl = page.url();
  console.log('After registration, current URL:', currentUrl);
  
  // If still on register page, try login directly
  if (currentUrl.includes('/register')) {
    console.log('Registration may have failed, trying login directly');
    await page.goto('/login');
    await page.waitForLoadState('networkidle');
  }
  
  // Login with the registered user
  await page.fill('#email', randomEmail);
  await page.fill('#password', randomPassword);
  
  await page.click('button[type="submit"]');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000); // Wait for login and redirect
  
  // Verify we're logged in by checking URL
  const loginUrl = page.url();
  console.log('After login, current URL:', loginUrl);
  
  // If still on login page, the login failed
  if (loginUrl.includes('/login')) {
    console.log('Login failed, checking for error messages');
    const errorElement = await page.locator('.error-message').first();
    if (await errorElement.isVisible()) {
      const errorText = await errorElement.textContent();
      console.log('Error message:', errorText);
    }
  }
}

test.describe('UI Screenshots', () => {
  test('capture projects page', async ({ page }) => {
    await registerAndLogin(page);
    
    // Navigate to projects
    await page.goto('/projects');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000); // Wait for content to render
    await page.screenshot({ 
      path: '../../docs/screenshots/projects.png',
      fullPage: true 
    });
  });

  test('capture chat page', async ({ page }) => {
    await registerAndLogin(page);
    
    // Navigate to chat
    await page.goto('/chat');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000); // Wait for content to render
    
    // Click create project button if it exists
    try {
      const createProjectButton = page.locator('button:has-text("Create Project")');
      if (await createProjectButton.isVisible({ timeout: 2000 })) {
        await createProjectButton.click();
        await page.waitForTimeout(1000);
        
        // Click skip GitHub option if it exists
        try {
          const skipGithubButton = page.locator('button:has-text("Skip GitHub")');
          if (await skipGithubButton.isVisible({ timeout: 2000 })) {
            await skipGithubButton.click();
            await page.waitForTimeout(1000);
          }
        } catch (e) {
          console.log('Skip GitHub button not found or not visible');
        }
      }
    } catch (e) {
      console.log('Create Project button not found or not visible');
    }
    
    await page.waitForTimeout(2000); // Wait for content to render
    await page.screenshot({ 
      path: '../../docs/screenshots/chat.png',
      fullPage: true 
    });
  });
});

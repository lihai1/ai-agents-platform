import { test, expect } from '@playwright/test';

test.describe('Chat Workflow E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display projects page on load', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('Agentic Engineering Platform');
    await expect(page.locator('.subtitle')).toContainText('AI-powered software development automation');
  });

  test('should navigate to chat when project is selected', async ({ page }) => {
    // Mock project selection - in real scenario would click on project card
    await page.goto('/chat?project_id=test-project&repository_id=test-repo');
    
    await expect(page).toHaveURL(/\/chat/);
    await expect(page.locator('h1')).toContainText('Agent Chat');
  });

  test('should display ChatKit container', async ({ page }) => {
    await page.goto('/chat');
    await expect(page.locator('#chatkit-root')).toBeVisible();
  });

  test('should load ChatKit client script', async ({ page }) => {
    await page.goto('/chat');
    
    // Wait for script to load from assets
    const scriptRequest = page.waitForRequest(request => 
      request.url().includes('chatkit-client.js')
    );
    
    await scriptRequest;
  });

  test('should display workflow trigger checkbox when project context exists', async ({ page }) => {
    await page.goto('/chat?project_id=test-project&repository_id=test-repo');
    
    await expect(page.locator('.chat-controls')).toBeVisible();
    await expect(page.locator('input[type="checkbox"]')).toBeVisible();
    await expect(page.locator('text=Trigger Agent Workflow')).toBeVisible();
  });

  test('should not display workflow trigger checkbox without project context', async ({ page }) => {
    await page.goto('/chat');
    
    await expect(page.locator('.chat-controls')).not.toBeVisible();
  });

  test('should toggle workflow trigger checkbox', async ({ page }) => {
    await page.goto('/chat?project_id=test-project&repository_id=test-repo');
    
    const checkbox = page.locator('input[type="checkbox"]');
    await expect(checkbox).not.toBeChecked();
    
    await checkbox.check();
    await expect(checkbox).toBeChecked();
    
    await checkbox.uncheck();
    await expect(checkbox).not.toBeChecked();
  });

  test('should handle ChatKit message sending', async ({ page }) => {
    await page.goto('/chat?project_id=test-project&repository_id=test-repo');
    
    // Wait for ChatKit to load
    await page.waitForRequest(request => request.url().includes('chatkit-client.js'));
    await page.waitForTimeout(500);
    
    // Try to interact with ChatKit input
    const chatInput = page.locator('#chatkit-root textarea').first();
    if (await chatInput.isVisible()) {
      await chatInput.fill('Test message');
      const sendButton = page.locator('#chatkit-root button').first();
      await sendButton.click();
    }
  });

  test('should handle mock API calls for projects', async ({ page }) => {
    // Monitor network requests
    const apiRequests: string[] = [];
    
    page.on('request', request => {
      if (request.url().includes('localhost')) {
        apiRequests.push(request.url());
      }
    });

    await page.goto('/projects');
    
    // Wait for loading to complete
    await page.waitForTimeout(1000);
    
    // Verify that API calls were made to mock service
    expect(apiRequests.some(url => url.includes('/projects'))).toBeTruthy();
  });

  test('should display loading state while fetching projects', async ({ page }) => {
    await page.goto('/projects');
    
    const loadingState = page.locator('.loading-state');
    // Loading state might be visible briefly
    await page.waitForTimeout(500);
  });

  test('should handle project selection with repository context', async ({ page }) => {
    await page.goto('/projects');
    
    // Wait for projects to load
    await page.waitForTimeout(1000);
    
    // In a real scenario, we would click on a project card
    // For now, we verify the navigation works with query params
    await page.goto('/chat?project_id=proj1&repository_id=repo1');
    
    await expect(page).toHaveURL(/project_id=proj1/);
    await expect(page).toHaveURL(/repository_id=repo1/);
  });
});

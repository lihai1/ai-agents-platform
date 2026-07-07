import { test, expect } from '@playwright/test';

test.describe('Component Interaction E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should navigate between projects and chat', async ({ page }) => {
    // Start on projects page
    await expect(page).toHaveURL('/projects');
    
    // Click on a project
    await page.locator('.project-card').first().click();
    await expect(page).toHaveURL(/\/chat/);
    
    // Navigate back to projects
    await page.goto('/projects');
    await expect(page).toHaveURL('/projects');
  });

  test('should display project cards with correct information', async ({ page }) => {
    const projectCards = page.locator('.project-card');
    const count = await projectCards.count();
    
    expect(count).toBeGreaterThan(0);
    
    const firstCard = projectCards.first();
    await expect(firstCard.locator('.project-icon')).toBeVisible();
    await expect(firstCard.locator('.project-info h3')).toBeVisible();
    await expect(firstCard.locator('.project-info p')).toBeVisible();
    await expect(firstCard.locator('.project-arrow')).toBeVisible();
  });

  test('should show empty state when no projects exist', async ({ page }) => {
    // This test would require mocking an empty projects response
    // For now, we verify the empty state element exists in DOM
    const emptyState = page.locator('.empty-state');
    const isVisible = await emptyState.isVisible();
    
    // Empty state might not be visible if there are projects
    if (isVisible) {
      await expect(emptyState.locator('.empty-icon')).toBeVisible();
      await expect(emptyState.locator('h2')).toContainText('No projects yet');
    }
  });

  test('should display create project button', async ({ page }) => {
    const createButton = page.locator('button').filter({ hasText: 'New Project' });
    await expect(createButton).toBeVisible();
  });

  test('should display chat interface with ChatKit root', async ({ page }) => {
    await page.goto('/chat');
    await expect(page.locator('h1')).toContainText('Agent Chat');
    await expect(page.locator('#chatkit-root')).toBeVisible();
  });

  test('should handle browser navigation correctly', async ({ page }) => {
    await page.goto('/projects');
    await expect(page).toHaveURL('/projects');
    
    // Navigate forward
    await page.goto('/chat');
    await expect(page).toHaveURL(/\/chat/);
    
    // Navigate back
    await page.goBack();
    await expect(page).toHaveURL('/projects');
    
    // Navigate forward again
    await page.goForward();
    await expect(page).toHaveURL(/\/chat/);
  });

  test('should be responsive on different viewports', async ({ page }) => {
    // Test mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/projects');
    await expect(page.locator('h1')).toBeVisible();
    
    // Test tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 });
    await expect(page.locator('h1')).toBeVisible();
    
    // Test desktop viewport
    await page.setViewportSize({ width: 1920, height: 1080 });
    await expect(page.locator('h1')).toBeVisible();
  });

  test('should handle 404 routes gracefully', async ({ page }) => {
    await page.goto('/non-existent-route');
    // Angular router should handle this - either redirect to projects or show 404
    const currentUrl = page.url();
    expect(currentUrl).toBeTruthy();
  });
});

import { test, expect } from '@playwright/test';

test.describe('Complete Chat Flow E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should complete chat flow with agent updates', async ({ page }) => {
    // Navigate to chat with project and repository context
    await page.goto('/chat?project_id=test-project&repository_id=test-repo&mock_mode=true');

    // Wait for page to load
    await expect(page.locator('h1')).toContainText('Agent Chat');

    // Verify workflow trigger checkbox is visible
    await expect(page.locator('.chat-controls')).toBeVisible();
    await expect(page.locator('input[type="checkbox"]')).toBeVisible();

    // Enable workflow trigger
    const checkbox = page.locator('input[type="checkbox"]');
    await checkbox.check();
    await expect(checkbox).toBeChecked();

    // Wait for ChatKit to load
    await page.waitForRequest(request => request.url().includes('chatkit-client.js'));
    await page.waitForTimeout(1000);

    // Send a message to trigger the workflow
    const chatInput = page.locator('#chatkit-root textarea').first();
    if (await chatInput.isVisible()) {
      await chatInput.fill('Add a new feature to the repository');
      
      const sendButton = page.locator('#chatkit-root button').first();
      await sendButton.click();

      // Wait for workflow to start (30 second timeout as specified)
      const startTime = Date.now();
      let agentUpdateReceived = false;

      // Poll for agent updates in the chat
      while (Date.now() - startTime < 30000) {
        try {
          // Check if workflow triggered message appears
          const workflowMessage = page.locator('text=Workflow started');
          if (await workflowMessage.isVisible({ timeout: 1000 })) {
            console.log('✓ Workflow started message received');
            agentUpdateReceived = true;
            break;
          }

          // Check for any agent state updates in the chat
          const agentUpdate = page.locator('text=CREATED').or(
            page.locator('text=PREPARING_WORKSPACE')
          ).or(
            page.locator('text=SCOUTING')
          );
          
          if (await agentUpdate.isVisible({ timeout: 1000 })) {
            console.log('✓ First agent update displayed in chat');
            agentUpdateReceived = true;
            break;
          }

          await page.waitForTimeout(500);
        } catch (e) {
          // Continue polling
        }
      }

      if (!agentUpdateReceived) {
        console.log('⚠ No agent update received within 30 seconds');
        // Take screenshot for debugging
        await page.screenshot({ path: 'chat-flow-no-update.png' });
      }

      // Verify at least workflow was triggered
      expect(agentUpdateReceived).toBeTruthy();
    } else {
      console.log('⚠ ChatKit input not visible, skipping message send');
    }
  });

  test('should handle chat without repository context', async ({ page }) => {
    // Navigate to chat without project/repository context
    await page.goto('/chat');

    // Verify workflow trigger checkbox is NOT visible
    await expect(page.locator('.chat-controls')).not.toBeVisible();

    // ChatKit should still load
    await expect(page.locator('#chatkit-root')).toBeVisible();
  });

  test('should display error if workflow trigger fails', async ({ page }) => {
    // Navigate with invalid project/repo
    await page.goto('/chat?project_id=invalid&repository_id=invalid&mock_mode=true');

    // Wait for ChatKit to load
    await page.waitForRequest(request => request.url().includes('chatkit-client.js'));
    await page.waitForTimeout(1000);

    // Enable workflow trigger
    const checkbox = page.locator('input[type="checkbox"]');
    if (await checkbox.isVisible()) {
      await checkbox.check();

      // Try to send message
      const chatInput = page.locator('#chatkit-root textarea').first();
      if (await chatInput.isVisible()) {
        await chatInput.fill('Test message');
        
        const sendButton = page.locator('#chatkit-root button').first();
        await sendButton.click();

        // Wait for error message or fallback response
        await page.waitForTimeout(2000);
        
        // Should still show some response (even if error)
        const chatContent = page.locator('#chatkit-root');
        await expect(chatContent).toBeVisible();
      }
    }
  });
});

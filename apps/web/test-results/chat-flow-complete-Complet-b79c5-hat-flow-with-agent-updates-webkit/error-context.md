# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: chat-flow-complete.spec.ts >> Complete Chat Flow E2E >> should complete chat flow with agent updates
- Location: tests/e2e/chat-flow-complete.spec.ts:8:7

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: page.waitForRequest: Test timeout of 30000ms exceeded.
```

# Page snapshot

```yaml
- generic [ref=e5]:
  - heading "Agent Chat" [level=1] [ref=e6]
  - generic [ref=e8] [cursor=pointer]:
    - checkbox "Trigger Agent Workflow" [checked] [ref=e9]
    - text: Trigger Agent Workflow
```

# Test source

```ts
  1   | import { test, expect } from '@playwright/test';
  2   | 
  3   | test.describe('Complete Chat Flow E2E', () => {
  4   |   test.beforeEach(async ({ page }) => {
  5   |     await page.goto('/');
  6   |   });
  7   | 
  8   |   test('should complete chat flow with agent updates', async ({ page }) => {
  9   |     // Navigate to chat with project and repository context
  10  |     await page.goto('/chat?project_id=test-project&repository_id=test-repo&mock_mode=true');
  11  | 
  12  |     // Wait for page to load
  13  |     await expect(page.locator('h1')).toContainText('Agent Chat');
  14  | 
  15  |     // Verify workflow trigger checkbox is visible
  16  |     await expect(page.locator('.chat-controls')).toBeVisible();
  17  |     await expect(page.locator('input[type="checkbox"]')).toBeVisible();
  18  | 
  19  |     // Enable workflow trigger
  20  |     const checkbox = page.locator('input[type="checkbox"]');
  21  |     await checkbox.check();
  22  |     await expect(checkbox).toBeChecked();
  23  | 
  24  |     // Wait for ChatKit to load
> 25  |     await page.waitForRequest(request => request.url().includes('chatkit-client.js'));
      |                ^ Error: page.waitForRequest: Test timeout of 30000ms exceeded.
  26  |     await page.waitForTimeout(1000);
  27  | 
  28  |     // Send a message to trigger the workflow
  29  |     const chatInput = page.locator('#chatkit-root textarea').first();
  30  |     if (await chatInput.isVisible()) {
  31  |       await chatInput.fill('Add a new feature to the repository');
  32  |       
  33  |       const sendButton = page.locator('#chatkit-root button').first();
  34  |       await sendButton.click();
  35  | 
  36  |       // Wait for workflow to start (30 second timeout as specified)
  37  |       const startTime = Date.now();
  38  |       let agentUpdateReceived = false;
  39  | 
  40  |       // Poll for agent updates in the chat
  41  |       while (Date.now() - startTime < 30000) {
  42  |         try {
  43  |           // Check if workflow triggered message appears
  44  |           const workflowMessage = page.locator('text=Workflow started');
  45  |           if (await workflowMessage.isVisible({ timeout: 1000 })) {
  46  |             console.log('✓ Workflow started message received');
  47  |             agentUpdateReceived = true;
  48  |             break;
  49  |           }
  50  | 
  51  |           // Check for any agent state updates in the chat
  52  |           const agentUpdate = page.locator('text=CREATED').or(
  53  |             page.locator('text=PREPARING_WORKSPACE')
  54  |           ).or(
  55  |             page.locator('text=SCOUTING')
  56  |           );
  57  |           
  58  |           if (await agentUpdate.isVisible({ timeout: 1000 })) {
  59  |             console.log('✓ First agent update displayed in chat');
  60  |             agentUpdateReceived = true;
  61  |             break;
  62  |           }
  63  | 
  64  |           await page.waitForTimeout(500);
  65  |         } catch (e) {
  66  |           // Continue polling
  67  |         }
  68  |       }
  69  | 
  70  |       if (!agentUpdateReceived) {
  71  |         console.log('⚠ No agent update received within 30 seconds');
  72  |         // Take screenshot for debugging
  73  |         await page.screenshot({ path: 'chat-flow-no-update.png' });
  74  |       }
  75  | 
  76  |       // Verify at least workflow was triggered
  77  |       expect(agentUpdateReceived).toBeTruthy();
  78  |     } else {
  79  |       console.log('⚠ ChatKit input not visible, skipping message send');
  80  |     }
  81  |   });
  82  | 
  83  |   test('should handle chat without repository context', async ({ page }) => {
  84  |     // Navigate to chat without project/repository context
  85  |     await page.goto('/chat');
  86  | 
  87  |     // Verify workflow trigger checkbox is NOT visible
  88  |     await expect(page.locator('.chat-controls')).not.toBeVisible();
  89  | 
  90  |     // ChatKit should still load
  91  |     await expect(page.locator('#chatkit-root')).toBeVisible();
  92  |   });
  93  | 
  94  |   test('should display error if workflow trigger fails', async ({ page }) => {
  95  |     // Navigate with invalid project/repo
  96  |     await page.goto('/chat?project_id=invalid&repository_id=invalid&mock_mode=true');
  97  | 
  98  |     // Wait for ChatKit to load
  99  |     await page.waitForRequest(request => request.url().includes('chatkit-client.js'));
  100 |     await page.waitForTimeout(1000);
  101 | 
  102 |     // Enable workflow trigger
  103 |     const checkbox = page.locator('input[type="checkbox"]');
  104 |     if (await checkbox.isVisible()) {
  105 |       await checkbox.check();
  106 | 
  107 |       // Try to send message
  108 |       const chatInput = page.locator('#chatkit-root textarea').first();
  109 |       if (await chatInput.isVisible()) {
  110 |         await chatInput.fill('Test message');
  111 |         
  112 |         const sendButton = page.locator('#chatkit-root button').first();
  113 |         await sendButton.click();
  114 | 
  115 |         // Wait for error message or fallback response
  116 |         await page.waitForTimeout(2000);
  117 |         
  118 |         // Should still show some response (even if error)
  119 |         const chatContent = page.locator('#chatkit-root');
  120 |         await expect(chatContent).toBeVisible();
  121 |       }
  122 |     }
  123 |   });
  124 | });
  125 | 
```
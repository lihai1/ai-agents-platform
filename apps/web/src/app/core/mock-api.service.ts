import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders, HttpErrorResponse, HttpEvent, HttpHandler, HttpInterceptor, HttpRequest } from '@angular/common/http';
import { Observable, of, throwError } from 'rxjs';
import { delay, tap } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class MockApiService implements HttpInterceptor {
  constructor(private http: HttpClient) {}

  intercept(request: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    // Mock interceptor disabled - using real backend
    return next.handle(request);
  }

  private handleMockRequest(request: HttpRequest<unknown>): Observable<HttpEvent<unknown>> {
    const url = request.url;
    const method = request.method;

    // Mock auth endpoints
    if (url.includes('/auth/login') && method === 'POST') {
      return of(this.createResponse({ token: 'mock-jwt-token' })).pipe(delay(100));
    }

    if (url.includes('/auth/register') && method === 'POST') {
      return of(this.createResponse({ id: '1', email: 'test@example.com', name: 'Test User' })).pipe(delay(100));
    }

    // Mock projects endpoints
    if (url.includes('/projects') && method === 'GET') {
      return of(this.createResponse([
        { id: '1', name: 'Sample Project', description: 'A demo project' },
        { id: '2', name: 'Test Project', description: 'A test project' }
      ])).pipe(delay(100));
    }

    if (url.includes('/projects') && method === 'POST') {
      return of(this.createResponse({ id: '3', name: 'New Project', description: 'New description' })).pipe(delay(100));
    }

    // Mock repositories endpoints
    if (url.includes('/repositories') && method === 'GET') {
      return of(this.createResponse([
        { id: '1', name: 'sample-repo', url: 'https://github.com/test/sample' }
      ])).pipe(delay(100));
    }

    // Mock ChatKit endpoints
    if (url.includes('/api/chatkit/') && method === 'POST') {
      return this.createMockChatResponse();
    }

    if (url.includes('/api/chatkit/threads') && method === 'GET') {
      return of(this.createResponse({
        thread: { id: 'thread-1', title: 'Test Thread', created_at: new Date().toISOString() },
        items: [
          { id: '1', role: 'user', content: 'Hello', created_at: new Date().toISOString() },
          { id: '2', role: 'assistant', content: 'Hi there!', created_at: new Date().toISOString() }
        ]
      })).pipe(delay(100));
    }

    // Mock agent run endpoints
    if (url.includes('/api/agent/runs') && method === 'POST') {
      return of(this.createResponse({
        id: 'run-1',
        status: 'created',
        created_at: new Date().toISOString()
      })).pipe(delay(100));
    }

    if (url.includes('/api/agent/runs/') && method === 'GET') {
      return of(this.createResponse({
        id: 'run-1',
        status: 'completed',
        created_at: new Date().toISOString(),
        completed_at: new Date().toISOString()
      })).pipe(delay(100));
    }

    // Default: pass through
    return throwError(() => new HttpErrorResponse({ status: 404, statusText: 'Not Found' }));
  }

  private createMockChatResponse(): Observable<HttpEvent<unknown>> {
    return new Observable<HttpEvent<unknown>>(subscriber => {
      const responses = [
        { content: 'Hello', thread_id: 'thread-1' },
        { content: ' there!', thread_id: 'thread-1' },
        { content: ' How can I help you today?', thread_id: 'thread-1' }
      ];

      let index = 0;
      const interval = setInterval(() => {
        if (index < responses.length) {
          subscriber.next(this.createResponse(responses[index]));
          index++;
        } else {
          clearInterval(interval);
          subscriber.complete();
        }
      }, 100);
    });
  }

  private createResponse(data: any): any {
    return {
      body: data,
      status: 200,
      statusText: 'OK',
      headers: new HttpHeaders({ 'Content-Type': 'application/json' })
    };
  }
}

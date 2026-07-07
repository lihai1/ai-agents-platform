import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class HttpClientService {
  private apiUrl = '/api/v1'; // Use relative path for Angular proxy
  private agentApiUrl = 'http://localhost:8000';

  constructor(private http: HttpClient) {}

  private getHeaders(): HttpHeaders {
    const token = localStorage.getItem('jwt_token');
    return new HttpHeaders({
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    });
  }

  get<T>(url: string, useAgentApi = false): Observable<T> {
    const baseUrl = useAgentApi ? this.agentApiUrl : this.apiUrl;
    return this.http.get<T>(`${baseUrl}${url}`, { headers: this.getHeaders() })
      .pipe(catchError(this.handleError));
  }

  post<T>(url: string, body: any, useAgentApi = false): Observable<T> {
    const baseUrl = useAgentApi ? this.agentApiUrl : this.apiUrl;
    return this.http.post<T>(`${baseUrl}${url}`, body, { headers: this.getHeaders() })
      .pipe(catchError(this.handleError));
  }

  private handleError(error: HttpErrorResponse) {
    if (error.error instanceof ErrorEvent) {
      console.error('An error occurred:', error.error.message);
    } else {
      console.error(`Backend returned code ${error.status}, body was:`, error.error);
    }
    return throwError(() => 'Something bad happened; please try again later.');
  }
}

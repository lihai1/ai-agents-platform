import { Injectable } from '@angular/core';
import { HttpClientService } from '../core/http-client.service';
import { Observable } from 'rxjs';

interface LoginResponse {
  token: string;
}

interface User {
  id: string;
  email: string;
  name: string;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  constructor(private http: HttpClientService) {}

  login(email: string, password: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>('/auth/login', { email, password });
  }

  register(email: string, password: string, name: string): Observable<User> {
    return this.http.post<User>('/auth/register', { email, password, name });
  }

  logout(): void {
    localStorage.removeItem('jwt_token');
  }

  isAuthenticated(): boolean {
    return !!localStorage.getItem('jwt_token');
  }

  getToken(): string | null {
    return localStorage.getItem('jwt_token');
  }
}

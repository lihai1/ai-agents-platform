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
    return this.http.post<LoginResponse>('/api/auth/login', { email, password });
  }

  register(email: string, password: string, name: string): Observable<User> {
    return this.http.post<User>('/api/auth/register', { email, password, name });
  }

  getCurrentUser(): Observable<User> {
    return this.http.get<User>('/api/auth/me');
  }

  logout(): void {
    localStorage.removeItem('jwt_token');
    localStorage.removeItem('user');
  }

  isAuthenticated(): boolean {
    return !!localStorage.getItem('jwt_token');
  }

  getToken(): string | null {
    return localStorage.getItem('jwt_token');
  }

  setToken(token: string): void {
    localStorage.setItem('jwt_token', token);
  }

  getUser(): User | null {
    const userStr = localStorage.getItem('user');
    return userStr ? JSON.parse(userStr) : null;
  }

  setUser(user: User): void {
    localStorage.setItem('user', JSON.stringify(user));
  }
}

import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface OllamaModel {
  name: string;
  modified_at: string;
  size: number;
}

@Injectable({
  providedIn: 'root'
})
export class OllamaService {
  private controlPlaneUrl = 'http://localhost:8080/api/v1/ollama/models';

  constructor(private http: HttpClient) {}

  getModels(): Observable<OllamaModel[]> {
    return this.http.get<OllamaModel[]>(this.controlPlaneUrl);
  }
}

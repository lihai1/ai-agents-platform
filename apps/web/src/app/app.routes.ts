import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: '/projects', pathMatch: 'full' },
  { path: 'projects', loadComponent: () => import('./projects/projects.component').then(m => m.ProjectsComponent) },
  { path: 'chat', loadComponent: () => import('./chat/chat.component').then(m => m.ChatComponent) },
];

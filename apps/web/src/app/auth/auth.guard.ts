import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  console.log('authGuard called for route:', state.url);
  console.log('isAuthenticated:', authService.isAuthenticated());
  console.log('localStorage jwt_token:', localStorage.getItem('jwt_token'));

  if (authService.isAuthenticated()) {
    return true;
  }

  console.log('Redirecting to login with returnUrl:', state.url);
  // Store the attempted URL for redirect after login
  router.navigate(['/login'], { queryParams: { returnUrl: state.url } });
  return false;
};

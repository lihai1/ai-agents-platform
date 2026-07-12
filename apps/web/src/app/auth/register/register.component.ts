import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { AuthService } from '../auth.service';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, RouterModule],
  template: `
    <div class="auth-container">
      <div class="auth-card">
        <h2>Register</h2>
        <form [formGroup]="registerForm" (ngSubmit)="onSubmit()">
          <div class="form-group">
            <label for="name">Name</label>
            <input
              id="name"
              type="text"
              formControlName="name"
              placeholder="Enter your name"
              required
            />
            @if (registerForm.get('name')?.touched && registerForm.get('name')?.invalid) {
              <div class="error">
                @if (registerForm.get('name')?.errors?.['required']) {
                  <span>Name is required</span>
                }
              </div>
            }
          </div>

          <div class="form-group">
            <label for="email">Email</label>
            <input
              id="email"
              type="email"
              formControlName="email"
              placeholder="Enter your email"
              required
            />
            @if (registerForm.get('email')?.touched && registerForm.get('email')?.invalid) {
              <div class="error">
                @if (registerForm.get('email')?.errors?.['required']) {
                  <span>Email is required</span>
                }
                @if (registerForm.get('email')?.errors?.['email']) {
                  <span>Invalid email format</span>
                }
              </div>
            }
          </div>

          <div class="form-group">
            <label for="password">Password</label>
            <input
              id="password"
              type="password"
              formControlName="password"
              placeholder="Enter your password"
              required
            />
            @if (registerForm.get('password')?.touched && registerForm.get('password')?.invalid) {
              <div class="error">
                @if (registerForm.get('password')?.errors?.['required']) {
                  <span>Password is required</span>
                }
                @if (registerForm.get('password')?.errors?.['minlength']) {
                  <span>Password must be at least 8 characters</span>
                }
              </div>
            }
          </div>

          <div class="form-group">
            <label for="confirmPassword">Confirm Password</label>
            <input
              id="confirmPassword"
              type="password"
              formControlName="confirmPassword"
              placeholder="Confirm your password"
              required
            />
            @if (registerForm.get('confirmPassword')?.touched && registerForm.get('confirmPassword')?.invalid) {
              <div class="error">
                @if (registerForm.get('confirmPassword')?.errors?.['required']) {
                  <span>Please confirm your password</span>
                }
                @if (registerForm.get('confirmPassword')?.errors?.['mismatch']) {
                  <span>Passwords do not match</span>
                }
              </div>
            }
          </div>

          @if (errorMessage) {
            <div class="error-message">
              {{ errorMessage }}
            </div>
          }

          <button type="submit" [disabled]="registerForm.invalid || isLoading" (click)="onButtonClick()">
            {{ isLoading ? 'Registering...' : 'Register' }}
          </button>
        </form>

        <div class="auth-footer">
          <p>Already have an account? <a routerLink="/login">Login</a></p>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .auth-container {
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }

    .auth-card {
      background: white;
      padding: 2rem;
      border-radius: 8px;
      box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
      width: 100%;
      max-width: 400px;
    }

    h2 {
      margin: 0 0 1.5rem 0;
      color: #333;
      text-align: center;
    }

    .form-group {
      margin-bottom: 1rem;
    }

    label {
      display: block;
      margin-bottom: 0.5rem;
      color: #555;
      font-weight: 500;
    }

    input {
      width: 100%;
      padding: 0.75rem;
      border: 1px solid #ddd;
      border-radius: 4px;
      font-size: 1rem;
      box-sizing: border-box;
    }

    input:focus {
      outline: none;
      border-color: #667eea;
    }

    .error {
      color: #e53e3e;
      font-size: 0.875rem;
      margin-top: 0.25rem;
    }

    .error-message {
      color: #e53e3e;
      margin-bottom: 1rem;
      text-align: center;
    }

    button {
      width: 100%;
      padding: 0.75rem;
      background: #667eea;
      color: white;
      border: none;
      border-radius: 4px;
      font-size: 1rem;
      cursor: pointer;
      transition: background 0.2s;
    }

    button:hover:not(:disabled) {
      background: #5568d3;
    }

    button:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }

    .auth-footer {
      margin-top: 1.5rem;
      text-align: center;
    }

    .auth-footer p {
      color: #666;
      margin: 0;
    }

    .auth-footer a {
      color: #667eea;
      text-decoration: none;
      font-weight: 500;
    }

    .auth-footer a:hover {
      text-decoration: underline;
    }
  `]
})
export class RegisterComponent {
  registerForm: FormGroup;
  isLoading = false;
  errorMessage = '';

  constructor(
    private fb: FormBuilder,
    private authService: AuthService,
    private router: Router
  ) {
    console.log('RegisterComponent constructor called');
    this.registerForm = this.fb.group({
      name: ['', [Validators.required]],
      email: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(8)]],
      confirmPassword: ['', [Validators.required]]
    }, { validators: this.passwordMatchValidator });
    console.log('RegisterForm initialized:', this.registerForm);
  }

  passwordMatchValidator(g: FormGroup): { [key: string]: any } | null {
    const password = g.get('password')?.value;
    const confirmPassword = g.get('confirmPassword')?.value;
    return password === confirmPassword ? null : { mismatch: true };
  }

  onButtonClick(): void {
    console.log('Button clicked!');
    console.log('Form valid:', this.registerForm.valid);
    console.log('Form disabled:', this.registerForm.invalid || this.isLoading);
  }

  onSubmit(): void {
    console.log('Register form submitted', this.registerForm.value);
    console.log('Form valid:', this.registerForm.valid);
    console.log('Form errors:', this.registerForm.errors);

    if (this.registerForm.invalid) {
      console.log('Form is invalid, not submitting');
      return;
    }

    this.isLoading = true;
    this.errorMessage = '';

    const { name, email, password } = this.registerForm.value;

    console.log('Calling register API with:', { name, email });

    this.authService.register(email, password, name).subscribe({
      next: (user) => {
        console.log('Registration successful:', user);
        // Registration succeeded; proceed to login so the auth guard is exercised
        this.router.navigate(['/login']);
      },
      error: (err) => {
        console.error('Registration failed:', err);
        this.errorMessage = 'Registration failed. Email may already be in use.';
        this.isLoading = false;
      }
    });
  }
}

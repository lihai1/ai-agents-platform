import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

interface RunContext {
  runId: string;
  status: string;
  createdAt: string;
}

@Component({
  selector: 'app-run-context',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="run-context" *ngIf="run">
      <div class="run-info">
        <span class="run-id">Run: {{ run.runId }}</span>
        <span class="run-status" [class.status-active]="run.status === 'running'">
          {{ run.status }}
        </span>
      </div>
    </div>
  `,
  styles: [`
    .run-context {
      padding: 1rem;
      background: #f5f5f5;
      border-radius: 4px;
      margin-bottom: 1rem;
    }
    .run-info {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .run-status {
      padding: 0.25rem 0.5rem;
      border-radius: 4px;
      background: #e0e0e0;
    }
    .status-active {
      background: #4caf50;
      color: white;
    }
  `]
})
export class RunContextComponent {
  @Input() run: RunContext | null = null;
}

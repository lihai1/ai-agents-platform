import {
  Component,
  Input,
  OnChanges,
  SimpleChanges,
  ViewChild,
  AfterViewInit,
  Output,
  EventEmitter,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subject } from 'rxjs';
import { NgTerminalComponent, NgTerminalModule } from 'ng-terminal';
import { TerminalSession } from '../chat/chat.component';

@Component({
  selector: 'app-terminal',
  standalone: true,
  imports: [CommonModule, NgTerminalModule],
  template: `
    <div class="terminal-panel" *ngIf="session">
      <div class="terminal-header">
        <div class="terminal-title">
          <span class="terminal-dot" [class]="session.status"></span>
          <span class="terminal-command">{{ session.command }}</span>
        </div>
        <div class="terminal-meta">
          <span class="terminal-status">{{ session.status }}</span>
          <span *ngIf="session.exitCode !== undefined" class="terminal-exit-code">
            exit {{ session.exitCode }}
          </span>
          <span class="terminal-duration" *ngIf="duration">{{ duration }}</span>
        </div>
      </div>
      <div class="terminal-body">
        <ng-terminal
          #term
          [dataSource]="dataSource"
          (keyEvent)="onKeyEvent($event)"
        ></ng-terminal>
      </div>
    </div>
  `,
  styles: [`
    .terminal-panel {
      border: 1px solid #2d2d2d;
      border-radius: 8px;
      overflow: hidden;
      background: #1e1e1e;
      margin: 0.75rem 0;
    }

    .terminal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.5rem 0.75rem;
      background: #2d2d2d;
      border-bottom: 1px solid #3d3d3d;
    }

    .terminal-title {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      color: #ccc;
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      font-size: 0.8rem;
    }

    .terminal-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #4caf50;
    }

    .terminal-dot.running {
      background: #4caf50;
      animation: pulse 1.5s infinite;
    }

    .terminal-dot.completed {
      background: #4caf50;
    }

    .terminal-dot.failed {
      background: #f44336;
    }

    .terminal-dot.cancelled {
      background: #ff9800;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.4; }
    }

    .terminal-command {
      font-size: 0.75rem;
      color: #aaa;
      max-width: 300px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .terminal-meta {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-size: 0.7rem;
      color: #888;
    }

    .terminal-status {
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .terminal-exit-code {
      color: #f44336;
    }

    .terminal-duration {
      color: #888;
    }

    .terminal-body {
      height: 350px;
      overflow: auto;
    }

    :host ::ng-deep .terminal-body ng-terminal {
      display: block;
      width: 100%;
      height: 100%;
    }
  `],
})
export class TerminalComponent implements OnChanges, AfterViewInit {
  @Input() session: TerminalSession | null = null;
  @Output() stdinInput = new EventEmitter<string>();
  @ViewChild('term') term!: NgTerminalComponent;

  dataSource = new Subject<string>();
  duration = '';
  private lastWrittenChunkCount = 0;
  private initialized = false;

  ngAfterViewInit(): void {
    this.initialized = true;
    if (this.term?.underlying) {
      this.term.setXtermOptions({
        fontSize: 13,
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
        theme: {
          background: '#1e1e1e',
          foreground: '#d4d4d4',
          cursor: '#d4d4d4',
          black: '#000000',
          red: '#cd3131',
          green: '#0dbc79',
          yellow: '#e5e510',
          blue: '#2472c8',
          magenta: '#bc3fbc',
          cyan: '#11a8cd',
          white: '#e5e5e5',
          brightBlack: '#666666',
          brightRed: '#f14c4c',
          brightGreen: '#23d18b',
          brightYellow: '#f5f543',
          brightBlue: '#3b8eea',
          brightMagenta: '#d670d6',
          brightCyan: '#29b8db',
          brightWhite: '#ffffff',
        },
        cursorBlink: true,
        scrollback: 5000,
        scrollSensitivity: 5,
        allowProposedApi: true,
      });
    }
    this.writeNewChunks();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['session']) {
      const prev = changes['session'].previousValue as TerminalSession | null;
      const curr = changes['session'].currentValue as TerminalSession | null;

      if (!prev && curr) {
        this.lastWrittenChunkCount = 0;
      } else if (prev?.sessionId !== curr?.sessionId) {
        this.lastWrittenChunkCount = 0;
      }

      this.writeNewChunks();
      this.computeDuration();
    }
  }

  onKeyEvent(event: { key: string; domEvent: KeyboardEvent }): void {
    if (this.session?.status !== 'running') return;
    this.stdinInput.emit(event.key);
  }

  private writeNewChunks(): void {
    if (!this.session || !this.initialized) return;

    const sorted = [...this.session.output].sort((a, b) => a.sequence - b.sequence);
    const newChunks = sorted.slice(this.lastWrittenChunkCount);

    for (const chunk of newChunks) {
      this.dataSource.next(chunk.data);
    }
    this.lastWrittenChunkCount = sorted.length;
  }

  private computeDuration(): void {
    if (!this.session) {
      this.duration = '';
      return;
    }
    const end = this.session.endedAt ?? Date.now();
    const ms = end - this.session.startedAt;
    if (ms < 1000) {
      this.duration = `${ms}ms`;
    } else {
      this.duration = `${(ms / 1000).toFixed(1)}s`;
    }
  }
}

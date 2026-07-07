import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';

interface DiffLine {
  lineNumber: number;
  type: 'added' | 'removed' | 'context';
  content: string;
}

@Component({
  selector: 'app-diff-viewer',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="diff-viewer">
      <div class="diff-header">
        <h3>Code Diff</h3>
        <div class="header-actions">
          <button (click)="copyDiff()" class="copy-button">Copy</button>
          <button (click)="close.emit()" class="close-button">×</button>
        </div>
      </div>
      <div class="diff-content">
        <div *ngIf="!diffLines.length" class="no-diff">
          No changes to display
        </div>
        <div *ngFor="let line of diffLines" class="diff-line" [class.added]="line.type === 'added'" [class.removed]="line.type === 'removed'">
          <span class="line-number">{{ line.lineNumber }}</span>
          <span class="line-content">{{ line.content }}</span>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .diff-viewer {
      background: #f5f5f5;
      border-radius: 8px;
      padding: 20px;
    }
    
    .diff-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 15px;
    }
    
    .header-actions {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    
    .copy-button {
      padding: 8px 16px;
      background: #2196f3;
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
    }
    
    .copy-button:hover {
      background: #1976d2;
    }
    
    .close-button {
      background: none;
      border: none;
      font-size: 1.5rem;
      cursor: pointer;
      color: #666;
      padding: 0;
      width: 24px;
      height: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
      line-height: 1;
    }
    
    .close-button:hover {
      color: #1a1a1a;
    }
    
    .diff-content {
      background: white;
      border-radius: 4px;
      overflow-x: auto;
      font-family: 'Courier New', monospace;
      font-size: 13px;
    }
    
    .no-diff {
      padding: 40px;
      text-align: center;
      color: #999;
    }
    
    .diff-line {
      display: flex;
      padding: 2px 10px;
      border-bottom: 1px solid #f0f0f0;
    }
    
    .diff-line.added {
      background: #e8f5e9;
    }
    
    .diff-line.removed {
      background: #ffebee;
    }
    
    .line-number {
      width: 50px;
      color: #999;
      text-align: right;
      padding-right: 15px;
      user-select: none;
    }
    
    .line-content {
      flex: 1;
      white-space: pre;
    }
  `]
})
export class DiffViewerComponent {
  @Input() diff: string = '';
  @Output() close = new EventEmitter<void>();
  
  diffLines: DiffLine[] = [];
  
  ngOnChanges() {
    this.parseDiff();
  }
  
  parseDiff() {
    this.diffLines = [];
    const lines = this.diff.split('\n');
    let lineNumber = 1;
    
    for (const line of lines) {
      if (line.startsWith('+')) {
        this.diffLines.push({
          lineNumber: lineNumber++,
          type: 'added',
          content: line.substring(1)
        });
      } else if (line.startsWith('-')) {
        this.diffLines.push({
          lineNumber: lineNumber++,
          type: 'removed',
          content: line.substring(1)
        });
      } else if (line.startsWith(' ')) {
        this.diffLines.push({
          lineNumber: lineNumber++,
          type: 'context',
          content: line.substring(1)
        });
      } else if (line.startsWith('@@') || line.startsWith('diff') || line.startsWith('index')) {
        // Diff metadata, skip line number increment
        this.diffLines.push({
          lineNumber: 0,
          type: 'context',
          content: line
        });
      }
    }
  }
  
  copyDiff() {
    navigator.clipboard.writeText(this.diff);
  }
}

import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

interface Artifact {
  id: string;
  kind: string;
  title: string;
  content: string;
  metadata: any;
  created_at: string;
}

@Component({
  selector: 'app-artifact-viewer',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="artifact-viewer">
      <div class="artifact-header">
        <h3>{{ artifact.title || 'Artifact' }}</h3>
        <div class="header-actions">
          <span class="artifact-kind">{{ artifact.kind }}</span>
          <button class="close-btn" (click)="close.emit()">×</button>
        </div>
      </div>
      <div class="artifact-content" [innerHTML]="renderedContent"></div>
    </div>
  `,
  styles: [`
    .artifact-viewer {
      background: #f5f5f5;
      border-radius: 8px;
      padding: 20px;
    }
    
    .artifact-header {
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
    
    .artifact-kind {
      padding: 4px 12px;
      background: #e3f2fd;
      color: #1976d2;
      border-radius: 12px;
      font-size: 12px;
      text-transform: uppercase;
    }
    
    .close-btn {
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
    
    .close-btn:hover {
      color: #1a1a1a;
    }
    
    .artifact-content {
      background: white;
      border-radius: 4px;
      padding: 20px;
      min-height: 200px;
    }
    
    .artifact-content pre {
      white-space: pre-wrap;
      word-wrap: break-word;
      margin: 0;
    }
  `]
})
export class ArtifactViewerComponent {
  @Input() artifact!: Artifact;
  @Output() close = new EventEmitter<void>();
  
  renderedContent: SafeHtml = '';
  
  constructor(private sanitizer: DomSanitizer) {}
  
  ngOnChanges() {
    this.renderArtifact();
  }
  
  renderArtifact() {
    if (!this.artifact) return;
    
    switch (this.artifact.kind) {
      case 'code_diff':
        this.renderedContent = this.sanitizer.bypassSecurityTrustHtml(
          `<pre>${this.escapeHtml(this.artifact.content)}</pre>`
        );
        break;
      
      case 'test_report':
        this.renderedContent = this.sanitizer.bypassSecurityTrustHtml(
          this.renderTestReport(this.artifact.content)
        );
        break;
      
      case 'review_report':
        this.renderedContent = this.sanitizer.bypassSecurityTrustHtml(
          this.renderReviewReport(this.artifact.content)
        );
        break;
      
      case 'verification_report':
        this.renderedContent = this.sanitizer.bypassSecurityTrustHtml(
          this.renderVerificationReport(this.artifact.content)
        );
        break;
      
      case 'diagram':
        // Render Mermaid diagram
        this.renderedContent = this.sanitizer.bypassSecurityTrustHtml(
          `<pre class="mermaid">${this.escapeHtml(this.artifact.content)}</pre>`
        );
        break;
      
      default:
        this.renderedContent = this.sanitizer.bypassSecurityTrustHtml(
          `<pre>${this.escapeHtml(this.artifact.content)}</pre>`
        );
    }
  }
  
  renderTestReport(content: string): string {
    const data = JSON.parse(content);
    return `
      <div class="test-report">
        <h4>Test Results</h4>
        <div class="test-summary">
          <div class="summary-item">
            <span class="label">Total:</span>
            <span class="value">${data.total_tests}</span>
          </div>
          <div class="summary-item">
            <span class="label">Passed:</span>
            <span class="value success">${data.passed}</span>
          </div>
          <div class="summary-item">
            <span class="label">Failed:</span>
            <span class="value error">${data.failed}</span>
          </div>
          <div class="summary-item">
            <span class="label">Coverage:</span>
            <span class="value">${data.coverage}%</span>
          </div>
        </div>
        ${data.failed_tests.length ? `
          <h5>Failed Tests</h5>
          <ul>
            ${data.failed_tests.map((t: string) => `<li>${t}</li>`).join('')}
          </ul>
        ` : ''}
      </div>
    `;
  }
  
  renderReviewReport(content: string): string {
    const data = JSON.parse(content);
    return `
      <div class="review-report">
        <h4>Code Review</h4>
        <div class="review-decision ${data.decision}">
          Decision: ${data.decision}
        </div>
        <h5>Findings</h5>
        <ul>
          ${data.findings.map((f: any) => `
            <li class="finding ${f.severity}">
              <span class="severity">[${f.severity}]</span>
              <span class="message">${f.message}</span>
              ${f.file ? `<span class="file">${f.file}:${f.line}</span>` : ''}
            </li>
          `).join('')}
        </ul>
      </div>
    `;
  }
  
  renderVerificationReport(content: string): string {
    const data = JSON.parse(content);
    return `
      <div class="verification-report">
        <h4>Verification Results</h4>
        <div class="verification-decision ${data.accepted ? 'accepted' : 'rejected'}">
          ${data.accepted ? '✓ Accepted' : '✗ Rejected'}
        </div>
        <h5>Criteria Results</h5>
        <ul>
          ${data.criteria_results.map((c: any) => `
            <li class="criterion ${c.passed ? 'passed' : 'failed'}">
              <span class="status">${c.passed ? '✓' : '✗'}</span>
              <span class="criterion-text">${c.criterion}</span>
              <span class="evidence">${c.evidence}</span>
            </li>
          `).join('')}
        </ul>
      </div>
    `;
  }
  
  escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

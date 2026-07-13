import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';

/** Shape of the result returned by the Python `run_matching` API method. */
interface RunSummary {
  ok: boolean;
  error?: string;
  total_source_lines?: number;
  matched_source_lines?: number;
  unmatched_source_lines?: number;
  total_matched_rows?: number;
  total_source_points?: number;
  orphan_source_points?: number;
  output_path?: string;
}

interface PywebviewApi {
  pick_source_file(): Promise<string | null>;
  pick_target_file(): Promise<string | null>;
  pick_output_file(): Promise<string | null>;
  run_matching(sourcePath: string, targetPath: string, outputPath: string): Promise<RunSummary>;
}

declare global {
  interface Window {
    pywebview?: { api: PywebviewApi };
  }
}

@Component({
  selector: 'app-root',
  imports: [CommonModule],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  protected readonly title = signal('GeometryMatcher');

  protected readonly apiReady = signal(false);
  protected readonly sourcePath = signal<string | null>(null);
  protected readonly targetPath = signal<string | null>(null);
  protected readonly outputPath = signal<string | null>(null);

  protected readonly running = signal(false);
  protected readonly summary = signal<RunSummary | null>(null);

  constructor() {
    if (window.pywebview) {
      this.apiReady.set(true);
    } else {
      window.addEventListener('pywebviewready', () => this.apiReady.set(true));
    }
  }

  protected get canRun(): boolean {
    return (
      this.apiReady() &&
      !this.running() &&
      !!this.sourcePath() &&
      !!this.targetPath() &&
      !!this.outputPath()
    );
  }

  async pickSource(): Promise<void> {
    const path = await window.pywebview?.api.pick_source_file();
    if (path) this.sourcePath.set(path);
  }

  async pickTarget(): Promise<void> {
    const path = await window.pywebview?.api.pick_target_file();
    if (path) this.targetPath.set(path);
  }

  async pickOutput(): Promise<void> {
    const path = await window.pywebview?.api.pick_output_file();
    if (path) this.outputPath.set(path);
  }

  async run(): Promise<void> {
    const source = this.sourcePath();
    const target = this.targetPath();
    const output = this.outputPath();
    if (!source || !target || !output) return;

    this.running.set(true);
    this.summary.set(null);
    try {
      const result = await window.pywebview!.api.run_matching(source, target, output);
      this.summary.set(result);
    } catch (err) {
      this.summary.set({ ok: false, error: String(err) });
    } finally {
      this.running.set(false);
    }
  }
}

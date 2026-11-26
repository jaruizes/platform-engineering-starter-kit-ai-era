import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: `<main><h1>${{ values.name }}</h1><p>${{ values.description }}</p><router-outlet /></main>`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppComponent {}

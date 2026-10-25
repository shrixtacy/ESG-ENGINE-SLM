/**
 * ESGPilot SDK — Components registration.
 * Register all custom elements here.
 */
export { ChatPanel } from './ChatPanel';
export { SuggestionCardElement } from './SuggestionCard';

/** Register all ESGPilot custom elements. */
export function registerComponents(): void {
  if (!customElements.get('esgpilot-panel')) {
    import('./ChatPanel').then(({ ChatPanel }) => {
      customElements.define('esgpilot-panel', ChatPanel);
    });
  }
  if (!customElements.get('esgpilot-suggestion-card')) {
    import('./SuggestionCard').then(({ SuggestionCardElement }) => {
      customElements.define('esgpilot-suggestion-card', SuggestionCardElement);
    });
  }
}

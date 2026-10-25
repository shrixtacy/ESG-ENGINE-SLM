/**
 * ESGPilot SDK — Public Entry Point
 *
 * Drop-in script usage:
 *   <script src="https://cdn.esgpilot.io/sdk.js"
 *     data-tenant="meil" data-key="pk_live_xxx"
 *     data-position="bottom-right" data-lang="en"></script>
 *
 * Programmatic usage:
 *   import { ESGPilot } from '@esgpilot/sdk';
 *   ESGPilot.init({ tenant: 'meil', key: 'pk_live_xxx', user: {...} });
 *   ESGPilot.attachForm('#brsr-form', { framework: 'BRSR', section: 'C-P6' });
 */

export { ESGPilotSDK as ESGPilot } from './core/ESGPilotSDK';
export type { SDKConfig, UserContext, FormConfig, SuggestionCard } from './types';

// Auto-init when loaded as a <script> tag
if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  const currentScript =
    document.currentScript as HTMLScriptElement | null;

  if (currentScript) {
    const tenant = currentScript.dataset.tenant;
    const key = currentScript.dataset.key;
    const position = currentScript.dataset.position || 'bottom-right';
    const lang = currentScript.dataset.lang || 'en';
    const apiUrl = currentScript.dataset.apiUrl || 'https://api.esgpilot.io';

    if (tenant && key) {
      import('./core/ESGPilotSDK').then(({ ESGPilotSDK }) => {
        ESGPilotSDK.init({ tenant, key, position, lang, apiUrl });
      });
    }
  }
}

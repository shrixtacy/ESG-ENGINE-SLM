/**
 * ESGPilot SDK — L2 Adapter (Declarative data-esg-* attributes).
 *
 * Host app adds HTML attributes to inputs — no JavaScript calls needed:
 *   <input name="scope1_emissions"
 *          data-esg-field="brsr_p6_ei7_scope1"
 *          data-esg-unit="tCO2e"
 *          data-esg-label="Scope 1 GHG Emissions"
 *          data-esg-framework="BRSR"
 *          data-esg-section="P6"
 *   />
 *
 * The adapter auto-discovers these attributes via MutationObserver
 * and uses L1Adapter under the hood for debounced snapshotting.
 *
 * Privacy:
 * - Only fields with data-esg-field attribute are captured (allow-list).
 */

import type { FormContext } from '../types';
import { L1Adapter } from './L1Adapter';

type ContextUpdateCallback = (ctx: FormContext) => void;

export class L2Adapter {
  private onUpdate: ContextUpdateCallback;
  private adapters: Map<string, L1Adapter> = new Map();
  private rootObserver: MutationObserver | null = null;
  private attached = false;

  constructor(onUpdate: ContextUpdateCallback) {
    this.onUpdate = onUpdate;
  }

  /**
   * Start scanning the document for data-esg-* attributes.
   * Called once when SDK initializes.
   */
  attach(root: Element = document.body): void {
    if (this.attached) return;
    this.attached = true;

    // Initial scan
    this._scanAndRegister(root);

    // Watch for new forms/fields added dynamically
    this.rootObserver = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            this._scanAndRegister(node as Element);
          }
        });
      }
    });

    this.rootObserver.observe(root, { childList: true, subtree: true });
  }

  detach(): void {
    this.rootObserver?.disconnect();
    this.adapters.forEach((a) => a.detach());
    this.adapters.clear();
    this.attached = false;
  }

  // ──────────────────────────────────────────────
  // Private
  // ──────────────────────────────────────────────

  private _scanAndRegister(root: Element): void {
    // Find all form elements containing data-esg-field inputs
    const esgInputs = root.querySelectorAll('[data-esg-field]');
    if (!esgInputs.length) return;

    // Group by form / framework+section to create logical form contexts
    const formGroups = this._groupByForm(Array.from(esgInputs) as HTMLElement[]);

    for (const [formKey, elements] of formGroups.entries()) {
      if (this.adapters.has(formKey)) continue;

      // Determine form context from the first element's attributes
      const first = elements[0];
      const framework = first.dataset.esgFramework ?? 'BRSR';
      const section = first.dataset.esgSection;
      const fy = first.dataset.esgFy ?? 'FY2025';

      // Find parent form element or use document body as selector
      const formEl = first.closest('form') ?? first.closest('[data-esg-form]');
      const selector = formEl
        ? (formEl.id ? `#${formEl.id}` : `[data-esg-form="${(formEl as HTMLElement).dataset.esgForm ?? ''}"]`)
        : 'body';

      const baseContext: FormContext = {
        formId: formKey,
        framework,
        section,
        fy,
        fields: [],
      };

      const adapter = new L1Adapter(selector, baseContext, this.onUpdate);
      this.adapters.set(formKey, adapter);
      adapter.attach();
    }
  }

  private _groupByForm(elements: HTMLElement[]): Map<string, HTMLElement[]> {
    const groups = new Map<string, HTMLElement[]>();

    for (const el of elements) {
      // Key by form ID, then by framework+section, then by a generic key
      const formEl = el.closest('form');
      const formDataAttr = el.closest('[data-esg-form]') as HTMLElement | null;
      const key =
        (formEl?.id ? `form_${formEl.id}` : null) ??
        (formDataAttr ? `form_${formDataAttr.dataset.esgForm}` : null) ??
        `form_${el.dataset.esgFramework ?? 'brsr'}_${el.dataset.esgSection ?? 'default'}`;

      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(el);
    }

    return groups;
  }
}

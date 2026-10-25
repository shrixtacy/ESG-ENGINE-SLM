/**
 * ESGPilot SDK — L3 Adapter (Auto-Discovery).
 *
 * Lowest-friction but medium-reliability integration.
 * Scans form labels, placeholders, and field names to map them
 * to BRSR/ESG framework fields using keyword matching.
 *
 * IMPORTANT: L3 matches require user confirmation before sending data.
 * This is a best-effort adapter for third-party apps the host cannot modify.
 *
 * Usage flow:
 *  1. L3Adapter scans visible form fields
 *  2. Proposes mappings (confidence score per field)
 *  3. Shows confirmation UI to user
 *  4. On confirmation, delegates to L1Adapter for capture
 */

import type { FormContext, FieldData } from '../types';

export interface FieldMapping {
  inputElement: HTMLInputElement;
  proposedFieldCode: string;
  proposedLabel: string;
  confidence: number;   // 0-1
  framework: string;
  section: string;
}

type ContextUpdateCallback = (ctx: FormContext) => void;

// ──────────────────────────────────────────────
// Keyword → BRSR field mapping table
// ──────────────────────────────────────────────

interface FieldPattern {
  keywords: string[];
  fieldCode: string;
  label: string;
  unit: string;
  framework: string;
  section: string;
}

const FIELD_PATTERNS: FieldPattern[] = [
  {
    keywords: ['scope 1', 'scope1', 'direct emission', 'ghg scope 1', 'direct ghg'],
    fieldCode: 'brsr_p6_ei7_scope1',
    label: 'Scope 1 GHG Emissions',
    unit: 'tCO2e', framework: 'BRSR', section: 'P6',
  },
  {
    keywords: ['scope 2', 'scope2', 'indirect emission', 'purchased electricity emission', 'ghg scope 2'],
    fieldCode: 'brsr_p6_ei7_scope2',
    label: 'Scope 2 GHG Emissions',
    unit: 'tCO2e', framework: 'BRSR', section: 'P6',
  },
  {
    keywords: ['total ghg', 'total emission', 'scope 1+2', 'scope 1 and 2', 'ghg total'],
    fieldCode: 'brsr_p6_ei7_total',
    label: 'Total GHG Emissions (Scope 1+2)',
    unit: 'tCO2e', framework: 'BRSR', section: 'P6',
  },
  {
    keywords: ['total energy', 'energy consumption', 'total energy consumed'],
    fieldCode: 'brsr_p6_ei6_total',
    label: 'Total Energy Consumption',
    unit: 'GJ', framework: 'BRSR', section: 'P6',
  },
  {
    keywords: ['renewable energy', 'solar', 'wind energy', 'green energy'],
    fieldCode: 'brsr_p6_ei6_renewable',
    label: 'Energy from Renewable Sources',
    unit: 'GJ', framework: 'BRSR', section: 'P6',
  },
  {
    keywords: ['water withdrawal', 'water sourced', 'total water', 'water consumption'],
    fieldCode: 'brsr_p6_ei9_withdrawal',
    label: 'Total Water Withdrawal',
    unit: 'KL', framework: 'BRSR', section: 'P6',
  },
  {
    keywords: ['water discharge', 'wastewater', 'effluent discharge'],
    fieldCode: 'brsr_p6_ei9_discharge',
    label: 'Total Water Discharge',
    unit: 'KL', framework: 'BRSR', section: 'P6',
  },
  {
    keywords: ['total waste', 'waste generated', 'waste produced'],
    fieldCode: 'brsr_p6_ei10_total',
    label: 'Total Waste Generated',
    unit: 'MT', framework: 'BRSR', section: 'P6',
  },
  {
    keywords: ['hazardous waste', 'haz waste'],
    fieldCode: 'brsr_p6_ei10_hazardous',
    label: 'Hazardous Waste Generated',
    unit: 'MT', framework: 'BRSR', section: 'P6',
  },
  {
    keywords: ['total employees', 'total headcount', 'workforce'],
    fieldCode: 'brsr_p3_ei1_total',
    label: 'Total Number of Employees',
    unit: '', framework: 'BRSR', section: 'P3',
  },
  {
    keywords: ['permanent employee', 'full-time', 'fulltime'],
    fieldCode: 'brsr_p3_ei1_permanent',
    label: 'Number of Permanent Employees',
    unit: '', framework: 'BRSR', section: 'P3',
  },
  {
    keywords: ['csr spend', 'csr expenditure', 'csr amount spent', 'amount spent on csr'],
    fieldCode: 'brsr_secb_csr_spent',
    label: 'CSR Expenditure (Amount Spent)',
    unit: '₹ crore', framework: 'CSR', section: 'Section B',
  },
  {
    keywords: ['csr obligation', 'csr budget', '2% csr', 'csr prescribed'],
    fieldCode: 'brsr_secb_csr_obligation',
    label: 'CSR Obligation (2% of net profit)',
    unit: '₹ crore', framework: 'CSR', section: 'Section B',
  },
];


export class L3Adapter {
  private onUpdate: ContextUpdateCallback;
  private confirmedMappings: FieldMapping[] = [];

  constructor(onUpdate: ContextUpdateCallback) {
    this.onUpdate = onUpdate;
  }

  /**
   * Scan a form and propose field mappings.
   * Returns proposals for user confirmation.
   */
  scan(formSelector: string): FieldMapping[] {
    const form = document.querySelector(formSelector);
    if (!form) return [];

    const inputs = Array.from(
      form.querySelectorAll('input, select, textarea')
    ) as HTMLInputElement[];

    const mappings: FieldMapping[] = [];

    for (const input of inputs) {
      const text = this._getFieldText(input).toLowerCase();
      if (!text) continue;

      const best = this._findBestMatch(text);
      if (best && best.confidence >= 0.5) {
        mappings.push({
          inputElement: input,
          proposedFieldCode: best.pattern.fieldCode,
          proposedLabel: best.pattern.label,
          confidence: best.confidence,
          framework: best.pattern.framework,
          section: best.pattern.section,
        });
      }
    }

    return mappings;
  }

  /**
   * Accept confirmed mappings and start capturing.
   */
  confirmMappings(mappings: FieldMapping[]): void {
    this.confirmedMappings = mappings;

    // Listen for changes on confirmed fields
    for (const mapping of mappings) {
      mapping.inputElement.addEventListener('change', () => this._onConfirmedChange());
      mapping.inputElement.addEventListener('blur', () => this._onConfirmedChange());
    }
  }

  private _onConfirmedChange(): void {
    const fields: FieldData[] = this.confirmedMappings.map((m) => ({
      fieldCode: m.proposedFieldCode,
      label: m.proposedLabel,
      value: m.inputElement.type === 'number'
        ? (parseFloat(m.inputElement.value) || null)
        : (m.inputElement.value || null),
    }));

    // Determine form context from first confirmed mapping
    const first = this.confirmedMappings[0];
    const ctx: FormContext = {
      formId: `l3_auto_${first?.framework ?? 'brsr'}`,
      framework: first?.framework ?? 'BRSR',
      section: first?.section,
      fy: 'FY2025',
      fields,
    };

    this.onUpdate(ctx);
  }

  private _getFieldText(input: HTMLInputElement): string {
    const parts: string[] = [];

    // Aria label
    const ariaLabel = input.getAttribute('aria-label');
    if (ariaLabel) parts.push(ariaLabel);

    // Associated <label>
    if (input.id) {
      const label = document.querySelector(`label[for="${input.id}"]`);
      if (label) parts.push((label as HTMLElement).innerText);
    }

    // Placeholder
    if (input.placeholder) parts.push(input.placeholder);

    // name attribute
    if (input.name) parts.push(input.name.replace(/[_-]/g, ' '));

    return parts.join(' ').trim();
  }

  private _findBestMatch(text: string): { pattern: FieldPattern; confidence: number } | null {
    let best: { pattern: FieldPattern; confidence: number } | null = null;

    for (const pattern of FIELD_PATTERNS) {
      for (const keyword of pattern.keywords) {
        if (text.includes(keyword)) {
          // Confidence based on keyword length relative to field text
          const confidence = Math.min(keyword.length / text.length + 0.4, 1.0);
          if (!best || confidence > best.confidence) {
            best = { pattern, confidence: parseFloat(confidence.toFixed(2)) };
          }
        }
      }
    }

    return best;
  }

  /**
   * Generate a user-visible confirmation UI for proposed mappings.
   * Returns HTML string — host app can inject this anywhere.
   */
  renderConfirmationUI(mappings: FieldMapping[], onConfirm: (mappings: FieldMapping[]) => void): string {
    if (!mappings.length) return '<p>No ESG fields detected in this form.</p>';

    const rows = mappings.map((m, i) => `
      <tr>
        <td><input type="checkbox" id="map_${i}" data-index="${i}" checked/></td>
        <td>${this._getFieldText(m.inputElement) || m.inputElement.name}</td>
        <td><strong>${m.proposedLabel}</strong></td>
        <td>${m.framework}</td>
        <td>${(m.confidence * 100).toFixed(0)}%</td>
      </tr>
    `).join('');

    return `
      <div id="esgpilot-l3-confirm">
        <h3>ESGPilot detected ESG fields</h3>
        <p>Please confirm which fields to map:</p>
        <table>
          <thead>
            <tr><th></th><th>Form field</th><th>Maps to</th><th>Framework</th><th>Confidence</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
        <button id="l3-confirm-btn">Confirm selected mappings</button>
        <button id="l3-cancel-btn">Cancel</button>
      </div>
    `;
  }
}

/**
 * ESGPilot SDK — Adapters.
 * L1: Schema push (highest reliability)
 * L2: data-esg-* attributes (high reliability)
 * L3: Auto-discovery (medium, requires user confirm)
 */
export { L1Adapter } from './L1Adapter';
export { L2Adapter } from './L2Adapter';
export { L3Adapter } from './L3Adapter';
export type { FieldMapping } from './L3Adapter';

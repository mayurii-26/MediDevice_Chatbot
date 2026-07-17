/**
 * sampleReportDetector.js
 *
 * Detects requests for sample / example reports (ECG reports, PDF samples, etc.)
 * This module is intentionally side-effect-free and has zero external
 * dependencies so it can be unit-tested in isolation.
 *
 * Usage:
 *   import { isSampleReportIntent, SAMPLE_REPORT_REPLY } from "./sampleReportDetector";
 *   if (isSampleReportIntent(userMessage)) { ... }
 */

// ── Keyword list ──────────────────────────────────────────────────────────
// Each entry is a word / phrase. Matching is case-insensitive and uses
// whole-word boundaries so single words won't trigger on partial matches.
const SAMPLE_REPORT_KEYWORDS = [
  // "sample" combinations
  "sample report",
  "sample ecg report",
  "sample ecg",
  "sample output",
  "sample patient report",
  "sample pdf",
  "sample print",
  "sample printout",
  "sample result",
  "sample test report",
  "sample document",
  "sample reading",

  // "example" combinations
  "example report",
  "example ecg",
  "example ecg report",
  "example output",
  "example patient report",
  "example pdf",
  "example result",

  // "report format" combinations
  "report format",
  "ecg report format",
  "report template",
  "report layout",
  "report structure",
  "report style",

  // "ECG print" combinations
  "ecg print sample",
  "ecg printout sample",
  "ecg print example",
  "ecg printout",
  "ecg print",

  // "PDF report" combinations
  "pdf report sample",
  "pdf report example",
  "pdf sample",
  "pdf example",
  "pdf output",

  // generic demo/preview report requests
  "demo report",
  "report preview",
  "report demo",
  "report specimen",
  "specimen report",

  // "what does the report look like" style queries handled via single keywords below
];

// Single-word triggers only when paired with "report" context — handled separately
// via compound phrase matching above. The following single words are standalone
// triggers that strongly imply a sample/report request in this domain:
const SAMPLE_REPORT_SINGLE_WORDS = [
  // none added — single words like "report" or "sample" are too broad on their own
];

// Build a single compiled regex from all keywords.
// - Phrase keywords (containing spaces) → simple escaped match.
// - Single-word keywords → word-boundary check (\b…\b).
const _PHRASE_PATTERNS = SAMPLE_REPORT_KEYWORDS.map((kw) =>
  kw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
);

const _WORD_PATTERNS = SAMPLE_REPORT_SINGLE_WORDS.map(
  (kw) => `\\b${kw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`
);

const _SAMPLE_REPORT_RE = new RegExp(
  [..._PHRASE_PATTERNS, ..._WORD_PATTERNS].join("|"),
  "i"
);

/**
 * Returns true if the message is requesting a sample / example report.
 * @param {string} message
 * @returns {boolean}
 */
export function isSampleReportIntent(message) {
  if (!message || typeof message !== "string") return false;
  return _SAMPLE_REPORT_RE.test(message.trim());
}

// ── Canned response shown in the chat bubble ─────────────────────────────
export const SAMPLE_REPORT_REPLY =
  "Sample reports related information is not available through the chatbot.\n\n" +
  "Please contact our support team and we'll get back to you shortly.";

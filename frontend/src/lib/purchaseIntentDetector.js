/**
 * purchaseIntentDetector.js
 *
 * Detects purchase / pricing / quote related intents in user messages.
 * This module is intentionally side-effect-free and has zero external
 * dependencies so it can be unit-tested in isolation.
 *
 * Usage:
 *   import { isPurchaseIntent, PURCHASE_INTENT_REPLY } from "./purchaseIntentDetector";
 *   if (isPurchaseIntent(userMessage)) { ... }
 */

// ── Keyword list ──────────────────────────────────────────────────────────
// Each entry is a word / phrase.  Matching is case-insensitive and uses
// whole-word boundaries so "process" won't trigger on "price".
const PURCHASE_KEYWORDS = [
  // buying
  "buy",
  "purchase",
  "buying",
  "purchasing",
  "procure",
  "procurement",
  "acquire",
  "acquisition",

  // pricing
  "price",
  "pricing",
  "cost",
  "costs",
  "costing",
  "rate",
  "rates",
  "tariff",
  "fee",
  "fees",
  "charges",
  "charge",
  "expensive",
  "affordable",
  "budget",

  // quotation
  "quote",
  "quotes",
  "quotation",
  "quotations",
  "rfq",
  "request for quote",
  "request a quote",
  "get a quote",
  "send a quote",

  // ordering
  "order",
  "orders",
  "ordering",
  "place an order",
  "place order",

  // sales / commercial
  "sales",
  "sale",
  "contact sales",
  "sales team",
  "sales rep",
  "sales representative",
  "commercial",

  // demo
  "demo",
  "request demo",
  "request a demo",
  "book a demo",
  "schedule a demo",
  "free demo",

  // distribution
  "dealer",
  "dealers",
  "dealership",
  "distributor",
  "distributors",
  "distribution",
  "reseller",
  "resellers",
  "vendor",
  "vendors",
  "supplier",
  "suppliers",

  // availability / stock
  "availability",
  "in stock",
  "out of stock",
  "stock",

  // invoice / payment
  "invoice",
  "invoicing",
  "payment",
  "payments",
  "pay",
  "checkout",
  "billing",
];

// Build a single compiled regex from all keywords.
// - Phrase keywords (containing spaces) get a simple case-insensitive check.
// - Single-word keywords get a word-boundary check (\b…\b).
const _WORD_RE = new RegExp(
  PURCHASE_KEYWORDS.map((kw) =>
    kw.includes(" ")
      ? kw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") // escape special chars
      : `\\b${kw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`
  ).join("|"),
  "i"
);

/**
 * Returns true if the message contains a purchase/pricing/quote intent.
 * @param {string} message
 * @returns {boolean}
 */
export function isPurchaseIntent(message) {
  if (!message || typeof message !== "string") return false;
  return _WORD_RE.test(message.trim());
}

// ── Canned response shown in the chat bubble ─────────────────────────────
export const PURCHASE_INTENT_REPLY =
  "Pricing and purchasing information is not available through the chatbot.\n\n" +
  "Please contact our support team and we'll get back to you shortly.";

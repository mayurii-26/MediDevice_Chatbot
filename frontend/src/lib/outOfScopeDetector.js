/**
 * outOfScopeDetector.js
 *
 * Detects queries that are completely unrelated to medical devices or healthcare.
 * Uses a two-pass approach:
 *   1. ALLOWLIST — if the query contains any medical / healthcare term, it is
 *      always allowed through regardless of anything else.
 *   2. BLOCKLIST — if the query matches a known off-topic category keyword, it
 *      is rejected with the out-of-scope reply.
 *
 * This order prevents false positives such as:
 *   - "cricket elbow" → medical, allowed  ✅
 *   - "python snake bite treatment" → medical, allowed  ✅
 *   - "cricket score" → no medical term, blocked  🚫
 *   - "write a python program" → no medical term, blocked  🚫
 *
 * Zero external dependencies — safe to unit-test in isolation.
 */

// ─────────────────────────────────────────────────────────────────────────────
// ALLOWLIST  — any query containing these terms is in-scope by definition.
// Keep this comprehensive so we never accidentally block a real medical query.
// ─────────────────────────────────────────────────────────────────────────────
const MEDICAL_ALLOWLIST = [
  // Philips brand & product families
  "philips", "pagewriter", "heartstart", "efficia", "trilogy",
  "tc50", "tc35", "tc10", "frx", "hs1", "dfm100", "st80i", "oscar 2",
  "cardiac workstation",

  // Device categories
  "medical device", "medical equipment", "medical technology", "healthcare",
  "patient monitor", "patient monitoring", "bedside monitor",
  "ecg", "ekg", "electrocardiogram", "electrocardiograph",
  "defibrillator", "aed", "automated external defibrillator",
  "holter", "holter monitor", "abpm", "ambulatory blood pressure",
  "pulse oximeter", "spo2", "oximetry", "oxygen saturation",
  "ventilator", "cpap", "bipap", "respiratory", "respiration",
  "infusion pump", "syringe pump",
  "anaesthesia", "anesthesia", "anaesthetic", "anesthetic",
  "laryngoscope", "video laryngoscope",
  "ctg", "cardiotocograph", "fetal monitor",
  "phototherapy", "phototherapy lamp", "radiant warmer",
  "surgical", "surgery", "operating theatre", "ot complex",
  "neonatal", "incubator", "nicu", "picu",
  "cardiology", "cardiac", "cardio",

  // Medical concepts & procedures
  "clinical", "diagnosis", "diagnostic", "treatment", "therapy",
  "hospital", "clinic", "icu", "critical care", "ward",
  "doctor", "physician", "nurse", "clinician", "paramedic",
  "patient", "blood pressure", "heart rate", "temperature",
  "waveform", "arrhythmia", "ecg lead", "electrode",
  "intubation", "airway", "ventilation", "tidal volume",
  "cardiac arrest", "defibrillation", "resuscitation", "cpr",
  "stress test", "holter", "telemetry",
  "medical", "health", "clinical", "biomedical",
  // Anatomy — allow "cricket elbow", "tennis elbow", etc.
  "elbow", "knee", "shoulder", "spine", "fracture", "tendon", "ligament",
  "joint", "bone", "nerve", "tissue", "organ", "muscle",
  "wound", "injury", "sprain", "strain", "pain relief",
];

// Compiled allowlist regex — whole-word matching, case-insensitive.
const _ALLOW_RE = new RegExp(
  MEDICAL_ALLOWLIST.map((term) =>
    term.includes(" ")
      ? term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
      : `\\b${term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`
  ).join("|"),
  "i"
);

// ─────────────────────────────────────────────────────────────────────────────
// BLOCKLIST — off-topic category keywords.
// Only checked when the allowlist does NOT match.
// ─────────────────────────────────────────────────────────────────────────────
const OOS_BLOCKLIST = [
  // ── Programming / Tech ───────────────────────────────────────────────────
  "python", "javascript", "typescript", "java", "kotlin", "swift",
  "c++", "c#", "golang", "rust", "ruby", "php", "perl",
  "react", "angular", "vue", "django", "flask", "fastapi framework",
  "nodejs", "node.js", "express.js",
  "algorithm", "data structure", "linked list", "binary tree",
  "sorting", "recursion", "fibonacci",
  "html", "css", "sass", "bootstrap", "tailwind",
  "sql", "nosql", "mongodb", "postgresql", "mysql",
  "docker", "kubernetes", "aws", "azure", "gcp", "cloud computing",
  "machine learning", "deep learning", "neural network", "llm",
  "chatgpt", "openai", "generative ai", "artificial intelligence",
  "blockchain", "cryptocurrency", "bitcoin", "ethereum", "nft",
  "coding", "programming", "developer", "software engineer",
  "debug", "compile", "runtime error", "null pointer",
  "api endpoint", "rest api", "graphql", "webhook",
  "github", "gitlab", "git commit", "pull request",
  "linux", "ubuntu", "windows 11", "macos",
  "smartphone", "iphone", "android", "laptop", "gaming",
  "video game", "esports", "minecraft", "fortnite", "pubg",

  // ── Cricket / Sports ────────────────────────────────────────────────────
  "cricket", "ipl", "t20", "test match", "one day",
  "batsman", "bowler", "wicket", "century", "over",
  "football", "soccer", "fifa", "premier league", "la liga",
  "basketball", "nba", "tennis", "wimbledon", "grand slam",
  "badminton", "hockey", "volleyball", "wrestling",
  "olympics", "commonwealth games", "world cup",
  "athlete", "sports team", "stadium",

  // ── Movies / Entertainment ───────────────────────────────────────────────
  "movie", "film", "cinema", "bollywood", "hollywood",
  "netflix", "amazon prime", "disney plus", "hulu",
  "actor", "actress", "director", "screenplay", "box office",
  "tv show", "web series", "season 2", "episode",
  "music", "song", "album", "concert", "spotify", "youtube music",
  "singer", "rapper", "band", "playlist",
  "anime", "manga", "cartoon",

  // ── Politics ────────────────────────────────────────────────────────────
  "politics", "political party", "election", "vote", "referendum",
  "president", "prime minister", "parliament", "senate", "congress",
  "government policy", "diplomacy", "foreign policy",
  "democrat", "republican", "left wing", "right wing",

  // ── General Knowledge / Trivia ──────────────────────────────────────────
  "capital of", "president of", "population of",
  "history of", "when was", "who invented",
  "geography", "country", "continent", "ocean",
  "mathematics", "calculus", "algebra", "geometry",
  "physics", "chemistry", "biology class",
  "periodic table", "atom", "molecule",
  "explain gravity", "speed of light", "black hole",

  // ── Jokes / Fun ─────────────────────────────────────────────────────────
  "tell me a joke", "funny joke", "knock knock",
  "pun", "riddle", "funny story",

  // ── Weather ─────────────────────────────────────────────────────────────
  "weather", "temperature today", "forecast", "rain today",
  "humidity", "monsoon season", "snowfall",

  // ── Shopping / eCommerce ────────────────────────────────────────────────
  "amazon", "flipkart", "ebay", "shopify", "meesho",
  "discount code", "coupon", "cashback", "shopping cart",
  "fashion", "clothing", "shoes", "jewellery", "makeup",
  "restaurant", "food delivery", "swiggy", "zomato",

  // ── Finance / Stocks ────────────────────────────────────────────────────
  "stock market", "sensex", "nifty", "share price",
  "mutual fund", "mutual funds", "sip investment", "forex", "trading",
  "loan", "emi", "interest rate", "insurance policy",

  // ── Travel ──────────────────────────────────────────────────────────────
  "flight booking", "book a flight", "hotel booking", "travel itinerary",
  "tourist spot", "visa application", "passport",

  // ── Social Media / Internet ─────────────────────────────────────────────
  "instagram", "twitter", "facebook", "tiktok", "snapchat",
  "whatsapp", "telegram", "reddit", "quora",
  "viral post", "meme", "reel", "hashtag",

  // ── Food / Recipes ───────────────────────────────────────────────────────
  "recipe", "ingredients", "how to cook", "biryani", "pizza",
  "calories in", "diet plan",

  // ── Astrology / Religion ────────────────────────────────────────────────
  "horoscope", "zodiac sign", "astrology", "numerology",
  "prayer", "worship",
];

// Compiled blocklist regex.
const _BLOCK_RE = new RegExp(
  OOS_BLOCKLIST.map((term) =>
    term.includes(" ")
      ? term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
      : `\\b${term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`
  ).join("|"),
  "i"
);

/**
 * Returns true when the query is out of scope (not medical / healthcare).
 *
 * Logic:
 *   1. If message contains any ALLOWLIST medical term  → NOT out of scope (false).
 *   2. If message matches any BLOCKLIST off-topic term → IS out of scope (true).
 *   3. Otherwise                                       → NOT out of scope (false).
 *      (Unknown queries pass through to the pipeline which handles them.)
 *
 * @param {string} message
 * @returns {boolean}
 */
export function isOutOfScope(message) {
  if (!message || typeof message !== "string") return false;
  const q = message.trim();
  // Medical allowlist wins — never block a healthcare query
  if (_ALLOW_RE.test(q)) return false;
  // Check blocklist
  return _BLOCK_RE.test(q);
}

// ── Canned response shown in the chat bubble ─────────────────────────────
export const OUT_OF_SCOPE_REPLY =
  "This platform is designed only for Medical devices and healthcare-related queries.\n\n" +
  "Please contact our support team for further assistance.";

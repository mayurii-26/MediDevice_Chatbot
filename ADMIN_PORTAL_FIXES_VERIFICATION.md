# Admin Portal Fixes - Verification Test Scenarios

## Issue 1: Unknown Queries - Healthcare Out-of-Scope Storage

### Root Cause
**Problem:** Medical/healthcare queries that received fallback responses were NOT being stored in `unknown_queries` table because:
1. `is_out_of_scope()` guard - short-circuits BEFORE `log_unanswered_query()` call
2. Orchestrator out-of-scope sentinel (`result.source == "out_of_scope"`) - also short-circuits
3. Both paths returned canned responses without logging

### Fix Applied
Added `log_unanswered_query()` calls to **4 locations** in `backend/app.py`:
1. `/chat` endpoint - `is_out_of_scope()` guard path (line ~406)
2. `/chat` endpoint - orchestrator out-of-scope sentinel path (line ~479)
3. `/chat/stream` endpoint - `is_out_of_scope()` guard path (line ~790)
4. `/chat/stream` endpoint - orchestrator out-of-scope sentinel path (line ~870)

All calls include:
```python
log_unanswered_query(
    question=req.question,
    answer_source="out_of_scope",
    user_id=authenticated_user_id,
    is_guest=_is_guest,
    confidence=0.0,
    matched_product=None,
)
```

The `analytics_logger.py` already has healthcare filtering via `_is_healthcare_query()` which checks for medical/healthcare/device terms.

### Test Scenarios & Expected Results

#### Test 1: Medical Query Out-of-Scope
**Input:**
```
User: What medicine should I take for fever?
```

**Response:**
```
This platform is designed only for Medical devices and healthcare-related queries.

Please contact our support team for further assistance.
```

**Expected Unknown Queries Record:**
| Column | Value |
|--------|-------|
| query | What medicine should I take for fever? |
| user | Guest (or user ID) |
| date | 2026-07-22 20:xx:xx |
| time | 20:xx:xx |
| times_asked | 1 |
| reason | No Knowledge Match |
| status | Pending |

**Log Output:**
```
[unknown] query='What medicine should I take for fever?' | is_medical=True | 
knowledge_found=False | dynamic_found=False | fallback=False | saved=True(insert) | times_asked=1
```

---

#### Test 2: Healthcare Device Query (Not in KB)
**Input:**
```
User: Tell me about MRI machine brands
```

**Response:**
```
This platform is designed only for Medical devices and healthcare-related queries.

Please contact our support team for further assistance.
```

**Expected Unknown Queries Record:**
| Column | Value |
|--------|-------|
| query | Tell me about MRI machine brands |
| user | Guest |
| date | 2026-07-22 20:xx:xx |
| time | 20:xx:xx |
| times_asked | 1 |
| reason | Unknown Device |
| status | Pending |

**Log Output:**
```
[unknown] query='Tell me about MRI machine brands' | is_medical=True | 
knowledge_found=False | dynamic_found=False | fallback=False | saved=True(insert) | times_asked=1
```

---

#### Test 3: General Healthcare Question
**Input:**
```
User: What are the medical devices you provide?
```

**Response:**
```
Dynamic Search / Web Information
(or)
This platform is designed only for Medical devices and healthcare-related queries.
```

**Expected Unknown Queries Record:**
| Column | Value |
|--------|-------|
| query | What are the medical devices you provide? |
| user | Guest |
| date | 2026-07-22 20:xx:xx |
| time | 20:xx:xx |
| times_asked | 1 |
| reason | Outside Product Scope |
| status | Pending |

**Log Output:**
```
[unknown] query='What are the medical devices you provide?' | is_medical=True | 
knowledge_found=False | dynamic_found=True | fallback=False | saved=True(insert) | times_asked=1
```

---

#### Test 4: Off-Topic Query (Should NOT be stored)
**Input:**
```
User: What is the weather today?
```

**Response:**
```
This platform is designed only for Medical devices and healthcare-related queries.

Please contact our support team for further assistance.
```

**Expected Unknown Queries Record:**
❌ **NOT STORED** (fails healthcare filter in `analytics_logger.py`)

**Log Output:**
```
[unknown] query='What is the weather today?' | is_medical=False | 
knowledge_found=False | dynamic_found=False | fallback=False | saved=False | times_asked=0
```

---

#### Test 5: Duplicate Healthcare Query (Deduplication Test)
**First Request:**
```
User: What medicine should I take for fever?
```

**Second Request (same query):**
```
User: What medicine should I take for fever?
```

**Expected Unknown Queries Record:**
| Column | Value |
|--------|-------|
| query | What medicine should I take for fever? |
| user | Guest |
| date | 2026-07-22 20:xx:xx |
| time | 20:xx:xx (updated to latest) |
| **times_asked** | **2** (incremented) |
| reason | No Knowledge Match |
| status | Pending |

**Log Output (second request):**
```
[unknown] query='What medicine should I take for fever?' | is_medical=True | 
knowledge_found=False | dynamic_found=False | fallback=False | saved=True(update) | times_asked=2
```

---

## Issue 2: Contact Request Type Detection

### Root Cause
**Problem:** Every contact request was stored with:
- Reason: `General Inquiry`
- Submission Type: `General Support`

This happened because:
1. Frontend forms did NOT pass `reason` or `submission_type` fields
2. Backend defaulted to "General Inquiry" / "General Support" when missing
3. No differentiation between Pricing, Sample Report, and General Support forms

### Fix Applied

#### Backend (models.py)
Already supported optional fields:
```python
class ContactRequest(BaseModel):
    reason:          Optional[str] = "General Inquiry"
    submission_type: Optional[str] = "General Support"
```

#### Frontend Changes

**1. ContactForm.jsx**
- Now accepts `reason` and `submissionType` props
- Passes them to the API:
```javascript
await axios.post("/contact", {
  name, email, message,
  reason: reason || "General Inquiry",
  submission_type: submissionType || "General Support",
});
```

**2. ContactPage.jsx**
- Passes explicit values for general support form:
```javascript
await axios.post("/contact", {
  ...form,
  reason: "General Support",
  submission_type: "General Inquiry",
});
```

**3. FloatingChatbot.jsx**
- Added `contactFormType` state: `"pricing" | "sample" | "general"`
- Updated 3 button triggers:
  - Purchase Intent → `setContactFormType("pricing")`
  - Sample Report → `setContactFormType("sample")`
  - Out-of-Scope → `setContactFormType("general")`
- Updated `ContactFormInline` with type mapping:
```javascript
const _typeMap = {
  pricing: { reason: "Pricing / Purchase", submission_type: "Pricing Inquiry" },
  sample:  { reason: "Sample Report",      submission_type: "Sample Report Request" },
  general: { reason: "General Support",    submission_type: "General Inquiry" },
};
```

### Test Scenarios & Expected Results

#### Test 1: Pricing / Purchase Contact Form
**User Action:**
1. Ask chatbot: "How much does PageWriter TC50 cost?"
2. Chatbot responds with purchase intent reply
3. Click "📬 Contact Support" button
4. Fill form and submit

**Expected contact_requests Record:**
| Column | Value |
|--------|-------|
| name | Dr. Rajesh Kumar |
| email | rajesh@hospital.com |
| phone | +91 98765 43210 |
| hospital | AIIMS Delhi |
| message | Interested in purchasing 5 units |
| **reason** | **Pricing / Purchase** |
| **submission_type** | **Pricing Inquiry** |
| status | Pending |
| created_at | 2026-07-22 20:xx:xx |

---

#### Test 2: Sample Report Contact Form
**User Action:**
1. Ask chatbot: "Can you provide a sample ECG report?"
2. Chatbot responds with sample report intent reply
3. Click "📬 Get Sample Report" button
4. Fill form and submit

**Expected contact_requests Record:**
| Column | Value |
|--------|-------|
| name | Dr. Priya Sharma |
| email | priya@clinic.com |
| phone | +91 87654 32109 |
| hospital | Max Healthcare |
| message | Need sample ECG reports for evaluation |
| **reason** | **Sample Report** |
| **submission_type** | **Sample Report Request** |
| status | Pending |
| created_at | 2026-07-22 20:xx:xx |

---

#### Test 3: General Support Contact Form
**User Action:**
1. Navigate to Contact Page (website)
2. Fill contact form
3. Submit

**Expected contact_requests Record:**
| Column | Value |
|--------|-------|
| name | Dr. Amit Verma |
| email | amit@hospital.com |
| phone | +91 76543 21098 |
| hospital | Fortis Hospital |
| message | General inquiry about device specifications |
| **reason** | **General Support** |
| **submission_type** | **General Inquiry** |
| status | Pending |
| created_at | 2026-07-22 20:xx:xx |

---

#### Test 4: Out-of-Scope Query Contact Form
**User Action:**
1. Ask chatbot: "What medicine should I take for fever?"
2. Chatbot responds with out-of-scope reply
3. Click "📬 Contact Support" button
4. Fill form and submit

**Expected contact_requests Record:**
| Column | Value |
|--------|-------|
| name | Dr. Neha Gupta |
| email | neha@healthcare.com |
| phone | +91 65432 10987 |
| hospital | Apollo Hospital |
| message | Need help with medical device selection |
| **reason** | **General Support** |
| **submission_type** | **General Inquiry** |
| status | Pending |
| created_at | 2026-07-22 20:xx:xx |

---

## Admin Portal Display Verification

### Unknown Queries Tab
After the fix, the admin should see:

**Before:**
- Empty or only showing non-medical queries
- Medical out-of-scope queries were missing

**After:**
| Query | User | Date | Time | Times Asked | Reason | Status |
|-------|------|------|------|-------------|--------|--------|
| What medicine should I take for fever? | Guest | 2026-07-22 | 20:30:15 | 2 | No Knowledge Match | Pending |
| Tell me about MRI machine brands | Guest | 2026-07-22 | 20:31:22 | 1 | Unknown Device | Pending |
| What are the medical devices you provide? | Guest | 2026-07-22 | 20:32:10 | 1 | Outside Product Scope | Pending |

**NOT shown:**
- "What is the weather today?" (filtered out - not medical)
- "Tell me a joke" (filtered out - not medical)
- "Python programming tutorial" (filtered out - not medical)

---

### Contact Requests Tab
After the fix, the admin should see:

**Before:**
| Name | Email | Reason | Submission Type | Status |
|------|-------|--------|----------------|--------|
| Dr. Rajesh Kumar | rajesh@hospital.com | **General Inquiry** | **General Support** | Pending |
| Dr. Priya Sharma | priya@clinic.com | **General Inquiry** | **General Support** | Pending |
| Dr. Amit Verma | amit@hospital.com | **General Inquiry** | **General Support** | Pending |

**After:**
| Name | Email | Reason | Submission Type | Status |
|------|-------|--------|----------------|--------|
| Dr. Rajesh Kumar | rajesh@hospital.com | **Pricing / Purchase** | **Pricing Inquiry** | Pending |
| Dr. Priya Sharma | priya@clinic.com | **Sample Report** | **Sample Report Request** | Pending |
| Dr. Amit Verma | amit@hospital.com | **General Support** | **General Inquiry** | Pending |

---

## Files Modified

### Backend
1. **backend/app.py** (4 additions)
   - Line ~406: Added `log_unanswered_query()` to `/chat` OOS guard
   - Line ~479: Added `log_unanswered_query()` to `/chat` OOS sentinel
   - Line ~790: Added `log_unanswered_query()` to `/chat/stream` OOS guard
   - Line ~870: Added `log_unanswered_query()` to `/chat/stream` OOS sentinel

### Frontend
1. **frontend/src/components/ContactForm.jsx**
   - Accept `reason` and `submissionType` props
   - Pass them to API request

2. **frontend/src/pages/ContactPage.jsx**
   - Include `reason: "General Support"` and `submission_type: "General Inquiry"` in API request

3. **frontend/src/components/FloatingChatbot.jsx**
   - Added `contactFormType` state
   - Updated 3 button handlers to set correct type
   - Updated `ContactFormInline` to accept and map `contactFormType` to reason/submission_type

---

## Important Notes

### Issue 1 - Unknown Queries
✅ **Working as expected if:**
- Medical/healthcare queries that receive fallback responses appear in Unknown Queries
- Off-topic queries (weather, sports, movies) are NOT stored
- Duplicate queries increment `times_asked` instead of creating new rows
- `reason` column shows: "No Knowledge Match", "Unknown Device", or "Outside Product Scope"

❌ **Still broken if:**
- Medical queries don't appear
- Off-topic queries appear in the table
- Every query creates a new row (deduplication not working)

### Issue 2 - Contact Request Type
✅ **Working as expected if:**
- Contact requests from pricing/purchase flow show "Pricing / Purchase" / "Pricing Inquiry"
- Contact requests from sample report flow show "Sample Report" / "Sample Report Request"
- Contact requests from general support show "General Support" / "General Inquiry"

❌ **Still broken if:**
- All requests still show "General Inquiry" / "General Support"
- Wrong categorization (e.g., pricing showing as sample report)

---

## Verification Commands

### Check Unknown Queries Table
```sql
SELECT query, user_id, is_guest, times_asked, reason, status, last_asked_at
FROM unanswered_queries
ORDER BY last_asked_at DESC
LIMIT 20;
```

### Check Contact Requests Table
```sql
SELECT name, email, reason, submission_type, status, created_at
FROM contact_requests
ORDER BY created_at DESC
LIMIT 20;
```

### Check Backend Logs
```bash
# Look for [unknown] log entries
grep "\\[unknown\\]" backend/logs/search_logs.txt

# Should show:
# [unknown] query='...' | is_medical=True/False | ... | saved=True/False | times_asked=N
```

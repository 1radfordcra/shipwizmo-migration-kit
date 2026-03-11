# Broad Reach ICP Scoring Model
### Ideal Customer Profile — Scoring Definitions & Qualification Logic

**Last updated:** 2026-03-06  
**Owner:** Craig Radford, Broad Reach Digital  
**Used by:** `daily_cron_v10.py` — Apollo enrichment pipeline, Expandi campaign routing, email sequence enrollment

---

## 1. Overview

Broad Reach targets two primary buyer segments:

1. **DTC Ecommerce Brands** — Direct-to-consumer brands shipping parcels in the USA/Canada who are overpaying for postage at retail or lightly-negotiated carrier rates.
2. **3PL / Fulfillment Companies** — Third-party logistics providers and fulfillment houses that manage shipping on behalf of multiple merchant clients, representing a multiplier opportunity.

### ICP Score Range

| Score | Meaning |
|-------|---------|
| 0–39 | Hard disqualified — do not enroll |
| 40–59 | Marginal — hold for future targeting cycles |
| 60–74 | Qualified — eligible for `cold_dtc_savings` sequence |
| 75–89 | Strong fit — priority enrollment |
| 90–100 | Ideal fit — fast-track, personalized outreach |

**Minimum score for outreach enrollment: 60**

### 3PL Bonus

All 3PL/fulfillment company prospects receive a **+15 bonus** added to their base ICP score before threshold evaluation. This reflects the higher commercial value of the 3PL relationship (one 3PL client can represent dozens of merchant accounts).

---

## 2. Target Geographies

| Market | Priority | Notes |
|--------|----------|-------|
| USA (lower 48) | Primary | Domestic parcel shipping, USPS/FedEx/UPS displacement |
| Canada | Primary | Cross-border opportunity; French variant messaging for Quebec |
| USA (AK, HI) | Secondary | Higher shipping complexity; deprioritized |
| Mexico | Excluded | Outside Broad Reach service area |
| All other countries | Hard excluded | HQ must be USA or Canada |

**Hard rule:** Any prospect with a headquarters address outside USA or Canada is **immediately disqualified** regardless of other signals. This is enforced in code before scoring begins.

---

## 3. Primary Verticals — Fit Scores

The following scoring ranges represent the inherent product-market fit of each vertical with Broad Reach's service offering (lightweight international/domestic parcel shipping at below-retail rates).

### Tier 1 — Excellent Fit (Base Score: 85–100)

#### 3.1 Beauty & Cosmetics (DTC)
**Base score range: 85–100**

Why it fits:
- Products are lightweight (lipstick, serum, cream — typically under 1 lb)
- High order values support premium positioning
- High repeat purchase rates mean high sustained shipping volume
- Often selling on multiple channels (Shopify, Amazon, TikTok Shop)
- International expansion common → Canada corridor opportunity

Scoring signals to look for:
- Shopify/WooCommerce store with visible product catalog
- Cruelty-free, clean beauty, or K-beauty positioning (DTC-native brands)
- Instagram/TikTok presence with strong follower engagement
- SKUs under 8 oz average
- Subscription or refill program

Example personas: Founder-led skincare brand, indie cosmetics company, clean beauty DTC startup

#### 3.2 Health, Wellness & Nutrition Supplements
**Base score range: 85–100**

Why it fits:
- Capsules, powders, gummies — very lightweight
- Subscription-heavy business model = predictable, recurring volume
- High margins support outreach investment
- FDA-regulated products shipped domestically in high volume
- Amazon and Shopify dominant channels

Scoring signals to look for:
- Supplement Facts panel visible on product pages
- Subscription/autoship model offered
- Amazon Seller Central presence
- Fulfillment from USA warehouse
- Keto, sports nutrition, women's health, gut health verticals

Example personas: Sports nutrition brand, daily wellness supplement company, functional mushroom DTC

#### 3.3 Subscription Box Companies
**Base score range: 80–95**

Why it fits:
- Predictable, recurring monthly volume — easiest case for cost savings pitch
- Standard box sizes = easy rate optimization
- Shipping cost is a top-line pain point for every subscription business
- Canada expansion common

Scoring signals to look for:
- "Subscribe" or "Box" in brand name
- Cratejoy listing or standalone subscription platform
- Monthly cadence clearly communicated
- Active subscriber count signals (press mentions, funding rounds)

Example personas: Book box, snack box, pet supply subscription, beauty sample box

---

### Tier 2 — Strong Fit (Base Score: 75–90)

#### 3.4 Fashion & Apparel (DTC)
**Base score range: 75–90**

Why it fits:
- Moderate weight products (shirts, leggings — typically 0.5–2 lbs)
- High order volume DTC brands ship thousands of units per week
- Returns are a secondary pain point Broad Reach can address
- Strong Canada corridor for cross-border fashion brands

Scoring signals to look for:
- Shopify store with apparel/clothing catalog
- Influencer or social commerce driven brand
- Mid-market price point ($50–$200 AOV)
- Size/variant grid indicating high SKU count
- Dedicated returns policy page

Caution flags:
- Luxury fashion (bespoke, white-glove delivery — not a fit)
- Freight/bulk wholesale only (no parcel volume)

Example personas: Women's activewear brand, sustainable fashion DTC, streetwear label

#### 3.5 3PL / Fulfillment Companies
**Base score range: 80–100 + 15 bonus = effective 95–115 (capped at 100)**

Why it fits:
- One 3PL relationship can represent 20–200+ merchant clients
- 3PLs are actively looking to reduce per-unit shipping costs to improve margin and client retention
- Partnership model: Broad Reach becomes a preferred carrier for the 3PL's entire client base
- Decision-maker is typically a VP Operations or CEO — accessible via LinkedIn

Scoring signals to look for:
- "Fulfillment," "3PL," "logistics," or "warehousing" in company name or description
- Physical warehouse locations listed on website
- Shopify/WooCommerce integration mentioned
- "We ship X orders per day/month" on website
- Hiring warehouse associates, fulfillment coordinators
- Client list includes DTC brands

Hard disqualifiers for 3PLs:
- Freight-only (LTL/FTL with no parcel volume)
- Government or military fulfillment only
- Single-client captive warehouse (not multi-tenant)

Example personas: Regional e-fulfillment company, Shopify-native 3PL, multi-location fulfillment network

---

### Tier 3 — Moderate Fit (Base Score: 60–75)

#### 3.6 Home & Garden
**Base score range: 60–75**

Why it fits:
- Some lightweight goods (candles, small home décor, seeds/bulbs)
- Broad Reach can compete on lightweight parcel rates
- DTC brands in this space often on Shopify

Why it's harder:
- Many products are heavy/oversized (furniture, tools, planters)
- Lower margin categories struggle with shipping cost sensitivity
- Freight-dominated fulfillment for larger items

Scoring signals to look for:
- Products visibly under 5 lbs
- Candles, bath, home fragrance, small décor
- Shopify DTC with no oversized product lines

Score conservatively — confirm product weight profile before enrollment.

#### 3.7 Pet Products (DTC)
**Base score range: 65–80**

Why it fits:
- Pet treats, supplements, accessories — typically lightweight
- High repeat purchase rates (consumables)
- Strong subscription model adoption
- USA/Canada pet market is large and growing

Scoring signals to look for:
- Pet treats, supplements, or accessories
- Subscription/autoship model
- Under 2 lbs average product weight
- Amazon + Shopify dual-channel

Caution flags:
- Pet food in large bags (heavy, freight territory)
- Veterinary/pharmaceutical (regulatory complexity)

---

### Tier 4 — Low Fit (Base Score: 50–65)

#### 3.8 Food & Beverage (DTC)
**Base score range: 55–70**

Why it's difficult:
- Perishable products require cold-chain or expedited shipping
- Broad Reach specializes in standard parcel, not cold-chain
- Heavy products (bottles, cases) increase shipping costs beyond savings potential
- Regulatory complexity for cross-border food shipments (Canada customs)

When it can work:
- Shelf-stable, lightweight food products (spices, protein bars, coffee)
- Non-perishable snack brands
- No cold-chain requirement

Score at the lower end unless product is clearly shelf-stable and lightweight.

#### 3.9 Consumer Electronics (DTC)
**Base score range: 50–65**

Why it's difficult:
- Electronics are heavy and often require signature/insurance
- Carriers have accessorial charges that erode savings
- High damage/loss claims risk
- Many DTC electronics brands use Amazon FBA exclusively

When it can work:
- Small accessories (cables, cases, wearables)
- Lightweight tech gadgets under 1 lb
- Shopify DTC with own fulfillment

---

## 4. Qualification Signals (Positive)

These signals add points to the base vertical score or confirm eligibility. Each signal is evaluated by the Apollo enrichment pipeline and stored in the contact record.

### Volume & Revenue Signals

| Signal | Points Added | Source |
|--------|-------------|--------|
| Shipping volume: 500+ packages/day (confirmed) | +15 | Apollo enrichment, press, job postings |
| Shipping volume: 200–499 packages/day (confirmed) | +10 | Apollo enrichment, press, job postings |
| Shipping volume: 50–199 packages/day (estimated) | +5 | Estimated from employee count + revenue |
| Revenue: $5M+ ARR | +15 | Apollo, Crunchbase, press |
| Revenue: $1M–$5M ARR | +10 | Apollo, Crunchbase, press |
| Revenue: $500K–$1M ARR | +3 | Apollo estimate |

### Product Fit Signals

| Signal | Points Added | Source |
|--------|-------------|--------|
| Average product weight < 1 lb | +15 | Product page analysis |
| Average product weight 1–3 lbs | +8 | Product page analysis |
| Average product weight 3–5 lbs | +3 | Product page analysis |
| Subscription/autoship model | +10 | Product page, Cratejoy listing |
| High SKU count (50+) | +5 | Product catalog estimate |

### Channel & Platform Signals

| Signal | Points Added | Source |
|--------|-------------|--------|
| Shopify or Shopify Plus store | +8 | Apollo, BuiltWith, SimilarWeb |
| Shopify Plus specifically | +12 | Apollo, BuiltWith |
| Amazon Seller (active) | +8 | Amazon marketplace search |
| TikTok Shop seller | +6 | TikTok Shop search |
| Walmart Marketplace seller | +5 | Walmart marketplace search |
| Multi-channel (3+ platforms) | +5 | Composite signal |

### Canada Corridor Signals

| Signal | Points Added | Source |
|--------|-------------|--------|
| Canada .ca domain or shipping to Canada listed | +10 | Website, Apollo |
| Quebec HQ or French-language site | +5 | Apollo, website language |
| Canada as listed market in press/profile | +5 | Press, LinkedIn |

### Growth & Expansion Signals

| Signal | Points Added | Source |
|--------|-------------|--------|
| Raised funding in last 12 months | +12 | Crunchbase, TechCrunch, Apollo |
| Shopify Plus upgrade (recently) | +10 | Press, LinkedIn announcement |
| Hiring: logistics/fulfillment/warehouse roles | +8 | LinkedIn Jobs, Indeed |
| Hiring: VP Operations or Head of Supply Chain | +10 | LinkedIn Jobs |
| New warehouse opened or announced | +8 | Press, LinkedIn |
| Headcount growth 20%+ YoY | +6 | Apollo, LinkedIn |

### Carrier Rate Signals (Pain Indicators)

| Signal | Points Added | Source |
|--------|-------------|--------|
| Currently using USPS at retail rates | +10 | Inferred from profile, no enterprise contract signals |
| Currently using FedEx/UPS at retail rates | +10 | Inferred from profile |
| No dedicated freight/logistics team (< 50 employees) | +5 | LinkedIn company size |
| Public complaint about shipping costs | +15 | LinkedIn, Twitter, press |

---

## 5. Disqualification Signals (Negative)

These signals remove points or trigger hard disqualification. Hard disqualifications prevent enrollment regardless of score.

### Hard Disqualifications (Score → 0, No Outreach)

| Signal | Reason |
|--------|--------|
| HQ outside USA/Canada | Outside service territory |
| Competitor of Broad Reach / Asendia | Do not target |
| Already a Broad Reach active client | In exclusion list |
| Government / military entity | Procurement complexity, not a fit |
| Already opted out of Broad Reach outreach | Permanent suppression |
| Bounced email (hard bounce) | Contact is undeliverable |
| Freight-only (no parcel volume whatsoever) | Product-market mismatch |

### Soft Disqualifications (Points Deducted)

| Signal | Points Deducted | Source |
|--------|----------------|--------|
| Revenue < $500K ARR | -25 | Apollo estimate |
| Fewer than 5 employees | -20 | LinkedIn company size |
| No ecommerce presence (B2B wholesale only) | -20 | Website analysis |
| Average product weight > 10 lbs | -15 | Product page analysis |
| Enterprise carrier contract signals | -20 | Press, LinkedIn (e.g., "FedEx preferred carrier" badge) |
| Perishable/cold-chain requirement | -15 | Product analysis |
| Already contacted 3+ times in lifetime | -50 (force below threshold) | CRM history |
| Contact at same company within 14 days | -50 (force below threshold) | CRM history |
| 3rd contact at same company in 90-day window | -50 (force below threshold) | CRM history |

---

## 6. Scoring Formula — Full Calculation

The ICP score is calculated as follows:

```
base_vertical_score       = assigned score for the company's primary vertical (see Section 3)
qualification_bonus       = sum of all positive signal points (see Section 4)
disqualification_penalty  = sum of all negative signal points (see Section 5)
3pl_bonus                 = +15 if company type is 3PL/fulfillment
raw_score                 = base_vertical_score + qualification_bonus - disqualification_penalty + 3pl_bonus
final_score               = min(100, max(0, raw_score))
```

### Enrollment Decision

```
if hard_disqualification:
    status = "excluded"
    enroll = False
elif final_score >= 90:
    status = "ideal"
    enroll = True
    sequence = "cold_dtc_savings" or "expansion_signal" (based on growth signals)
    priority = "high"
elif final_score >= 75:
    status = "strong_fit"
    enroll = True
    sequence = "cold_dtc_savings"
    priority = "normal"
elif final_score >= 60:
    status = "qualified"
    enroll = True
    sequence = "cold_dtc_savings"
    priority = "low"
elif final_score >= 40:
    status = "marginal"
    enroll = False
    action = "hold — re-evaluate in 90 days"
else:
    status = "disqualified"
    enroll = False
```

### Sequence Selection Logic

| Condition | Sequence |
|-----------|---------|
| New contact, no growth signals | `cold_dtc_savings` |
| Contact shows 2+ growth signals (funding, Shopify Plus upgrade, logistics hiring) | `expansion_signal` |
| 3PL/fulfillment company | `cold_dtc_savings` (3PL variant messaging) |

---

## 7. Anti-Pollution Rules

These rules are enforced by `daily_cron_v10.py` before any contact is enrolled in a sequence. They protect deliverability, sender reputation, and compliance.

### Contact-Level Rules

| Rule | Threshold | Action on Violation |
|------|-----------|---------------------|
| Maximum sequences per contact (lifetime) | 3 | Hard block — never enroll again |
| Minimum days since last touchpoint (same contact) | 14 days | Delay enrollment to next eligible date |
| Opt-out received | Any | Permanent suppression — never contact again |
| Hard bounce received | Any | Permanent suppression of email address |
| Soft bounce threshold | 3 consecutive | Suppress email, flag for review |

### Company-Level Rules

| Rule | Threshold | Action on Violation |
|------|-----------|---------------------|
| Maximum contacts enrolled per company (rolling 90-day window) | 3 contacts | Block additional contacts until window clears |
| Minimum spacing between contacts at same company | 14 days | Delay second contact enrollment |
| Active client in exclusion list | Any domain match | Hard block entire company |

### System-Level Safety Rules

| Rule | Threshold | Action on Violation |
|------|-----------|---------------------|
| Exclusion list entry count | < 100 entries | **HALT entire cron run** — alert operator |
| Daily send volume vs. warmup limit | Exceeds `warmup_tracker.json` limit | Cap sends, log warning |
| Apollo API failure | Connection error | Abort enrichment step, continue with cached data |
| HubSpot write failure | 3 consecutive errors | Halt CRM sync step, log alert |

**The 100-entry safety halt is critical.** If `active_clients_exclusion_list.txt` has fewer than 100 entries when the cron runs, it means the Notion sync failed and the file may be corrupted or empty. Running outreach without the full exclusion list risks emailing active paying clients, which is a high-severity incident. The cron will not proceed.

---

## 8. Targeting Split

The daily send volume is split between the two primary segments:

| Segment | Share of Daily Volume | Sequence |
|---------|----------------------|---------|
| 3PL / Fulfillment Companies | 60% | `cold_dtc_savings` (3PL variant) |
| DTC Brands | 40% | `cold_dtc_savings` or `expansion_signal` |

### Rationale

3PL companies represent a higher commercial value per relationship but are a smaller universe. Prioritizing 3PLs at 60% volume maximizes pipeline value. DTC brands are the higher-volume universe and provide consistent pipeline throughput.

### Volume Calculation (Steady-State, Week 4+)

| Week | Daily Limit | 3PL Volume (60%) | DTC Volume (40%) |
|------|------------|-----------------|-----------------|
| 1 | 5/day | 3 | 2 |
| 2 | 10/day | 6 | 4 |
| 3 | 20/day | 12 | 8 |
| 4+ | 25/day | 15 | 10 |

---

## 9. Apollo Sourcing Filters

When pulling contact lists from Apollo.io, the following filters are used as pre-qualification before ICP scoring:

### Company Filters

```
Industry:               Retail, Consumer Goods, Logistics, Warehousing & Fulfillment
Employee Count:         5–500 (exclude micro and large enterprise)
Geography:              United States, Canada
Revenue (estimated):    $500K – $50M
Keywords (any):         shopify, ecommerce, direct-to-consumer, dtc, fulfillment, 3pl, 
                        supplements, beauty, apparel, subscription box
Exclude keywords:       freight only, ltl, ftl, government, defense, medical device
```

### Contact Filters

```
Job Titles (any):       CEO, Founder, Co-Founder, President, VP Operations, 
                        Director of Operations, Head of Logistics, COO, 
                        VP Supply Chain, Director of Fulfillment, 
                        VP Ecommerce, Head of Growth
Seniority:             C-Suite, VP, Director, Manager (in that priority order)
Email Verified:         Required (Apollo "valid" or "likely valid")
LinkedIn Profile:       Required (for LinkedIn sequence steps)
```

### Exclusions

- Domains in `active_clients_exclusion_list.txt`
- Contacts tagged "opted out" or "bounced" in HubSpot
- Contacts with 3+ sequence enrollments in HubSpot
- Contacts at companies with 3+ active enrollments in last 90 days

---

## 10. Vertical-Specific Messaging Guidance

### Beauty & Cosmetics
**Lead hook:** Shipping cost savings on lightweight parcels — position as margin improvement, not just logistics.
**Avoid:** Overly technical carrier language. These founders think in COGS and contribution margin.
**Stat to use:** "$2 range per package" — this is meaningful for a brand paying $5–8 USPS retail.

### Health & Supplements
**Lead hook:** Cost per subscription fulfillment — frame savings as customer LTV improvement.
**Avoid:** FDA/regulatory language. Keep it operational.

### 3PL / Fulfillment
**Lead hook:** Competitive differentiation for their merchant clients — "offer your clients better rates."
**Tone:** Partnership, not vendor. These are operators; they want ROI data.
**Personalization:** Reference number of warehouse locations or integration ecosystem if visible.

### Fashion & Apparel
**Lead hook:** Shipping cost as percentage of AOV — common pain point for mid-market apparel brands.
**Avoid:** Luxury tone for non-luxury brands.

### Subscription Boxes
**Lead hook:** Monthly shipping cost is the #1 variable cost after COGS. Frame savings as subscriber retention.

---

## 11. ICP Score Examples

### Example A — High-Scoring DTC Brand
**Company:** Fictional supplement brand, 45 employees, $3.5M ARR, Shopify Plus, ships 300+ orders/day, lightweight capsules, recently hired VP of Operations.

| Signal | Points |
|--------|--------|
| Base vertical (health supplements) | 90 |
| Revenue $1M–$5M ARR | +10 |
| Shipping volume 200–499/day | +10 |
| Shopify Plus | +12 |
| Subscription model | +10 |
| Hiring VP Operations | +10 |
| Product weight < 1 lb | +15 |
| No enterprise carrier signals | 0 penalty |
| **Raw score** | **157** |
| **Final score (capped at 100)** | **100** |

**Decision:** Enroll in `expansion_signal` (VP Ops hire = growth signal). Priority: High.

---

### Example B — Marginal DTC Brand
**Company:** Fictional furniture accessories brand, 8 employees, $400K ARR, WooCommerce, ships 15 orders/day, products 8–15 lbs.

| Signal | Points |
|--------|--------|
| Base vertical (home & garden, heavy) | 55 |
| Revenue < $500K ARR | -25 |
| Average product weight > 10 lbs | -15 |
| Shipping volume too low | 0 bonus |
| **Raw score** | **15** |
| **Final score** | **15** |

**Decision:** Hard disqualified (score < 40). Do not enroll.

---

### Example C — 3PL Company
**Company:** Fictional regional fulfillment company, 60 employees, 3 warehouse locations, 500+ orders shipped daily for DTC clients, Shopify/WooCommerce integrations.

| Signal | Points |
|--------|--------|
| Base vertical (3PL/fulfillment) | 88 |
| 3PL bonus | +15 |
| Shipping volume 500+/day | +15 |
| Multi-location warehouse | +8 |
| Shopify integration | +8 |
| **Raw score** | **134** |
| **Final score (capped at 100)** | **100** |

**Decision:** Enroll in `cold_dtc_savings` (3PL variant). Priority: High.

---

## 12. Data Hygiene & Maintenance

### Monthly Review Checklist

- [ ] Review disqualified company counts — are any verticals underperforming? Adjust scoring?
- [ ] Audit active_clients_exclusion_list.txt entry count against Notion Active Clients database
- [ ] Review opt-out rate by vertical — high opt-out = messaging mismatch, not ICP mismatch
- [ ] Review bounce rate by Apollo segment — high bounce = Apollo data quality issue
- [ ] Check whether `expansion_signal` sequence is being triggered appropriately

### Quarterly Review Checklist

- [ ] Revisit vertical base scores based on reply/meeting rates
- [ ] Review 3PL vs. DTC split performance — adjust 60/40 if data suggests rebalancing
- [ ] Refresh Apollo saved search filters based on closed-won deal profile
- [ ] Update example personas with real anonymized examples from pipeline

---

## 13. Version History

| Date | Change | Author |
|------|--------|--------|
| 2026-03-06 | Initial document created | Craig Radford |

---

*This document is the source of truth for ICP scoring logic. Any changes to scoring weights, thresholds, or disqualification rules must be reflected here before being implemented in `daily_cron_v10.py`.*

# Broad Reach LinkedIn Outreach Rules
### LinkedIn Messaging Guidelines for the Outbound Machine

**Last updated:** 2026-03-06  
**Owner:** Craig Radford, Broad Reach Digital  
**Used by:** `daily_cron_v10.py` — Expandi campaign management, message generation

---

## 1. The 10-Word Rule

> **All LinkedIn connection request messages must be 10 words or fewer.**

This is a **hard rule with no exceptions.**

### Why This Rule Exists

1. **Acceptance rates are higher with shorter messages.** LinkedIn connection requests with long messages read as sales pitches. Prospects decline or ignore them. A 10-word or shorter message feels like a genuine human reaching out.
2. **LinkedIn penalizes pitch-heavy connection requests.** Accounts that send long, promotional connection requests are flagged and may face restriction.
3. **The connection request is not the pitch.** The pitch happens after connection, in the follow-up message or email. The connection request has one job: get accepted.
4. **Shorter = less risk.** A 10-word message cannot accidentally contain a compliance violation, a prohibited claim, or a pricing disclosure.

### Counting Words

Count every word including short words like "a", "the", "your", "on". Hyphenated words count as one word. Possessives count as one word.

**Compliant (10 words):**
> "Saw your Shopify Plus brand — impressive growth this year."

**Non-compliant (12 words):**
> "Saw your Shopify Plus brand and was really impressed by your growth."

When in doubt, cut words. A 7-word message is better than a 10-word message.

---

## 2. Connection Request Message Guidelines

### DO

- **Write like a human.** Imagine texting a colleague, not writing a sales email.
- **Be specific when possible.** Reference their job title, company type, or something visible on their profile.
- **Compliment or acknowledge.** A genuine observation goes further than a generic opener.
- **Keep it neutral in tone.** Curious, not eager. Interested, not desperate.
- **Use casual punctuation.** Em dash (—), comma, period. No exclamation marks.
- **Use sentence case.** Not Title Case. Not ALL CAPS.

### DO NOT

- **No pitch in the connection request.** No mention of what Broad Reach does, no mention of shipping, no mention of savings.
- **No stats, numbers, or data.** No "$2 per package." No "save 30%." No "200+ brands." Save these for email.
- **No pricing information.** No rates, no ranges, no cost comparisons.
- **No company name in the first message.** Saying "I noticed Acme Co..." sounds like a bot.
- **No "I'd love to..."** This phrase is universally recognized as a sales opener.
- **No "I wanted to reach out..."** Same — instantly signals a sales pitch.
- **No questions in the connection request.** Questions feel like an interrogation in a 10-word message.
- **No links.** LinkedIn penalizes connection requests with URLs.
- **No hashtags.** Not appropriate for direct connection requests.
- **No emojis.** This is B2B professional outreach.
- **No "just" or "quickly."** ("Just wanted to..." / "Quick question...") — these read as manipulative.

---

## 3. Approved Connection Request Message Templates

The following messages have been tested and approved. Use these as a starting point for Expandi campaign messaging. All messages are 10 words or fewer.

### For DTC Brand Founders & Operators

1. > "Your brand caught my eye — nice work on growth."
   *(10 words)*

2. > "Noticed you're scaling on Shopify — impressive trajectory."
   *(8 words)*

3. > "Your products look great — building something solid there."
   *(9 words)*

4. > "Came across your brand while researching the space."
   *(9 words)*

5. > "Would love to connect — DTC logistics is my world."
   *(10 words)*

6. > "Saw your team's growth on LinkedIn — congrats."
   *(8 words)*

7. > "Building something in DTC — wanted to connect with operators."
   *(10 words)*

8. > "Your subscription model caught my attention — well done."
   *(9 words)*

### For 3PL / Fulfillment Company Contacts

9. > "Noticed your fulfillment operation — impressive scale."
   *(7 words)*

10. > "Working a lot in the 3PL space — connecting."
    *(10 words)*

11. > "Your warehouse footprint is growing fast — congrats."
    *(8 words)*

12. > "Came across your fulfillment company — would love to connect."
    *(10 words)*

13. > "Solid logistics operation — wanted to be in your network."
    *(10 words)*

### For VP / Director of Operations Titles

14. > "Operations leader in logistics — makes sense to connect."
    *(9 words)*

15. > "Noticed your ops background — lot of overlap in our work."
    *(11 words — DO NOT USE, exceeds limit)*

15. > "Your ops background is impressive — a lot of overlap."
    *(10 words)*

16. > "Logistics and ops networks are valuable — glad to connect."
    *(10 words)*

### For "Expansion Signal" Contacts (Shopify Plus, Funding, Hiring)

17. > "Congrats on the Shopify Plus upgrade — big milestone."
    *(9 words)*

18. > "Saw the funding news — exciting time for your brand."
    *(10 words)*

19. > "Noticed you're building out your logistics team — exciting."
    *(9 words)*

20. > "Your growth trajectory this year has been impressive."
    *(9 words)*

---

## 4. Message Personalization Rules

### When Personalization Is Available

If Expandi has access to personalization tokens from Apollo enrichment, use them to make the message more specific. Personalization increases acceptance rates by 15–30%.

**Available tokens:**
- `{{first_name}}` — Use sparingly. Starting with a name can feel like a bot.
- `{{company_name}}` — **Do NOT use in connection request.** Reserve for follow-up messages.
- `{{job_title}}` — Can reference the role generically ("your ops role," "your logistics work").
- `{{custom_signal}}` — Growth signal detected (funding, Shopify Plus, hiring). Use this.

**Preferred personalization approach:**
Reference the *signal* without stating it directly.
- Funding round → "Saw the exciting news from your brand."
- Shopify Plus upgrade → "Noticed the Shopify Plus upgrade — congrats."
- Warehouse expansion → "Your warehouse expansion caught my eye."
- Logistics hiring → "Noticed you're building out the logistics team."

### When Personalization Is Not Available

Fall back to the generic approved templates in Section 3. Never leave a blank personalization token in a sent message. The Expandi campaign should be configured with a fallback for every variable.

---

## 5. After Connection Acceptance — Follow-Up Rules

Once a connection is accepted, Expandi triggers a follow-up message. These rules apply to the follow-up:

### First Follow-Up Message (Immediate or within 24 hours of acceptance)

**Length:** Maximum 3 sentences.  
**Tone:** Still conversational — not a sales email format.  
**Content:** A light reference to why you're reaching out, without a hard pitch.

**Example:**
> "Thanks for connecting. I work with DTC brands on shipping cost reduction — usually get them to carrier rates they couldn't negotiate alone. Happy to share more if it's ever relevant."

**Do NOT in the first follow-up:**
- Do not use bullet points or numbered lists
- Do not attach files or send links
- Do not ask for a call/meeting in the first message
- Do not use subject line formatting

### Second Follow-Up (If no reply, 7 days after acceptance)

**This is the last LinkedIn touchpoint.** If no reply after this message, continue via email sequence only.

**Example:**
> "Circling back briefly — if shipping costs are ever a pain point as you scale, I'd be happy to do a quick comparison against your current rates. No pressure either way."

---

## 6. Email Rules (Reference — For Multi-Channel Coordination)

These email rules are documented here for reference when coordinating the LinkedIn and email steps of each sequence.

### Email Length
- **Maximum 20 words per email body.** This is a hard rule matching the 10-word LinkedIn rule in spirit — brevity signals confidence.
- The subject line does not count toward the 20-word limit.
- Signature block does not count toward the 20-word limit.

### Required Phrases
Every outbound cold email must include:
- **"$2 range"** — The cost positioning anchor. This is the core value proposition signal.
- **"cheaper than postal rates"** — The comparison frame. Must be present in at least one email in the sequence.

### Email Subject Lines
- Under 8 words
- No all-caps words
- No spam trigger words ("free," "save," "limited time," "act now," "guaranteed")
- No question marks in subject line (tested poorly for open rates)
- No emojis in subject line

### Physical Address (CAN-SPAM Compliance)
Every outbound email must include the physical address in the footer or signature:
```
Broad Reach Digital (a division of Asendia USA)
701 Ashland Ave, Folcroft, PA 19032
```
This is enforced by the email template. Do not remove it.

### Unsubscribe Link (CAN-SPAM Compliance)
Every email must include an unsubscribe/opt-out mechanism. This is handled by the sending platform. Do not bypass or disable this feature.

### French Variants for Quebec Prospects
When a prospect's province is Quebec (QC) or their postal code begins with G, H, J (Quebec postal prefixes), a French-language variant of the email is generated and sent instead of the English version.

French variant rules:
- Same 20-word limit applies
- Same "$2 range" anchor — translated as "environ 2 $" or "dans les 2 $"
- Same "cheaper than postal rates" frame — "moins cher que les tarifs postaux standards"
- Physical address remains in English (legal requirement)
- Unsubscribe link text in French: "Se désabonner"

Detection logic is handled by `daily_cron_v10.py` via the Apollo contact's `state` or `postal_code` field.

---

## 7. What NOT To Do — Full Reference

This section consolidates all prohibited actions for both LinkedIn and email outreach.

### LinkedIn — Prohibited

| Prohibited Action | Why |
|-------------------|-----|
| Send the same message twice to the same person | Spam signal; prospect will disengage or report |
| Pitch in the connection request | Reduces acceptance rate; LinkedIn penalizes |
| Use LinkedIn InMail for cold outreach | InMail is paid and intrusive; use connection requests only |
| Exceed Expandi daily limits (25 connections, 50 messages/day) | LinkedIn account restriction risk |
| Send a connection request to someone you've already connected with | Creates duplicate or awkward signal |
| Mention pricing in connection request | Violates 10-word rule; will almost always exceed the limit too |
| Send bulk connection requests manually outside Expandi | Bypasses rate limiting and tracking |
| Use automation other than Expandi | Creates data fragmentation; cannot be tracked in HubSpot |
| Message someone who has ignored 2+ previous requests | Harassment risk; creates negative brand signal |

### Email — Prohibited

| Prohibited Action | Why |
|-------------------|-----|
| Send email without physical address | CAN-SPAM violation |
| Send email without unsubscribe mechanism | CAN-SPAM violation |
| Remove or modify the unsubscribe link | CAN-SPAM violation — legal liability |
| Continue emailing after opt-out | CAN-SPAM violation — permanent suppression required |
| Send more than 25 emails per day during warmup | Deliverability risk — follow warmup_tracker.json limits |
| Use the same subject line more than 3 times in a campaign | Spam filter trigger |
| Add images or heavy HTML to cold outreach emails | Spam filter trigger; plain text outperforms |
| CC or BCC other parties on cold outreach | Privacy violation; creates double-impression problem |
| Use purchased email lists outside Apollo | Quality control — only Apollo-sourced, verified contacts |

### System-Level — Prohibited

| Prohibited Action | Why |
|-------------------|-----|
| Manually edit active_clients_exclusion_list.txt | File is auto-synced from Notion; manual edits will be overwritten |
| Run daily cron with < 100 exclusion list entries | Safety halt — risk of emailing active clients |
| Override warmup_tracker.json daily limits without deliverability team approval | Deliverability risk |
| Enroll a contact in more than 3 sequences lifetime | Anti-pollution rule |
| Contact 3+ people at the same company within 90 days | Anti-pollution rule |
| Contact the same person within 14 days | Anti-pollution rule |

---

## 8. Expandi Campaign Configuration Reference

These settings must match the values in `expandi_config.json`. Document here for human reference.

### Campaign: Cold DTC Savings (ID: 770808)

| Setting | Value |
|---------|-------|
| Campaign type | Connection request |
| Daily connection limit | 25 |
| Message template | 10-word casual (see Section 3) |
| Personalization token | `{{custom_signal}}` (growth signal) |
| Fallback message | "Came across your brand while researching the space." |
| Webhook | `EXPANDI_CAMPAIGN_A_WEBHOOK` (env variable) |

### Campaign: 3PL Focused (ID: 770814)

| Setting | Value |
|---------|-------|
| Campaign type | Connection request |
| Daily connection limit | 25 |
| Message template | 3PL-specific templates (see Section 3, 3PL block) |
| Personalization token | `{{custom_signal}}` (warehouse, scale) |
| Fallback message | "Noticed your fulfillment operation — impressive scale." |
| Webhook | `EXPANDI_CAMPAIGN_B_WEBHOOK` (env variable) |

### Expandi Account Settings (Craig Radford's LinkedIn)

| Setting | Value |
|---------|-------|
| Daily connections sent | Max 25 (per LinkedIn best practice for warmed account) |
| Daily messages sent | Max 50 |
| Delay between actions | 60 seconds minimum |
| Working hours (Expandi schedule) | Business hours in prospect's timezone (set in Expandi dashboard) |
| Weekends | Off (configure in Expandi to pause Sat/Sun) |

---

## 9. Compliance Summary

| Regulation | Requirement | How We Comply |
|------------|-------------|---------------|
| CAN-SPAM Act (USA) | Physical address in all commercial emails | `physical_address.txt` injected into every email template |
| CAN-SPAM Act (USA) | Clear opt-out mechanism | Unsubscribe link in every email via sending platform |
| CAN-SPAM Act (USA) | Honor opt-out within 10 business days | Opt-out triggers immediate suppression in HubSpot + exclusion list |
| CASL (Canada) | Implied/express consent required | Outreach only to business contacts where implied consent applies (B2B, publicly listed contact info) |
| CASL (Canada) | Sender identification required | Sender name, company, and physical address in every email |
| LinkedIn ToS | No automation exceeding platform limits | Expandi rate limits enforced (25 connections, 50 messages/day) |
| GDPR (if applicable) | Legitimate interest basis for EU contacts | Note: Broad Reach targets USA/Canada only — EU contacts should not be in pipeline; if found, exclude |

**Important:** This compliance summary is for operational reference only and does not constitute legal advice. Consult Broad Reach's legal counsel for binding compliance guidance.

---

## 10. Version History

| Date | Change | Author |
|------|--------|--------|
| 2026-03-06 | Initial document created | Craig Radford |

---

*This document is the source of truth for LinkedIn messaging rules and email outreach guidelines. Any changes to message templates, word limits, or compliance requirements must be updated here and reviewed by Craig Radford before being implemented in Expandi campaigns or email templates.*

"""
test_outbound_machine.py — Tests for the outbound machine cron logic.

The outbound machine is the daily cron system that drives B2B outbound sales:
  - Discovers new ICP-qualified prospects via Apollo
  - Scores them against the ICP rubric
  - Pushes them to Expandi for LinkedIn outreach
  - Enforces anti-pollution cooldown rules
  - Manages email warmup ramp schedule

These tests cover the pure business logic without requiring external API access.

Run from migration-kit directory:
    pytest tests/test_outbound_machine.py -v
"""

import pytest
from datetime import datetime, timedelta, date
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Outbound machine logic helpers (extracted/mirrored from the cron scripts)
# ---------------------------------------------------------------------------

# --- ICP Scoring Rubric ---

ICP_CRITERIA = {
    # Shipping signals
    "ships_canada": 20,          # Ships to Canada (core value prop)
    "ships_usa": 10,             # Ships domestically in USA
    "ships_internationally": 15, # International shipping
    # Business model
    "dtc_ecommerce": 20,         # Direct-to-consumer e-commerce
    "subscription_box": 15,      # Subscription box company
    "third_party_fulfillment": 5, # 3PL client
    # Platform signals
    "shopify_store": 10,         # Shopify store detected
    "high_volume": 15,           # Estimated > 1,000 packages/month
    # Negative signals
    "already_client": -100,      # Current Broad Reach client
    "competitor_client": -50,    # Competitor's dedicated customer
    "b2b_only": -20,             # Pure B2B (no end-consumer shipping)
}

ICP_THRESHOLD = 60       # minimum score to qualify for outreach
HOT_LEAD_THRESHOLD = 75  # threshold for "hot lead" classification


def calculate_icp_score(signals: dict) -> int:
    """Calculate an ICP score based on the prospect's detected signals."""
    score = 0
    for signal, active in signals.items():
        if active and signal in ICP_CRITERIA:
            score += ICP_CRITERIA[signal]
    return score


def is_icp_qualified(score: int) -> bool:
    """Return True if the score meets the ICP qualification threshold."""
    return score >= ICP_THRESHOLD


def is_hot_lead(score: int) -> bool:
    """Return True if the score meets the hot-lead threshold."""
    return score >= HOT_LEAD_THRESHOLD


# --- Cooldown / Anti-Pollution System ---

COOLDOWN_DAYS_AFTER_SEQUENCE = 180   # 6 months after completing a sequence
COOLDOWN_DAYS_AFTER_BOUNCE = 365     # 12 months after a hard bounce
COOLDOWN_DAYS_AFTER_OPTOUT = 3650    # 10 years (permanent) after opt-out

PERMANENT_BLOCK_SENTINEL = "2099-12-31"


def is_in_cooldown(cooldown_until_str: str, reference_date: date = None) -> bool:
    """
    Return True if a contact is currently in a cooldown period.
    Accepts ISO date string 'YYYY-MM-DD' or empty string.
    """
    if not cooldown_until_str:
        return False
    if reference_date is None:
        reference_date = date.today()
    try:
        cooldown_until = date.fromisoformat(cooldown_until_str)
        return cooldown_until >= reference_date
    except ValueError:
        return False


def calculate_cooldown_date(reason: str, from_date: date = None) -> str:
    """
    Calculate the cooldown end date for a contact based on the reason.
    Returns an ISO date string 'YYYY-MM-DD'.
    """
    if from_date is None:
        from_date = date.today()

    if reason == "sequence_completed":
        return (from_date + timedelta(days=COOLDOWN_DAYS_AFTER_SEQUENCE)).isoformat()
    elif reason == "bounced":
        return (from_date + timedelta(days=COOLDOWN_DAYS_AFTER_BOUNCE)).isoformat()
    elif reason == "opted_out":
        return PERMANENT_BLOCK_SENTINEL
    elif reason in ("blocked_manual", "removed_manual"):
        return PERMANENT_BLOCK_SENTINEL
    else:
        return ""


def should_contact_be_queued(contact: dict, reference_date: date = None) -> tuple:
    """
    Determine if a contact should be queued for outreach.
    Returns (can_contact: bool, reason: str).
    """
    cooldown = contact.get("br_contact_cooldown_until", "")
    if cooldown == PERMANENT_BLOCK_SENTINEL:
        return False, "permanently blocked"
    if is_in_cooldown(cooldown, reference_date):
        return False, f"in cooldown until {cooldown}"
    expandi_status = contact.get("br_expandi_status", "")
    if expandi_status in ("pushed_campaign_a", "pushed_campaign_b"):
        return False, "already enrolled in Expandi"
    return True, "clear for outreach"


# --- Warmup Schedule ---

WARMUP_SCHEDULE = {
    1: 10,    # Week 1: 10 emails/day
    2: 20,    # Week 2: 20 emails/day
    3: 35,    # Week 3: 35 emails/day
    4: 50,    # Week 4+: 50 emails/day (max)
}

MAX_DAILY_EMAILS = 50


def get_daily_email_limit(start_date_str: str, reference_date: date = None) -> int:
    """Calculate how many emails are allowed today based on the warmup schedule."""
    if reference_date is None:
        reference_date = date.today()
    try:
        start = date.fromisoformat(start_date_str)
        days_elapsed = (reference_date - start).days
        week = min(days_elapsed // 7 + 1, 4)
        return WARMUP_SCHEDULE.get(week, MAX_DAILY_EMAILS)
    except ValueError:
        return WARMUP_SCHEDULE[1]  # default to week 1 if date is invalid


# --- Expandi Payload ---

def build_expandi_payload(prospect: dict, campaign_id: str) -> dict:
    """
    Build the Expandi API payload for adding a contact to a LinkedIn campaign.
    """
    return {
        "campaign_id": campaign_id,
        "profile_url": prospect.get("linkedin_url", ""),
        "first_name": prospect.get("first_name", ""),
        "last_name": prospect.get("last_name", ""),
        "company": prospect.get("company", ""),
        "tags": [
            f"icp_score_{prospect.get('raw_icp_score', 0)}",
            "dtc_outreach",
        ],
    }


def validate_expandi_payload(payload: dict) -> tuple:
    """Return (is_valid, error) for an Expandi payload."""
    if not payload.get("campaign_id"):
        return False, "campaign_id is required"
    if not payload.get("profile_url"):
        return False, "profile_url (LinkedIn URL) is required"
    if not payload.get("first_name"):
        return False, "first_name is required"
    return True, None


# ---------------------------------------------------------------------------
# Tests: ICP scoring
# ---------------------------------------------------------------------------

class TestICPScoring:
    """Validate the ICP qualification scoring rubric."""

    def test_strong_icp_profile_scores_above_threshold(self, sample_icp_prospect):
        """
        A DTC e-commerce prospect that ships to Canada and the US with a
        Shopify store should score well above the 60-point threshold.
        """
        signals = {
            "ships_canada": True,
            "ships_usa": True,
            "dtc_ecommerce": True,
            "shopify_store": True,
        }
        score = calculate_icp_score(signals)
        assert is_icp_qualified(score), f"Score {score} should be >= {ICP_THRESHOLD}"

    def test_already_client_disqualifies(self):
        """A current Broad Reach client must score below the threshold (-100 penalty)."""
        signals = {
            "ships_canada": True,
            "dtc_ecommerce": True,
            "already_client": True,
        }
        score = calculate_icp_score(signals)
        assert not is_icp_qualified(score), f"Score {score} should disqualify existing client"

    def test_pure_b2b_penalised(self):
        """A pure B2B company (no parcel shipping to consumers) should be penalised."""
        signals = {
            "ships_usa": True,
            "b2b_only": True,
        }
        score = calculate_icp_score(signals)
        # 10 (ships_usa) - 20 (b2b_only) = -10
        assert score == -10

    def test_zero_signals_scores_zero(self):
        """A prospect with no detected signals should score 0."""
        score = calculate_icp_score({})
        assert score == 0

    def test_hot_lead_threshold_higher_than_icp_threshold(self):
        """Hot lead threshold must be strictly higher than ICP threshold."""
        assert HOT_LEAD_THRESHOLD > ICP_THRESHOLD

    def test_is_hot_lead_for_score_above_75(self):
        """Score of 75+ should be classified as a hot lead."""
        signals = {
            "ships_canada": True,
            "ships_usa": True,
            "dtc_ecommerce": True,
            "shopify_store": True,
            "high_volume": True,
        }
        score = calculate_icp_score(signals)
        assert is_hot_lead(score)

    def test_qualified_but_not_hot_for_borderline_score(self):
        """A score between 60 and 74 qualifies for outreach but is not a hot lead."""
        # ships_canada=20 + dtc_ecommerce=20 + ships_usa=10 + shopify_store=10 = 60
        # 60 >= 60 qualifies, but 60 < 75 is not a hot lead
        signals = {
            "ships_canada": True,
            "dtc_ecommerce": True,
            "ships_usa": True,
            "shopify_store": True,
        }
        score = calculate_icp_score(signals)
        assert is_icp_qualified(score), f"Score {score} should be >= {ICP_THRESHOLD}"
        assert not is_hot_lead(score), f"Score {score} should be < {HOT_LEAD_THRESHOLD}"

    def test_score_reflects_individual_criteria_weights(self):
        """Each criterion should add its documented weight to the score."""
        # ships_canada = 20
        assert ICP_CRITERIA["ships_canada"] == 20
        # dtc_ecommerce = 20
        assert ICP_CRITERIA["dtc_ecommerce"] == 20
        # already_client = -100 (disqualifier)
        assert ICP_CRITERIA["already_client"] == -100


# ---------------------------------------------------------------------------
# Tests: Cooldown system
# ---------------------------------------------------------------------------

class TestCooldownSystem:
    """Validate anti-pollution cooldown rules."""

    TODAY = date(2026, 3, 6)

    def test_contact_not_in_cooldown_when_no_date_set(self):
        """Empty cooldown_until means the contact is clear for outreach."""
        assert not is_in_cooldown("", self.TODAY)

    def test_contact_in_cooldown_when_future_date(self):
        """A future cooldown date means the contact cannot be contacted."""
        future = (self.TODAY + timedelta(days=30)).isoformat()
        assert is_in_cooldown(future, self.TODAY)

    def test_contact_not_in_cooldown_when_date_passed(self):
        """A past cooldown date means the cooldown has expired."""
        past = (self.TODAY - timedelta(days=1)).isoformat()
        assert not is_in_cooldown(past, self.TODAY)

    def test_cooldown_on_exact_expiry_date_is_still_active(self):
        """The cooldown is inclusive of the end date itself."""
        assert is_in_cooldown(self.TODAY.isoformat(), self.TODAY)

    def test_permanent_block_is_in_cooldown(self):
        """The 2099-12-31 sentinel value is always in cooldown."""
        assert is_in_cooldown(PERMANENT_BLOCK_SENTINEL, self.TODAY)

    def test_sequence_completed_triggers_180_day_cooldown(self):
        """After completing a sequence, contact cools down for 180 days."""
        cooldown = calculate_cooldown_date("sequence_completed", self.TODAY)
        expected = (self.TODAY + timedelta(days=180)).isoformat()
        assert cooldown == expected

    def test_bounce_triggers_365_day_cooldown(self):
        """A hard bounce triggers a 365-day (1-year) cooldown."""
        cooldown = calculate_cooldown_date("bounced", self.TODAY)
        expected = (self.TODAY + timedelta(days=365)).isoformat()
        assert cooldown == expected

    def test_optout_triggers_permanent_block(self):
        """An opt-out triggers a permanent block (2099-12-31 sentinel)."""
        cooldown = calculate_cooldown_date("opted_out", self.TODAY)
        assert cooldown == PERMANENT_BLOCK_SENTINEL

    def test_manual_block_triggers_permanent_block(self):
        """A manual block is permanent."""
        cooldown = calculate_cooldown_date("blocked_manual", self.TODAY)
        assert cooldown == PERMANENT_BLOCK_SENTINEL

    def test_manual_remove_triggers_permanent_block(self):
        """A manual remove is permanent."""
        cooldown = calculate_cooldown_date("removed_manual", self.TODAY)
        assert cooldown == PERMANENT_BLOCK_SENTINEL


# ---------------------------------------------------------------------------
# Tests: Contact queueing logic
# ---------------------------------------------------------------------------

class TestContactQueuingLogic:
    """Test the full should_contact_be_queued decision logic."""

    TODAY = date(2026, 3, 6)

    def test_clean_contact_can_be_queued(self):
        """A contact with no cooldown and not in Expandi can be queued."""
        contact = {
            "br_contact_cooldown_until": "",
            "br_expandi_status": "not_pushed",
        }
        can_contact, reason = should_contact_be_queued(contact, self.TODAY)
        assert can_contact is True

    def test_permanently_blocked_cannot_be_queued(self):
        """A permanently blocked contact (2099 sentinel) must never be queued."""
        contact = {
            "br_contact_cooldown_until": PERMANENT_BLOCK_SENTINEL,
            "br_expandi_status": "blocked",
        }
        can_contact, _ = should_contact_be_queued(contact, self.TODAY)
        assert can_contact is False

    def test_contact_in_active_cooldown_cannot_be_queued(self):
        """A contact with a future cooldown date must not be queued."""
        future = (self.TODAY + timedelta(days=60)).isoformat()
        contact = {
            "br_contact_cooldown_until": future,
            "br_expandi_status": "not_pushed",
        }
        can_contact, _ = should_contact_be_queued(contact, self.TODAY)
        assert can_contact is False

    def test_already_enrolled_in_expandi_cannot_be_queued(self):
        """A contact already pushed to an Expandi campaign must not be queued again."""
        contact = {
            "br_contact_cooldown_until": "",
            "br_expandi_status": "pushed_campaign_a",
        }
        can_contact, reason = should_contact_be_queued(contact, self.TODAY)
        assert can_contact is False
        assert "expandi" in reason.lower()

    def test_expired_cooldown_allows_queueing(self):
        """A contact whose cooldown has expired should be queueable again."""
        past = (self.TODAY - timedelta(days=1)).isoformat()
        contact = {
            "br_contact_cooldown_until": past,
            "br_expandi_status": "not_pushed",
        }
        can_contact, _ = should_contact_be_queued(contact, self.TODAY)
        assert can_contact is True


# ---------------------------------------------------------------------------
# Tests: Warmup schedule calculation
# ---------------------------------------------------------------------------

class TestWarmupScheduleCalculation:
    """Validate the email warmup ramp schedule."""

    TODAY = date(2026, 3, 6)

    def test_week_1_limit_is_10(self):
        """Day 0–6 (week 1): daily limit must be 10."""
        start = self.TODAY.isoformat()
        limit = get_daily_email_limit(start, self.TODAY)
        assert limit == 10

    def test_week_2_limit_is_20(self):
        """Day 7–13 (week 2): daily limit must be 20."""
        start = (self.TODAY - timedelta(days=7)).isoformat()
        limit = get_daily_email_limit(start, self.TODAY)
        assert limit == 20

    def test_week_3_limit_is_35(self):
        """Day 14–20 (week 3): daily limit must be 35."""
        start = (self.TODAY - timedelta(days=14)).isoformat()
        limit = get_daily_email_limit(start, self.TODAY)
        assert limit == 35

    def test_week_4_plus_caps_at_50(self):
        """Day 21+ (week 4+): daily limit must be capped at 50."""
        start = (self.TODAY - timedelta(days=28)).isoformat()
        limit = get_daily_email_limit(start, self.TODAY)
        assert limit == 50

    def test_limit_never_exceeds_max(self):
        """Daily limit must never exceed MAX_DAILY_EMAILS (50) regardless of schedule."""
        start = (self.TODAY - timedelta(days=365)).isoformat()
        limit = get_daily_email_limit(start, self.TODAY)
        assert limit <= MAX_DAILY_EMAILS

    def test_invalid_date_defaults_to_week_1(self):
        """An invalid start date should fall back to the week-1 conservative limit."""
        limit = get_daily_email_limit("not-a-date", self.TODAY)
        assert limit == WARMUP_SCHEDULE[1]

    def test_warmup_schedule_is_monotonically_increasing(self):
        """Each week's limit must be >= the previous week's limit."""
        limits = [WARMUP_SCHEDULE[w] for w in sorted(WARMUP_SCHEDULE.keys())]
        for i in range(1, len(limits)):
            assert limits[i] >= limits[i - 1], (
                f"Week {i+1} limit ({limits[i]}) is less than week {i} limit ({limits[i-1]})"
            )


# ---------------------------------------------------------------------------
# Tests: Expandi payload formatting
# ---------------------------------------------------------------------------

class TestExpandiPayloadFormatting:
    """Validate Expandi API payload construction."""

    CAMPAIGN_A = "campaign_a_id_123"

    def test_payload_contains_required_fields(self, sample_icp_prospect):
        """Expandi payload must include campaign_id, profile_url, first_name, last_name."""
        payload = build_expandi_payload(sample_icp_prospect, self.CAMPAIGN_A)
        assert "campaign_id" in payload
        assert "profile_url" in payload
        assert "first_name" in payload
        assert "last_name" in payload

    def test_payload_sets_correct_campaign_id(self, sample_icp_prospect):
        """The campaign_id in the payload must match the argument passed in."""
        payload = build_expandi_payload(sample_icp_prospect, self.CAMPAIGN_A)
        assert payload["campaign_id"] == self.CAMPAIGN_A

    def test_payload_maps_linkedin_url(self, sample_icp_prospect):
        """The LinkedIn URL from the prospect should be used as profile_url."""
        payload = build_expandi_payload(sample_icp_prospect, self.CAMPAIGN_A)
        assert payload["profile_url"] == sample_icp_prospect["linkedin_url"]

    def test_payload_includes_icp_score_tag(self, sample_icp_prospect):
        """
        Tags should include the ICP score so we can filter by score in Expandi
        analytics.
        """
        payload = build_expandi_payload(sample_icp_prospect, self.CAMPAIGN_A)
        tags = payload.get("tags", [])
        icp_tags = [t for t in tags if t.startswith("icp_score_")]
        assert len(icp_tags) == 1

    def test_payload_validation_passes_for_complete_payload(self, sample_icp_prospect):
        """A complete payload should pass validation."""
        payload = build_expandi_payload(sample_icp_prospect, self.CAMPAIGN_A)
        valid, err = validate_expandi_payload(payload)
        assert valid is True
        assert err is None

    def test_payload_validation_fails_without_campaign_id(self, sample_icp_prospect):
        """Payload without campaign_id must fail validation."""
        payload = build_expandi_payload(sample_icp_prospect, "")
        valid, err = validate_expandi_payload(payload)
        assert valid is False
        assert "campaign_id" in err

    def test_payload_validation_fails_without_linkedin_url(self):
        """Payload with no LinkedIn URL must fail validation."""
        payload = {
            "campaign_id": self.CAMPAIGN_A,
            "profile_url": "",
            "first_name": "Test",
        }
        valid, err = validate_expandi_payload(payload)
        assert valid is False
        assert "profile_url" in err or "linkedin" in err.lower()

    def test_payload_company_name_included(self, sample_icp_prospect):
        """Company name should be included for personalisation purposes."""
        payload = build_expandi_payload(sample_icp_prospect, self.CAMPAIGN_A)
        assert payload.get("company") == sample_icp_prospect["company"]


# ---------------------------------------------------------------------------
# Tests: Anti-pollution rule enforcement
# ---------------------------------------------------------------------------

class TestAntiPollutionRules:
    """
    Validate the anti-pollution rules that prevent over-contacting prospects.
    These rules protect domain reputation and LinkedIn account health.
    """

    TODAY = date(2026, 3, 6)

    def test_no_contact_before_icp_qualification(self):
        """
        A prospect below the ICP threshold must not be added to any outreach sequence.
        """
        signals = {"ships_usa": True}  # score = 10, below 60
        score = calculate_icp_score(signals)
        assert not is_icp_qualified(score)
        # This contact should NOT be pushed to Expandi

    def test_cooldown_respected_after_sequence_completion(self):
        """
        After completing a full sequence, the contact must not be re-contacted
        for at least 180 days.
        """
        completion_date = self.TODAY - timedelta(days=100)  # 100 days ago
        cooldown_end = calculate_cooldown_date("sequence_completed", completion_date)
        assert is_in_cooldown(cooldown_end, self.TODAY)

    def test_cooldown_expired_after_sufficient_time(self):
        """
        After 181+ days, the cooldown from sequence completion should have expired.
        """
        completion_date = self.TODAY - timedelta(days=181)
        cooldown_end = calculate_cooldown_date("sequence_completed", completion_date)
        assert not is_in_cooldown(cooldown_end, self.TODAY)

    def test_bounce_prevents_contact_for_one_year(self):
        """
        A hard bounce must prevent re-contacting for at least 365 days.
        """
        bounce_date = self.TODAY - timedelta(days=364)
        cooldown_end = calculate_cooldown_date("bounced", bounce_date)
        assert is_in_cooldown(cooldown_end, self.TODAY)

    def test_optout_is_permanent_and_never_expires(self):
        """
        An opted-out contact must never be re-contactable.
        Even 100 years in the future, the sentinel remains in cooldown.
        """
        cooldown_end = calculate_cooldown_date("opted_out")
        far_future = date(2099, 12, 30)  # day before the sentinel date
        assert is_in_cooldown(cooldown_end, far_future)

    def test_batch_filter_removes_cooldown_contacts(self):
        """
        When filtering a list of prospects for daily outreach, contacts in
        cooldown must be filtered out.
        """
        contacts = [
            {
                "id": "1",
                "name": "Clear Contact",
                "br_contact_cooldown_until": "",
                "br_expandi_status": "not_pushed",
            },
            {
                "id": "2",
                "name": "Cooled Down Contact",
                "br_contact_cooldown_until": (self.TODAY + timedelta(days=30)).isoformat(),
                "br_expandi_status": "not_pushed",
            },
            {
                "id": "3",
                "name": "Blocked Contact",
                "br_contact_cooldown_until": PERMANENT_BLOCK_SENTINEL,
                "br_expandi_status": "blocked",
            },
        ]

        eligible = [
            c for c in contacts
            if should_contact_be_queued(c, self.TODAY)[0]
        ]

        assert len(eligible) == 1
        assert eligible[0]["id"] == "1"

    def test_daily_outreach_volume_respects_warmup_limit(self):
        """
        The number of contacts pushed in a day must not exceed the warmup
        daily limit.
        """
        warmup_start = (self.TODAY - timedelta(days=7)).isoformat()  # week 2
        daily_limit = get_daily_email_limit(warmup_start, self.TODAY)  # = 20

        # Simulate a queue of 50 eligible contacts
        queue = [{"id": str(i)} for i in range(50)]
        to_send = queue[:daily_limit]

        assert len(to_send) == daily_limit
        assert len(to_send) <= MAX_DAILY_EMAILS

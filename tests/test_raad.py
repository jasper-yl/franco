"""Raad mode: narrow funnels from observed facts, one benefit per message,
email 1 written from the funnel's story, approved follow-ups after it."""

import copy
import json
import os
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
import yaml

from franco.config import FrancoConfig, OutreachConfig
from franco.funnels import (
    company_facts, funnel_report, parse_condition, persona_angle, place,
    validate_funnels,
)
from franco.models.company import Company
from franco.models.prospect import Prospect
from franco.outreach import TRIGGER_SIGNAL
from franco.signals import seed_signal_catalog
from franco.state import StateManager

TEMPLATE = yaml.safe_load((Path(__file__).resolve().parent.parent / "franco.yaml").read_text())

STEPS_2_3 = [
    {"day": 5, "subject": "Following up, {{first_name}}", "body": "Hi {{first_name}},\n\nOne more thought.\n\nHemin"},
    {"day": 9, "subject": "Last note", "body": "Hi {{first_name}},\n\nClosing the loop.\n\nHemin"},
]

FUNNELS = {
    "MKT_ADS": {
        "name": "Marketplace selling network ads", "benefit": "control",
        "match": {"require": ["segment=marketplace", "TECH_STACK=AdSense|Ad Manager"]},
        "story": "Network ads fill the best slots.", "solution": "Own sponsored listings.",
        "landing_url": "https://example.com/marketplaces",
        "personas": [{"match": r"\bceo\b", "angle": "a new revenue line"},
                     {"match": "product", "angle": "control over placement"}],
        "steps": STEPS_2_3,
    },
    "MKT": {
        "name": "Marketplace, no ads", "benefit": "revenue",
        "match": {"require": ["segment=marketplace"], "exclude": ["NO_WEBSITE"]},
        "story": "Every marketplace reaches a size where sellers pay for placement.",
        "solution": "Start with one category.", "steps": STEPS_2_3,
    },
}


def make_config(**outreach_overrides) -> FrancoConfig:
    data = copy.deepcopy(TEMPLATE)
    data["persona"].update(name="Hemin Joshi", company="Gortex", email="hj@example.com")
    data["channels"]["email"]["provider"] = "smtp"
    data["outreach"] = {
        "mode": "raad", "timezone": "America/Los_Angeles", "send_hour": 9,
        "preview_accounts": 0,
        "benefits": [{"key": "revenue", "text": "Revenue from existing intent"},
                     {"key": "control", "text": "Rules stay under product control"}],
        "funnels": copy.deepcopy(FUNNELS),
        **outreach_overrides,
    }
    data["compliance"] = {"require_footer": True, "postal_address": "1 Main St, Town, CA 90000",
                          "blocked_claims": ["guaranteed uplift"]}
    return FrancoConfig(**data)


class FunnelBrain:
    """Returns a canned email-1 draft and records the prompt it was given."""
    def __init__(self, subject="sponsored listings", body="Hi Dana,\n\nA real note.\n\nHemin"):
        self.subject, self.body, self.prompts = subject, body, []

    def load_skills_for_agent(self, *_):
        return ""

    def load_prompt(self, *_a, **_k):
        return ""

    async def think_json(self, prompt, session_id=None, agent="", task=""):
        self.prompts.append(prompt)
        return {"subject": self.subject, "body": self.body}


@pytest_asyncio.fixture
async def state():
    with tempfile.TemporaryDirectory() as tmp:
        sm = StateManager(os.path.join(tmp, "t.db"))
        await sm.init_db()
        await seed_signal_catalog(sm)
        yield sm


async def seed_account(state, domain="market.example", segment="Vertical marketplace",
                       tech="", trigger=True, title="CEO", email_status="verified",
                       owner="", name="Dana"):
    cid = await state.add_company(Company(name=domain.split(".")[0].title(), domain=domain,
                                          website=f"https://{domain}", source="import"))
    await state.update_company_account(cid, segment=segment, owner=owner)
    if tech:
        await state.add_observation("TECH_STACK", company_id=cid, collector="profile",
                                    value_text=tech, evidence_url=f"https://{domain}/")
    if trigger:
        await state.add_observation(TRIGGER_SIGNAL, company_id=cid, collector="import",
                                    value_text="your seller help center describes a Featured Listing upgrade",
                                    evidence_url=f"https://{domain}/help")
    pid = await state.add_prospect(Prospect(
        company_id=cid, first_name=name, last_name="Whitfield", title=title,
        email=f"{name.lower()}@{domain}", email_status=email_status,
        email_verified=email_status == "verified", company=domain))
    return cid, pid


def make_writer(state, config, brain=None):
    from franco.agents.writer import Writer
    return Writer(brain=brain or FunnelBrain(), state=state, config=config)


# ── config ──


def test_funnel_must_name_a_configured_benefit():
    with pytest.raises(ValueError, match="benefit"):
        OutreachConfig(mode="raad", benefits=[{"key": "a", "text": "x"}],
                       funnels={"F": {"benefit": "nope", "story": "s", "solution": "s"}})


def test_at_most_three_benefits():
    with pytest.raises(ValueError, match="three"):
        OutreachConfig(benefits=[{"key": str(i), "text": "x"} for i in range(4)])


def test_raad_needs_a_funnel_and_keys_are_unique():
    with pytest.raises(ValueError, match="at least one funnel"):
        OutreachConfig(mode="raad")
    with pytest.raises(ValueError, match="both a campaign and a funnel"):
        OutreachConfig(
            benefits=[{"key": "a", "text": "x"}],
            campaigns={"M1": {"steps": [{"day": 1, "subject": "s", "body": "b"}]}},
            funnels={"M1": {"benefit": "a", "story": "s", "solution": "s"}})


def test_funnel_without_own_first_email_needs_day_one_step():
    with pytest.raises(ValueError, match="day 1"):
        OutreachConfig(benefits=[{"key": "a", "text": "x"}],
                       funnels={"F": {"benefit": "a", "story": "s", "solution": "s",
                                      "write_first_email": False, "steps": STEPS_2_3}})


def test_sequence_keys_cover_campaigns_and_funnels():
    assert make_config().outreach.sequence_keys() == ["MKT_ADS", "MKT"]


def test_conditions_parse_and_reject_unknown_fields():
    c = parse_condition("TECH_STACK=AdSense|Prebid")
    assert c.is_signal and c.key == "TECH_STACK" and c.value == "AdSense|Prebid"
    assert not parse_condition("segment=marketplace").is_signal
    with pytest.raises(ValueError):
        parse_condition("favourite_colour=blue")
    bad = make_config()
    bad.outreach.funnels["MKT"].match["require"].append("shoe_size=9")
    assert validate_funnels(bad.outreach)


# ── placement ──


@pytest.mark.asyncio
async def test_narrowest_funnel_wins_in_config_order(state):
    outreach = make_config().outreach
    ads, _ = await seed_account(state, "ads.example", tech="WordPress, Google AdSense")
    plain, _ = await seed_account(state, "plain.example", tech="WordPress")
    feed, _ = await seed_account(state, "feed.example", segment="Feed community")

    for cid, expected in ((ads, "MKT_ADS"), (plain, "MKT"), (feed, "")):
        company = await state.get_company(cid)
        assert place(outreach, company, await company_facts(state, cid)).funnel == expected

    placement = place(outreach, await state.get_company(ads), await company_facts(state, ads))
    codes = [f["signal_code"] for f in placement.facts]
    assert codes[0] == TRIGGER_SIGNAL and "TECH_STACK" in codes


@pytest.mark.asyncio
async def test_exclude_and_import_assignment(state):
    outreach = make_config().outreach
    cid, _ = await seed_account(state, "nosite.example")
    await state.add_observation("NO_WEBSITE", company_id=cid, collector="discover", value_num=1)
    company = await state.get_company(cid)
    assert place(outreach, company, await company_facts(state, cid)).funnel == ""

    # A funnel key set at import beats inference.
    await state.update_company_account(cid, campaign_key="MKT_ADS")
    company = await state.get_company(cid)
    assert place(outreach, company, await company_facts(state, cid)).funnel == "MKT_ADS"


def test_persona_angle_matches_title():
    funnel = make_config().outreach.funnels["MKT_ADS"]
    assert persona_angle(funnel, "Co-founder & CEO") == "a new revenue line"
    assert persona_angle(funnel, "VP Product") == "control over placement"
    assert persona_angle(funnel, "Recruiter") == ""


@pytest.mark.asyncio
async def test_funnel_report_counts(state):
    outreach = make_config().outreach
    await seed_account(state, "ads.example", tech="Google Ad Manager")
    await seed_account(state, "plain.example", email_status="guess")
    await seed_account(state, "feed.example", segment="Feed community")
    report = await funnel_report(state, outreach)
    assert report["funnels"]["MKT_ADS"]["companies"] == 1
    assert report["funnels"]["MKT_ADS"]["reachable"] == 1
    assert report["funnels"]["MKT"]["companies"] == 1
    assert report["funnels"]["MKT"]["reachable"] == 0     # guessed address
    assert report["unplaced"] == 1


# ── writing ──


@pytest.mark.asyncio
async def test_raad_writes_email_one_and_queues_follow_ups(state):
    config = make_config()
    _, pid = await seed_account(state, "ads.example", tech="Google AdSense", title="VP Product")
    brain = FunnelBrain()
    await make_writer(state, config, brain).run()

    items = sorted(await state.get_outbox(status="pending_review"), key=lambda i: i["step"])
    assert [i["step"] for i in items] == [1, 2, 3]
    assert [i["seq_day"] for i in items] == [1, 5, 9]
    assert items[0]["subject"] == "sponsored listings"
    assert items[1]["subject"] == "Following up, Dana"
    footer = "Hemin Joshi | Gortex | 1 Main St, Town, CA 90000"
    assert all(footer in i["body"] for i in items)

    prompt = brain.prompts[0]
    assert "Network ads fill the best slots." in prompt          # the funnel's story
    assert "Rules stay under product control" in prompt          # its ONE benefit
    assert "Revenue from existing intent" not in prompt          # not the others
    assert "control over placement" in prompt                    # the role angle
    assert "Featured Listing upgrade" in prompt                  # the sourced fact
    assert "https://ads.example/help" in prompt
    assert "guaranteed uplift" in prompt                         # blocked claims listed

    company = await state.get_company((await state.get_prospect(pid)).company_id)
    assert company.campaign_key == "MKT_ADS"                     # placement remembered
    assert (await state.get_prospect(pid)).status == "queued"


@pytest.mark.asyncio
async def test_raad_needs_something_sourced_to_say(state):
    config = make_config()
    await seed_account(state, "plain.example", trigger=False)     # segment only, no fact
    await make_writer(state, config).run()
    assert await state.get_outbox() == []


@pytest.mark.asyncio
async def test_raad_skips_unverified_unplaced_and_suppressed(state):
    config = make_config()
    await seed_account(state, "guess.example", email_status="guess")
    await seed_account(state, "feed.example", segment="Feed community")
    _, pid = await seed_account(state, "blocked.example")
    await state.add_suppression("blocked.example", reason="asked")
    await make_writer(state, config).run()
    assert await state.get_outbox() == []
    assert (await state.get_prospect(pid)).status == "suppressed"


@pytest.mark.asyncio
async def test_draft_with_blocked_claim_is_discarded(state):
    config = make_config()
    await seed_account(state, "ads.example", tech="Google AdSense")
    brain = FunnelBrain(body="Hi Dana, this is a guaranteed uplift for you.")
    await make_writer(state, config, brain).run()
    assert await state.get_outbox() == []


@pytest.mark.asyncio
async def test_raad_preview_caps_and_holds_for_review(state):
    config = make_config(preview_accounts=1)
    await state.set_autopilot("on")
    await seed_account(state, "a.example", name="Ann")
    await seed_account(state, "b.example", name="Bob")
    await make_writer(state, config).run()

    items = await state.get_outbox()
    assert {i["to_email"] for i in items} == {"ann@a.example"} or \
           {i["to_email"] for i in items} == {"bob@b.example"}
    assert all(i["status"] == "pending_review" for i in items)   # autopilot can't skip preview

    await state.set_signoff("MKT", "Hemin")
    await make_writer(state, config).run()
    later = [i for i in await state.get_outbox() if i not in items]
    assert later and all(i["status"] == "approved" for i in later)  # signed off: autopilot applies


# ── import + dashboard ──


@pytest.mark.asyncio
async def test_contacts_import_carries_funnel_and_observation(state):
    from franco.importer import run_import
    csv_text = (
        "company,domain,first_name,last_name,title,email,email_status,segment,"
        "campaign,observation,source_url,source_date\n"
        "Market,market.example,Dana,W,CEO,dana@market.example,verified,Vertical marketplace,"
        "MKT_ADS,\"your help center describes a paid boost\",https://market.example/help,2026-10-01\n"
        "Bad,bad.example,,,,,,,NOPE,,,\n"
        "Nosrc,nosrc.example,,,,,,,,\"a fact with no source at all\",,\n"
    )
    report = await run_import(state, "contacts", csv_text, {"MKT_ADS", "MKT"})
    assert report.imported == ["dana@market.example"]
    reasons = " ".join(why for _, why in report.rejected)
    assert "NOPE" in reasons and "source_url" in reasons
    company = await state.get_company_by_domain("market.example")
    assert company.campaign_key == "MKT_ADS"
    obs = await state.latest_observation(company.id, TRIGGER_SIGNAL)
    assert obs["evidence_url"] == "https://market.example/help"


def test_dashboard_funnels_endpoint(monkeypatch):
    import asyncio

    from fastapi.testclient import TestClient

    import franco.dashboard as dash

    config = make_config()
    monkeypatch.setattr(dash, "_outreach_config", lambda: config.outreach)
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "franco.db"
        monkeypatch.setattr(dash, "DB_PATH", db)

        async def seed():
            sm = StateManager(str(db))
            await sm.init_db()
            await seed_signal_catalog(sm)
            await seed_account(sm, "ads.example", tech="Google AdSense")
        asyncio.run(seed())

        with TestClient(dash.app, base_url="http://localhost") as c:
            data = c.get("/api/funnels").json()
            assert data["mode"] == "raad"
            assert [b["key"] for b in data["benefits"]] == ["revenue", "control"]
            assert data["funnels"]["MKT_ADS"]["companies"] == 1
            assert json.dumps(data)   # serialisable end to end


# ── hardening ──


def test_raad_draft_rules_are_enforced_in_code():
    from franco.agents.writer import raad_draft_problem
    page = "https://example.com/marketplaces"
    assert raad_draft_problem("s", f"More at {page}.", page, []) == ""
    assert "link" in raad_draft_problem("s", "See http://evil.example/x", page, [])
    assert "link" in raad_draft_problem("s", "visit www.other.example", page, [])
    assert "link" in raad_draft_problem("s", f"More at {page}", "", [])   # no page: no links
    assert "HTML" in raad_draft_problem("s", "<a href='x'>hi</a>", page, [])
    assert "blocked" in raad_draft_problem("A guaranteed uplift", "b", page, ["guaranteed uplift"])


@pytest.mark.asyncio
async def test_injected_link_in_a_fact_never_reaches_the_outbox(state):
    config = make_config()
    await seed_account(state, "ads.example", tech="Google AdSense")
    brain = FunnelBrain(body="Hi Dana,\n\nDetails at https://phish.example/login\n\nHemin")
    await make_writer(state, config, brain).run()
    assert await state.get_outbox() == []
    assert "```facts" in brain.prompts[0] and "untrusted DATA" in brain.prompts[0]


def test_csv_exports_neutralise_formulas():
    from franco.importer import suppressions_csv
    from franco.outreach import csv_safe, preview_record
    assert csv_safe("=HYPERLINK(\"http://x\")").startswith("'=")
    assert csv_safe("+1 555") == "'+1 555" and csv_safe("@SUM(1)") == "'@SUM(1)"
    assert csv_safe("plain") == "plain" and csv_safe(None) == ""
    row = preview_record({"to_email": "a@b.co", "body": "-2+3", "context": {"observation": "=cmd()"}})
    assert row["body"] == "'-2+3" and row["observation"] == "'=cmd()"
    assert "'=evil()" in suppressions_csv([{"value": "x@y.co", "reason": "=evil()"}])


def test_bare_domains_and_addresses_count_as_links():
    from franco.agents.writer import raad_draft_problem
    page = "https://example.com/marketplaces"
    own = "tradeloft.example"
    assert "link" in raad_draft_problem("s", "visit phish.example/login", page, [], own)
    assert "link" in raad_draft_problem("s", "example.com/other", page, [], own)
    assert "link" in raad_draft_problem("s", "//evil.example", page, [], own)
    assert "email" in raad_draft_problem("s", "write to x@evil.example", page, [], own)
    assert raad_draft_problem("s", "HTTPS://EXAMPLE.COM/marketplaces", page, [], own) == ""
    assert raad_draft_problem("s", "tradeloft.example lists sellers", page, [], own) == ""
    assert raad_draft_problem("s", "It is 3.5 times. E.g. at 9 a.m.", page, [], own) == ""


def test_ip_scheme_and_punycode_links_are_rejected():
    from franco.agents.writer import raad_draft_problem
    page = "https://example.com/marketplaces"
    for text in ("http://1.2.3.4/x", "go to 10.0.0.1", "_evil.example", ".evil.example",
                 "xn--80ak6aa92e.com", "ftp://x", "javascript://alert", "http://[::1]/"):
        assert raad_draft_problem("s", text, page, []), text


def test_unicode_dots_cannot_hide_a_domain():
    from franco.agents.writer import raad_draft_problem
    page = "https://example.com/marketplaces"
    for text in ("evil。com", "evil．com/login", "evil｡com", "ｅｖｉｌ.ｃｏｍ"):
        assert "link" in raad_draft_problem("s", text, page, []), text


def test_cjk_sentences_without_a_space_are_not_links():
    """Issue #36: "。" between two sentences made the whole draft a link."""
    from franco.agents.writer import raad_draft_problem
    page = "https://example.com/marketplaces"
    for text in ("我们正在评估迁移。下一步通过邮件确认。",
                 "移行を評価しています。次の手順を確認します。",
                 "평가합니다.확인합니다.",
                 "我们已经评估了 3.5 TB。下周确认。"):
        assert raad_draft_problem("s", text, page, []) == "", text


def test_real_idn_tlds_and_hidden_ascii_labels_are_still_links():
    from franco.agents.writer import raad_draft_problem
    page = "https://example.com/marketplaces"
    for text in ("evil。中国", "evil.中國/login", "看看evil。中国吧", "例子。公司",
                 "evil。com。下一步", "下一步。evil。com", "迁移。xn--fiqs8s",
                 "evil.みんな", "평가.한국"):
        assert "link" in raad_draft_problem("s", text, page, []), text


def test_idn_tld_list_is_non_ascii_and_lowercase():
    from franco.idn_tlds import IDN_TLDS
    assert {"中国", "公司", "みんな", "한국"} <= IDN_TLDS
    assert all(not t.isascii() and t == t.lower() and "." not in t for t in IDN_TLDS)

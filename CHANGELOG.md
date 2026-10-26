# Changelog

Notable changes to Franco. Dates are release dates; the format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) loosely and versions
follow [semver](https://semver.org/), with the caveat that Franco is pre-1.0 and
minor versions can still change behaviour.

## [Unreleased]

### Fixed

- **Raad drafts in Chinese, Japanese or Korean are no longer discarded as containing a link** ([#36](https://github.com/GortexAI/franco/issues/36)). A full stop with no space after it (`迁移。下一步`) was read as a domain, so nearly every such draft was rejected, and rejected again on every retry. A non-ASCII label after a dot now counts as a link only when it starts with a real IDN top-level domain from the IANA root zone (`evil。中国` is still rejected). ASCII and punycode labels are checked exactly as before. `scripts/idn_tlds.py` regenerates the list.

## [0.5.1] — 2026-10-17

### Security

- **Bounces are verified before Franco acts on them.** Anyone can send a message that looks like a bounce, and acting on one marks a contact's address invalid and moves the bounce rate toward the kill switch. A delivery report is acted on only when it references the Message-ID of an email Franco actually sent (`In-Reply-To` or `References`) and names that email's recipient. A report that matches only by naming an address Franco emailed in the last 14 days could be forged by anyone who knows whom Franco emails, so it is logged as `bounce_needs_review` for a person to check, and changes nothing. Unmatched reports are logged as `bounce_ignored`.
- Temporary delivery delays ("delayed", `4.x.x` statuses) are no longer treated as hard bounces, and the same bounce is never counted twice.

### Changed

- The README's dashboard GIF shows the current Outbox: approved-copy campaigns in preview, sign-off cards, and each draft's campaign, owner, sourced observation and compliance footer.

## [0.5.0] — 2026-10-16

### Added

- **`pip install franco`.** Franco is on [PyPI](https://pypi.org/project/franco/) and works without a checkout:
  - `franco init [DIR]` creates a **home folder**: `franco.yaml`, a private `.env`, editable `prompts/` and `skills/`, `data/` and a `.gitignore` that keeps credentials and contact data out of git. It never overwrites existing files.
  - Franco finds its home as `$FRANCO_HOME`, else the source checkout (unchanged for clones and Docker), else the current folder when it has a `franco.yaml`, else `~/.franco`.
  - The wheel bundles the default prompts, skills and templates. A file in the home folder wins; delete it to fall back to the shipped version.
  - A pip-installed Franco never writes into its installed package.
  - `franco install` only fetches Chromium when Franco was installed from PyPI.
- **Releases publish to PyPI** with trusted publishing (no stored token) and PEP 740 attestations, before the GitHub Release is created.

### Fixed

- `franco train` created `skills/` files without creating the folder first, which failed in a fresh home folder.
- The dashboard's setup check counted only a `.venv` inside the project as a virtual environment.


## [0.4.0] — 2026-10-16

Franco is now open source under [GortexAI/franco](https://github.com/GortexAI/franco), published as a container image, and released automatically.

### Upgrading from 0.3.0

- **Set your postal address.** The template `franco.yaml` now ships with `compliance.require_footer: true` and a blank `postal_address`. No cold email sends until you enter your own address. If your config predates this, the footer stays off until you turn it on.
- **The dashboard only answers on localhost.** If you reach it under another hostname (from Docker, for example), list it in `FRANCO_DASHBOARD_HOSTS`.
- New config sections (`outreach`, `compliance`) all have defaults. Existing configs load unchanged.

### Added

- **Approved-copy outreach** (`outreach.mode: templates`):
  - Signed-off sequences in `outreach.campaigns` are sent word for word to researched accounts, with no model involved.
  - Merge fields are limited to `{{first_name}}`, `{{last_name}}`, `{{company}}`, `{{title}}`, `{{sender_name}}` and `{{verified_observation}}`. The observation is a sourced, dated fact recorded per account. An account with an unfilled field is skipped, never sent with a gap.
  - Steps are scheduled in business days in `outreach.timezone`, and each follow-up is re-timed from the day the previous step actually went out.
- **Raad mode** (`outreach.mode: raad`), named after Raad Mobrem, CEO of Intro, whose outbound approach it follows:
  - Up to three `outreach.benefits`; every funnel names exactly one.
  - `outreach.funnels` are narrow segments matched on observed signals (`TECH_STACK=AdSense|Prebid`) or account fields (`segment=marketplace`), tried narrowest first.
  - Email 1 is written from the funnel's story, the account's sourced facts, the one benefit and a role-specific angle, then the funnel's approved follow-ups are queued.
  - `franco funnels` (and the dashboard's Campaigns tab) shows how companies split across funnels; `--company DOMAIN` explains one placement.
  - The profiler now detects publisher ad tags (Google AdSense, Ad Manager, Prebid, Amazon Publisher Services).
- **Bring your own lists as CSV files.** `franco import FILE --kind accounts|contacts|suppressions`, plus an Import CSV panel on the dashboard's Contacts tab:
  - Each kind has a template (`--template`), header aliases, `--dry-run` and optional `--verify`.
  - Every row is validated before anything is written.
  - `franco suppress import` parses real CSV (with a `reason` column, or one address per line), and `export` quotes properly.
- **Preview and sign-off.** New approved-copy campaigns and raad funnels start in preview (`outreach.preview_accounts`, default 10 per owner):
  - Preview emails always wait for review, even on autopilot, and nothing sends until someone signs off.
  - Commands: `franco preview [KEY] [--csv FILE]`, `franco preview signoff KEY --by NAME`, `franco preview reopen KEY`. The Outbox shows a sign-off card for each campaign in preview.
- **Compliance in code:**
  - `compliance.require_footer` puts the sender, company and postal address plus "Reply "no thanks" to stop." on every cold email in every mode. The gate refuses cold email without the footer, and nothing sends while the postal address is blank.
  - Cold email gets List-Unsubscribe headers (mailto, plus optional one-click HTTPS).
  - `compliance.blocked_claims` is enforced on every email, replies included.
  - A shared suppression list covers addresses and whole domains (`franco suppress`).
- **Account-level outreach:**
  - One contact per account in a sequence at a time, and one owner per account.
  - A reply or opt-out from anyone stops queued email to everyone at that company.
  - Follow-ups wait for the previous step, and are cancelled if it was rejected or failed.
- **Replies:**
  - Quoted history and Franco's own footer are removed before any rule runs.
  - "no thanks" (body or subject) is an opt-out, and is suppressed before the optional acknowledgement is sent.
  - Out-of-office replies no longer end a sequence.
  - A new `later` intent pauses the contact and records when to get back in touch.
  - `outreach.reply_templates` provides approved wording per intent; `not_interested` sends its template as written.
- **Autopilot toggle.** `franco autopilot on|off|default` (and an Outbox button) overrides `channels.email.require_approval` at runtime; turning it on approves what is waiting. Every gate still applies.
- **Outbox context and editing.** Each draft shows why it exists: campaign, owner, buyer, observation with its source and the date checked. Drafts can be edited before approval with `franco outbox --edit ID` or `E` on the dashboard.
- **Container image** `ghcr.io/gortexai/franco`, for linux/amd64 and linux/arm64, with an SBOM and a signed build-provenance attestation:
  - Pull requests build and smoke-test it.
  - Every push to `main` publishes `:edge`, and each release publishes `:X.Y.Z`, `:X.Y` and `:latest`.
  - `docker-compose.yml` uses the published image.
- **Release workflow.** Tagging `vX.Y.Z` checks the version against `pyproject.toml` and the CHANGELOG, builds and tests the sdist and wheel, and creates the GitHub Release. See "Releasing" in `CONTRIBUTING.md`.
- CI tests Python 3.11, 3.12, 3.13 and 3.14 on Linux, macOS and Windows.
- `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue forms and a pull request template.

### Security

- **The dashboard refuses cross-site requests and DNS-rebound hosts.** Any web page could previously POST to `localhost:5555`, for example to turn on autopilot.
- **Raad-mode drafts are checked in code.** Facts reach the model as fenced, untrusted data. Code rejects any draft that contains a blocked claim, HTML, an email address, an IP address, or any link or domain other than the funnel's landing page (Unicode look-alike dots included).
- **Dependencies are locked and fully scanned.** `requirements.txt` is generated by `pip-compile` from `requirements.in`, with every package pinned and hashed.
  - Dependabot alerts now cover all 28 packages, up from 12.
  - Dependabot security updates work again; they had been failing without a lockfile.
  - Renovate recompiles the lock and keeps `pyproject.toml`, `requirements.in` and the lock in step. `tests/test_dependencies.py` checks that they agree.
- **Every GitHub Action is pinned to a full commit SHA**, with Renovate keeping the pins current, so a moved or hijacked tag can't change what runs with publishing and signing permissions.
- **Fixed all 32 CodeQL alerts inherited from the original code:**
  - **Path injection (4, high):** the dashboard serves only files listed under `franco/web/`, never a requested path.
  - **Clear-text logging of secrets (6, high):** the setup wizard reads API keys and passwords through a separate hidden-input function. Secrets were only ever written to `.env`.
  - **Bad HTML tag filter (1, high):** script and style stripping handles end tags like `</script >`.
  - **Stack-trace exposure (20, medium):** dashboard endpoints and run reports log the details and show fixed wording. Franco's own explanations, such as "OpenStreetMap has no category for 'widgets'", are still shown as written.
  - **Log injection (1, medium):** newlines are removed from logged search terms, provider names and errors.
- CSV exports (prospects, preview, suppressions) neutralise cells starting with `=`, `+`, `-` or `@`, so imported or scraped text can't run as a spreadsheet formula.
- Scraped website and LinkedIn URLs are linked only when they are http(s).
- Secret scanning with push protection, private vulnerability reporting, CodeQL and Code Quality are enabled on the repository.

### Fixed

- **The Docker image never had the Claude CLI.** Its installer is a bash script but ran under `sh`, and `|| true` hid the failure, so containers couldn't make any model call. It now runs with bash, and the build fails if `claude` is missing.
- A `.dockerignore` keeps `.env`, `franco.local.yaml`, `data/` and the virtualenv out of local Docker builds.
- When several steps of a sequence were overdue at once, they no longer all send in the same cycle.
- Accounts staged on a weekend start on Monday, not Tuesday.
- No empty campaign rows when every account in a batch is skipped.
- A usage test no longer fails between 5pm and midnight Pacific (it seeded data with the UTC date while Franco uses the local one).

## [0.3.0] — 2026-10-13

### Added

- **Opt-in Codex brain (ChatGPT plan).** Set `brain.provider: codex` (or pick
  it in `franco setup`, or `franco train --provider codex`) to think with the
  Codex CLI on a ChatGPT subscription instead of Claude. Claude remains the
  default and there is no automatic fallback between providers. Each call
  runs a throwaway, isolated `codex app-server` with no tools; Franco verifies
  the lockdown from Codex's own reports before sending any prompt, aborts on
  any attempted tool use, refuses API-key logins and custom endpoints
  (checked before your login is exposed to Codex), and never changes your own
  Codex settings or login: each call gets a private copy of the login without
  its refresh token, so an expired login must be renewed with Codex itself or
  `codex login`. Requires Codex CLI 0.159.3; other versions are refused. See
  the README section "Using a ChatGPT plan instead (Codex)".
- `brain.model` picks the model for either provider, for Franco only. For
  Codex use `gpt-5.5` (suggested by `franco setup`): the verified text-only
  model. Blank auto-selection only picks listed models without code-execution
  tools, and on current ChatGPT accounts there are none; code-mode models are
  refused.
- If Codex can't be used (expired or renewal-due login, unsupported CLI,
  unsafe Codex config, rejected model, plan usage limit), Franco pauses the
  heartbeat instead of running agents that would fail: replies stay unread
  and unescalated, queued emails wait, and the reason shows in the log,
  `franco status` and the dashboard. It resumes on its own once the cause is
  fixed. `franco status --check` runs the same check (no prompt sent) on demand
  and exits non-zero when it fails. The Codex provider supports macOS and
  Linux; it is refused on Windows (use Claude there).

### Changed

- Each heartbeat now sends email after the agents that read and answer
  replies have finished, and native mail providers (Gmail/SMTP) read the
  mailbox every cycle, so a reply always cancels its queued follow-ups before
  that cycle's sends (previously the two could run at the same time, and a
  reply arriving with no open conversation waited for a later cycle). This
  applies to Claude and Codex alike.
- A reply is only recorded once its reply draft (if it needs one) is
  written, so a brain outage part-way never half-records it. If a working
  brain returns no usable draft, the conversation is flagged for a human
  instead of being left open with no answer.
- Usage is tracked per provider. The budget gate, `franco usage`, `franco
  status` and the dashboard read and label the active provider's own quota;
  existing usage history is kept and attributed to Claude.

### Fixed

- Dashboard HTML and text assets now use UTF-8 explicitly, fixing Windows
  decoding failures. Regression tests cover HTML, CSS, JavaScript and SVG.

## [0.2.1] — 2026-10-13

A security release. Update if you run Franco.

### Security

- **Claude now runs with no tools.** Every Claude call used to run with
  `--dangerously-skip-permissions`, and prompts include text Franco doesn't
  control: prospect email replies and scraped web pages. Instructions hidden
  in that text could make Claude run commands, read or write files, or use
  the operator's connected MCP servers. Calls now run with `--tools ""` and
  `--strict-mcp-config`; Franco only ever needed text back, so nothing else
  changes.
  If you ran an earlier version with live replies coming in, check the
  account that ran Franco for unexpected files or activity.

### Fixed

- `franco run` no longer drops into the setup wizard when the trained config
  lives in `franco.local.yaml`; the dashboard reads it too.
- A heartbeat cycle is capped at 10 minutes, so one hung agent can't freeze
  Franco, and quiet hours are re-checked every 5 minutes so a Mac waking from
  sleep resumes on time.
- Sites that only answer on plain HTTP or `www.` are no longer marked
  unreachable.
- Profile and contact backfills rotate through every company instead of
  retrying the same few forever.
- The trainer writes full place names ("Solon, Ohio") and real job titles, so
  discovery doesn't geocode to the wrong city and found contacts aren't
  silently discarded.

### Added

- Contacts are backfilled for companies found without any, from their own team
  pages and, if a key is set, Hunter's named-people search.
- `HUNTER_MONTHLY_SEARCHES` (default 25) sets one Hunter budget shared by every
  domain search.

## [0.2.0] — 2026-09-13

The release that made Franco worth running. The previous version could write
and send email but could not reliably find anyone to send it to, and it needed
a paid third-party platform to send at all. Both are fixed.

### Added

- **A prospecting pipeline that works.** Four stages, each independently
  runnable and re-runnable: DISCOVER (who exists) → PROFILE (what they are) →
  ENRICH (who decides) → VERIFY (can you reach them).
- **DISCOVER, with a provider menu.** Four sources behind one adapter
  interface, shown side by side in the dashboard with what each does, what it
  costs, its free tier and which keys it needs. The default — OpenStreetMap —
  needs no account, no card and no key, so the whole pipeline can be run
  before paying anyone. `franco discover`.
- **Cost discipline in the collector.** Every discovery run estimates before it
  spends, refuses to start over your cap, re-checks the cap between batches,
  reads a kill switch, and flushes observations per batch so a run that dies
  keeps what it learned. `franco discover --estimate` prints the projection and
  exits.
- **PROFILE.** Free — three HTTP requests per business, no browser, no model
  call. Reads the incumbent agency out of the site footer, ad pixels, missing
  schema, abandoned blogs, open roles and named people. Chained onto DISCOVER
  and run on every heartbeat. `franco profile`.
- **A signal catalog you confirm.** Franco knows how to collect 23 signals and
  collects none of them until a human says so. Each shows a plain-language
  description, what it costs, and how many companies already carry it.
  `franco signals`.
- **The cohort builder.** Pick what a prospect must have and what disqualifies
  them; see the matching companies live. A prospect list is a query you can
  explain, not a file.
- **Native mail providers.** Gmail (REST + OAuth) and any SMTP+IMAP mailbox.
- **The outbox approval ladder.** Every outgoing email waits for approval by
  default (`pending_review → approved → sent`), reviewed one at a time in a
  decisions desk with `A`/`R`/`J`/`K`. A deterministic pre-send gate — no model
  involved — rejects unrendered merge tags, banned phrases, over-length bodies,
  too many links, HTML, undeliverable addresses and recipient mismatches.
- **Bounce handling and a kill switch.** A bounce marks the address invalid,
  cancels that prospect's queued sends, and trips a global pause past a
  configured bounce rate. `franco sending pause|resume`.
- **Claude usage tracking.** Per-call attribution by agent, task and model, plus
  live subscription-quota gauges read the same way `/usage` does, so Franco
  throttles itself and leaves headroom for your own interactive work.
  `franco usage`.
- **CSV export.** `franco export` writes a sequencer-ready list. Franco is worth
  running as a list-builder even if you never let it send.
- **A dashboard worth looking at.** Opens on Today — what needs a human — with
  an activity feed and a rail of pipeline figures, collector runs and setup.
  Light and dark are the same design re-tokenised; appearance follows your OS by
  default. Fonts are vendored so it renders with the network off.
- **A Python version guard.** `python3 -m venv` on macOS builds from the system
  3.9, which cannot run Franco. It now fails immediately with the fix instead of
  surfacing later as an unrelated-looking ImportError.

### Changed

- **The data model.** Every fact Franco learns is now an observation — a row in
  `observations`, never a column. A new signal needs no migration, re-observing
  over time is a free time series, and confidence and provenance travel with the
  fact. The vocabulary is governed: a database trigger rejects any signal code
  not in `signal_codes`.
- **Email finding is pattern-first.** Franco derives the domain's address format
  and verifies one candidate rather than brute-forcing name variations, and
  grades every address honestly as `verified` / `risky` / `guess` / `invalid`.
  Only deliverable addresses are ever sent to.
- **The default mail provider** is now `gmail`. Instantly is still supported as
  a legacy option.
- **Discovery depth defaults to 30, not 100.** Google removed
  100-results-per-page in September 2025, so depth 100 is now billed as ten
  pages nearly everywhere — and below rank 30 it is mostly directories.
- **The dashboard's HTML, CSS and JS** are real files in `franco/web/` instead
  of a 1,500-line string literal in `dashboard.py`. Still no build step.

### Fixed

- **Guessed emails were being reported as verified** whenever the domain merely
  had an MX record. The migration downgrades every legacy `email_verified=1` row
  to `guess`.
- **Cohorts counted the wrong companies.** PROFILE records a false boolean when
  it checks and finds nothing — which is correct — but `cohort()` matched on the
  row existing, so "companies running Google Ads" silently meant "companies we
  checked for Google Ads", which was all of them. Cohorts now read the newest
  observation per company and signal, and require it to be true.
- **Usage tracking counted every Claude session on the machine**, not just
  Franco's. The transcript reconciler is gone; the ledger contains only rows
  Franco's own Brain wrote.
- **Page titles were being extracted as people** ("Request Service", "Commercial
  Services"), and titles bled between team members.
- **Confirming a signal before anything had loaded the catalog** reported success
  while changing nothing.
- **The free OSM provider answered unmapped search terms with every registered
  office in the area** — coffee roasters and churches for a roofing query. It now
  refuses the query and names the trades it can search.

### Security

- Test fixtures no longer carry real businesses' phone numbers or street
  addresses.
- `franco.local.yaml` (gitignored) overrides the tracked `franco.yaml`, so a
  fork can hold real product configuration without it reaching a public repo.

## [0.1.0]

Initial release: the heartbeat loop, five sub-agents, the skills library, the
website trainer, Instantly-based sending, and the first dashboard.

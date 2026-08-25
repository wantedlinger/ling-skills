---
name: seo-audit
description: "Full SEO audit — technical, on-page, content, schema, AI readiness + AI visibility (dual scores). Browser edition of the Claude Code /seo-audit skill: same audit rules and scoring methodology, artifact output instead of files. Content criteria shared with the blog skill. Multilingual. Trigger with \"seo-audit\", \"audit my site\", or a URL."
---

# Full Website SEO Audit — Downloadable PDF Report

## About

**Privilege level: read-only.** This skill only performs HTTP GET fetches of public pages (homepage, robots.txt, llms.txt, sitemaps, sampled pages) and renders a report as an in-conversation artifact. It writes nothing to any external system, sends nothing, and does not read or write local files.

**Tools needed:** web fetch only. No Google Workspace, ClickUp, or other connections required.

**Criteria versioning:** the audit criteria reflect current search-engine and AI-search guidance as of the version date (e.g. Google's June 2026 AI Optimization Guide for the llms.txt stance, INP as a Core Web Vital, the dual AI Readiness/Visibility scoring model). Core checks (crawlability, HTTPS, titles/metas, heading hierarchy, schema validity, E-E-A-T signals) are long-stable; the AI-search sections are the fastest-moving and are expected to be revised in future versions of this plugin. When guidance changes, update this file and bump the plugin version rather than forking.

## Trigger
Activate when the user says: "seo-audit", "audit my site", "full SEO check", "website health check", or provides a URL and asks for an SEO audit.

## Behavior
When triggered, immediately run a comprehensive SEO audit on the provided URL. Do not ask clarifying questions. Execute the full audit process below, then output the complete report as a single self-contained, print-ready **HTML artifact** the user can download as a PDF from their browser (see "Output Format" below). This skill does not read or write any local files.

---

## Language Detection (Run Before Any Analysis)

**Step 0 — Detect site language and report language.**

1. **Site language:** Fetch the homepage and detect the primary language from `<html lang="...">`, `Content-Language` headers, `og:locale` meta, or dominant text content. This determines which readability benchmarks and content quality criteria apply.

2. **Report language:** Default to English unless the user wrote their request in another language. If the user asks in German, French, Spanish, etc., write the entire report in that language.

3. **Record the detected site language code** (e.g., `en`, `de`, `fr`, `es`, `nl`, `it`, `pt`, `pl`, `ja`, `zh`, `ar`) and apply it throughout Steps 3–4.

**Language codes → inLanguage values for schema validation:**

| Language | Expected inLanguage | Notes |
|---|---|---|
| English | `en`, `en-US`, `en-GB` | Default |
| German | `de`, `de-DE`, `de-AT`, `de-CH` | |
| French | `fr`, `fr-FR`, `fr-BE`, `fr-CH` | |
| Spanish | `es`, `es-ES`, `es-MX`, `es-AR` | |
| Dutch | `nl`, `nl-NL`, `nl-BE` | |
| Italian | `it`, `it-IT` | |
| Portuguese | `pt`, `pt-PT`, `pt-BR` | |
| Polish | `pl`, `pl-PL` | |
| Japanese | `ja`, `ja-JP` | Readability: use character-based metrics, not Flesch |
| Chinese | `zh`, `zh-CN`, `zh-TW` | Readability: use character-based metrics, not Flesch |
| Arabic | `ar` | RTL — flag missing `dir="rtl"` on `<html>` as Medium issue |
| Korean | `ko`, `ko-KR` | Readability: use character-based metrics, not Flesch |

When validating schema, flag any `inLanguage` value that does not match the detected site language as a Medium issue.

---

## Strict Fetch Rules — Mandatory Behavior, No Exceptions

### Rule 1 — llms.txt
Fetch `https://{domain}/llms.txt` as the VERY FIRST action before any other analysis.

- HTTP 200 → EXISTS. Read and parse contents. Mark as present. Done.
- HTTP 404 → MISSING. Flag as **Low/Info** (never Medium or higher). Note in the finding: "Google's AI Optimization Guide (June 2026) states llms.txt is unnecessary for Google AI features. Potentially useful for ChatGPT/Perplexity discovery."
- Fetch blocked by CDN/WAF/Cloudflare (any error, 403, connection refused, timeout) → **Remove from the findings table entirely.** Do not add it as any severity level. In the appendix only, add one line: "llms.txt: fetch blocked by CDN — status unverifiable." That is all. Do not recommend creating it based solely on a blocked fetch.

Also check `https://{domain}/llms-full.txt` with the same logic.

Never infer llms.txt presence or absence from page HTML, meta tags, or any other source.

### Rule 2 — robots.txt and AI Crawlers
Fetch `https://{domain}/robots.txt`.

- Fetch returns content → parse it, report what you find.
- Fetch BLOCKED by CDN/WAF/Cloudflare → **Remove "AI crawler rules unverified/unconfirmed" from the findings table entirely.** Do not add it as any severity level. In the appendix only, add one line: "robots.txt: fetch blocked by CDN — AI crawler rules unverifiable." Do not flag AI crawler access as unknown or unverified anywhere else in the report.

A CDN blocking your WebFetch request is not evidence of a site configuration problem.

### Rule 3 — Schema Detection (JS-Rendered Sites)
Fetch the raw page HTML and search for every `<script type="application/ld+json">` block. Parse each one as JSON.

- Schema found in static HTML → report what was found.
- Schema NOT found in static HTML on a site using Elementor, WordPress, Squarespace, Webflow, or any JS-heavy CMS/page builder → **Do NOT flag those schema types as missing.** Schema on these platforms is frequently injected by SEO plugins (Yoast, RankMath, Schema Pro) in ways that do not appear in a raw WebFetch due to CDN caching or JavaScript rendering. Instead, for any schema type you could not confirm, write: "Not detected in static HTML — likely JavaScript-rendered or plugin-injected. Verify at search.google.com/test/rich-results before flagging as absent."
- Only flag a schema type as definitively MISSING if the site is a static HTML site with no CMS or JS rendering.

Do NOT infer schema presence or absence from the CMS stack, installed plugins, or visual page content.

### Rule 4 — Non-Standard URL Slugs
Language subfolder slugs like `/spa/`, `/jpn/`, `/kr/`, `/fra/`, `/rus/`, `/chs/`, `/cht/` are a deliberate business decision.

- **Never add them to the findings table.** Not as any severity level.
- **Never add ⚠️ warning symbols next to them in the appendix.** List them neutrally, e.g.: `Spanish: /spa/ — hreflang="es"` (just showing the mapping, no warning icon).
- The only hreflang issues to flag are: (a) the `hreflang="..."` attribute values themselves are invalid BCP 47 codes, (b) reciprocal return tags are confirmed missing, or (c) x-default is confirmed absent. Suspicion alone is not enough — only flag if you can confirm the error from fetched page source.

### Rule 5 — CDN/WAF Blocked Fetches (General)
When any fetch is blocked by server-level protection (Cloudflare, WAF, CDN — identified by connection errors, firewall 403s, or empty responses rather than actual 404s):

- Do NOT penalize the site's score for that item.
- Do NOT add it to the findings table.
- Do NOT describe it as an "issue" or "risk" in the report.
- Add a single neutral line in the appendix: "[file]: fetch blocked by CDN — status unverifiable via automated audit."
- Move on.

---

## Audit Process

### Step 1 — Fetch & Analyze Homepage
- Fetch the homepage HTML
- Detect: business type, industry, CMS/platform, tech stack
- Record: title tag, meta description, H1, canonical, robots meta, Open Graph, Twitter Card

### Step 2 — Technical SEO
- robots.txt: accessible, disallow rules, sitemap reference
- XML sitemap: present, valid, indexed pages count
- HTTPS: valid SSL, HSTS headers, mixed content
- Canonical tags: self-referencing, conflicting
- Redirect chains: 3xx hops, www/non-www, trailing slashes
- Core Web Vitals: LCP, INP, CLS estimates
- Mobile-friendliness: viewport meta, tap target sizes
- Page speed signals: render-blocking resources, image compression, lazy loading
- Security headers: CSP, X-Frame-Options, X-Content-Type-Options
- Crawl depth and internal link structure
- Hreflang:
  - After fetching the raw page HTML, scan the full `<head>` for ALL of the following before drawing any conclusion:
    - `<link rel="alternate" hreflang="..." href="...">` tags
    - `<link rel="alternate" hreflang="x-default" href="...">` tag
  - Also check the HTTP response headers for `Link:` header hreflang entries
  - Also fetch and parse the XML sitemap(s) for `<xhtml:link rel="alternate" hreflang="...">` entries
  - Only flag hreflang as MISSING if it is absent from ALL three locations: page `<head>`, HTTP headers, and sitemaps
  - If hreflang IS present, validate it:
    - Every hreflang URL must have a reciprocal return tag on the target page
    - `x-default` tag should be present
    - Language codes must be valid BCP 47 (e.g. `en`, `en-US`, `fr-CA`)
    - All hreflang URLs must return 200 (not 404 or redirect)
  - Do NOT infer hreflang absence from page content, language signals, or any source other than direct inspection of the fetched HTML, headers, and sitemap

### Step 3 — On-Page SEO
- Title tags: length (50–60 chars), uniqueness, keyword placement
- Meta descriptions: length (150–160 chars), CTR-optimized
- Heading hierarchy: H1 uniqueness, H2–H4 structure
- URL structure: clean slugs, keyword inclusion, length
- Image alt text: presence, descriptiveness, keyword use
- Internal linking: anchor text diversity, orphan pages
- Content length and depth per page type
- Duplicate content signals

### Step 4 — Content Quality (E-E-A-T)

The criteria in this step are shared with the Blog Engine skill (`blog-write` / `blog-audit` / `blog-rewrite`) so content-quality findings and scores are consistent whichever skill produced them.

- Author signals: named author with bio and a specific credential. Flag "Admin", "Staff", or missing bylines (same rule as the blog skill)
- Trust signals: About page, Contact page, Privacy Policy, Terms, editorial policy/methodology disclosure
- Expertise signals: citations, sources, data freshness. Apply the shared source tier standard: Tier 1 (.gov, .edu, peer-reviewed, official standards bodies), Tier 2 (established industry research firms and studies), Tier 3 (reputable industry publications) are acceptable. Flag Tier 4-5 sources (generic SEO blogs, affiliate sites, content mills, unsourced roundups) and any statistic with no named source
- Experience signals: first-hand content indicators ("When we tested...", "In our experience...", original screenshots, first-party data)
- Thin content: pages under 300 words. For blog/article pages, also apply the shared length benchmarks: standard post minimum 1,500 words (target 2,000-2,500); pillar/comprehensive guide minimum 2,500 (target 3,000-4,000); comparison minimum 1,200; news/update minimum 600
- Content structure (blog/article pages): flag paragraphs over 150 words (critical at 200+), skipped heading levels (e.g. H1 straight to H3), and section openers that bury the answer instead of leading with a 40-60 word direct answer containing a sourced stat (answer-first formatting)
- AI-generated content signals — use the shared 3-signal detection method and thresholds:
  1. **Burstiness:** sentence-length standard deviation under 5 words = flag
  2. **AI phrase density:** more than 5 flagged phrases per 1,000 words = flag. Apply language-appropriate overused-phrase detection; do not flag German, French, or Spanish text against English AI phrase lists. Em dash overuse counts as an additional AI-writing signal
  3. **Vocabulary diversity:** Type-Token Ratio under 0.40 = flag (healthy is above 0.50)
  Report the combined result as "AI content estimate: ~X%"
- Severity mapping for content issues (same ladder as the blog skill): fabricated or unsourced statistics, broken heading hierarchy, paragraphs over 200 words = CRITICAL. Missing answer-first formatting, fewer than 8 sourced statistics on a data-driven post, missing meta description, passive voice over 15% = HIGH. Tier 4-5 sources, no first-person experience markers, sections over 300 words without a sub-heading = MEDIUM
- Readability: estimate grade level using language-appropriate benchmarks:
  - **English:** Flesch Reading Ease 60–70 (acceptable 55–75); Grade 7–8
  - **German:** Flesch RE 40–55 (acceptable 30–60) — compound words structurally lower scores; do NOT apply English thresholds
  - **French:** Flesch RE 50–65 (acceptable 45–70)
  - **Spanish:** Flesch RE 55–70 (acceptable 50–75)
  - **CJK (Japanese, Chinese, Korean) / Arabic:** Do not use Flesch. Assess subjectively: sentence complexity, paragraph length, use of plain language vs jargon. Flag only if content is demonstrably difficult to parse for the target audience.
  - **All other languages:** Assess subjectively against the same structural criteria (short paragraphs, plain language, logical flow) without applying English Flesch thresholds

### Step 5 — Schema Markup
- Fetch the raw page source and parse ALL of the following locations for structured data:
  - `<script type="application/ld+json">` blocks (JSON-LD) — check every instance on the page
  - `<meta>` and `<link>` tags (RDFa, Open Graph, Twitter Card)
  - Microdata attributes (`itemscope`, `itemtype`, `itemprop`) embedded in HTML elements
  - Check the `/wp-json/` REST API endpoint (if WordPress detected) for schema output
  - Check `<head>` for any injected JSON payloads from SEO plugins (Yoast, RankMath, Schema Pro)
- For each JSON-LD block found: parse the full JSON, identify `@type`, `@context`, and all properties
- Validate each schema object against Schema.org specs — flag missing required and recommended properties
- Check for nested/graph schemas (`@graph` arrays) and validate each node individually
- Flag malformed JSON (parse errors, unclosed brackets, trailing commas)
- Flag missing high-impact schema types: Organization, WebSite, BreadcrumbList, Article/BlogPosting, FAQPage, LocalBusiness (if applicable), Product (if applicable), SiteLinksSearchBox
- Report: schema types found, properties present, properties missing, validation errors, rich result eligibility per type

### Step 6 — AI Readiness & AI Visibility (two separate scores)
- AI crawler access: explicitly fetch `https://{domain}/robots.txt` and scan for:
  GPTBot, ClaudeBot, PerplexityBot, Googlebot-Extended — note Allow/Disallow rules per bot

- llms.txt: 
  - Explicitly fetch `https://{domain}/llms.txt` via HTTP GET
  - If HTTP 200 is returned: file EXISTS — read and parse the full contents
  - Check for: `# {Site Name}` header, `> description` block, `## Section` headings, and `- [Title](URL)` link entries
  - Verify that the audited URL's domain matches links listed in the file
  - Flag as MISSING only if the fetch returns 404 or a non-200 status
  - Do NOT infer llms.txt presence from page HTML, meta tags, or any source other than a direct HTTP request to `/llms.txt`
  - Also check `https://{domain}/llms-full.txt` as a secondary extended file
- Brand mention signals and citability
- Passage-level citability: clear answers, structured facts, quotable paragraphs
- AI Overview eligibility indicators

**This step produces TWO separate 0-100 scores. Never blend them, never report only one.** Readiness is the technical/structural foundation (can AI systems find, parse, and extract from the site). Visibility is the observed or modeled outcome (is the brand actually showing up in AI answers). A site can score high on one and low on the other; that gap is itself a finding to name plainly, not a contradiction to resolve.

#### Score 1 — AI Readiness Score (0-100, checklist-based)

Plain-English explanation to use in the report: "This shows whether the site has the technical foundation AI systems need in order to find, crawl, and pull accurate information from it. It does not measure whether AI tools are actually citing the brand yet; that is the separate AI Visibility score."

Five weighted categories summing to 100. Score each proportionally to checks passed (e.g. 3 of 5 AI crawlers allowed = 15 of 25), sum, round to nearest integer:

| Category | Points | What it checks |
|---|---|---|
| AI crawler accessibility | 25 | robots.txt allows GPTBot, ClaudeBot, PerplexityBot, Google-Extended, and Amazonbot; key pages are not JS-rendered with no crawlable fallback |
| Structured data for AI extraction | 25 | Relevant schema present and error-free: Organization, FAQPage/HowTo where applicable, Article/Product, breadcrumbs (use Step 5 results; JS-render rule applies) |
| Passage-level citability | 20 | Key pages have direct-answer intros, clear Q&A formatting, scannable headers, concise definitional paragraphs an AI system can lift cleanly |
| llms.txt presence & quality | 10 | Present, accurate, substantive rather than a stub (low weight per Google's June 2026 AI Optimization Guide: Low/Info priority, not required) |
| E-E-A-T / entity clarity | 20 | Author bylines, consistent organization entity (sameAs links, NAP), content freshness (dateModified), sourced claims |

Any check that is unverifiable due to a CDN-blocked fetch is scored neutrally per the Strict Fetch Rules: exclude that check from its category and score the category on the remaining verifiable checks. Uses the standard score classes (Good ≥80 / Needs Work 50-79 / Poor <50).

#### Score 2 — AI Visibility Score (0-100, prompt-based)

Plain-English explanation to use in the report: "This shows how often, and how strongly, AI tools recommend the brand when people ask real questions. It does not measure whether the site is technically set up for AI to find it."

Crawler access, llms.txt, schema, and passage structure are leading indicators that make citation more likely. They belong in the Readiness score above and must NEVER be folded into this number.

1. Build 8-12 **unbranded, buyer-intent** prompts a real prospect would ask, covering: category definition, best-of/listicle, comparison/alternatives, regional or contextual, and problem/solution. Never include brand-lookup prompts ("What is [Brand]?"); they test recall, not competitive recommendation, and inflate the score.
2. Score every (prompt × platform) event for ChatGPT, Perplexity, and Google AI Overviews on prominence: 5 = named as the primary/top recommendation, 3 = named as a secondary recommendation or linked source, 1 = mentioned only in passing or buried in a list, 0 = absent.
3. `AI Visibility Score = (total raw prominence points ÷ (5 × prompts × platforms)) × 100`
4. Since this skill cannot query AI platforms live, **model** each prompt's likely outcome from evidence actually gathered: brand/entity presence (Wikipedia, Reddit, YouTube, LinkedIn), press and launch coverage, and content citability. Do not substitute a domain-authority or readiness composite for this. Label the result clearly as an estimate with a one-line method note (e.g. "Estimated from brand mention signals found during this audit; no live AI platform testing was run").
5. Include the full prompt × platform results table in the report, including every "Not mentioned" row; the misses are the finding. Use plain-English cell labels: "Top pick" / "Mentioned as an option" / "Mentioned briefly" / "Not mentioned".

**Bands (AI Visibility only — do NOT apply the standard 80/50 classes to this score):**

| Band | Range | Class |
|---|---|---|
| Pre-visibility | 0-8 | poor |
| Early Traction | 8-25 | poor |
| Category Presence | 25-50 | avg |
| Category Authority | 50-75 | good |
| Category Dominance | 75-100 | good |

Disclose limitations rather than paper over them: AI responses are non-deterministic (a single snapshot is noise), a modeled estimate is only as good as the brand-signal research feeding it, and this is a leading indicator, not a revenue metric.

### Step 7 — Local SEO (if local business detected)
- Google Business Profile signals
- NAP consistency (Name, Address, Phone) across page
- Local schema: LocalBusiness, geo coordinates, opening hours
- Location page quality
- Review signals

### Step 8 — Scoring
Calculate scores (0–100) for each category:
- Overall SEO Health Score
- Technical SEO
- On-Page SEO
- Content Quality
- Schema Markup
- AI Readiness (checklist score from Step 6)
- AI Visibility (prompt-based score from Step 6 — reported with its own bands, see below)
- (Local SEO if applicable)

Score classes: Good = 80–100, Needs Work = 50–79, Poor = 0–49. **Exception:** AI Visibility uses its own bands (good ≥50 / avg 25-49 / poor <25) because observed citation share is a different scale than a checklist score; never apply the 80/50 rule to it.

**Alignment with the Claude Code `/seo-audit` skill (this is the browser edition of that skill):**
- The Strict Fetch Rules, hreflang/slug handling, schema JS-render rule, CDN neutrality, and llms.txt Low/Info stance mirror the desktop skill's Audit Rules
- The dual AI scoring model (Readiness 25/25/20/10/20 checklist + Visibility via 5/3/1/0 prominence on unbranded prompts, with the 50/25 visibility bands) follows the same canonical methodology the desktop skill and its `seo-geo` subagent use. Both scores must always appear together; the readiness-vs-visibility gap is a named finding, not an error
- What this edition intentionally does NOT replicate from the desktop skill: the 500-page crawl (WebFetch sampling only — disclose sampled page count), the 9 parallel subagents, Domain Authority and estimated-organic-reach modeling, the 9-tab HTML template with local file output, and FTP publishing. Do not fake any of these; a print-ready artifact from sampled pages is the deliverable
- Content Quality criteria (Step 4) additionally match the Blog Engine skill (`blog-write` / `blog-audit` / `blog-rewrite`): source tiers, author attribution, answer-first formatting, paragraph/heading limits, 3-signal AI detection, language-adjusted readability. When this audit surfaces weak blog content, recommend running `blog-audit` on the specific posts (and `blog-rewrite` to fix them)

---

## Output Format — Downloadable PDF Report (Browser)

Generate a single, complete, print-ready **HTML artifact** rendered directly in the conversation for the user to download as a PDF from their browser. This skill does NOT read, write, or reference any local files, templates, or filesystem paths — everything is self-contained in the artifact.

The artifact must be:
- **Fully self-contained** — inline CSS only, no external stylesheets, fonts, scripts, or image dependencies.
- **Print-ready** — formatted to print cleanly as a PDF at A4/Letter size.

The report must include:

### Cover Section
- Site URL and domain
- Audit date
- Business/industry type
- Overall SEO Health Score (large, prominent, color-coded)

### Executive Summary
- 3–5 sentence plain-English summary of site health
- Top 3 critical issues that need immediate attention
- Quick wins (3 issues that are easy to fix for fast gains)

### Score Dashboard
All category scores as a visual scorecard table:
| Category | Score | Status |
Each row color-coded: green (Good), amber (Needs Work), red (Poor). The AI Visibility row is color-coded by its own bands (green ≥50, amber 25-49, red <25) and shows its band name (e.g. "Early Traction") as the status.

### AI Search Section (required)
- Both AI scores side by side with their plain-English explanations from Step 6 (never just one score)
- The estimation method note for AI Visibility
- The full prompt × platform results table, including every "Not mentioned" row
- Readiness signal findings (crawler access, schema, llms.txt, passage structure) listed under Readiness only, never as visibility evidence

### Section-by-Section Findings
For each audit section, include:
- Section score
- Key findings (bullet list)
- Issues found, each labeled: CRITICAL / HIGH / MEDIUM / LOW

### Prioritized Action Plan
Four sections:
1. **Critical** — fix within 48 hours
2. **High** — fix within 2 weeks
3. **Medium** — fix within 30 days
4. **Low / Quick Wins** — ongoing improvements

Each action item includes: issue name, why it matters, specific fix instructions.

### Full Findings Table
| Issue | Severity | Category | Recommended Fix |

### Appendix
- Raw technical data: response codes, page count, crawl stats
- Schema types detected
- AI platform visibility breakdown

**Score class rule (apply everywhere):** `good`/green = ≥80, `avg`/amber = 50–79, `poor`/red = <50.

---

## PDF Download Instructions

After generating the artifact, add this message outside the artifact:

---
**To save as PDF:**
- **Mac:** Press `Cmd + P` → set destination to "Save as PDF" → Save
- **Windows:** Press `Ctrl + P` → set destination to "Save as PDF" → Save
- **Tip:** Set print margins to "Minimum" or "None" for best results
---

## Inline CSS Requirements for the Artifact

The artifact HTML must include these print styles in a `<style>` block:

```css
@media print {
  body { font-family: -apple-system, Arial, sans-serif; font-size: 11pt; color: #111; }
  .page-break { page-break-before: always; }
  .no-print { display: none; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #ddd; padding: 6px 10px; font-size: 10pt; }
  th { background-color: #f5f5f5 !important; -webkit-print-color-adjust: exact; }
  .score-good { color: #16a34a; font-weight: bold; }
  .score-avg { color: #d97706; font-weight: bold; }
  .score-poor { color: #dc2626; font-weight: bold; }
  .badge-critical { background: #dc2626; color: white; padding: 2px 6px; border-radius: 3px; font-size: 9pt; -webkit-print-color-adjust: exact; }
  .badge-high { background: #ea580c; color: white; padding: 2px 6px; border-radius: 3px; font-size: 9pt; -webkit-print-color-adjust: exact; }
  .badge-medium { background: #d97706; color: white; padding: 2px 6px; border-radius: 3px; font-size: 9pt; -webkit-print-color-adjust: exact; }
  .badge-low { background: #6b7280; color: white; padding: 2px 6px; border-radius: 3px; font-size: 9pt; -webkit-print-color-adjust: exact; }
  h1 { font-size: 22pt; margin-bottom: 4px; }
  h2 { font-size: 15pt; border-bottom: 2px solid #111; padding-bottom: 4px; margin-top: 24px; }
  h3 { font-size: 12pt; margin-top: 16px; }
  .cover { text-align: center; padding: 60px 0 40px; }
  .score-circle { display: inline-block; width: 100px; height: 100px; border-radius: 50%; line-height: 100px; font-size: 32pt; font-weight: bold; text-align: center; -webkit-print-color-adjust: exact; }
}
body { font-family: -apple-system, Arial, sans-serif; font-size: 13px; color: #111; max-width: 900px; margin: 0 auto; padding: 24px; }
```

---

## Non-Negotiable Rules
- Output the report ONLY as a self-contained HTML artifact in the conversation — never read or write local files, templates, or filesystem paths.
- Run the full audit. Do not truncate findings or summarize early. Every section must be populated with real data fetched from the URL.
- If a page cannot be fetched, state so and audit what is accessible.

---

## Definition of done

**Pass condition (checkable without argument):**
- The output is one self-contained HTML artifact (inline CSS only, no external dependencies) containing every required section: cover, executive summary, score dashboard, AI search section, per-section findings, prioritized action plan, full findings table, appendix.
- Both AI scores appear together (Readiness 0-100 checklist score AND Visibility 0-100 prompt-based score with its band name), each with its plain-English explanation, and the full prompt-by-platform table includes every "Not mentioned" row.
- Every claim in the findings table traces to something actually fetched during the run. Nothing that a CDN-blocked fetch made unverifiable appears in the findings table; blocked fetches appear only as one neutral appendix line each, per the Strict Fetch Rules.
- The AI Visibility method note states whether results were live-tested or estimated.

**Golden example:** Input: "audit https://example-shop.com". Output: a print-ready HTML report artifact where, e.g., llms.txt returned 404 and is listed once as Low/Info with the Google June 2026 note; schema found in static HTML is validated with missing recommended properties listed; the AI section shows Readiness 62 and Visibility 14 (Early Traction) with a 10-prompt x 3-platform table where most cells read "Not mentioned"; the action plan has concrete fixes grouped Critical/High/Medium/Low.

**Adversarial case:** Input: a URL fully behind Cloudflare where robots.txt, llms.txt, and most page fetches are blocked. Expected behavior: the report says plainly which fetches were blocked, audits only what was accessible (e.g. the rendered homepage content), scores affected categories on the remaining verifiable checks, adds one neutral appendix line per blocked file, and does NOT fabricate crawler-access findings, invent schema conclusions, or penalize the score for unverifiable items. If nothing at all is fetchable, it says the audit cannot be run rather than inventing a report.
# Phone AI Agent

Phone AI Agent recommends phones from the user's budget, market, platform preference,
important use cases, and exclusions.

The project is being built around one rule:

> Data filters and scoring choose the phones. The AI explains the result.

## Current MVP

The first MVP already separates the main responsibilities:

- `app.py` collects user preferences in a Streamlit form.
- `schemas.py` defines the user preferences, phone candidates, and scored results.
- `services/scoring_service.py` filters and ranks phones with deterministic weights.
- `services/recommendation_service.py` returns the top three candidates.
- `llm/explainer.py` explains ranked results with OpenAI when `OPENAI_API_KEY` exists.
- `models.py`, `db.py`, and `services/cache_service.py` provide the Neon/Postgres
  cache tables and TTL-backed cache access.
- `services/specs_service.py` fetches and normalizes initial phone specs from official
  manufacturer support or product pages.
- `services/spec_discovery_service.py` uses Tavily search, when configured, to
  discover additional official Apple and OnePlus spec pages that match supported
  normalizers.
- `services/search_service.py` can fetch structured Google Shopping results through
  SerpAPI and cache those payloads in Neon.
- `services/mediamarkt_tr_service.py` reads JSON-LD prices from MediaMarkt Turkey as
  the first direct retailer provider.
- `services/pttavm_tr_service.py` reads JSON-LD prices from PttAVM Turkey as the
  second direct retailer provider.
- `services/price_service.py` turns matching shopping results into price observations.

The recommendation flow now starts from official spec pages for an initial supported
phone set. It ranks only phones that have a real recent market price converted to USD
from the price layer or loaded from Neon.

## User Workflow

The user answers:

1. Budget in USD.
2. Country or target market.
3. Android, iPhone, or no preference.
4. Important uses:
   - Camera
   - Gaming
   - Battery
   - Screen
   - Work and study
   - Social media
   - Compact size
   - Large storage
5. Exclusions:
   - Rejected brands
   - Large screens
   - Fast charging requirement

The app returns:

1. The best three phones for the budget.
2. Why each phone was selected.
3. Weaknesses and tradeoffs.
4. The important specs behind the recommendation.
5. A ranking focused on value for the budget.

## System Workflow

```text
Streamlit UI
    |
UserPreferences
    |
Search / Specs / Price tools
    |
Normalize phone and price data
    |
Neon cache
    |
Deterministic filters and scoring
    |
Top 3 phones
    |
OpenAI explanation
```

For the current MVP, normalized specs come from official source pages for the initial
supported phone set. Shopping price observations can come from SerpAPI and use Neon
`search_cache` entries when a fresh cached payload already exists. Market prices are
stored in `phone_prices` and the recommendation filter uses `price_usd`.

## Recommendation Logic

Filtering happens before scoring:

- Reject phones over budget.
- Respect Android or iPhone preference.
- Exclude rejected brands.
- Exclude large screens when requested.
- Require fast charging when requested.

Scoring uses weighted phone attributes:

- Camera score
- Gaming score
- Battery score
- Screen score
- Work and study score
- Social media score
- Compact size score
- Storage score
- Value score

User priorities raise the weight of the matching attributes. Value remains important
so a light-use buyer is not pushed toward an expensive flagship without a reason.

## Planned Architecture

```text
app.py
agent.py
config.py
db.py
models.py
schemas.py
llm/
  explainer.py
services/
  cache_service.py
  price_service.py
  pttavm_tr_service.py
  recommendation_service.py
  scoring_service.py
  spec_discovery_service.py
  search_service.py
  specs_service.py
```

## Neon Cache Plan

Neon is intended as a short-lived cache, not a manually maintained catalog.

The planned live flow is:

1. Build a search query from the user's market and priorities.
2. Look for fresh cached candidates and prices.
3. If cache data is older than the configured TTL, fetch fresh shopping data.
4. Extract and normalize phone specs and prices.
5. Store the cleaned results in Neon.
6. Score the normalized candidates and explain the top results.

Prepared tables:

- `phones`: normalized phone specs and quality scores.
- `phone_prices`: market/store prices collected at different times.
- `search_cache`: stored provider responses or normalized search payloads.

Current cache behavior:

- If `DATABASE_URL` is missing, the app skips database caching cleanly.
- If `DATABASE_URL` exists, the cache service creates required tables before use.
- Official spec page payloads can be cached in Neon before normalization.
- Normalized official specs are upserted into `phones`.
- Fresh market prices are stored in `phone_prices`.
- If a SerpAPI payload is fresh, it is reused instead of requesting it again.
- If the price provider fails, recommendations still use the official specs path.

Suggested cache freshness:

- Phone specs: refresh when the source changes or after a longer interval.
- Prices: refresh after 24 to 48 hours.

## Data Source Direction

Prefer APIs or structured search providers when available.

Specs candidates:

- Official manufacturer pages
- GSMArena
- Kimovil
- 91mobiles

Price candidates:

- Search APIs with structured shopping results
- MediaMarkt Turkey JSON-LD search results for the first Turkey price provider
- Amazon and local retailers where allowed
- Trendyol and Hepsiburada for Turkey
- Noon and other local retailers for supported markets

Each provider should be isolated behind a service so data source changes do not rewrite
the UI or scoring engine.

## Search API Setup

Tavily is the current search provider for official spec discovery:

- It searches trusted official domains only.
- It feeds supported official Apple and OnePlus spec pages into the spec normalizers.

Setup steps:

1. Create or sign in to a Tavily account.
2. Copy the Tavily API key.
3. Add it to the local `.env` file:

```text
TAVILY_API_KEY=your_private_key_here
```

4. Restart Streamlit so the environment variable is loaded.
5. Run a recommendation again. The data note should mention Tavily discovery when
   newly supported official pages are found.

Keep the key only in backend environment variables. Do not place it in Streamlit UI
fields or browser-side JavaScript.

`SERPAPI_API_KEY` remains optional for Google Shopping prices. Turkey currently has
direct MediaMarkt and PttAVM price providers even without SerpAPI.

## Environment

Install dependencies:

```powershell
pip install -r requirements.txt
```

Useful environment variables:

```text
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
DATABASE_URL=
CACHE_TTL_HOURS=48
SERPAPI_API_KEY=
TAVILY_API_KEY=
```

Run the current app:

```powershell
streamlit run app.py
```

Without `OPENAI_API_KEY`, the app still returns a local explanation for scored
recommendations.

Without `SERPAPI_API_KEY`, the app still ranks official specs and reports that shopping
observations are not enabled yet. Turkey can still use the direct MediaMarkt provider.
If Neon and the active providers have no fresh real market prices for the selected
country, the app will return no budget-ranked phones instead of using invented prices.

## Development Roadmap

### Phase 1: MVP foundation

- Streamlit preference form.
- Deterministic filtering and scoring.
- Official specs collection for an initial supported phone set.
- OpenAI explanation with a local fallback.
- Neon schema foundation.

### Phase 2: Live candidate collection

- Add a search service for phone candidates. Started with cached SerpAPI shopping
  observations.
- Add a specs extractor and normalizer. Started with official source pages and
  SerpAPI-backed supported spec discovery.
- Add a price provider or price scraper for the first supported market. Started with
  MediaMarkt Turkey, PttAVM Turkey, and SerpAPI Google Shopping observations.
- Store and reuse fresh results from Neon. Started for search payloads.
- Add source URLs and freshness indicators to recommendations.

### Phase 3: Recommendation quality

- Improve phone variant matching for RAM, storage, and regional versions.
- Improve price conversion and market-specific availability logic.
- Add evidence-aware weaknesses and tradeoffs.
- Add tests for filters, scoring, and normalization.
- Add a comparison view for two or more phones.

### Phase 4: Product expansion

- Support more countries and retailers.
- Add best value analysis over time.
- Add price drop tracking and alerts.
- Add user memory for repeated preferences.
- Add recommendation history and feedback.

## Open Decisions

These decisions should be revisited as the project evolves:

- Which market should be the next live market after Turkey?
- Which structured search or shopping API should be used first?
- How should camera, gaming, battery, and value scores be calculated from raw specs?
- Which sources are reliable enough for automated refresh in each country?

#!/usr/bin/env python3
"""
Greenhouse Slug Discovery Tool

Discovers new Greenhouse companies from a curated seed list of tech companies
in London, NYC, and Denver. Validates they're scrapeable and optionally adds
to company_ats_mapping.json.

Usage:
    python pipeline/utilities/discover_greenhouse_slugs.py [--dry-run] [--batch-size 5] [--save]

Options:
    --dry-run       Test slugs but don't save results (default behavior)
    --save          Save valid slugs to company_ats_mapping.json
    --batch-size N  Number of concurrent tests (default: 5)
    --limit N       Limit total companies to test

Sources for seed list:
    - Y Combinator NYC/London companies (2023-2025)
    - Built In NYC/Colorado Best Places to Work (2024-2025)
    - London fintech Series B/C rounds (2024)
    - Denver/Boulder tech scene (2024)
    - Known Greenhouse customers from industry reports
    - Expanded verticals (2025-12): Cybersecurity, Climate Tech, Logistics,
      Crypto/Web3, Gaming, HR Tech, InsurTech, Sports Tech, Aerospace/Defense,
      Legal Tech, Hardware/Robotics, Food/Ag Tech, Infrastructure/Cloud, AI/ML
"""

import asyncio
import json
import re
import argparse
from pathlib import Path
from datetime import datetime

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Playwright not installed. Run: pip install playwright && playwright install chromium")
    exit(1)

# =============================================================================
# SEED LIST: Tech companies in target locations NOT already in mapping
# Compiled from web research on 2025-12-06, expanded 2025-12-30
# Locations: London, NYC, Denver, SF Bay Area, Singapore
# =============================================================================

SEED_COMPANIES = {
    # =========================================================================
    # NYC - AI/ML & Data Companies
    # =========================================================================
    "Plaid": ["plaid"],
    "Brex": ["brex"],
    "Ramp": ["ramp"],
    "Current": ["current", "currentmobile"],
    "SmartAsset": ["smartasset"],
    "Enigma": ["enigma", "enigmaio"],
    "Dagster": ["dagster", "dagsterlabs"],
    "Pinecone": ["pinecone", "pineconeio"],
    "Runway": ["runwayml", "runway"],
    "Osmo": ["osmo", "osmoai"],
    "Modal": ["modal", "modallabs"],
    "Cohere": ["cohere", "cohereai"],
    "Weights & Biases": ["wandb", "weightsandbiases"],
    "Labelbox": ["labelbox"],
    "Weights and Biases": ["wandb"],

    # NYC - Fintech & Insurtech
    "Petal": ["petal", "petalcard"],
    "Hopscotch": ["hopscotch"],
    "Commonstock": ["commonstock"],
    "Percent": ["percent"],
    "NewFront Insurance": ["newfront", "newfrontinsurance"],
    "Capitolis": ["capitolis"],
    "Betterment": ["betterment"],
    "MoneyLion": ["moneylion"],

    # NYC - Healthtech
    "Tempus": ["tempus", "tempuslabs"],
    "Nourish": ["nourish", "nourishco"],
    "Galileo Health": ["galileohealth", "galileo"],
    "Thirty Madison": ["thirtymadison"],
    "Alto Pharmacy": ["altopharmacy", "alto"],
    "Cityblock Health": ["cityblock", "cityblockhealth"],
    "Dispatch Health": ["dispatchhealth"],
    "Capsule": ["capsule", "capsulepharmacy"],
    "Color Health": ["color", "colorhealth"],
    "Sword Health": ["swordhealth", "sword"],

    # NYC - Enterprise/B2B SaaS
    "Stainless": ["stainless", "stainlessapi"],
    "Ambient AI": ["ambientai", "ambient"],
    "Nautilus Labs": ["nautiluslabs", "nautilus"],
    "Fora Travel": ["fora", "foratravel"],
    "Gynger": ["gynger"],
    "EquityMultiple": ["equitymultiple"],
    "Grocery TV": ["grocerytv"],
    "Atom Finance": ["atomfinance", "atom"],
    "Able": ["able", "ableteam"],
    "Courier Health": ["courierhealth"],
    "Landis": ["landis", "landishomes"],
    "Check": ["check", "checkhq"],
    "Monograph": ["monograph"],
    "Metadata": ["metadata", "metadataio"],
    "Personio": ["personio"],
    "Census": ["census", "getcensus"],
    "Hex": ["hex", "hextechnologies"],
    "Hightouch": ["hightouch"],
    "dbt Labs": ["dbtlabs", "dbt"],
    "Prefect": ["prefect", "prefectio"],
    "Airbyte": ["airbyte"],
    "Temporal": ["temporal", "temporalio"],
    "LaunchDarkly": ["launchdarkly"],
    "Split": ["split", "splitio"],
    "Statsig": ["statsig"],
    "Eppo": ["eppo", "geteppo"],

    # NYC - Media & Consumer
    "Substack": ["substack"],
    "Cameo": ["cameo"],
    "Strava": ["strava"],
    "AllTrails": ["alltrails"],
    "ClassPass": ["classpass"],
    "Goldbelly": ["goldbelly"],
    "Cake": ["cake", "joincake"],

    # =========================================================================
    # LONDON - Fintech & Banking
    # =========================================================================
    "Revolut": ["revolut"],
    "Checkout.com": ["checkout", "checkoutcom"],
    "OakNorth": ["oaknorth"],
    "9fin": ["9fin"],
    "Abound": ["abound", "getabound"],
    "Yonder": ["yonder", "yondercard"],
    "Tembo Money": ["tembo", "tembomoney"],
    "Fundment": ["fundment"],
    "Thought Machine": ["thoughtmachine"],
    "Yapily": ["yapily"],
    "Tink": ["tink"],
    "Soldo": ["soldo"],
    "Tide": ["tide", "tidebanking"],
    "Marqeta": ["marqeta"],
    "Flywire": ["flywire"],
    "SaltPay": ["saltpay"],
    "Alma": ["alma", "getalma"],
    "Qonto": ["qonto"],

    # London - AI/Tech
    "Improbable": ["improbable"],
    "Darktrace": ["darktrace"],
    "Permutive": ["permutive"],
    "Let's Do This": ["letsdothis"],
    "Tractable": ["tractable"],
    "Bloomreach": ["bloomreach"],
    "Behavox": ["behavox"],
    "Faculty AI": ["faculty", "facultyai"],
    "Eigen Technologies": ["eigen", "eigentechnologies"],
    "Synthesia": ["synthesia"],
    "Wayve": ["wayve"],
    "Cera Care": ["cera", "ceracare"],
    "Featurespace": ["featurespace"],
    "Signal AI": ["signalai"],

    # London - Enterprise
    "Beamery": ["beamery"],
    "Paddle": ["paddle"],
    "Hopin": ["hopin"],
    "WorldRemit": ["worldremit"],
    "Cazoo": ["cazoo"],
    "Babylon Health": ["babylon", "babylonhealth"],
    "Bulb": ["bulb", "bulbenergy"],
    "Citymapper": ["citymapper"],
    "Depop": ["depop"],
    "Farfetch": ["farfetch"],
    "Unmind": ["unmind"],
    "Nested": ["nested"],
    "Currencycloud": ["currencycloud"],
    "Bought By Many": ["boughtbymany"],

    # =========================================================================
    # DENVER/BOULDER - Tech Companies
    # =========================================================================
    "Guild Education": ["guild", "guildeducation"],
    "Pax8": ["pax8"],
    "StackHawk": ["stackhawk"],
    "Ibotta": ["ibotta"],
    "Apto": ["apto"],
    "JumpCloud": ["jumpcloud"],
    "FlareHR": ["flarehr", "flare"],
    "Red Canary": ["redcanary"],
    "Cin7": ["cin7"],
    "Matillion": ["matillion"],
    "InDevR": ["indevr"],
    "Scythe Robotics": ["scythe", "scytherobotics"],
    "Sierra Space": ["sierraspace"],
    "Quantum Metric": ["quantummetric"],
    "SambaSafety": ["sambasafety"],
    "Zayo": ["zayo", "zayogroup"],
    "Welltok": ["welltok"],
    "SendGrid": ["sendgrid"],
    "LogRhythm": ["logrhythm"],
    "Faction": ["faction", "factioninc"],
    "OneTrust": ["onetrust"],
    "GoSpotCheck": ["gospotcheck"],
    "Dispatch": ["dispatch"],
    "Uplight": ["uplight"],
    "Gusto Denver": ["gustodenver"],
    "TeamSnap": ["teamsnap"],
    "TrackVia": ["trackvia"],
    "SpotHero": ["spothero"],

    # =========================================================================
    # Additional High-Value Companies (Various Locations)
    # =========================================================================
    "Notion": ["notion"],
    "Canva": ["canva"],
    "Figma": ["figma"],  # Already in mapping but testing pattern
    "Miro": ["miro"],
    "Airtable": ["airtable"],  # Already in mapping
    "Coda": ["coda", "codahq"],
    "ClickUp": ["clickup"],
    "Monday.com": ["monday", "mondaycom"],
    "Zapier": ["zapier"],
    "Typeform": ["typeform"],
    "Calendly": ["calendly"],
    "Loom": ["loom"],
    "Pitch": ["pitch"],
    "Mural": ["mural"],
    "Lucidchart": ["lucidchart"],
    "Amplitude": ["amplitude"],
    "Heap": ["heap", "heapanalytics"],
    "Mixpanel": ["mixpanel"],
    "Segment": ["segment"],
    "Customer.io": ["customerio"],
    "Braze": ["braze"],
    "Iterable": ["iterable"],
    "Klaviyo": ["klaviyo"],
    "Attentive": ["attentive"],
    "Gorgias": ["gorgias"],
    "Intercom": ["intercom"],  # Already in mapping
    "Zendesk": ["zendesk"],
    "Freshworks": ["freshworks"],
    "ServiceTitan": ["servicetitan"],
    "Toast": ["toast", "toasttab"],
    "Procore": ["procore"],
    "Jobber": ["jobber"],
    "Housecall Pro": ["housecallpro"],
    "Buildium": ["buildium"],
    "AppFolio": ["appfolio"],
    "Yardi": ["yardi"],
    "CoStar": ["costar"],
    "Zillow": ["zillow"],
    "Redfin": ["redfin"],
    "Compass": ["compass", "compassinc"],
    "Opendoor": ["opendoor"],  # Already in mapping
    "Offerpad": ["offerpad"],
    "Knock": ["knock", "knockaway"],
    "Homeward": ["homeward"],
    "Divvy Homes": ["divvyhomes", "divvy"],
    "Arrived": ["arrived", "arrivedhomes"],

    # =========================================================================
    # CYBERSECURITY & SECURITY (~20 companies)
    # =========================================================================
    "Snyk": ["snyk"],
    "Wiz": ["wiz", "wizinc"],
    "Orca Security": ["orcasecurity", "orca"],
    "Lacework": ["lacework"],
    "Axonius": ["axonius"],
    "CrowdStrike": ["crowdstrike"],
    "SentinelOne": ["sentinelone"],
    "Cybereason": ["cybereason"],
    "Tenable": ["tenable"],
    "1Password": ["1password", "onepassword"],
    "Bitwarden": ["bitwarden"],
    "Keeper Security": ["keeper", "keepersecurity"],
    "Arctic Wolf": ["arcticwolf"],
    "Abnormal Security": ["abnormalsecurity", "abnormal"],
    "Tessian": ["tessian"],
    "Huntress": ["huntress"],
    "Expel": ["expel"],
    "Drata": ["drata"],
    "Vanta": ["vanta"],
    "Chainguard": ["chainguard"],

    # =========================================================================
    # CLIMATE TECH & CLEAN ENERGY (~15 companies)
    # =========================================================================
    "Pachama": ["pachama"],
    "Span": ["span", "spanio"],
    "Aurora Solar": ["aurorasolar", "aurora"],
    "Crusoe Energy": ["crusoe", "crusoeenergy"],
    "Arcadia": ["arcadia", "arcadiapower"],
    "Mosaic": ["mosaic", "joinmosaic"],
    "Palmetto": ["palmetto"],
    "EnergySage": ["energysage"],
    "Redwood Materials": ["redwoodmaterials", "redwood"],
    "Sila Nanotechnologies": ["sila", "silananotechnologies"],
    "QuantumScape": ["quantumscape"],
    "Form Energy": ["formenergy"],
    "Commonwealth Fusion": ["commonwealthfusion", "cfs"],
    "Twelve": ["twelve", "twelvelabs"],
    "Charm Industrial": ["charmindustrial", "charm"],

    # =========================================================================
    # LOGISTICS & SUPPLY CHAIN (~12 companies)
    # =========================================================================
    "Flexport": ["flexport"],
    "project44": ["project44", "p44"],
    "FourKites": ["fourkites"],
    "Stord": ["stord"],
    "Shippo": ["shippo", "goshippo"],
    "ShipBob": ["shipbob"],
    "Deliverr": ["deliverr"],
    "Shipium": ["shipium"],
    "Locus Robotics": ["locusrobotics", "locus"],
    "6 River Systems": ["6riversystems"],
    "Attabotics": ["attabotics"],
    "Fabric": ["fabric", "getfabric"],

    # =========================================================================
    # CRYPTO & WEB3 (~15 companies)
    # =========================================================================
    "Coinbase": ["coinbase"],
    "Chainalysis": ["chainalysis"],
    "Fireblocks": ["fireblocks"],
    "Alchemy": ["alchemy", "alchemyplatform"],
    "Consensys": ["consensys"],
    "Ledger": ["ledger"],
    "Anchorage Digital": ["anchorage", "anchoragedigital"],
    "Circle": ["circle"],
    "Paxos": ["paxos"],
    "Figment": ["figment"],
    "Messari": ["messari"],
    "Dune Analytics": ["dune", "duneanalytics"],
    "Nansen": ["nansen"],
    "OpenZeppelin": ["openzeppelin"],
    "Paradigm": ["paradigm"],

    # =========================================================================
    # GAMING & ENTERTAINMENT (~12 companies)
    # =========================================================================
    "Riot Games": ["riotgames", "riot"],
    "Unity": ["unity", "unity3d"],
    "Roblox": ["roblox"],
    "Niantic": ["niantic"],
    "Supercell": ["supercell"],
    "Jam City": ["jamcity"],
    "Scopely": ["scopely"],
    "Machine Zone": ["machinezone", "mz"],
    "Zynga": ["zynga"],
    "N3twork": ["n3twork"],
    "Manticore Games": ["manticoregames", "manticore"],
    "Rec Room": ["recroom"],

    # =========================================================================
    # HR TECH & FUTURE OF WORK (~12 companies)
    # =========================================================================
    "Deel": ["deel"],
    "Oyster": ["oyster", "oysterhr"],
    "Lattice": ["lattice", "latticehq"],
    "Culture Amp": ["cultureamp"],
    "15Five": ["15five"],
    "Workrise": ["workrise"],
    "Velocity Global": ["velocityglobal"],
    "Papaya Global": ["papayaglobal", "papaya"],
    "Hibob": ["hibob"],
    "Leapsome": ["leapsome"],
    "ChartHop": ["charthop"],

    # =========================================================================
    # INSURTECH (~10 companies)
    # =========================================================================
    "Lemonade": ["lemonade"],
    "Root Insurance": ["root", "rootinsurance"],
    "Hippo": ["hippo", "hippoinsurance"],
    "Coalition": ["coalition", "coalitioninc"],
    "Next Insurance": ["nextinsurance"],
    "Pie Insurance": ["pieinsurance", "pie"],
    "Branch": ["branch", "branchinsurance"],
    "Bestow": ["bestow"],
    "Ethos": ["ethos", "ethoslife"],
    "Clearcover": ["clearcover"],

    # =========================================================================
    # SPORTS TECH (~10 companies)
    # =========================================================================
    "Fanatics": ["fanatics"],
    "DraftKings": ["draftkings"],
    "FanDuel": ["fanduel"],
    "Sportradar": ["sportradar"],
    "Catapult": ["catapult", "catapultsports"],
    "Whoop": ["whoop"],
    "Oura": ["oura", "ouraring"],
    "Hyperice": ["hyperice"],
    "TMRW Sports": ["tmrwsports", "tmrw"],
    "Overtime": ["overtime"],

    # =========================================================================
    # AEROSPACE & DEFENSE TECH (~12 companies)
    # =========================================================================
    "Anduril": ["anduril"],
    "Shield AI": ["shieldai"],
    "Hadrian": ["hadrian"],
    "Relativity Space": ["relativityspace", "relativity"],
    "Rocket Lab": ["rocketlab"],
    "Astra": ["astra", "astraspace"],
    "Planet Labs": ["planetlabs", "planet"],
    "Spire Global": ["spire", "spireglobal"],
    "Capella Space": ["capellaspace", "capella"],
    "Hawkeye 360": ["hawkeye360"],
    "BlackSky": ["blacksky"],
    "Impulse Space": ["impulsespace"],

    # =========================================================================
    # LEGAL TECH (~8 companies)
    # =========================================================================
    "Ironclad": ["ironclad"],
    "Clio": ["clio", "goclio"],
    "LegalZoom": ["legalzoom"],
    "ContractPodAi": ["contractpodai"],
    "Juro": ["juro"],
    "Lawtrades": ["lawtrades"],
    "LinkSquares": ["linksquares"],
    "Evisort": ["evisort"],

    # =========================================================================
    # HARDWARE & ROBOTICS (~10 companies)
    # =========================================================================
    "Figure AI": ["figure", "figureai"],
    "Boston Dynamics": ["bostondynamics"],
    "Zipline": ["zipline", "flyzipline"],
    "Skydio": ["skydio"],
    "Saronic": ["saronic"],
    "Agility Robotics": ["agilityrobotics", "agility"],
    "Nuro": ["nuro"],
    "Cruise": ["cruise", "getcruise"],
    "Waymo": ["waymo"],
    "Zoox": ["zoox"],

    # =========================================================================
    # FOOD & AGRICULTURE TECH (~8 companies)
    # =========================================================================
    "Bowery Farming": ["bowery", "boweryfarming"],
    "Plenty": ["plenty", "plentyag"],
    "AppHarvest": ["appharvest"],
    "Impossible Foods": ["impossiblefoods", "impossible"],
    "Perfect Day": ["perfectday"],
    "Upside Foods": ["upsidefoods", "upside"],
    "Eat Just": ["eatjust", "just"],
    "NotCo": ["notco"],

    # =========================================================================
    # INFRASTRUCTURE & CLOUD (~8 companies)
    # =========================================================================
    "Cloudflare": ["cloudflare"],
    "Fastly": ["fastly"],
    "Fly.io": ["flyio", "fly"],
    "Railway": ["railway"],
    "Render": ["render"],
    "PlanetScale": ["planetscale"],
    "Supabase": ["supabase"],
    "Neon": ["neon", "neondatabase"],

    # =========================================================================
    # ADDITIONAL AI/ML COMPANIES (~15 companies)
    # =========================================================================
    "OpenAI": ["openai"],
    "Mistral AI": ["mistral", "mistralai"],
    "Character AI": ["character", "characterai"],
    "Inflection AI": ["inflection", "inflectionai"],
    "Hugging Face": ["huggingface"],
    "Adept AI": ["adept", "adeptai"],
    "Jasper": ["jasper", "jasperai"],
    "Copy.ai": ["copyai"],
    "Writer": ["writer", "writerai"],
    "Covariant": ["covariant"],
    "Sanctuary AI": ["sanctuaryai", "sanctuary"],
    "Physical Intelligence": ["physicalintelligence"],
    "Extropic": ["extropic"],
    "Cognition AI": ["cognition", "cognitionai"],
    "Magic": ["magic", "magicai"],

    # =========================================================================
    # SINGAPORE - Tech Companies (NEW 2025-12-30)
    # Source: topstartups.io, seedtable.com, tracxn.com
    # =========================================================================
    # Fintech & Crypto
    "Nansen": ["nansen"],  # Confirmed Greenhouse user
    "PatSnap": ["patsnap"],  # Confirmed Greenhouse user
    "Circles.Life": ["circleslife", "circles"],
    "Immunefi": ["immunefi"],
    "Matrixport": ["matrixport"],
    "Hex Trust": ["hextrust"],
    "Thunes": ["thunes"],
    "Grab": ["grab"],
    "Sea Group": ["sea", "seagroup"],

    # AI & Data - Singapore
    "Uniphore": ["uniphore"],
    "Atlan": ["atlan"],
    "ViSenze": ["visenze"],
    "Trax": ["trax", "traxretail"],
    "Mercu": ["mercu"],
    "Near": ["near", "nearintelligence"],

    # Deep Tech - Singapore
    "Horizon Quantum Computing": ["horizonquantum", "horizon"],
    "Transcelestial": ["transcelestial"],
    "MiRXES": ["mirxes"],
    "Shiok Meats": ["shiokmeats", "shiok"],
    "Silicon Box": ["siliconbox"],
    "Polyhedra Network": ["polyhedra"],

    # E-commerce & Consumer - Singapore
    "Carousell": ["carousell"],
    "Cococart": ["cococart"],
    "Funding Societies": ["fundingsocieties"],
    "Spenmo": ["spenmo"],
    "Volopay": ["volopay"],

    # =========================================================================
    # SF BAY AREA - 2024-2025 Funding Rounds (NEW 2025-12-30)
    # Source: growthlist.co, startupsavant.com, TechCrunch
    # =========================================================================
    "Mercury": ["mercury"],
    "Arrow": ["arrow", "arrowai"],
    "Mysten Labs": ["mystenlabs", "mysten"],
    "At-Bay": ["atbay"],
    "thirdweb": ["thirdweb"],
    "AtoB": ["atob"],
    "Glean": ["glean"],
    "Harvey AI": ["harvey", "harveyai"],
    "Cerebras": ["cerebras"],
    "Anysphere": ["anysphere"],  # Cursor AI
    "Sierra AI": ["sierra", "sierraai"],
    "Moveworks": ["moveworks"],
    "Notion": ["notion"],  # Re-test, major company
    "Vercel": ["vercel"],  # Re-test
    "Linear": ["linear"],
    "Replit": ["replit"],
    "Rippling": ["rippling"],
    "Ramp": ["ramp"],  # Re-test, major fintech
    "Brex": ["brex"],  # Re-test
    "Vanta": ["vanta"],  # Re-test, growing security company

    # =========================================================================
    # NYC - 2024-2025 Series B/C Rounds (NEW 2025-12-30)
    # Source: topstartups.io, vanguard-x.com, Tech:NYC
    # =========================================================================
    "Kalshi": ["kalshi"],  # Confirmed Greenhouse user
    "Camber": ["camber"],  # Confirmed Greenhouse user
    "Traba": ["traba"],  # Confirmed Greenhouse user
    "Stainless": ["stainless", "stainlessapi"],
    "Topline Pro": ["toplinepro", "topline"],
    "Profound": ["profound"],
    "NetBox Labs": ["netboxlabs", "netbox"],
    "Aiera": ["aiera"],
    "Tennr": ["tennr"],
    "Clay": ["clay", "clayhq"],
    "Cyera": ["cyera"],
    "Hebbia": ["hebbia"],
    "Elicit": ["elicit"],
    "Codeium": ["codeium"],
    "EvenUp": ["evenup"],
    "Anduril": ["anduril"],  # Re-test, major defense tech

    # =========================================================================
    # DENVER/COLORADO - 2024-2025 Startups (NEW 2025-12-30)
    # Source: builtincolorado.com, growthmentor.com
    # =========================================================================
    "Quantive": ["quantive", "gtmhub"],
    "Moov Financial": ["moov", "moovfinancial"],
    "Homebot": ["homebot"],
    "Identity Digital": ["identitydigital"],
    "AirDNA": ["airdna"],
    "Apryse": ["apryse"],
    "Caliola Engineering": ["caliola"],
    "True Anomaly": ["trueanomaly", "trueanomalyinc"],  # Re-test with new slug

    # =========================================================================
    # YC W24/S24 BATCHES - AI-First Companies (NEW 2025-12-30)
    # Source: ycombinator.com/companies, Crunchbase
    # =========================================================================
    "Leya": ["leya"],  # AI for lawyers
    "Greptile": ["greptile"],  # Code understanding API
    "YonedaLabs": ["yonedalabs", "yoneda"],  # Chemistry AI
    "Maihem": ["maihem"],  # AI testing
    "Basepilot": ["basepilot"],  # Web automation
    "Topo": ["topo", "topoai"],  # AI sales agents
    "Terrakotta": ["terrakotta"],  # Voicemail AI
    "Driver AI": ["driverai", "driver"],  # Codebase understanding
    "AgentHub": ["agenthub"],
    "Firebender": ["firebender"],
    "Sonia": ["sonia", "heysonia"],
    "Openmart": ["openmart"],
    "Crux": ["crux", "getcrux"],
    "Octolane AI": ["octolane", "octolaneai"],
    "Zaymo": ["zaymo"],
    "Duckie": ["duckie", "duckieai"],
    "Arini": ["arini"],  # AI dental receptionist
    "Pythagora": ["pythagora"],  # GPT Pilot
    "TensorFuse": ["tensorfuse"],
    "OpenCopilot": ["opencopilot"],
    "Blume": ["blume"],
    "Momentic": ["momentic"],  # AI testing
    "Artisan AI": ["artisanai", "artisan"],
    "phospho": ["phospho"],
    "Infinity AI": ["infinityai", "infinity"],
    "Lovable": ["lovable"],  # AI app builder
    "Wordware": ["wordware"],  # AI IDE
    "Letta": ["letta"],  # MemGPT
    "Pydantic": ["pydantic", "pydanticai"],  # Logfire
    "Continue": ["continue", "continuedev"],  # AI coding assistant
}

# Base URLs to try (EXACTLY same as validate_greenhouse_slugs.py)
BASE_URLS = [
    "https://job-boards.greenhouse.io",
    "https://job-boards.eu.greenhouse.io",
    "https://boards.greenhouse.io",
    "https://board.greenhouse.io",
    "https://boards.greenhouse.io/embed/job_board?for=",
]


async def test_slug(slug: str, timeout: int = 15000) -> tuple[bool, str | None]:
    """
    Test if a Greenhouse slug is valid using Playwright.

    Uses EXACT same validation logic as validate_greenhouse_slugs.py:
    - Try all URL patterns (including embed pattern)
    - If ANY pattern loads without 404 error, it's VALID
    - If ALL patterns return 404, it's INVALID

    Returns: (is_valid, working_url or None)
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            for base_url in BASE_URLS:
                # Handle embed URL pattern (ends with ?for=)
                if base_url.endswith('?for='):
                    url = f"{base_url}{slug}"
                else:
                    url = f"{base_url}/{slug}"

                page = None
                try:
                    page = await browser.new_page(
                        viewport={'width': 1280, 'height': 720}
                    )

                    try:
                        await page.goto(url, wait_until='networkidle', timeout=timeout)
                    except asyncio.TimeoutError:
                        # Timeout is not a 404 - still might be valid
                        if page:
                            await page.close()
                        continue

                    # Wait for page to fully load (EXACT match with validate script)
                    await page.wait_for_timeout(1000)

                    # Get page content
                    content = await page.content()
                    content_lower = content.lower()

                    # Check for various Greenhouse error messages (EXACT match)
                    error_messages = [
                        "sorry, but we can't find that page",
                        "the job board you were viewing is no longer active",
                        "page not found"
                    ]
                    is_error = any(msg in content_lower for msg in error_messages)

                    # Fallback: check for error page indicators
                    if not is_error:
                        # Genuine error pages are typically short; real job boards are large
                        if len(content) < 10000:  # Error pages usually < 10KB
                            is_error = True

                    if not is_error:
                        # Page loaded successfully without error message - it's valid!
                        await page.close()
                        await browser.close()
                        return True, url

                    await page.close()

                except Exception as e:
                    # Error on this URL, try next
                    if page:
                        try:
                            await page.close()
                        except:
                            pass
                    continue

            # All URLs either returned 404 or failed to load
            await browser.close()
            return False, None

    except Exception as e:
        return False, None


async def discover_company(company_name: str, slug_patterns: list[str]) -> tuple[str, str | None, str | None]:
    """
    Try to discover a valid Greenhouse slug for a company.

    Returns: (company_name, valid_slug or None, working_url or None)
    """
    for slug in slug_patterns:
        is_valid, url = await test_slug(slug)
        if is_valid:
            return company_name, slug, url

    return company_name, None, None


async def discover_batch(companies: dict, batch_size: int = 5) -> dict:
    """
    Discover valid slugs for a batch of companies.

    Returns dict with 'valid' and 'invalid' lists
    """
    results = {'valid': [], 'invalid': []}
    items = list(companies.items())
    total = len(items)

    for i in range(0, total, batch_size):
        batch = items[i:i+batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total + batch_size - 1) // batch_size

        print(f"\n[Batch {batch_num}/{total_batches}]")

        tasks = [
            discover_company(company, slugs)
            for company, slugs in batch
        ]
        batch_results = await asyncio.gather(*tasks)

        for company, slug, url in batch_results:
            if slug:
                status = "OK"
                results['valid'].append((company, slug, url))
            else:
                status = "XX"
                results['invalid'].append(company)

            print(f"  [{status}] {company:40} -> {slug or 'not found'}")

        tested = min(i + batch_size, total)
        print(f"  Progress: {tested}/{total}")

    return results


def load_existing_mapping() -> set:
    """Load existing company names from mapping file."""
    mapping_path = Path(__file__).parent.parent.parent / 'config' / 'greenhouse' / 'company_ats_mapping.json'

    try:
        with open(mapping_path) as f:
            mapping = json.load(f)

        existing = set()
        for company in mapping.get('greenhouse', {}).keys():
            existing.add(company.lower())

        return existing
    except FileNotFoundError:
        return set()


def get_checked_log_path() -> Path:
    """Get path to the checked companies log."""
    return Path(__file__).parent.parent.parent / 'config' / 'greenhouse' / 'checked_companies.json'


def load_checked_companies() -> tuple[set, set]:
    """
    Load previously checked companies from the persistent log.

    Returns: (valid_set, invalid_set) - both lowercase for comparison
    """
    log_path = get_checked_log_path()

    try:
        with open(log_path) as f:
            log = json.load(f)

        valid = {c.lower() for c in log.get('valid', [])}
        invalid = {c.lower() for c in log.get('invalid', [])}
        return valid, invalid
    except FileNotFoundError:
        return set(), set()


def update_checked_companies(results: dict):
    """
    Update the persistent checked companies log with new results.

    Appends newly tested companies to the existing log.
    """
    log_path = get_checked_log_path()

    # Load existing log or create new
    try:
        with open(log_path) as f:
            log = json.load(f)
    except FileNotFoundError:
        log = {
            'description': 'Persistent log of all Greenhouse slugs tested. Used by discover_greenhouse_slugs.py to skip re-testing.',
            'valid': [],
            'invalid': []
        }

    # Get existing sets for deduplication
    existing_valid = set(log.get('valid', []))
    existing_invalid = set(log.get('invalid', []))

    # Add new valid companies
    added_valid = 0
    for company, slug, url in results.get('valid', []):
        if company not in existing_valid:
            log['valid'].append(company)
            added_valid += 1

    # Add new invalid companies
    added_invalid = 0
    for company in results.get('invalid', []):
        if company not in existing_invalid:
            log['invalid'].append(company)
            added_invalid += 1

    # Update timestamp
    log['last_updated'] = datetime.now().isoformat()

    # Save
    with open(log_path, 'w') as f:
        json.dump(log, f, indent=2)

    total_valid = len(log['valid'])
    total_invalid = len(log['invalid'])
    print(f"\nUpdated checked companies log: +{added_valid} valid, +{added_invalid} invalid")
    print(f"  Total tracked: {total_valid} valid, {total_invalid} invalid ({total_valid + total_invalid} total)")


def save_results(results: dict, mapping_path: Path):
    """Save valid slugs to mapping file."""
    with open(mapping_path) as f:
        mapping = json.load(f)

    added = 0
    for company, slug, url in results['valid']:
        if company not in mapping['greenhouse']:
            mapping['greenhouse'][company] = {"slug": slug}
            added += 1
            print(f"  Added: {company} -> {slug}")

    if added > 0:
        with open(mapping_path, 'w') as f:
            json.dump(mapping, f, indent=4)
        print(f"\nSaved {added} new companies to {mapping_path}")
    else:
        print("\nNo new companies to add.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', default=True,
                        help='Test slugs but do not save (default)')
    parser.add_argument('--save', action='store_true',
                        help='Save valid slugs to company_ats_mapping.json')
    parser.add_argument('--batch-size', type=int, default=5,
                        help='Concurrent tests per batch (default: 5)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit total companies to test')
    parser.add_argument('--recheck', action='store_true',
                        help='Re-test previously invalid companies (ignore checked log)')

    args = parser.parse_args()

    print("=" * 80)
    print("GREENHOUSE SLUG DISCOVERY TOOL")
    print("=" * 80)
    print(f"\nSeed list contains {len(SEED_COMPANIES)} companies")

    # Load existing mapping and checked companies log
    existing_mapping = load_existing_mapping()
    checked_valid, checked_invalid = load_checked_companies()

    # Determine what to skip based on --recheck flag
    if args.recheck:
        # Only skip companies already in mapping or previously valid
        skip_set = existing_mapping | checked_valid
        print("\n[--recheck mode: will re-test previously invalid companies]")
    else:
        # Skip all previously checked companies
        skip_set = existing_mapping | checked_valid | checked_invalid

    # Filter out companies already tested
    to_test = {
        company: slugs
        for company, slugs in SEED_COMPANIES.items()
        if company.lower() not in skip_set
    }

    in_mapping = len([c for c in SEED_COMPANIES if c.lower() in existing_mapping])
    prev_valid = len([c for c in SEED_COMPANIES if c.lower() in checked_valid and c.lower() not in existing_mapping])
    prev_invalid = len([c for c in SEED_COMPANIES if c.lower() in checked_invalid])

    print(f"Already in mapping: {in_mapping}")
    print(f"Previously checked (valid, not in mapping): {prev_valid}")
    print(f"Previously checked (invalid): {prev_invalid}")
    if args.recheck:
        print(f"Re-checking invalid + new companies: {len(to_test)}")
    else:
        print(f"New companies to test: {len(to_test)}")

    if args.limit:
        to_test = dict(list(to_test.items())[:args.limit])
        print(f"Limited to: {len(to_test)}")

    if not to_test:
        print("\nNo new companies to test!")
        return

    print(f"\nTesting with batch size: {args.batch_size}")
    print("Status: [OK] = Valid Greenhouse board, [XX] = Not found")

    # Run discovery
    results = asyncio.run(discover_batch(to_test, args.batch_size))

    # Summary
    print("\n" + "=" * 80)
    print("DISCOVERY RESULTS")
    print("=" * 80)
    print(f"\nTested: {len(to_test)} companies")
    print(f"Valid (new Greenhouse boards): {len(results['valid'])}")
    print(f"Invalid (not found): {len(results['invalid'])}")

    if results['valid']:
        print(f"\n{'=' * 40}")
        print("VALID SLUGS FOUND")
        print("=" * 40)
        for company, slug, url in sorted(results['valid']):
            print(f"  {company:40} -> {slug}")

    # Save if requested
    if args.save and results['valid']:
        mapping_path = Path(__file__).parent.parent.parent / 'config' / 'greenhouse' / 'company_ats_mapping.json'
        save_results(results, mapping_path)
    elif args.save:
        print("\nNo valid slugs to save.")
    else:
        print("\n[Dry run mode - use --save to add to mapping]")

    # Update persistent checked companies log (always, even in dry-run)
    update_checked_companies(results)

    # Save discovery log (this run only)
    log_path = Path(__file__).parent.parent.parent / 'output' / 'greenhouse_discovery_log.json'
    log_path.parent.mkdir(exist_ok=True)

    log = {
        'timestamp': datetime.now().isoformat(),
        'tested': len(to_test),
        'valid': [(c, s, u) for c, s, u in results['valid']],
        'invalid': results['invalid']
    }

    with open(log_path, 'w') as f:
        json.dump(log, f, indent=2)

    print(f"Discovery log (this run) saved to: {log_path}")


if __name__ == '__main__':
    main()

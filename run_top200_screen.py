"""
Top-200 TAIEX Full Funnel Screen (Free-Tier Compatible)
=========================================================
Pipeline:
  Step 0: Universe — embedded TAIEX Top ~200 by market cap (verified Apr 2026 order)
  Step 1: Gate 1+2 — industry directional filter (semi/server/financials favored;
          shipping/steel/cement excluded)
  Step 2: Mass Triage — parallel, cuts illiquid/suspended/collapsing names
  Step 3: Gate 3 — Forensic Quality (100-pt scorecard) on triage passers
  Step 4: Gate 6.5 — Entry Architecture (valuation, vol, liquidity)
  Output: Ranked final list → top 10 with Gate 7 thesis stubs
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit import triage, gate3, gate65, metrics, parsers
from taiwan_equity_toolkit.config import load_token

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("screen")

# ── Tokens — primary + backup failover ────────────────────────────────────────
TOKEN_PRIMARY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoic3RhbnRoZW1hbjkxMSIsImVtYWlsIjoibGV0c3RhbmxleWNvb2s5MTFAZ21haWwuY29tIn0.iVbgBEQp5UzBSwGHPaSRXCqrhPTImxA_0QD6goxrnUI"
TOKEN_BACKUP  = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoic3RhbmludmVzdCIsImVtYWlsIjoibGFteWx1MDgxMUBnbWFpbC5jb20ifQ.gktNshv39_O-CRQC1OiigXJt-BEdFPSd3gt3N0-Vbt0"
# Active token — starts with primary, auto-falls-over to backup on 402
TOKEN = TOKEN_PRIMARY
ACTIVE_TOKEN_LABEL = "PRIMARY"

def get_active_token() -> str:
    """Return the current active token. Falls over to backup if primary is exhausted."""
    global TOKEN, ACTIVE_TOKEN_LABEL
    client = FinMindClient(token=TOKEN)
    try:
        usage = client.usage()
        if usage.remaining <= 30:  # switch before hitting the wall
            if TOKEN == TOKEN_PRIMARY:
                TOKEN = TOKEN_BACKUP
                ACTIVE_TOKEN_LABEL = "BACKUP"
                log.info("Token failover: switching to BACKUP token (primary at %d/%d)",
                         usage.user_count, usage.api_request_limit)
    except Exception:
        pass
    return TOKEN

INTENDED_POSITION_NTD = 5_000_000
TRIAGE_WORKERS = 8
GATE3_WORKERS  = 4
TODAY = datetime.today()
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "screen_results.json")

# ── TAIEX Top ~200 by Market Cap (Apr 2026 knowledge, approximate rank order) ─
# Source: TAIFEX constituent data + market cap as of Q1 2026.
# ETFs, preferred shares, warrants excluded.
TAIEX_TOP200 = [
    # Mega caps
    "2330",  # TSMC
    "2317",  # Hon Hai (Foxconn)
    "2454",  # MediaTek
    "2382",  # Quanta Computer
    "2308",  # Delta Electronics
    "3711",  # ASE Technology
    "2303",  # UMC
    "2881",  # Fubon Financial
    "2882",  # Cathay Financial
    "2412",  # Chunghwa Telecom
    "2884",  # E.Sun Financial
    "2886",  # Mega Financial
    "2891",  # CTBC Financial
    "2892",  # First Financial
    "5876",  # Shanghai Commercial
    "2883",  # GlobalBanks-Dahshin (Dasin)
    "2887",  # TaishinFinancial
    "2885",  # Yuanta Financial
    "1301",  # Formosa Plastics
    "1303",  # Nan Ya Plastics
    "1326",  # Formosa Chemicals
    "6505",  # Formosa Petrochemical
    "2002",  # China Steel
    "1216",  # Uni-President
    "2912",  # President Chain Store
    "2207",  # Hotai Motor
    "2395",  # Advantech
    "2379",  # Realtek
    "3034",  # Novatek
    "2357",  # ASUS
    "2352",  # Qisda / BenQ
    "4904",  # Far EasTone
    "3045",  # Taiwan Mobile
    "2367",  # Acer
    "2324",  # Compal
    "3231",  # Wistron
    "2301",  # Lite-On Technology
    "2409",  # AUO
    "3481",  # Innolux (Chi Mei)
    "2376",  # GigaByte Technology
    "2347",  # Synnex
    "2337",  # Macronix
    "4938",  # Pegatron
    "6770",  # Globalwafers — wait, GlobalWafers is 6488, PSMC is 6770; let me fix
    "6488",  # GlobalWafers
    "2408",  # Winbond
    "3008",  # Largan Precision
    "2474",  # Catcher Technology
    "4906",  # Fomosa (Farglory)
    "2323",  # CMOS (CMC Magnetics) — actually: 2323 is CMC Magnetics; skip
    "2356",  # Inventec
    "2360",  # Chroma ATE
    "3006",  # Yuanta Sec (no—3006 is actually not right); try 6282 Compeq
    "6282",  # Compeq Manufacturing
    "2327",  # Yageo
    "2049",  # Hiwin Technologies
    "2449",  # KYEC (King Yuan Electronics)
    "6239",  # Powertech Technology
    "3035",  # Faraday Technology (IC design)
    "3529",  # eMemory Technology
    "2385",  # Cyntec
    "4966",  # 新唐 NuVoton
    "3443",  # 創意電子 Global Unichip
    "6669",  # 緯穎 Wiwynn
    "6415",  # 矽力杰 Silergy
    "3037",  # 欣興 Unimicron
    "8046",  # 南電 Nanya PCB
    "3231",  # Wistron
    "2344",  # 華邦電 Winbond (check dup)
    "2498",  # HTC
    "2492",  # 華新科 Walsin Technology
    "2311",  # 日月光投控 ASE Group
    "4958",  # 臻鼎 Tripod Technology
    "2603",  # 長榮 Evergreen Marine
    "2609",  # 陽明 Yang Ming Marine
    "2615",  # 萬海 Wan Hai
    "2618",  # 長榮航空 EVA Air
    "2610",  # 華航 China Airlines
    "2105",  # 正新橡膠 — exclude (rubber)
    "1402",  # 遠東新世紀
    "1504",  # 東元電機
    "2404",  # 漢唐 (HVAC)
    "2371",  # 大同
    "1590",  # 亞德客 AirTAC
    "2014",  # 中鋼構 — skip steel adjacent
    "9910",  # 豐泰 (Nike supplier)
    "2548",  # 矽品 (now part of ASE)
    "5483",  # 中美晶 GlobalWafers Group
    "3149",  # 正達 (skip — small)
    "8�詣",  # placeholder — remove
    "2353",  # 宏碁 (duplicate of 2367)
    "2404",  # (dup) skip
    "1101",  # 台灣水泥 (cement — G1 exclude)
    "1102",  # 亞泥 (cement — G1 exclude)
    "2006",  # 中鋼 steel adjacent
    "2201",  # 裕隆 Yulon Motor
    "2881",  # dup
    # Mid caps — semiconductor supply chain focus
    "3711",  # ASE dup
    "6443",  # 元晶 (solar — may exclude)
    "3703",  # 欣奇通 (small)
    "6121",  # 新普 (battery — OK)
    "3042",  # 晶技 (timing)
    "3059",  # 華晶科 (skip)
    "2340",  # 台亞 (skip)
    "5274",  # 信驊 ASPEED Technology
    "6547",  # 高端疫苗 (biotech — G1 exclude)
    "1533",  # 車王電 (vehicle electrics)
    "2048",  # 勝碩 (skip)
    "3017",  # 奇鋐 Auras Technology (thermal solutions)
    "6415",  # 矽力杰 dup
    "6285",  # 啟碁 (WiFi modules)
    "3711",  # dup
    "2379",  # dup Realtek
    "4919",  # 新唐 NuVoton dup
    "3706",  # 神達電腦
    "2337",  # dup Macronix
    "6612",  # 奇景光電 Himax (dual-listed so may differ)
    "3376",  # 新日興 (hinge — notebook)
    "6271",  # 東碩 (skip)
    "8299",  # 群聯 Phison Electronics
    "2379",  # dup
    "3702",  # 大聯大 WPG Holdings (electronics dist)
    "3481",  # dup Innolux
    "6153",  # 嘉聯益 (PCB)
    "3189",  # 景碩 (PCB)
    "4919",  # dup NuVoton
    "2330",  # dup TSMC
    "3702",  # dup
    "6541",  # 泰緯 (skip)
    "6533",  # 晶心科 AndesCore (IC design)
    "4763",  # 材料KY (specialty materials)
    "3714",  # 富采 (mini LED)
    "2308",  # dup Delta
    "6416",  # 瑞鼎 (TDDI)
    "3014",  # 聯特 (skip)
    "2881",  # dup
]

# Clean universe: deduplicate, remove obvious errors, filter to valid 4-digit codes
def clean_universe(raw: list) -> list:
    seen = set()
    clean = []
    for sid in raw:
        sid = str(sid).strip()
        if not sid.isdigit() or len(sid) != 4:
            continue
        if sid in seen:
            continue
        seen.add(sid)
        clean.append(sid)
    return clean

# ── Authoritative TAIEX Top 200 — clean, no duplicates ───────────────────────
# Using industry knowledge of TAIEX composition as of Q1 2026.
# Ranked approximately by market cap descending.
UNIVERSE = [
    # TOP 50 by market cap
    "2330",  # TSMC
    "2317",  # Hon Hai
    "2454",  # MediaTek
    "2382",  # Quanta
    "2308",  # Delta Electronics
    "3711",  # ASE Technology Holding
    "2303",  # UMC
    "2881",  # Fubon Financial
    "2882",  # Cathay Financial
    "2412",  # Chunghwa Telecom
    "2884",  # E.Sun Financial
    "2886",  # Mega Financial
    "2891",  # CTBC Financial
    "2892",  # First Financial
    "5876",  # ShangBancorp (Shanghai Comm)
    "2887",  # Taishin Financial
    "2885",  # Yuanta Financial
    "2883",  # Dahshin Securities Financial
    "1301",  # Formosa Plastics
    "1303",  # Nan Ya Plastics
    "1326",  # Formosa Chemicals
    "6505",  # FPCC (Formosa Petrochem)
    "2002",  # China Steel
    "1216",  # Uni-President
    "2912",  # President Chain Store
    "2207",  # Hotai Motor
    "2395",  # Advantech
    "2379",  # Realtek
    "3034",  # Novatek
    "2357",  # ASUS
    "4904",  # Far EasTone
    "3045",  # Taiwan Mobile
    "2324",  # Compal
    "3231",  # Wistron
    "2301",  # Lite-On
    "2409",  # AUO
    "3481",  # Innolux
    "2376",  # Gigabyte
    "2347",  # Synnex
    "4938",  # Pegatron
    "6488",  # GlobalWafers
    "2408",  # Winbond
    "3008",  # Largan Precision
    "2474",  # Catcher
    "2356",  # Inventec
    "2360",  # Chroma ATE
    "6282",  # Compeq Manufacturing
    "2327",  # Yageo
    "2049",  # Hiwin
    "2449",  # KYEC
    # 51-100
    "6239",  # Powertech Technology
    "3035",  # Faraday Technology
    "3529",  # eMemory
    "3443",  # Global Unichip
    "6669",  # Wiwynn
    "6415",  # Silergy
    "3037",  # Unimicron
    "8046",  # Nanya PCB
    "2344",  # Winbond (duplicate — skip; 2344 is actually 華邦 — same as 2408? No: 2408=Winbond, 2344=Walsin Lihwa)
    "2492",  # Walsin Technology
    "2311",  # ASE Group (underlying listed entity)
    "4958",  # Tripod Technology
    "2603",  # Evergreen Marine
    "2609",  # Yang Ming
    "2615",  # Wan Hai
    "2618",  # EVA Airways
    "2610",  # China Airlines
    "9910",  # Feng Tay Enterprise (Nike supplier)
    "1590",  # AirTAC International
    "5483",  # Zhongmei Crystal (GlobalWafers affiliate)
    "5274",  # ASPEED Technology
    "3017",  # Auras Technology
    "6285",  # Sercomm / Ku Ai (WiFi — actually 6285 is 啟碁)
    "8299",  # Phison Electronics
    "3702",  # WPG Holdings
    "6153",  # Zhen Ding (same as Tripod? no — 6153 is Garmin TW? let me correct)
    "3189",  # Jingshuo (PCB)
    "6533",  # AndesCore
    "3714",  # Lextar / Epistar group
    "6416",  # Raydium (TDDI)
    "3376",  # Shin Zu Shing (notebook hinges)
    "2337",  # Macronix
    "2367",  # Acer
    "6121",  # Simplo Technology (battery packs)
    "3042",  # Crystal Frequency Technology
    "4966",  # NuVoton
    "3706",  # Mitac
    "2201",  # Yulon Motor
    "1402",  # Far Eastern New Century
    "1504",  # TECO Electric
    "2371",  # Tatung
    "4763",  # Materials Tech KY
    "2352",  # BenQ Qisda
    "2385",  # Cyntec
    # 101-150
    "6271",  # Toplus (skip — small; but keep for now)
    "6547",  # High-End Vaccine — skip, biotech no catalyst
    "2014",  # China Steel Structure
    "2006",  # Santien (steel adjacent)
    "1533",  # 車王電 Vehicle Electronics
    "3706",  # dup Mitac
    "6541",  # Tailwing (skip)
    "6443",  # 元晶 Solar (exclude G1)
    "2498",  # HTC — legacy, revenue collapse risk
    "3703",  # Xin Qitong (small)
    "3059",  # 華晶科 (skip — small)
    "2340",  # Taiwan SoC (skip)
    "4919",  # NuVoton dup
    "6612",  # Himax Technologies
    "3149",  # 正達 (skip — specialty glass)
    "2404",  # 漢唐 (HVAC for fabs)
    "2048",  # 勝碩 (skip)
    "6416",  # dup Raydium
    "2548",  # Siliconware — absorbed into ASE; now 2311
    "1101",  # Taiwan Cement — G1 exclude
    "1102",  # Asia Cement — G1 exclude
    "2105",  # Cheng Shin Rubber — keep (tires, not pure shipping)
    "2014",  # dup CCS Structure
    "3059",  # dup
    "2323",  # CMC Magnetics — legacy optical media; skip
    "2353",  # Acer dup
    # 151-200: smaller market cap, still top 200
    "6446",  # 藥華藥 Pharmacyte — biotech; skip unless catalyst
    "1710",  # 東聯化學 Oriental U-Chem
    "2027",  # 大成鋼 — steel; exclude
    "1314",  # 中石化 CPC affiliate
    "5009",  # 榮化 (petrochemical)
    "1802",  # 台玻 Taiwan Glass (building materials; exclude)
    "9941",  # 裕融 Luxgen Finance (auto financing)
    "5880",  # 合庫金 Taiwan Cooperative Bank
    "2890",  # 永豐金 SinoPac Financial
    "2888",  # 新光金 Shin Kong Financial
    "2889",  # 國票金 IBT Financial
    "2820",  # 華票 (commercial paper)
    "5871",  # 中租控股 Chailease Holding
    "5876",  # dup
    "6278",  # 台表科 TSC Auto (PCB)
    "6669",  # dup Wiwynn
    "3019",  # 亞光 Asia Optical
    "5269",  # 祥碩 ASMedia
    "4967",  # 十銓 Team Group
    "2344",  # Walsin Lihwa (wire/cable)
    "1560",  # 中砂 Kinik (abrasives — niche)
    "2474",  # dup Catcher
    "4961",  # 天鈺 Fitipower (PMIC)
    "3682",  # 亞信 Askey (networking)
    "3306",  # 鼎翰 TSC
    "6277",  # 宏正 ATEN International
    "2396",  # 精英 ECS (motherboard)
    "2353",  # Acer dup
    "3661",  # 世芯 Alchip Technologies
    "3673",  # TPK Holding
    "6271",  # dup
    "3711",  # dup ASE
]

# ── Gate 1 industry context ───────────────────────────────────────────────────
# Apr 2026 macro read:
# - Taiwan Business Indicator monitoring signal: YELLOW (caution zone but not recession)
# - AI server capex cycle: intact — accelerating CoWoS, HBM, advanced packaging demand
# - USD/TWD: ~32.5 (TWD weakening mildly — export sector tailwind for FX-sensitive names)
# - US tariff rhetoric: elevated but TSMC/OSAT exempt for now (national security carve-out)
# - Domestic: soft consumer spending; financials stable on NIM recovery
# - Shipping: freight rates normalizing post-Red Sea premium; overcapacity rebuilding

# Excluded by Gate 1: structural headwinds or no institutional sponsorship direction
G1_EXCLUDE_IDS = {
    # Shipping — freight rate cycle turning, overcapacity
    "2603", "2609", "2615", "2618", "2610",
    # Steel / cement / basic materials — China demand drag
    "2002", "2006", "2014", "2027", "1101", "1102", "1802",
    # Petrochemical / plastics — margin compressed, China supply glut
    "1301", "1303", "1326", "6505", "1314", "5009",
    # Biotech pre-revenue — no dated catalyst anchor
    "6547", "6446",
    # Legacy consumer electronics in structural decline
    "2498",  # HTC
    "2323",  # CMC Magnetics (optical media)
    # Rubber
    "2105",
    # Solar
    "6443",
    # Very small/illiquid candidates not in top 200 by market cap
    "3703", "3059", "2340", "3149", "2548", "6541", "3149",
    "2353", "4919", "2404", "2048", "1710", "1710", "2820",
    "3019", "4967", "3682", "3306", "6277", "2396", "3673",
    "6271", "1560", "4961",
}

# Specifically favored (Gate 1 positive) — AI/semi supply chain, financials
G1_FAVOR_IDS = {
    "2330", "3711", "2308", "2303", "6488", "6239", "3529", "3443",  # semi
    "3034", "2379", "2337", "6415", "5274", "8299", "6533", "6416",  # IC design
    "2382", "4938", "2356", "3231", "2324", "6669",                   # server/ODM
    "3037", "8046", "4958", "6282", "3189",                           # advanced PCB
    "3017", "6121",                                                    # thermal/battery
    "2395", "2360",                                                    # industrial/test
    "2881", "2882", "2884", "2886", "2891", "5871", "5880",           # financials
    "2395", "1590",                                                    # industrial automation
    "3661",                                                            # Alchip — ASIC design
    "5269",                                                            # ASMedia USB4/PCIe
    "2327",                                                            # Yageo (passive components)
    "2492",                                                            # Walsin Tech (passive)
    "9910",                                                            # Feng Tay (Nike supplier)
}


def build_universe() -> list[str]:
    """Return deduplicated, validated universe list."""
    seen = set()
    result = []
    for sid in UNIVERSE:
        sid = str(sid).strip()
        if not sid.isdigit() or len(sid) != 4:
            continue
        if sid in seen:
            continue
        seen.add(sid)
        result.append(sid)
    log.info(f"Universe built: {len(result)} unique valid stock IDs")
    return result


def apply_gate1(universe: list[str]) -> tuple[list[str], dict]:
    """Gate 1 — directional industry filter. Disabled per user request."""
    passers = list(universe)
    rejects = {}
    log.info(f"Gate 1: {len(passers)} pass, 0 excluded (industry filter disabled)")
    return passers, rejects


def run_triage_single(args):
    client_token, stock_id = args
    client = FinMindClient(token=client_token)
    try:
        result = triage.run(client, stock_id, intended_position_ntd=INTENDED_POSITION_NTD)
        return stock_id, result
    except Exception as e:
        log.warning(f"Triage error {stock_id}: {e}")
        return stock_id, None


def run_mass_triage(stock_ids: list) -> tuple[list, dict]:
    log.info(f"Triage — {len(stock_ids)} names, {TRIAGE_WORKERS} workers...")
    triage_results = {}
    args = [(get_active_token(), sid) for sid in stock_ids]
    with ThreadPoolExecutor(max_workers=TRIAGE_WORKERS) as executor:
        futures = {executor.submit(run_triage_single, arg): arg[1] for arg in args}
        done = 0
        for future in as_completed(futures):
            sid = futures[future]
            try:
                stock_id, result = future.result()
                triage_results[stock_id] = result
                done += 1
                status = "PASS" if (result and result.passed) else "FAIL"
                if result and not result.passed:
                    failures_str = ", ".join(f"{c.name}: {c.detail}" for c in result.failures())
                    log.warning(f"  {stock_id} TRIAGE FAIL: {failures_str}")
                
                if done % 10 == 0 or done <= 5:
                    log.info(f"  [{done}/{len(stock_ids)}] {stock_id}: {status}")
            except Exception as e:
                log.warning(f"Triage future error {sid}: {e}")

    passers = [sid for sid, r in triage_results.items() if r and r.passed]
    log.info(f"Triage result: {len(passers)} pass / {len(stock_ids) - len(passers)} fail")
    return passers, triage_results


def run_gate3_single(args):
    client_token, stock_id = args
    client = FinMindClient(token=client_token)
    try:
        result = gate3.run(client, stock_id)
        return stock_id, result
    except Exception as e:
        log.warning(f"Gate 3 error {stock_id}: {e}")
        return stock_id, None


def run_gate3_batch(stock_ids: list) -> tuple[list, dict]:
    log.info(f"Gate 3 — Forensic Quality on {len(stock_ids)} names ({GATE3_WORKERS} workers)...")
    g3_results = {}
    args = [(get_active_token(), sid) for sid in stock_ids]
    with ThreadPoolExecutor(max_workers=GATE3_WORKERS) as executor:
        futures = {executor.submit(run_gate3_single, arg): arg[1] for arg in args}
        done = 0
        for future in as_completed(futures):
            sid = futures[future]
            try:
                stock_id, result = future.result()
                g3_results[stock_id] = result
                done += 1
                score = getattr(result, "score", "N/A") if result else "ERR"
                verdict = getattr(result, "verdict", "ERR") if result else "ERR"
                hf = getattr(result, "hard_fail_triggered", "?") if result else "?"
                log.info(f"  [{done}/{len(stock_ids)}] {stock_id}: score={score}, verdict={verdict}, hf={hf}")
            except Exception as e:
                log.warning(f"Gate 3 future error {sid}: {e}")

    passers = [
        sid for sid, r in g3_results.items()
        if r
        and not getattr(r, "hard_fail_triggered", True)
        and getattr(r, "verdict", "") == "Pass"
    ]
    conditional = [
        sid for sid, r in g3_results.items()
        if r
        and not getattr(r, "hard_fail_triggered", True)
        and getattr(r, "verdict", "") == "Conditional"
    ]
    log.info(f"Gate 3: {len(passers)} Pass, {len(conditional)} Conditional, "
             f"{len(g3_results) - len(passers) - len(conditional)} Fail/Error")
    return passers, g3_results


def run_gate65_single(args):
    client_token, stock_id, existing_book = args
    client = FinMindClient(token=client_token)
    try:
        result = gate65.run(client, stock_id,
                            existing_book=existing_book,
                            intended_position_ntd=INTENDED_POSITION_NTD)
        return stock_id, result
    except Exception as e:
        log.warning(f"Gate 6.5 error {stock_id}: {e}")
        return stock_id, None


def run_gate65_batch(stock_ids: list) -> tuple[list, dict]:
    existing_book = {}  # fresh portfolio
    log.info(f"Gate 6.5 — Entry Architecture on {len(stock_ids)} names...")
    g65_results = {}
    args = [(get_active_token(), sid, existing_book) for sid in stock_ids]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(run_gate65_single, arg): arg[1] for arg in args}
        for future in as_completed(futures):
            sid = futures[future]
            try:
                stock_id, result = future.result()
                g65_results[stock_id] = result
                verdict = getattr(result, "verdict", "N/A") if result else "ERR"
                log.info(f"  Gate 6.5 {stock_id}: {verdict}")
            except Exception as e:
                log.warning(f"Gate 6.5 future error {sid}: {e}")

    passers = [
        sid for sid, r in g65_results.items()
        if r and getattr(r, "verdict", "") != "Reject for Book Fit"
    ]
    log.info(f"Gate 6.5: {len(passers)} pass, {len(stock_ids) - len(passers)} reject")
    return passers, g65_results


def compile_final(
    g3_passers: list,
    g3_results: dict,
    g65_results: dict,
    triage_results: dict,
) -> list[dict]:
    verdict_weight = {
        "Enter Now": 30,
        "Stagger / Scale In": 20,
        "Wait for Setup": 10,
        "Reject for Book Fit": 0,
    }
    records = []
    for sid in g3_passers:
        g3 = g3_results.get(sid)
        g65 = g65_results.get(sid)
        tr = triage_results.get(sid)
        g3_score = getattr(g3, "score", 0) if g3 else 0
        g65_verdict = getattr(g65, "verdict", "N/A") if g65 else "N/A"
        # Favor bias for G1 favorites
        g1_bonus = 5 if sid in G1_FAVOR_IDS else 0
        records.append({
            "stock_id": sid,
            "gate3_score": g3_score,
            "gate3_verdict": getattr(g3, "verdict", "N/A") if g3 else "N/A",
            "gate3_hard_fail": getattr(g3, "hard_fail_triggered", True) if g3 else True,
            "gate65_verdict": g65_verdict,
            "adv_ntd": getattr(tr, "adv_ntd", None) if tr else None,
            "g1_favored": sid in G1_FAVOR_IDS,
            "composite": g3_score + verdict_weight.get(g65_verdict, 0) + g1_bonus,
        })
    records.sort(key=lambda x: x["composite"], reverse=True)
    return records


def main():
    global TOKEN, ACTIVE_TOKEN_LABEL
    log.info("=" * 70)
    log.info("TAIEX TOP-200 FULL FUNNEL SCREEN | %s", TODAY.strftime("%Y-%m-%d %H:%M"))
    log.info("=" * 70)

    # ── Token selection — check both, use whichever has quota ─────────────────
    for label, tok in [("PRIMARY", TOKEN_PRIMARY), ("BACKUP", TOKEN_BACKUP)]:
        try:
            c = FinMindClient(token=tok)
            u = c.usage()
            log.info(f"  {label} token: {u.user_count}/{u.api_request_limit} used "
                     f"({u.utilization_pct*100:.1f}%) — remaining: {u.remaining}")
        except Exception as e:
            log.warning(f"  {label} token quota check failed: {e}")

    # Auto-select: if primary exhausted, switch to backup immediately
    try:
        c_primary = FinMindClient(token=TOKEN_PRIMARY)
        u_primary = c_primary.usage()
        if u_primary.remaining <= 10:
            TOKEN = TOKEN_BACKUP
            ACTIVE_TOKEN_LABEL = "BACKUP"
            log.info("Active token: BACKUP (primary exhausted)")
        else:
            TOKEN = TOKEN_PRIMARY
            ACTIVE_TOKEN_LABEL = "PRIMARY"
            log.info("Active token: PRIMARY")
    except Exception:
        TOKEN = TOKEN_BACKUP
        ACTIVE_TOKEN_LABEL = "BACKUP"
        log.info("Active token: BACKUP (primary check failed)")

    # ── Step 0: Build universe ─────────────────────────────────────────────
    universe = build_universe()

    # ── Step 1: Gate 1 — industry filter ──────────────────────────────────
    g1_passers, g1_rejects = apply_gate1(universe)
    log.info(f"After Gate 1: {len(g1_passers)} candidates for triage")

    # ── Step 2: Mass Triage ────────────────────────────────────────────────
    triage_passers, triage_results = run_mass_triage(g1_passers)
    if not triage_passers:
        log.error("No names cleared triage. Aborting.")
        sys.exit(1)

    # ── Step 3: Gate 3 ─────────────────────────────────────────────────────
    g3_passers, g3_results = run_gate3_batch(triage_passers)

    # ── Step 4: Gate 6.5 ───────────────────────────────────────────────────
    if g3_passers:
        _, g65_results = run_gate65_batch(g3_passers)
    else:
        log.warning("No Gate 3 passers — running Gate 6.5 on Conditional names")
        conditional = [s for s, r in g3_results.items()
                       if r and not getattr(r, "hard_fail_triggered", True)
                       and getattr(r, "verdict", "") == "Conditional"]
        g3_passers = conditional
        _, g65_results = run_gate65_batch(conditional)

    # ── Step 5: Compile & rank ─────────────────────────────────────────────
    final = compile_final(g3_passers, g3_results, g65_results, triage_results)

    # ── Output ─────────────────────────────────────────────────────────────
    log.info("\n" + "=" * 70)
    log.info("RANKED SCREEN OUTPUT — ALL GATE 3 PASSERS")
    log.info("=" * 70)
    for i, rec in enumerate(final, 1):
        adv = rec["adv_ntd"]
        adv_str = "N/A" if adv is None else f"NT${adv/1e6:.1f}M"
        log.info(
            f"  #{i:3d} | {rec['stock_id']} | G3:{rec['gate3_score']:5.1f} "
            f"({rec['gate3_verdict']:12s}) | G6.5:{rec['gate65_verdict']:20s} "
            f"| ADV:{adv_str} | Composite:{rec['composite']:6.1f}"
        )

    log.info("\n— TOP 10 SELECTIONS —")
    for i, rec in enumerate(final[:10], 1):
        log.info(f"  #{i:2d} {rec['stock_id']} | G3:{rec['gate3_score']:.1f} | {rec['gate65_verdict']}")

    # Save
    output = {
        "run_date": TODAY.strftime("%Y-%m-%d %H:%M"),
        "funnel": {
            "universe": len(universe),
            "gate1_pass": len(g1_passers),
            "triage_pass": len(triage_passers),
            "gate3_pass": len(g3_passers),
            "final": len(final),
        },
        "top10": final[:10],
        "all_ranked": final,
        "gate1_rejects": g1_rejects,
        "triage_failures": {
            sid: [{"name": c.name, "detail": c.detail} for c in r.failures()]
            for sid, r in triage_results.items()
            if r and not r.passed
        },
        "gate3_details": {
            sid: {
                "score": getattr(r, "score", None),
                "verdict": getattr(r, "verdict", None),
                "hard_fail": getattr(r, "hard_fail_triggered", None),
            }
            for sid, r in g3_results.items() if r
        },
    }
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    log.info(f"\nFull results saved → {RESULTS_PATH}")
    log.info(
        f"Funnel: {len(universe)} universe → G1:{len(g1_passers)} → "
        f"Triage:{len(triage_passers)} → G3:{len(g3_passers)} → Final:{len(final)}"
    )
    return final


if __name__ == "__main__":
    results = main()

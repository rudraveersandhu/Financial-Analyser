"""
generate_bank_data.py

Generates a realistic dummy Indian bank statement CSV (HDFC-style export)
with embedded UPI / NEFT / ACH / POS / ATM / Cheque transactions, for
practicing a transaction-categorization + spend-analysis pipeline.

Design notes (why it looks like this):
- Real bank statement exports do NOT contain a "category" column -- that's
  the whole point of the tool being built. Categorization must be inferred
  from the free-text `Narration` field, exactly like real life.
- Only one of Withdrawal Amt. / Deposit Amt. is populated per row, the
  other is left BLANK (not 0) -- this matches real exports and is a common
  gotcha (needs fillna / combining into a signed amount column).
- Dates are DD/MM/YYYY strings (dayfirst), another real-world gotcha.
- Closing Balance is a running balance computed transaction-by-transaction,
  in chronological order, like a real passbook/statement.
- Narration formats vary by transaction mode (UPI/NEFT/ACH/POS/ATM/CHQ/etc)
  the way a single bank's statement genuinely mixes rail types.
- Includes recurring monthly items (salary, rent, EMI, SIP, bills,
  subscriptions), frequent small UPI spends, occasional refunds, and
  deliberate outliers (medical emergency, electronics, travel, bonuses)
  for the outlier-detection part of the project.
"""

import random
import datetime
import csv

random.seed(42)

START = datetime.date(2023, 1, 1)
END = datetime.date(2026, 6, 30)

OUT_PATH = "data/bank_transactions_dummy.csv"

# ----------------------------------------------------------------------
# Reference number / masking helpers
# ----------------------------------------------------------------------

def upi_ref():
    return str(random.randint(200000000000, 499999999999))  # 12-digit RRN

def utr_ref():
    bank = random.choice(["HDFC", "ICIC", "SBIN", "YESB", "UTIB", "AXIS"])
    return f"{bank}N{random.randint(10**12, 10**13 - 1)}"

def masked_card():
    bins = ["434358", "512345", "400123", "489562", "477845"]
    return f"{random.choice(bins)}XXXXXX{random.randint(1000, 9999)}"

def chq_no():
    return str(random.randint(100001, 100999))

MONTHS_ABBR = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]

def month_tag(d):
    return f"{MONTHS_ABBR[d.month-1]}{d.strftime('%y')}"

def fmt_date(d):
    return d.strftime("%d/%m/%Y")

def rupee(x):
    return f"{round(x, 2):.2f}"

# ----------------------------------------------------------------------
# Merchant pools: name -> (vpa, bank_ifsc_prefix)
# ----------------------------------------------------------------------

UPI_MERCHANTS = {
    "food_delivery": {
        "SWIGGY": ("swiggy.instamart@icici", "ICIC0000104"),
        "ZOMATO": ("zomato-order@ybl", "YESB0000002"),
    },
    "groceries": {
        "BIGBASKET": ("bigbasket@hdfcbank", "HDFC0000001"),
        "BLINKIT": ("blinkit.payments@axisbank", "UTIB0000123"),
        "ZEPTO": ("zeptonow@icici", "ICIC0000201"),
        "DMART READY": ("dmartready@ybl", "YESB0000045"),
        "SHARMA GENERAL STORE": ("sharmagenstore@paytm", "PYTM0123456"),
        "GUPTA KIRANA STORE": ("guptakirana@oksbi", "SBIN0004521"),
        "NEW DELHI PROVISION STORE": ("ndps2019@okhdfcbank", "HDFC0002233"),
    },
    "dining_out": {
        "STARBUCKS COFFEE": ("starbucksin@icici", "ICIC0000550"),
        "CAFE COFFEE DAY": ("ccd.payments@ybl", "YESB0000132"),
        "DOMINOS PIZZA": ("dominos@hdfcbank", "HDFC0000601"),
        "HALDIRAM RESTAURANT": ("haldiram.cp@oksbi", "SBIN0007744"),
        "SPICE GARDEN RESTAURANT": ("spicegarden22@ybl", "YESB0000210"),
        "THE COFFEE HOUSE": ("thecoffeehouse@okaxis", "UTIB0000789"),
        "BARBEQUE NATION": ("bbqnation@icici", "ICIC0000633"),
    },
    "transport": {
        "UBER INDIA": ("uberindia@hdfcbank", "HDFC0000333"),
        "OLA CABS": ("olacabs@icici", "ICIC0000410"),
        "RAPIDO": ("rapido@ybl", "YESB0000091"),
        "DELHI METRO RAIL CORP": ("dmrcqr@sbi", "SBIN0000556"),
    },
    "fuel": {
        "INDIAN OIL PETROL PUMP": ("indianoilcorp@sbi", "SBIN0000771"),
        "BHARAT PETROLEUM": ("bharatpetro@hdfcbank", "HDFC0000899"),
        "HP PETROL PUMP SEC-15": ("hppcl.sec15@icici", "ICIC0000772"),
    },
    "shopping": {
        "AMAZON": ("amazon@apl", "AIRP0000001"),
        "FLIPKART": ("flipkart@axisbank", "UTIB0000456"),
        "MYNTRA": ("myntra@icici", "ICIC0000305"),
        "AJIO": ("ajio@ybl", "YESB0000078"),
        "NYKAA": ("nykaa@hdfcbank", "HDFC0000212"),
        "CROMA RETAIL": ("cromaretail@icici", "ICIC0000890"),
    },
    "entertainment": {
        "BOOKMYSHOW": ("bookmyshow@ybl", "YESB0000345"),
        "PVR CINEMAS": ("pvrcinemas@hdfcbank", "HDFC0000456"),
        "INOX LEISURE": ("inoxleisure@icici", "ICIC0000556"),
    },
    "medical": {
        "APOLLO PHARMACY": ("apollopharmacy@hdfcbank", "HDFC0000678"),
        "MEDPLUS": ("medplusmart@ybl", "YESB0000456"),
        "PRACTO": ("practo@icici", "ICIC0000901"),
    },
    "education": {
        "UDEMY": ("udemy@apl", "AIRP0000045"),
        "OXFORD BOOKSTORE": ("oxfordbooks.cp@sbi", "SBIN0003321"),
    },
    "travel": {
        "MAKEMYTRIP": ("makemytrip@icici", "ICIC0001002"),
        "OYO ROOMS": ("oyorooms@ybl", "YESB0000678"),
        "GOIBIBO": ("goibibo@hdfcbank", "HDFC0000921"),
    },
    "misc": {
        "PAYTM WALLET LOAD": ("paytmwallet@paytm", "PYTM0000001"),
        "GOOGLE PLAY": ("googleplay@apl", "AIRP0000090"),
        "MOHIT ENTERPRISES": ("mohitent@ybl", "YESB0000501"),
        "SR TRADERS": ("srtraders2018@oksbi", "SBIN0009988"),
        "AGGARWAL TAILORS": ("aggarwaltailors@okicici", "ICIC0001188"),
    },
    "daily_micro": {
        "CHAI POINT": ("chaipoint@ybl", "YESB0000601"),
        "LOCAL VEGETABLE VENDOR": ("vegvendor.rk@oksbi", "SBIN0008812"),
        "PAAN SHOP": ("paanshop.corner@okicici", "ICIC0002233"),
        "AUTO RICKSHAW": ("autofare.delhi@okhdfcbank", "HDFC0003344"),
        "PARKING FEE": ("smartparking@paytm", "PYTM0002211"),
        "STREET FOOD STALL": ("streetfoodstall@ybl", "YESB0000722"),
        "TEA STALL": ("teastall.corner@oksbi", "SBIN0009911"),
        "XEROX PRINT SHOP": ("xeroxshop@okaxis", "UTIB0002299"),
    },
}

FIRST_NAMES = ["ROHIT","PRIYA","AMIT","SNEHA","VIKRAM","POOJA","RAHUL","NEHA",
               "SURESH","KAVITA","ANIL","DEEPIKA","SANJAY","RITU","ARJUN",
               "MEERA","KARAN","SHREYA","NITIN","ANJALI"]
LAST_NAMES = ["SHARMA","VERMA","GUPTA","SINGH","KUMAR","AGARWAL","MEHTA",
              "REDDY","NAIR","JOSHI","MALHOTRA","CHAUHAN","BHATIA","RAO"]
UPI_HANDLES = ["@okhdfcbank","@oksbi","@okicici","@okaxis","@ybl","@paytm","@apl"]

def random_person():
    name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    handle = f"{name.split()[0].lower()}{random.randint(1,999)}{random.choice(UPI_HANDLES)}"
    bank = random.choice(["HDFC0000234","ICIC0000345","SBIN0002211","UTIB0000567","YESB0000789"])
    return name, handle, bank

LANDLORD_NAME, LANDLORD_VPA, LANDLORD_BANK = "RAJESH KUMAR VERMA", "rajeshverma78@oksbi", "SBIN0001122"
EMPLOYER_NAME = "TECHNOVA SOFTWARE SOLUTIONS PVT LTD"

# ----------------------------------------------------------------------
# Row builder
# ----------------------------------------------------------------------

rows = []          # list of dicts: date(date obj), narration, ref, value_date, withdrawal, deposit, _sort
pending_refunds = []  # (date_to_post, merchant, vpa, bank, amount)

def add_row(d, narration, ref, withdrawal=None, deposit=None, value_date=None, sort_hint=None):
    rows.append({
        "date": d,
        "narration": narration,
        "ref": ref,
        "value_date": value_date or d,
        "withdrawal": withdrawal,
        "deposit": deposit,
        "_sort": sort_hint if sort_hint is not None else random.random(),
    })

def upi_debit(d, category, remark="UPI"):
    merchant, (vpa, bank) = random.choice(list(UPI_MERCHANTS[category].items()))
    ref = upi_ref()
    narration = f"UPI-{merchant}-{vpa}-{bank}-{ref}-{remark}"
    return merchant, vpa, bank, ref, narration

def p2p_transfer(d):
    name, vpa, bank = random_person()
    ref = upi_ref()
    is_credit = random.random() < 0.35
    remark = random.choice(["Payment", "UPI", "Rent Split", "For Dinner", "Gift", "Loan Return"])
    if is_credit:
        narration = f"UPI-{name}-{vpa}-{bank}-{ref}-{remark}"
        return narration, ref, "credit"
    else:
        narration = f"UPI-{name}-{vpa}-{bank}-{ref}-{remark}"
        return narration, ref, "debit"

# ----------------------------------------------------------------------
# 1) Recurring monthly transactions
# ----------------------------------------------------------------------

def month_range(start, end):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1

base_salary = 99000
base_rent = 18500
sip1_amt = 6000
sip2_amt = 4000
home_loan_emi = 17500

for (y, m) in month_range(START, END):
    days_in_month = (datetime.date(y + (m == 12), (m % 12) + 1, 1) - datetime.timedelta(days=1)).day
    month_progress = (y - START.year) * 12 + (m - START.month)

    # ---- Salary credit (1st-2nd working day) ----
    sal_day = random.choice([1, 1, 1, 2, 2, 30]) if m != 2 else 1
    sal_date = datetime.date(y, m, min(sal_day, days_in_month)) if sal_day != 30 else datetime.date(y, m, days_in_month)
    salary_amt = base_salary + month_progress * 350 + random.randint(-400, 400)
    # Annual appraisal bump every April, bonus in March (FY-end) and Nov (festival)
    if m == 4:
        salary_amt += 6000
    bonus_month = m in (3, 11)
    utr = utr_ref()
    add_row(sal_date, f"NEFT CR-{utr}-{EMPLOYER_NAME}-SALARY-{month_tag(sal_date)}", utr,
            deposit=salary_amt, sort_hint=0.01)
    if bonus_month and random.random() < 0.8:
        bonus_amt = random.randint(15000, 55000)
        bonus_date = sal_date + datetime.timedelta(days=random.randint(0, 3))
        utr2 = utr_ref()
        tag = "PERFORMANCE BONUS" if m == 3 else "FESTIVAL BONUS"
        add_row(bonus_date, f"NEFT CR-{utr2}-{EMPLOYER_NAME}-{tag}-{month_tag(bonus_date)}", utr2,
                deposit=bonus_amt, sort_hint=0.02)

    # ---- Rent (3rd-6th) ----
    rent_day = min(random.randint(3, 6), days_in_month)
    rent_date = datetime.date(y, m, rent_day)
    rent_amt = base_rent + (500 if month_progress >= 12 else 0) + (500 if month_progress >= 24 else 0)
    ref = upi_ref()
    add_row(rent_date, f"UPI-{LANDLORD_NAME}-{LANDLORD_VPA}-{LANDLORD_BANK}-{ref}-Rent {month_tag(rent_date)}",
            ref, withdrawal=rent_amt, sort_hint=0.05)

    # ---- Home loan EMI (5th-7th, ACH) ----
    emi_day = min(random.randint(5, 7), days_in_month)
    emi_date = datetime.date(y, m, emi_day)
    mandate = f"HDFCLTD{random.randint(10000000,99999999)}"
    add_row(emi_date, f"ACH D-HDFC LTD-HOMELOAN EMI-{mandate}", mandate,
            withdrawal=home_loan_emi, sort_hint=0.1)

    # ---- Mutual fund SIPs (7th-10th, ACH via CAMS/Karvy) ----
    sip_day = min(random.randint(7, 10), days_in_month)
    sip_date = datetime.date(y, m, sip_day)
    folio1 = f"1234{random.randint(1000,9999)}"
    add_row(sip_date, f"ACH D-CAMS NPCI-ICICI PRU MF SIP-{folio1}", folio1,
            withdrawal=sip1_amt, sort_hint=0.11)
    folio2 = f"5678{random.randint(1000,9999)}"
    sip2_date = min(sip_day + 2, days_in_month)
    add_row(datetime.date(y, m, sip2_date), f"ACH D-CAMS NPCI-HDFC MF SIP-{folio2}", folio2,
            withdrawal=sip2_amt, sort_hint=0.12)

    # ---- Electricity bill (10th-16th, variable, seasonal) ----
    elec_day = min(random.randint(10, 16), days_in_month)
    elec_date = datetime.date(y, m, elec_day)
    seasonal = 1.6 if m in (4, 5, 6) else (1.3 if m in (7, 8) else 1.0)  # summer AC load
    elec_amt = round(random.uniform(1400, 3200) * seasonal, 2)
    ref = upi_ref()
    add_row(elec_date, f"UPI-BSES RAJDHANI POWER-bsesrajdhani@sbi-SBIN0000441-{ref}-ElectricityBill",
            ref, withdrawal=elec_amt, sort_hint=0.2)

    # ---- Broadband + mobile postpaid (1st-4th) ----
    bb_day = min(random.randint(1, 4), days_in_month)
    bb_date = datetime.date(y, m, bb_day)
    ref = upi_ref()
    add_row(bb_date, f"UPI-AIRTEL BROADBAND-airtelbroadband@ybl-YESB0000998-{ref}-BillPayment",
            ref, withdrawal=round(random.uniform(999, 1499), 2), sort_hint=0.21)
    ref = upi_ref()
    add_row(bb_date, f"UPI-AIRTEL POSTPAID-airtel.postpaid@icici-ICIC0000112-{ref}-BillPayment",
            ref, withdrawal=round(random.uniform(449, 899), 2), sort_hint=0.22)

    # ---- Gym membership (fixed day) ----
    gym_day = min(5, days_in_month)
    add_row(datetime.date(y, m, gym_day), "ACH D-CULT FITNESS-MEMBERSHIP-CULTFIT" + str(random.randint(100000,999999)),
            f"CULTFIT{random.randint(100000,999999)}", withdrawal=1499.00, sort_hint=0.3)

    # ---- Subscriptions: Netflix, Prime, Hotstar (via card, ECOM) ----
    for svc, amt, day_ in [("NETFLIX.COM", 649, 8), ("AMAZON PRIME", 179, 14), ("HOTSTAR", 299, 19)]:
        sday = min(day_, days_in_month)
        card = masked_card()
        add_row(datetime.date(y, m, sday), f"ECOM PUR/{card}/{svc}", card,
                withdrawal=float(amt), sort_hint=0.35)

    # ---- Quarterly interest credit ----
    if m in (3, 6, 9, 12):
        q_start = datetime.date(y, m - 2, 1)
        q_end = datetime.date(y, m, days_in_month)
        add_row(q_end, f"INT.PD:{fmt_date(q_start)} TO {fmt_date(q_end)}", "",
                deposit=round(random.uniform(280, 650), 2), sort_hint=0.9)

    # ---- Quarterly insurance premiums ----
    if m in (1, 7):  # health insurance, twice a year
        idate = datetime.date(y, m, min(random.randint(18, 24), days_in_month))
        ref = upi_ref()
        add_row(idate, f"UPI-HDFC ERGO HEALTH INS-hdfcergo.premium@hdfcbank-HDFC0000777-{ref}-PremiumPayment",
                ref, withdrawal=round(random.uniform(9500, 14500), 2), sort_hint=0.5)
    if m == 9:  # car insurance, annual
        idate = datetime.date(y, m, min(22, days_in_month))
        ref = upi_ref()
        add_row(idate, f"UPI-ICICI LOMBARD GIC-icicilombard.premium@icici-ICIC0000888-{ref}-CarInsurance",
                ref, withdrawal=round(random.uniform(7500, 11000), 2), sort_hint=0.5)
    if m == 12:  # LIC premium annual
        idate = datetime.date(y, m, min(10, days_in_month))
        add_row(idate, "ACH D-LIC OF INDIA-PREMIUM-LICPOL" + str(random.randint(100000,999999)),
                f"LICPOL{random.randint(100000,999999)}", withdrawal=round(random.uniform(18000, 26000), 2),
                sort_hint=0.5)

    # ---- Bank charges (occasional) ----
    if random.random() < 0.35:
        charge_type = random.choice([
            f"SMS ALERT CHARGES-{month_tag(datetime.date(y,m,1))}+GST",
            "DEBIT CARD ANNUAL FEE+GST",
            "MIN BAL CHARGES+GST",
            "CHEQUE BOOK ISSUE CHARGES+GST",
        ])
        cday = min(random.randint(20, days_in_month), days_in_month)
        add_row(datetime.date(y, m, cday), charge_type, "", withdrawal=round(random.uniform(29, 590), 2), sort_hint=0.95)

# ----------------------------------------------------------------------
# 2) Daily discretionary transactions
# ----------------------------------------------------------------------

CATEGORY_WEIGHTS = [
    ("daily_micro", 28),
    ("food_delivery", 13),
    ("groceries", 12),
    ("dining_out", 8),
    ("transport", 9),
    ("fuel", 3),
    ("shopping", 6),
    ("entertainment", 3),
    ("medical", 3),
    ("education", 1),
    ("travel", 1),
    ("misc", 4),
    ("p2p", 9),
]
CAT_NAMES = [c for c, w in CATEGORY_WEIGHTS]
CAT_W = [w for c, w in CATEGORY_WEIGHTS]

AMOUNT_RANGES = {
    "daily_micro": (10, 110),
    "food_delivery": (89, 290),
    "groceries": (100, 800),
    "dining_out": (140, 650),
    "transport": (30, 200),
    "fuel": (350, 1250),
    "shopping": (180, 1650),
    "entertainment": (100, 450),
    "medical": (80, 850),
    "education": (250, 1200),
    "travel": (800, 2600),
    "misc": (49, 520),
}

d = START
card_txn_flag_categories = {"shopping", "fuel", "entertainment"}  # sometimes card instead of UPI

while d <= END:
    weekday = d.weekday()  # 0=Mon .. 6=Sun
    is_weekend = weekday >= 5
    day_of_month = d.day

    # base transaction count per day, boosted on weekends and post-salary days
    base_n = random.choices([0,1,2,3,4,5,6,7], weights=[3,8,14,18,18,14,10,5])[0]
    if is_weekend:
        base_n = int(base_n * 1.3)
    if day_of_month <= 8:  # more discretionary spend right after salary
        base_n = int(base_n * 1.15)

    for _ in range(base_n):
        cat = random.choices(CAT_NAMES, weights=CAT_W, k=1)[0]

        if cat == "p2p":
            narration, ref, direction = p2p_transfer(d)
            amt = round(random.choice([
                random.uniform(40, 350),
                random.uniform(350, 1200),
                random.uniform(1200, 3000) if random.random() < 0.08 else random.uniform(40, 350),
            ]), 2)
            if direction == "credit":
                add_row(d, narration, ref, deposit=amt)
            else:
                add_row(d, narration, ref, withdrawal=amt)
            continue

        lo, hi = AMOUNT_RANGES[cat]
        amt = round(random.uniform(lo, hi), 2)
        # occasional intra-category outlier (e.g. big group order, bulk shopping haul)
        is_outlier = random.random() < 0.015
        if is_outlier:
            amt = round(amt * random.uniform(3, 6), 2)

        use_card = cat in card_txn_flag_categories and random.random() < 0.3
        merchant, (vpa, bank) = random.choice(list(UPI_MERCHANTS[cat].items()))

        if use_card:
            card = masked_card()
            loc = random.choice(["NEW DELHI", "GURGAON", "NOIDA", "BENGALURU", "MUMBAI"])
            narration = f"POS {card} {merchant} {loc}"
            add_row(d, narration, card, withdrawal=amt, value_date=d + datetime.timedelta(days=1))
        else:
            ref = upi_ref()
            remark = random.choice(["Payment from Phone", "UPI", "Order Payment", "Payment"])
            narration = f"UPI-{merchant}-{vpa}-{bank}-{ref}-{remark}"
            add_row(d, narration, ref, withdrawal=amt)

            # small chance of a refund a few days later (order cancelled / returned)
            if cat in ("shopping", "food_delivery") and random.random() < 0.02:
                refund_date = d + datetime.timedelta(days=random.randint(2, 6))
                refund_amt = amt if random.random() < 0.7 else round(amt * random.uniform(0.4, 0.9), 2)
                pending_refunds.append((refund_date, merchant, vpa, bank, refund_amt))

    # ATM withdrawal, occasional
    if random.random() < 0.032:
        amt = random.choice([500, 1000, 1500, 2000, 3000, 5000])
        card = masked_card()
        loc_bank = random.choice(["SBIN0001234", "HDFC0002345", "ICIC0003456", "UTIB0004567"])
        add_row(d, f"NWD-{card}-{loc_bank}-ATM CASH WDL", card, withdrawal=float(amt))

    # cheque payment, rare (e.g. paying domestic help / contractor / society maintenance)
    if random.random() < 0.008:
        payee = random.choice(["SOCIETY MAINTENANCE", "HOUSE RENOVATION CONTRACTOR", "DOMESTIC STAFF SALARY"])
        add_row(d, f"CHQ PAID-{chq_no()}-{payee}", chq_no(), withdrawal=round(random.uniform(2000, 15000), 2))

    d += datetime.timedelta(days=1)

# ----------------------------------------------------------------------
# 3) Post pending refunds
# ----------------------------------------------------------------------

for (rdate, merchant, vpa, bank, amt) in pending_refunds:
    if rdate > END:
        continue
    ref = upi_ref()
    add_row(rdate, f"UPI-{merchant}-{vpa}-{bank}-{ref}-Refund/Reversal", ref, deposit=amt, sort_hint=0.0)

# ----------------------------------------------------------------------
# 4) Deliberate big-ticket outliers (rare, one-off, real-life events)
# ----------------------------------------------------------------------

OUTLIER_EVENTS = [
    ("MAX SUPER SPECIALTY HOSPITAL", "medical emergency", (35000, 78000)),
    ("APOLLO HOSPITALS", "hospitalization", (28000, 65000)),
    ("CROMA RETAIL", "laptop purchase", (42000, 95000)),
    ("RELIANCE DIGITAL", "television purchase", (35000, 68000)),
    ("MAKEMYTRIP", "international flight booking", (38000, 82000)),
    ("TANISHQ JEWELLERY", "gold jewellery purchase", (45000, 120000)),
    ("IKEA INDIA", "furniture purchase", (18000, 45000)),
    ("WEDDING GIFT TRANSFER", "wedding gift", (15000, 40000)),
    ("HOME RENOVATION CONTRACTOR", "renovation advance", (25000, 70000)),
]

n_outliers = int((END - START).days / 130)  # roughly one every ~4.3 months
for _ in range(n_outliers):
    offset = random.randint(0, (END - START).days)
    ev_date = START + datetime.timedelta(days=offset)
    name, remark, (lo, hi) = random.choice(OUTLIER_EVENTS)
    amt = round(random.uniform(lo, hi), 2)
    ref = upi_ref()
    vpa = f"{name.split()[0].lower()}@okhdfcbank"
    narration = f"UPI-{name}-{vpa}-HDFC0000999-{ref}-{remark.title().replace(' ', '')}"
    add_row(ev_date, narration, ref, withdrawal=amt, sort_hint=0.6)

# ----------------------------------------------------------------------
# 5) Sort, compute running balance, write CSV
# ----------------------------------------------------------------------

rows.sort(key=lambda r: (r["date"], r["_sort"]))

opening_balance = 46250.75
balance = opening_balance

with open(OUT_PATH, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Date", "Narration", "Chq./Ref.No.", "Value Dt", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"])
    for r in rows:
        w = r["withdrawal"]
        dep = r["deposit"]
        if w:
            balance -= w
        if dep:
            balance += dep
        writer.writerow([
            fmt_date(r["date"]),
            r["narration"],
            r["ref"],
            fmt_date(r["value_date"]),
            rupee(w) if w else "",
            rupee(dep) if dep else "",
            rupee(balance),
        ])

print(f"Wrote {len(rows)} rows to {OUT_PATH}")
print(f"Date range: {START} to {END}")
print(f"Opening balance: {opening_balance}, Closing balance: {round(balance,2)}")
print(f"Min balance seen: (checking...)")

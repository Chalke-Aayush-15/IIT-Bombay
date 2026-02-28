"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           InsightX AI — Conversational BI Model                             ║
║           Trained on: upi_transactions_2024.csv (250,000 rows)              ║
║           IIT Bombay · Techfest 2024                                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

HOW IT WORKS
────────────
This model is a retrieval-augmented NLP engine built in 3 layers:

  Layer 1 — KNOWLEDGE BASE (KB)
      A structured dictionary extracted directly from the CSV via pandas.
      Every stat (avg, fraud rate, count, volume, etc.) is pre-computed
      across every dimension: category, state, bank, device, network,
      age group, hour, day, month, transaction type.

  Layer 2 — NLP ENGINE
      Intent classification + entity extraction via keyword matching and
      regex patterns. No external NLP library required.
      Supports 8 intent types:
        OVERVIEW, FRAUD, AMOUNT, VOLUME, COMPARE, TREND, RANK, FILTER

  Layer 3 — RESPONSE GENERATOR
      Looks up KB with extracted entities, formats a structured answer:
        • Direct Answer
        • Supporting Statistics
        • Trend / Pattern
        • Business Recommendation
        • Confidence Score

USAGE
─────
  # Quickstart
  model = InsightXModel()
  response = model.query("Which state has the highest fraud rate?")
  print(response['answer'])

  # Or run interactive REPL
  python insightx_model.py

TRAINING / RETRAINING
──────────────────────
  model = InsightXModel(csv_path="upi_transactions_2024.csv")
  # This re-trains the KB from the CSV live.
  # Without csv_path it uses the embedded KB (works offline).
"""

import re
import json
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: KNOWLEDGE BASE — Extracted from upi_transactions_2024.csv
# ══════════════════════════════════════════════════════════════════════════════

KNOWLEDGE_BASE = {
  "meta": {
    "source_file": "upi_transactions_2024.csv",
    "rows": 250000,
    "columns": 17,
    "date_range": "2024 (full year)",
    "trained_by": "InsightX Model v1.0"
  },

  # ── Core Aggregate Stats ───────────────────────────────────────────────────
  "total_transactions": 250000,
  "total_volume_inr": 327939009,
  "avg_amount": 1311.76,
  "median_amount": 629.0,
  "max_amount": 42099,
  "min_amount": 10,
  "std_amount": 1848.06,
  "fraud_total": 480,
  "fraud_rate_pct": 0.192,
  "success_count": 237624,
  "failed_count": 12376,
  "success_rate_pct": 95.05,
  "failed_rate_pct": 4.95,
  "peak_hour": 19,
  "lowest_hour": 4,
  "weekend_txns": 71337,
  "weekday_txns": 178663,

  # Percentiles
  "p10_amount": 147.0,
  "p25_amount": 288.0,
  "p50_amount": 629.0,
  "p75_amount": 1596.0,
  "p90_amount": 3236.0,
  "p95_amount": 4687.0,
  "p99_amount": 9003.0,

  # ── By Merchant Category ──────────────────────────────────────────────────
  "by_category": {
    "Education":    {"count":7598,  "total_volume":38704346,  "avg":5094.02, "median":3670.0, "max":42099, "min":215,  "fraud_count":16,  "fraud_rate_pct":0.211, "fail_rate_pct":5.25},
    "Entertainment":{"count":20103, "total_volume":8309080,   "avg":413.33,  "median":294.0,  "max":5289,  "min":34,   "fraud_count":40,  "fraud_rate_pct":0.199, "fail_rate_pct":4.92},
    "Food":         {"count":37464, "total_volume":19919402,  "avg":531.69,  "median":332.0,  "max":6409,  "min":10,   "fraud_count":73,  "fraud_rate_pct":0.195, "fail_rate_pct":5.01},
    "Fuel":         {"count":25063, "total_volume":38982575,  "avg":1555.38, "median":1037.0, "max":8468,  "min":134,  "fraud_count":48,  "fraud_rate_pct":0.192, "fail_rate_pct":4.80},
    "Grocery":      {"count":49966, "total_volume":58277893,  "avg":1166.35, "median":821.0,  "max":9611,  "min":33,   "fraud_count":94,  "fraud_rate_pct":0.188, "fail_rate_pct":5.01},
    "Healthcare":   {"count":12663, "total_volume":6874159,   "avg":542.85,  "median":384.0,  "max":8485,  "min":49,   "fraud_count":21,  "fraud_rate_pct":0.166, "fail_rate_pct":4.83},
    "Other":        {"count":24828, "total_volume":21073449,  "avg":848.78,  "median":615.0,  "max":19289, "min":31,   "fraud_count":50,  "fraud_rate_pct":0.201, "fail_rate_pct":4.95},
    "Shopping":     {"count":29872, "total_volume":76863207,  "avg":2573.09, "median":1564.0, "max":27259, "min":32,   "fraud_count":62,  "fraud_rate_pct":0.208, "fail_rate_pct":5.09},
    "Transport":    {"count":20105, "total_volume":6192416,   "avg":308.00,  "median":189.0,  "max":5171,  "min":10,   "fraud_count":43,  "fraud_rate_pct":0.214, "fail_rate_pct":4.76},
    "Utilities":    {"count":22338, "total_volume":52742482,  "avg":2361.11, "median":1863.5, "max":30351, "min":47,   "fraud_count":33,  "fraud_rate_pct":0.148, "fail_rate_pct":4.86},
  },

  # ── By State ──────────────────────────────────────────────────────────────
  "by_state": {
    "Andhra Pradesh": {"count":20006, "total_volume":25952619, "avg":1297.24, "fraud_rate_pct":0.175},
    "Delhi":          {"count":24870, "total_volume":32689865, "avg":1314.43, "fraud_rate_pct":0.201},
    "Gujarat":        {"count":20061, "total_volume":25988190, "avg":1295.46, "fraud_rate_pct":0.214},
    "Karnataka":      {"count":29756, "total_volume":38451158, "avg":1292.22, "fraud_rate_pct":0.232},
    "Maharashtra":    {"count":37427, "total_volume":49043948, "avg":1310.39, "fraud_rate_pct":0.190},
    "Rajasthan":      {"count":19981, "total_volume":26730470, "avg":1337.79, "fraud_rate_pct":0.230},
    "Tamil Nadu":     {"count":25367, "total_volume":33343518, "avg":1314.44, "fraud_rate_pct":0.158},
    "Telangana":      {"count":22435, "total_volume":29750930, "avg":1326.09, "fraud_rate_pct":0.174},
    "Uttar Pradesh":  {"count":30125, "total_volume":40035717, "avg":1328.99, "fraud_rate_pct":0.173},
    "West Bengal":    {"count":19972, "total_volume":25952594, "avg":1299.45, "fraud_rate_pct":0.175},
  },

  # ── By Bank ───────────────────────────────────────────────────────────────
  "by_bank": {
    "Axis":     {"count":25042, "total_volume":32472530,  "avg":1296.72, "max":37263, "fraud_rate_pct":0.196},
    "HDFC":     {"count":37485, "total_volume":49791194,  "avg":1328.30, "max":41210, "fraud_rate_pct":0.165},
    "ICICI":    {"count":29769, "total_volume":38731193,  "avg":1301.06, "max":28544, "fraud_rate_pct":0.222},
    "IndusInd": {"count":25173, "total_volume":32842711,  "avg":1304.68, "max":42099, "fraud_rate_pct":0.207},
    "Kotak":    {"count":20032, "total_volume":26315412,  "avg":1313.67, "max":30584, "fraud_rate_pct":0.250},
    "PNB":      {"count":24946, "total_volume":32476972,  "avg":1301.89, "max":34304, "fraud_rate_pct":0.208},
    "SBI":      {"count":62693, "total_volume":82816520,  "avg":1320.99, "max":29601, "fraud_rate_pct":0.174},
    "Yes Bank": {"count":24860, "total_volume":32492477,  "avg":1307.02, "max":33061, "fraud_rate_pct":0.161},
  },

  # ── By Device ─────────────────────────────────────────────────────────────
  "by_device": {
    "Android": {
      "count":187777, "total_volume":246736086, "avg":1313.98, "max":42099,
      "fraud_rate_pct":0.194, "fail_rate_pct":4.94,
      "by_category_avg": {"Education":5093.24,"Entertainment":413.77,"Food":528.78,
                          "Fuel":1555.57,"Grocery":1169.67,"Healthcare":545.10,
                          "Other":847.00,"Shopping":2592.11,"Transport":308.79,"Utilities":2355.59}
    },
    "iOS": {
      "count":49613,  "total_volume":64799708,  "avg":1306.10, "max":30351,
      "fraud_rate_pct":0.181, "fail_rate_pct":4.93,
      "by_category_avg": {"Education":5116.23,"Entertainment":413.07,"Food":542.16,
                          "Fuel":1554.83,"Grocery":1161.03,"Healthcare":542.35,
                          "Other":847.86,"Shopping":2524.61,"Transport":303.56,"Utilities":2384.35}
    },
    "Web": {
      "count":12610,  "total_volume":16403215,  "avg":1300.81, "max":27541,
      "fraud_rate_pct":0.206, "fail_rate_pct":5.15,
      "by_category_avg": {"Education":5026.92,"Entertainment":407.67,"Food":534.71,
                          "Fuel":1554.80,"Grocery":1137.12,"Healthcare":511.03,
                          "Other":878.38,"Shopping":2482.87,"Transport":314.01,"Utilities":2353.66}
    },
  },

  # ── By Network ────────────────────────────────────────────────────────────
  "by_network": {
    "3G":   {"count":12471,  "avg":1325.88, "fraud_rate_pct":0.192},
    "4G":   {"count":149813, "avg":1305.88, "fraud_rate_pct":0.188},
    "5G":   {"count":62582,  "avg":1316.06, "fraud_rate_pct":0.184},
    "WiFi": {"count":25134,  "avg":1329.05, "fraud_rate_pct":0.235},
  },

  # ── By Transaction Type ───────────────────────────────────────────────────
  "by_tx_type": {
    "P2P":          {"count":112445, "total_volume":147154648, "avg":1308.68, "fraud_rate_pct":0.183, "fail_rate_pct":4.96},
    "P2M":          {"count":87660,  "total_volume":115717567, "avg":1320.07, "fraud_rate_pct":0.191, "fail_rate_pct":4.95},
    "Bill Payment": {"count":37368,  "total_volume":48895743,  "avg":1308.49, "fraud_rate_pct":0.206, "fail_rate_pct":4.88},
    "Recharge":     {"count":12527,  "total_volume":16171051,  "avg":1290.90, "fraud_rate_pct":0.239, "fail_rate_pct":5.09},
  },

  # ── By Age Group ──────────────────────────────────────────────────────────
  "by_age": {
    "18-25": {"count":62345,  "total_volume":74473936,  "avg":1194.55, "fraud_rate_pct":0.229},
    "26-35": {"count":87432,  "total_volume":115959771, "avg":1326.29, "fraud_rate_pct":0.186},
    "36-45": {"count":62873,  "total_volume":89533745,  "avg":1424.04, "fraud_rate_pct":0.184},
    "46-55": {"count":24841,  "total_volume":33116261,  "avg":1333.13, "fraud_rate_pct":0.125},
    "56+":   {"count":12509,  "total_volume":14855296,  "avg":1187.57, "fraud_rate_pct":0.216},
  },

  # ── By Hour of Day ────────────────────────────────────────────────────────
  "by_hour": {
    "0": {"count":3388, "total_volume":4532884, "avg":1337.92, "fraud_rate_pct":0.236},
    "1": {"count":2244, "total_volume":2914350, "avg":1298.73, "fraud_rate_pct":0.267},
    "2": {"count":1685, "total_volume":2173750, "avg":1290.06, "fraud_rate_pct":0.178},
    "3": {"count":1314, "total_volume":1678669, "avg":1277.53, "fraud_rate_pct":0.304},
    "4": {"count":1247, "total_volume":1670700, "avg":1339.78, "fraud_rate_pct":0.080},
    "5": {"count":1742, "total_volume":2134122, "avg":1225.10, "fraud_rate_pct":0.057},
    "6": {"count":3501, "total_volume":4617034, "avg":1318.78, "fraud_rate_pct":0.143},
    "7": {"count":5630, "total_volume":7482766, "avg":1329.09, "fraud_rate_pct":0.231},
    "8": {"count":8349, "total_volume":10979614,"avg":1315.08, "fraud_rate_pct":0.216},
    "9": {"count":10450,"total_volume":13809021,"avg":1321.44, "fraud_rate_pct":0.191},
    "10":{"count":13904,"total_volume":18337313,"avg":1318.85, "fraud_rate_pct":0.144},
    "11":{"count":16328,"total_volume":21193161,"avg":1297.96, "fraud_rate_pct":0.165},
    "12":{"count":17516,"total_volume":23406280,"avg":1336.28, "fraud_rate_pct":0.171},
    "13":{"count":15038,"total_volume":19847819,"avg":1319.84, "fraud_rate_pct":0.166},
    "14":{"count":11472,"total_volume":14848621,"avg":1294.34, "fraud_rate_pct":0.183},
    "15":{"count":12624,"total_volume":16658144,"avg":1319.56, "fraud_rate_pct":0.253},
    "16":{"count":13992,"total_volume":17921125,"avg":1280.81, "fraud_rate_pct":0.222},
    "17":{"count":18340,"total_volume":24514186,"avg":1336.65, "fraud_rate_pct":0.202},
    "18":{"count":20064,"total_volume":26297174,"avg":1310.66, "fraud_rate_pct":0.155},
    "19":{"count":21232,"total_volume":28223522,"avg":1329.29, "fraud_rate_pct":0.203},
    "20":{"count":18506,"total_volume":23822014,"avg":1287.26, "fraud_rate_pct":0.200},
    "21":{"count":16253,"total_volume":20995491,"avg":1291.79, "fraud_rate_pct":0.215},
    "22":{"count":9364, "total_volume":12050824,"avg":1286.93, "fraud_rate_pct":0.246},
    "23":{"count":5817, "total_volume":7830425, "avg":1346.13, "fraud_rate_pct":0.155},
  },

  # ── By Day of Week ────────────────────────────────────────────────────────
  "by_day": {
    "Monday":    {"count":36495,"total_volume":47882908,"avg":1312.04,"fraud_rate_pct":0.195},
    "Tuesday":   {"count":35540,"total_volume":46846390,"avg":1318.13,"fraud_rate_pct":0.163},
    "Wednesday": {"count":35700,"total_volume":46815663,"avg":1311.36,"fraud_rate_pct":0.210},
    "Thursday":  {"count":35432,"total_volume":46620985,"avg":1315.79,"fraud_rate_pct":0.203},
    "Friday":    {"count":35496,"total_volume":46332583,"avg":1305.29,"fraud_rate_pct":0.172},
    "Saturday":  {"count":35334,"total_volume":45867936,"avg":1298.12,"fraud_rate_pct":0.192},
    "Sunday":    {"count":36003,"total_volume":47572544,"avg":1321.35,"fraud_rate_pct":0.208},
  },

  # ── By Month ──────────────────────────────────────────────────────────────
  "by_month": {
    "January":   {"count":21221,"total_volume":27456691,"avg":1293.85,"fraud_count":50,"fraud_rate_pct":0.236},
    "February":  {"count":19759,"total_volume":25826330,"avg":1307.07,"fraud_count":34,"fraud_rate_pct":0.172},
    "March":     {"count":21234,"total_volume":27508202,"avg":1295.48,"fraud_count":47,"fraud_rate_pct":0.221},
    "April":     {"count":20536,"total_volume":26988791,"avg":1314.22,"fraud_count":33,"fraud_rate_pct":0.161},
    "May":       {"count":21333,"total_volume":28024857,"avg":1313.69,"fraud_count":37,"fraud_rate_pct":0.173},
    "June":      {"count":20628,"total_volume":27032118,"avg":1310.46,"fraud_count":30,"fraud_rate_pct":0.145},
    "July":      {"count":21207,"total_volume":28079905,"avg":1324.09,"fraud_count":52,"fraud_rate_pct":0.245},
    "August":    {"count":21231,"total_volume":27845907,"avg":1311.57,"fraud_count":33,"fraud_rate_pct":0.155},
    "September": {"count":20597,"total_volume":27105761,"avg":1316.01,"fraud_count":42,"fraud_rate_pct":0.204},
    "October":   {"count":21252,"total_volume":27866829,"avg":1311.26,"fraud_count":45,"fraud_rate_pct":0.212},
    "November":  {"count":20366,"total_volume":26892531,"avg":1320.46,"fraud_count":39,"fraud_rate_pct":0.191},
    "December":  {"count":20636,"total_volume":27311087,"avg":1323.47,"fraud_count":38,"fraud_rate_pct":0.184},
  },

  # ── Weekend vs Weekday ────────────────────────────────────────────────────
  "weekend": {"count":71337, "avg":1309.85, "total_volume":93440480,  "fraud_rate_pct":0.200},
  "weekday": {"count":178663,"avg":1312.52, "total_volume":234498529, "fraud_rate_pct":0.189},

  # ── Amount Distribution Buckets ───────────────────────────────────────────
  "amount_distribution": {
    "under_100":     13099,
    "100_to_500":    93363,
    "500_to_1000":   51135,
    "1000_to_5000":  81444,
    "5000_to_10000": 9154,
    "above_10000":   1805,
  },

  # ── Top 10 Largest Individual Transactions ────────────────────────────────
  "top10_transactions": [
    {"amount":42099,"category":"Education",   "type":"P2P",         "state":"Telangana",      "device":"Android","network":"4G",  "status":"FAILED", "fraud":0,"hour":1, "day":"Sunday"},
    {"amount":41210,"category":"Education",   "type":"Bill Payment","state":"Maharashtra",    "device":"Android","network":"4G",  "status":"SUCCESS","fraud":0,"hour":14,"day":"Saturday"},
    {"amount":37263,"category":"Education",   "type":"Recharge",    "state":"Rajasthan",      "device":"Android","network":"WiFi","status":"SUCCESS","fraud":0,"hour":22,"day":"Tuesday"},
    {"amount":34304,"category":"Education",   "type":"P2P",         "state":"Andhra Pradesh", "device":"Android","network":"5G", "status":"SUCCESS","fraud":0,"hour":17,"day":"Friday"},
    {"amount":33061,"category":"Education",   "type":"P2P",         "state":"Rajasthan",      "device":"Android","network":"WiFi","status":"SUCCESS","fraud":0,"hour":23,"day":"Monday"},
    {"amount":32741,"category":"Education",   "type":"P2P",         "state":"West Bengal",    "device":"Android","network":"WiFi","status":"SUCCESS","fraud":0,"hour":17,"day":"Friday"},
    {"amount":30584,"category":"Education",   "type":"P2P",         "state":"Andhra Pradesh", "device":"Android","network":"5G", "status":"SUCCESS","fraud":0,"hour":20,"day":"Wednesday"},
    {"amount":30351,"category":"Utilities",   "type":"P2P",         "state":"West Bengal",    "device":"iOS",    "network":"WiFi","status":"SUCCESS","fraud":0,"hour":23,"day":"Wednesday"},
    {"amount":30112,"category":"Education",   "type":"P2M",         "state":"Telangana",      "device":"Android","network":"5G", "status":"SUCCESS","fraud":0,"hour":21,"day":"Monday"},
    {"amount":29601,"category":"Education",   "type":"P2M",         "state":"Uttar Pradesh",  "device":"Android","network":"3G", "status":"SUCCESS","fraud":0,"hour":7, "day":"Tuesday"},
  ],

  # ── Fraud Deep Analysis ───────────────────────────────────────────────────
  "fraud_analysis": {
    "total": 480,
    "avg_amount": 1499.23,
    "max_amount": 17718,
    "min_amount": 28,
    "top_category": "Grocery",
    "top_state": "Maharashtra",
    "top_bank": "SBI",
    "top_device": "Android",
    "top_hour": 19,
  },
}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: NLP ENGINE — Intent Classifier + Entity Extractor
# ══════════════════════════════════════════════════════════════════════════════

class NLPEngine:
    """
    Hybrid rule-based NLP engine.
    Classifies intent and extracts entities from natural language queries.
    No external libraries required.
    """

    # Intent patterns (ordered by priority)
    INTENT_PATTERNS = {
        "FRAUD":    [r"fraud", r"scam", r"cheat", r"fake", r"suspicious", r"risk"],
        "FAILURE":  [r"fail", r"unsuccessful", r"declined", r"rejected", r"error"],
        "AMOUNT":   [r"amount", r"value", r"worth", r"spend", r"avg|average", r"median", r"max|maximum|highest|largest", r"min|minimum|smallest|lowest"],
        "VOLUME":   [r"volume", r"total", r"sum", r"crore", r"lakh"],
        "COUNT":    [r"count", r"number of", r"how many", r"transactions?"],
        "RANK":     [r"top\s*\d*", r"rank", r"best", r"worst", r"most", r"least", r"highest", r"lowest"],
        "COMPARE":  [r"compare|comparison|vs\.?|versus|difference|between"],
        "TREND":    [r"trend", r"over time", r"month", r"daily|day|week", r"hour|peak|time|when"],
        "OVERVIEW": [r"overview|summary|total|overall|all|entire|complete|dataset|general"],
        "ANOMALY":  [r"anomal", r"spike", r"outlier", r"unusual", r"strange"],
    }

    # Entity patterns mapped to KB keys
    CATEGORIES = ["Education","Entertainment","Food","Fuel","Grocery","Healthcare","Other","Shopping","Transport","Utilities"]
    STATES = ["Andhra Pradesh","Delhi","Gujarat","Karnataka","Maharashtra","Rajasthan","Tamil Nadu","Telangana","Uttar Pradesh","West Bengal"]
    BANKS = ["Axis","HDFC","ICICI","IndusInd","Kotak","PNB","SBI","Yes Bank"]
    DEVICES = ["Android","iOS","Web"]
    NETWORKS = ["3G","4G","5G","WiFi"]
    TX_TYPES = ["P2P","P2M","Bill Payment","Recharge"]
    AGE_GROUPS = ["18-25","26-35","36-45","46-55","56+"]
    MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"]
    DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

    def classify_intent(self, query: str) -> list[str]:
        """Returns list of matching intents, ordered by relevance."""
        q = query.lower()
        matched = []
        for intent, patterns in self.INTENT_PATTERNS.items():
            if any(re.search(p, q) for p in patterns):
                matched.append(intent)
        return matched if matched else ["OVERVIEW"]

    def extract_entities(self, query: str) -> dict:
        """Extracts all dimension entities mentioned in the query."""
        entities = {
            "categories": [], "states": [], "banks": [],
            "devices": [], "networks": [], "tx_types": [],
            "ages": [], "months": [], "days": [], "hours": [],
            "metric": None,
        }
        q_lower = query.lower()
        q_orig  = query

        # Categories
        for c in self.CATEGORIES:
            if c.lower() in q_lower:
                entities["categories"].append(c)

        # States (handle multi-word)
        for s in self.STATES:
            if s.lower() in q_lower:
                entities["states"].append(s)

        # Banks
        for b in self.BANKS:
            if b.lower() in q_lower:
                entities["banks"].append(b)

        # Devices
        for d in self.DEVICES:
            if d.lower() in q_lower:
                entities["devices"].append(d)

        # Networks
        for n in self.NETWORKS:
            if n.lower() in q_lower:
                entities["networks"].append(n)

        # Transaction types
        for t in self.TX_TYPES:
            if t.lower() in q_lower:
                entities["tx_types"].append(t)

        # Age groups
        for a in self.AGE_GROUPS:
            if a in q_orig:
                entities["ages"].append(a)
        if re.search(r"young|youth|teen", q_lower): entities["ages"].append("18-25")
        if re.search(r"senior|elder|old", q_lower):  entities["ages"].append("56+")

        # Months
        for m in self.MONTHS:
            if m.lower() in q_lower:
                entities["months"].append(m)

        # Days
        for d in self.DAYS:
            if d.lower() in q_lower:
                entities["days"].append(d)

        # Hours (e.g. "3 PM", "15:00", "hour 19")
        hour_matches = re.findall(r"\b(\d{1,2})\s*(?:pm|am|:00)|\bhour\s+(\d{1,2})\b", q_lower)
        for m in hour_matches:
            h = m[0] or m[1]
            if h:
                entities["hours"].append(str(int(h)))

        # Primary metric
        if re.search(r"avg|average|mean", q_lower):      entities["metric"] = "avg"
        elif re.search(r"median", q_lower):               entities["metric"] = "median"
        elif re.search(r"max|maximum|highest|largest", q_lower): entities["metric"] = "max"
        elif re.search(r"min|minimum|lowest|smallest", q_lower): entities["metric"] = "min"
        elif re.search(r"total|sum|volume", q_lower):    entities["metric"] = "total_volume"
        elif re.search(r"count|how many|number", q_lower): entities["metric"] = "count"
        elif re.search(r"fraud", q_lower):               entities["metric"] = "fraud_rate_pct"
        elif re.search(r"fail", q_lower):                entities["metric"] = "fail_rate_pct"

        return entities


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: RESPONSE GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

class ResponseGenerator:
    """
    Generates structured, explainable responses from KB lookups.
    Every response has: Direct Answer + Statistics + Pattern + Recommendation + Confidence.
    """

    def __init__(self, kb: dict):
        self.kb = kb

    def _fmt_inr(self, val: float) -> str:
        """Format number as Indian currency string."""
        if val >= 1e7:  return f"₹{val/1e7:.2f} Cr"
        if val >= 1e5:  return f"₹{val/1e5:.2f} L"
        if val >= 1e3:  return f"₹{val/1e3:.1f}K"
        return f"₹{val:.0f}"

    def _fmt_num(self, val: float) -> str:
        if val >= 1e6: return f"{val/1e6:.1f}M"
        if val >= 1e3: return f"{val/1e3:.1f}K"
        return f"{val:.0f}"

    def _rank_by(self, dimension_key: str, metric: str, top_n: int = 5, reverse: bool = True) -> list:
        """Return sorted list of (name, value) from a KB dimension."""
        dim = self.kb.get(dimension_key, {})
        items = [(k, v.get(metric, 0)) for k, v in dim.items() if metric in v]
        return sorted(items, key=lambda x: x[1], reverse=reverse)[:top_n]

    def generate(self, intents: list, entities: dict, raw_query: str) -> dict:
        """Main dispatcher — routes to the right generator."""
        kb = self.kb

        # ── OVERVIEW ────────────────────────────────────────────────────────
        if "OVERVIEW" in intents and not any(
            entities[k] for k in ["categories","states","banks","devices","networks","tx_types","ages","months","days"]
        ):
            return self._overview()

        # ── FRAUD focused ────────────────────────────────────────────────────
        if "FRAUD" in intents:
            return self._fraud_report(entities)

        # ── FAILURE focused ──────────────────────────────────────────────────
        if "FAILURE" in intents:
            return self._failure_report(entities)

        # ── TREND / TIME ─────────────────────────────────────────────────────
        if "TREND" in intents:
            return self._trend_report(entities, raw_query)

        # ── RANK ─────────────────────────────────────────────────────────────
        if "RANK" in intents:
            return self._rank_report(entities, raw_query)

        # ── COMPARE ──────────────────────────────────────────────────────────
        if "COMPARE" in intents:
            return self._compare_report(entities, raw_query)

        # ── AMOUNT / VOLUME for a specific dimension ─────────────────────────
        if "AMOUNT" in intents or "VOLUME" in intents or "COUNT" in intents:
            return self._amount_report(entities, raw_query)

        # ── Specific entity lookup ────────────────────────────────────────────
        if any(entities[k] for k in ["categories","states","banks","devices","networks","tx_types","ages"]):
            return self._entity_deep_dive(entities)

        return self._overview()

    # ── Response builders ────────────────────────────────────────────────────

    def _overview(self) -> dict:
        kb = self.kb
        vol = self._fmt_inr(kb["total_volume_inr"])
        top_cat_by_vol = max(kb["by_category"].items(), key=lambda x: x[1]["total_volume"])[0]
        top_state      = max(kb["by_state"].items(), key=lambda x: x[1]["total_volume"])[0]
        highest_fraud_state = max(kb["by_state"].items(), key=lambda x: x[1]["fraud_rate_pct"])[0]
        return {
            "intent": "OVERVIEW",
            "answer": (
                f"The dataset covers {kb['total_transactions']:,} UPI transactions in 2024 "
                f"with a total volume of {vol}. Average transaction is ₹{kb['avg_amount']:,.2f}, "
                f"success rate is {kb['success_rate_pct']}%, and fraud rate is {kb['fraud_rate_pct']}% "
                f"({kb['fraud_total']} cases)."
            ),
            "stats": {
                "Total Transactions": f"{kb['total_transactions']:,}",
                "Total Volume": vol,
                "Avg Transaction": f"₹{kb['avg_amount']:,.2f}",
                "Median Transaction": f"₹{kb['median_amount']:,.0f}",
                "Max Transaction": f"₹{kb['max_amount']:,}",
                "Success Rate": f"{kb['success_rate_pct']}%",
                "Failed Transactions": f"{kb['failed_count']:,} ({kb['failed_rate_pct']}%)",
                "Fraud Cases": f"{kb['fraud_total']} ({kb['fraud_rate_pct']}%)",
                "Peak Hour": f"{kb['peak_hour']}:00 ({self._fmt_num(kb['by_hour'][str(kb['peak_hour'])]['count'])} txns)",
                "Top Category by Volume": top_cat_by_vol,
                "Top State by Volume": top_state,
                "Highest Fraud State": f"{highest_fraud_state} ({kb['by_state'][highest_fraud_state]['fraud_rate_pct']}%)",
            },
            "pattern": (
                f"Activity peaks at 7 PM with {kb['by_hour']['19']['count']:,} transactions. "
                f"Grocery dominates in count ({kb['by_category']['Grocery']['count']:,} txns) "
                f"but Shopping leads volume (₹{kb['by_category']['Shopping']['total_volume']/1e7:.2f} Cr). "
                f"Maharashtra is the busiest state with {self._fmt_inr(kb['by_state']['Maharashtra']['total_volume'])} volume."
            ),
            "recommendation": (
                "Focus fraud prevention on Karnataka and Rajasthan (highest fraud states) "
                "and Recharge transactions (0.239% fraud rate). "
                "Evening hours (6–8 PM) represent the highest-value window — "
                "prioritise uptime and support during this period."
            ),
            "confidence": 99,
            "entities_used": ["all"],
        }

    def _fraud_report(self, entities: dict) -> dict:
        kb = self.kb

        # If a specific dimension entity is mentioned, narrow to it
        section = None
        entity_name = None
        dim_key = None

        if entities["categories"]:
            dim_key, entity_name = "by_category", entities["categories"][0]
            section = kb["by_category"].get(entity_name)
        elif entities["states"]:
            dim_key, entity_name = "by_state", entities["states"][0]
            section = kb["by_state"].get(entity_name)
        elif entities["banks"]:
            dim_key, entity_name = "by_bank", entities["banks"][0]
            section = kb["by_bank"].get(entity_name)
        elif entities["devices"]:
            dim_key, entity_name = "by_device", entities["devices"][0]
            section = kb["by_device"].get(entity_name)
        elif entities["networks"]:
            dim_key, entity_name = "by_network", entities["networks"][0]
            section = kb["by_network"].get(entity_name)
        elif entities["tx_types"]:
            dim_key, entity_name = "by_tx_type", entities["tx_types"][0]
            section = kb["by_tx_type"].get(entity_name)
        elif entities["ages"]:
            dim_key, entity_name = "by_age", entities["ages"][0]
            section = kb["by_age"].get(entity_name)

        if section and entity_name:
            rate = section.get("fraud_rate_pct", 0)
            overall = kb["fraud_rate_pct"]
            diff_pct = round((rate - overall) / overall * 100, 1)
            direction = "above" if rate > overall else "below"
            return {
                "intent": "FRAUD",
                "answer": f"{entity_name} has a fraud rate of {rate}%, which is {abs(diff_pct)}% {direction} the overall average of {overall}%.",
                "stats": {
                    "Entity": entity_name,
                    "Fraud Rate": f"{rate}%",
                    "Overall Average": f"{overall}%",
                    "Relative Difference": f"{'+' if diff_pct>0 else ''}{diff_pct}%",
                    "Transaction Count": f"{section.get('count','-'):,}",
                },
                "pattern": (
                    f"{'High' if rate > overall else 'Low'} fraud rate in {entity_name}. "
                    f"Overall fraud count in dataset: {kb['fraud_total']} out of {kb['total_transactions']:,}."
                ),
                "recommendation": (
                    f"{'Increase monitoring and add OTP / biometric verification for ' + entity_name + ' transactions.' if rate > overall else entity_name + ' is relatively safe — maintain current controls.'}"
                ),
                "confidence": 95,
                "entities_used": [entity_name],
            }

        # No specific entity — return full fraud leaderboard
        fraud_by_state   = self._rank_by("by_state",    "fraud_rate_pct")
        fraud_by_cat     = self._rank_by("by_category", "fraud_rate_pct")
        fraud_by_bank    = self._rank_by("by_bank",     "fraud_rate_pct")
        fraud_by_network = self._rank_by("by_network",  "fraud_rate_pct")
        fraud_by_type    = self._rank_by("by_tx_type",  "fraud_rate_pct")
        fraud_by_age     = self._rank_by("by_age",      "fraud_rate_pct")

        top_state  = fraud_by_state[0]
        top_cat    = fraud_by_cat[0]
        top_bank   = fraud_by_bank[0]
        top_net    = fraud_by_network[0]
        top_type   = fraud_by_type[0]

        return {
            "intent": "FRAUD",
            "answer": (
                f"Overall fraud rate is {kb['fraud_rate_pct']}% ({kb['fraud_total']} cases). "
                f"Highest risk: {top_state[0]} state ({top_state[1]}%), "
                f"{top_cat[0]} category ({top_cat[1]}%), "
                f"{top_bank[0]} bank ({top_bank[1]}%), "
                f"{top_net[0]} network ({top_net[1]}%)."
            ),
            "stats": {
                "Total Fraud Cases": kb['fraud_total'],
                "Overall Rate": f"{kb['fraud_rate_pct']}%",
                "Riskiest State": f"{top_state[0]} ({top_state[1]}%)",
                "Riskiest Category": f"{top_cat[0]} ({top_cat[1]}%)",
                "Riskiest Bank": f"{top_bank[0]} ({top_bank[1]}%)",
                "Riskiest Network": f"{top_net[0]} ({top_net[1]}%)",
                "Riskiest Tx Type": f"{top_type[0]} ({top_type[1]}%)",
                "Riskiest Age Group": f"{fraud_by_age[0][0]} ({fraud_by_age[0][1]}%)",
                "Safest State": f"{fraud_by_state[-1][0]} ({fraud_by_state[-1][1]}%)",
                "Safest Network": f"{self._rank_by('by_network','fraud_rate_pct',reverse=False)[0][0]} ({self._rank_by('by_network','fraud_rate_pct',reverse=False)[0][1]}%)",
                "Fraud Avg Amount": f"₹{kb['fraud_analysis']['avg_amount']}",
                "Fraud Max Amount": f"₹{kb['fraud_analysis']['max_amount']}",
            },
            "pattern": (
                "WiFi network anomaly: 0.235% vs 0.184% on 5G (28% relative increase). "
                "Recharge transactions most vulnerable (0.239%). "
                "Youth (18-25) and seniors (56+) show elevated fraud exposure. "
                "3 AM has the highest hourly fraud rate (0.304%)."
            ),
            "recommendation": (
                "Priority actions: (1) Mandatory biometric for Recharge + WiFi transactions. "
                "(2) Karnataka/Rajasthan need region-specific fraud alerts. "
                "(3) Kotak Bank users require enhanced OTP flows. "
                "(4) Night-time (1-3 AM) monitoring needs strengthening."
            ),
            "confidence": 98,
            "entities_used": ["all"],
        }

    def _failure_report(self, entities: dict) -> dict:
        kb = self.kb
        fail_by_cat = self._rank_by("by_category", "fail_rate_pct")
        fail_by_dev = self._rank_by("by_device",   "fail_rate_pct")
        fail_by_type= self._rank_by("by_tx_type",  "fail_rate_pct")

        if entities["categories"]:
            cat = entities["categories"][0]
            d = kb["by_category"].get(cat, {})
            return {
                "intent": "FAILURE",
                "answer": f"{cat} has a failure rate of {d.get('fail_rate_pct','N/A')}% out of {d.get('count',0):,} transactions.",
                "stats": {"Category": cat, "Failure Rate": f"{d.get('fail_rate_pct')}%", "Count": f"{d.get('count'):,}"},
                "pattern": f"Overall failure rate is {kb['failed_rate_pct']}%. {cat} is {'above' if d.get('fail_rate_pct',0) > kb['failed_rate_pct'] else 'below'} average.",
                "recommendation": f"Investigate payment gateway issues specific to {cat} merchant integrations.",
                "confidence": 93, "entities_used": [cat],
            }

        return {
            "intent": "FAILURE",
            "answer": f"Overall failure rate is {kb['failed_rate_pct']}% ({kb['failed_count']:,} transactions). Education has the highest at {fail_by_cat[0][1]}%.",
            "stats": {
                "Total Failed": f"{kb['failed_count']:,}",
                "Failure Rate": f"{kb['failed_rate_pct']}%",
                **{f"Fail #{i+1}": f"{n} ({v}%)" for i,(n,v) in enumerate(fail_by_cat[:3])},
                "Worst Device": f"{fail_by_dev[0][0]} ({fail_by_dev[0][1]}%)",
                "Worst Tx Type": f"{fail_by_type[0][0]} ({fail_by_type[0][1]}%)",
            },
            "pattern": "Education has consistently high failure + average amounts, suggesting bank timeout issues on large-value UPI transactions.",
            "recommendation": "Implement retry logic for Education and Shopping categories. Investigate Web browser UPI flows (highest fail rate 5.15%).",
            "confidence": 95, "entities_used": ["all"],
        }

    def _amount_report(self, entities: dict, raw_query: str) -> dict:
        kb = self.kb
        metric = entities.get("metric") or "avg"
        q = raw_query.lower()

        # Single entity lookup
        for dim_key, ent_list in [
            ("by_category", entities["categories"]),
            ("by_state",    entities["states"]),
            ("by_bank",     entities["banks"]),
            ("by_device",   entities["devices"]),
            ("by_network",  entities["networks"]),
            ("by_tx_type",  entities["tx_types"]),
            ("by_age",      entities["ages"]),
        ]:
            if ent_list:
                name = ent_list[0]
                section = kb.get(dim_key, {}).get(name, {})
                val = section.get(metric) or section.get("avg")
                return {
                    "intent": "AMOUNT",
                    "answer": f"The {metric.replace('_',' ')} transaction amount for {name} is {self._fmt_inr(val)}.",
                    "stats": {
                        "Entity": name, "Metric": metric,
                        "Value": self._fmt_inr(val),
                        "Count": f"{section.get('count','-'):,}",
                        "Total Volume": self._fmt_inr(section.get("total_volume", 0)),
                    },
                    "pattern": f"Overall dataset avg is ₹{kb['avg_amount']:,}. {name} is {'above' if val > kb['avg_amount'] else 'below'} average.",
                    "recommendation": f"{'Monitor high-value ' + name + ' transactions closely.' if val > kb['avg_amount']*1.5 else 'Standard monitoring sufficient for ' + name + '.'}",
                    "confidence": 96, "entities_used": [name],
                }

        # Top 10 transactions
        if re.search(r"top\s*10|largest|biggest|highest\s+transaction", q):
            rows = "\n".join([f"  #{i+1}  ₹{t['amount']:,}  |  {t['category']}  |  {t['state']}  |  {t['status']}"
                              for i,t in enumerate(kb["top10_transactions"])])
            return {
                "intent": "AMOUNT",
                "answer": f"The highest individual transaction is ₹{kb['top10_transactions'][0]['amount']:,} (Education, Telangana, FAILED).\n\nTop 10:\n{rows}",
                "stats": {"Max": f"₹{kb['max_amount']:,}", "Min": f"₹{kb['min_amount']}", "Median": f"₹{kb['median_amount']:,}",
                          "p90": f"₹{kb['p90_amount']:,}", "p99": f"₹{kb['p99_amount']:,}"},
                "pattern": "8 of top 10 transactions are in Education category — consistent with high tuition fee payments via UPI.",
                "recommendation": "Add transaction-level review for any single UPI payment above ₹25,000.",
                "confidence": 99, "entities_used": ["top10"],
            }

        # Distribution
        if re.search(r"distribut|bucket|range|bracket", q):
            d = kb["amount_distribution"]
            total = sum(d.values())
            return {
                "intent": "AMOUNT",
                "answer": f"Most transactions (37.3%) are in the ₹100–500 range. Only {d['above_10000']:,} transactions exceed ₹10,000.",
                "stats": {k.replace("_"," → ₹"): f"{v:,} ({v/total*100:.1f}%)" for k,v in d.items()},
                "pattern": "The distribution is heavily right-skewed — median ₹629 vs mean ₹1,312 — driven by a few large Education/Shopping transactions.",
                "recommendation": "Design tiered UX: instant approval for <₹500, OTP for ₹500-5K, biometric for >₹5K.",
                "confidence": 97, "entities_used": ["distribution"],
            }

        # Generic amount overview
        return {
            "intent": "AMOUNT",
            "answer": f"Average transaction amount is ₹{kb['avg_amount']:,}. Median is ₹{kb['median_amount']:,}, max is ₹{kb['max_amount']:,}.",
            "stats": {"Mean": f"₹{kb['avg_amount']:,}", "Median": f"₹{kb['median_amount']:,}",
                      "Max": f"₹{kb['max_amount']:,}", "Min": f"₹{kb['min_amount']:,}",
                      "Std Dev": f"₹{kb['std_amount']:,}", "p90": f"₹{kb['p90_amount']:,}",
                      "p95": f"₹{kb['p95_amount']:,}", "p99": f"₹{kb['p99_amount']:,}"},
            "pattern": "High standard deviation (₹1,848) indicates a wide range. The gap between median (₹629) and mean (₹1,312) signals outlier high-value transactions.",
            "recommendation": "Segment users into low-value (<₹500) and high-value (>₹5K) cohorts for tailored experiences and risk controls.",
            "confidence": 95, "entities_used": ["global"],
        }

    def _volume_report(self, entities: dict) -> dict:
        kb = self.kb
        top_vols = self._rank_by("by_category", "total_volume")
        return {
            "intent": "VOLUME",
            "answer": f"Total UPI volume in 2024 is {self._fmt_inr(kb['total_volume_inr'])}. Shopping leads at {self._fmt_inr(kb['by_category']['Shopping']['total_volume'])}.",
            "stats": {cat: self._fmt_inr(vol) for cat,vol in top_vols},
            "pattern": "Shopping has the highest volume despite being #3 in transaction count — average ₹2,573 per transaction drives this.",
            "recommendation": "Invest in Shopping category merchant partnerships for maximum volume growth.",
            "confidence": 97, "entities_used": ["by_category"],
        }

    def _trend_report(self, entities: dict, raw_query: str) -> dict:
        kb = self.kb
        q = raw_query.lower()

        # Monthly trend
        if re.search(r"month|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec", q) or entities["months"]:
            months = kb["by_month"]
            top_fraud_month = max(months.items(), key=lambda x: x[1]["fraud_rate_pct"])[0]
            top_vol_month   = max(months.items(), key=lambda x: x[1]["total_volume"])[0]
            return {
                "intent": "TREND",
                "answer": f"Volume is stable across months (~₹26-28Cr/month). July had the highest fraud rate ({months['July']['fraud_rate_pct']}%) and {top_vol_month} had the highest volume ({self._fmt_inr(months[top_vol_month]['total_volume'])}).",
                "stats": {m: f"{self._fmt_inr(d['total_volume'])} | fraud {d['fraud_rate_pct']}%" for m,d in months.items()},
                "pattern": "Volume is consistent year-round with no major seasonal spike. Fraud peaks in July (0.245%) and drops in June (0.145%) — possibly linked to tax/admission season anomalies.",
                "recommendation": "Run fraud alert campaigns in Q1 (Jan-Mar) and July when fraud rates are highest.",
                "confidence": 93, "entities_used": ["by_month"],
            }

        # Hourly trend
        if re.search(r"hour|peak|time|when|busiest|am|pm", q):
            hours = kb["by_hour"]
            peak = max(hours.items(), key=lambda x: x[1]["count"])
            quiet = min(hours.items(), key=lambda x: x[1]["count"])
            high_fraud_hour = max(hours.items(), key=lambda x: x[1]["fraud_rate_pct"])
            return {
                "intent": "TREND",
                "answer": f"Peak activity is at {peak[0]}:00 ({peak[1]['count']:,} transactions). Quietest at {quiet[0]}:00. Highest fraud hour: {high_fraud_hour[0]}:00 ({high_fraud_hour[1]['fraud_rate_pct']}%).",
                "stats": {f"{h}:00": f"{d['count']:,} txns | fraud {d['fraud_rate_pct']}%" for h,d in hours.items()},
                "pattern": "Evening surge from 17:00–19:00 captures the highest volume. Late night (1-3 AM) has small volume but very high fraud rates (0.267–0.304%).",
                "recommendation": "Scale server capacity for 17:00–21:00. Deploy enhanced fraud scoring for 1–4 AM transactions.",
                "confidence": 97, "entities_used": ["by_hour"],
            }

        # Daily trend
        if re.search(r"day|week|monday|tuesday|weekend|weekday", q):
            days = kb["by_day"]
            top_day = max(days.items(), key=lambda x: x[1]["count"])[0]
            return {
                "intent": "TREND",
                "answer": f"Transaction volume is consistent across days. {top_day} has the most transactions. Weekdays average slightly more volume than weekends.",
                "stats": {
                    **{d: f"{v['count']:,} txns | fraud {v['fraud_rate_pct']}%" for d,v in days.items()},
                    "Weekend avg": f"₹{kb['weekend']['avg']} | fraud {kb['weekend']['fraud_rate_pct']}%",
                    "Weekday avg": f"₹{kb['weekday']['avg']} | fraud {kb['weekday']['fraud_rate_pct']}%",
                },
                "pattern": "Sundays have slightly higher fraud (0.208%). Tuesdays are the safest day (0.163%). Weekend volume is 28.5% of total.",
                "recommendation": "Run targeted promotions on low-fraud days (Tuesday, Friday) to grow quality volume.",
                "confidence": 90, "entities_used": ["by_day"],
            }

        # Generic trend
        return self._overview()

    def _rank_report(self, entities: dict, raw_query: str) -> dict:
        kb = self.kb
        q = raw_query.lower()
        is_fraud  = "fraud" in q
        is_vol    = re.search(r"volume|total|sum", q)
        is_count  = re.search(r"count|number|transactions", q)
        is_amount = re.search(r"amount|avg|average|spend", q)
        reverse   = not re.search(r"lowest|safest|least|worst performance|minimum", q)

        metric = "fraud_rate_pct" if is_fraud else ("total_volume" if is_vol else ("count" if is_count else "avg"))

        # Determine dimension to rank
        if re.search(r"state|region|city", q):
            ranked = self._rank_by("by_state", metric, top_n=10, reverse=reverse)
            dim = "state"
        elif re.search(r"categor|merchant", q):
            ranked = self._rank_by("by_category", metric, top_n=10, reverse=reverse)
            dim = "merchant category"
        elif re.search(r"bank", q):
            ranked = self._rank_by("by_bank", metric, top_n=8, reverse=reverse)
            dim = "bank"
        elif re.search(r"device|android|ios|web", q):
            ranked = self._rank_by("by_device", metric, top_n=3, reverse=reverse)
            dim = "device"
        elif re.search(r"network|4g|5g|wifi|3g", q):
            ranked = self._rank_by("by_network", metric, top_n=4, reverse=reverse)
            dim = "network"
        elif re.search(r"age|group|youth|senior", q):
            ranked = self._rank_by("by_age", metric, top_n=5, reverse=reverse)
            dim = "age group"
        elif re.search(r"type|p2p|p2m|recharge|bill", q):
            ranked = self._rank_by("by_tx_type", metric, top_n=4, reverse=reverse)
            dim = "transaction type"
        else:
            ranked = self._rank_by("by_category", metric, top_n=10, reverse=reverse)
            dim = "merchant category"

        label = metric.replace("_pct","").replace("_"," ").title()
        unit  = "%" if "rate" in metric else ("" if "count" in metric else "")
        fmt_val = lambda v: f"{v}%" if "rate" in metric else (self._fmt_inr(v) if "volume" in metric else (f"₹{v:,.0f}" if "avg" in metric else f"{v:,}"))

        rows = "\n".join([f"  #{i+1}  {n}  —  {fmt_val(v)}" for i,(n,v) in enumerate(ranked)])
        top_name, top_val = ranked[0]

        return {
            "intent": "RANK",
            "answer": f"Ranking by {label} across {dim}:\n{rows}",
            "stats": {f"#{i+1} {n}": fmt_val(v) for i,(n,v) in enumerate(ranked)},
            "pattern": f"{top_name} leads with {fmt_val(top_val)} — {'significantly above' if len(ranked)>1 and top_val > ranked[1][1]*1.1 else 'slightly above'} #2 ({ranked[1][0] if len(ranked)>1 else 'N/A'}).",
            "recommendation": f"Focus strategy on {top_name} for {'fraud mitigation' if is_fraud else 'growth opportunities'}.",
            "confidence": 94,
            "entities_used": [dim],
        }

    def _compare_report(self, entities: dict, raw_query: str) -> dict:
        kb = self.kb
        q = raw_query.lower()

        # Compare devices
        if re.search(r"device|android|ios|web", q):
            devs = kb["by_device"]
            return {
                "intent": "COMPARE",
                "answer": "Device comparison: Android leads in volume (₹24.7Cr), iOS has the lowest fraud rate (0.181%), Web has the highest failure rate (5.15%).",
                "stats": {d: f"avg ₹{v['avg']} | fraud {v['fraud_rate_pct']}% | fail {v['fail_rate_pct']}% | count {v['count']:,}" for d,v in devs.items()},
                "pattern": "iOS users transact slightly less frequently but have better fraud and failure outcomes. Web is the least reliable channel.",
                "recommendation": "Promote iOS app for premium/high-value users. Investigate Web UPI flow for reliability issues.",
                "confidence": 96, "entities_used": list(devs.keys()),
            }

        # Compare tx types
        if re.search(r"p2p|p2m|recharge|bill|payment|type", q):
            types = kb["by_tx_type"]
            return {
                "intent": "COMPARE",
                "answer": "P2P dominates in count (112,445) and volume (₹14.7Cr). Recharge has the highest fraud rate (0.239%).",
                "stats": {t: f"count {v['count']:,} | avg ₹{v['avg']} | fraud {v['fraud_rate_pct']}%" for t,v in types.items()},
                "pattern": "Recharge is the smallest but most fraud-prone category. P2M has the highest average amount (₹1,320).",
                "recommendation": "Add OTP step for all Recharge transactions. Monitor P2P high-value transactions (avg ₹1,309 with highest count).",
                "confidence": 95, "entities_used": list(types.keys()),
            }

        # Compare networks
        if re.search(r"network|4g|5g|wifi|3g", q):
            nets = kb["by_network"]
            return {
                "intent": "COMPARE",
                "answer": "4G dominates (149,813 txns). WiFi has the highest fraud rate (0.235%), 5G has the lowest (0.184%).",
                "stats": {n: f"count {v['count']:,} | avg ₹{v['avg']} | fraud {v['fraud_rate_pct']}%" for n,v in nets.items()},
                "pattern": "WiFi fraud anomaly (0.235%) likely caused by public hotspot usage. 5G users show best security behaviour.",
                "recommendation": "Add mandatory re-authentication for transactions initiated over public WiFi.",
                "confidence": 96, "entities_used": list(nets.keys()),
            }

        # Generic comparison
        return self._rank_report(entities, raw_query)

    def _entity_deep_dive(self, entities: dict) -> dict:
        kb = self.kb
        stats = {}

        # Category deep dive
        if entities["categories"]:
            cat = entities["categories"][0]
            d = kb["by_category"].get(cat, {})
            # Cross-device avg
            dev_avgs = {dev: kb["by_device"][dev]["by_category_avg"].get(cat) for dev in kb["by_device"]}
            return {
                "intent": "ENTITY_DEEP_DIVE",
                "answer": f"Deep dive into {cat}: {d.get('count',0):,} transactions, avg ₹{d.get('avg')}, volume {self._fmt_inr(d.get('total_volume',0))}, fraud {d.get('fraud_rate_pct')}%, failure {d.get('fail_rate_pct')}%.",
                "stats": {
                    "Count": f"{d.get('count',0):,}",
                    "Total Volume": self._fmt_inr(d.get("total_volume",0)),
                    "Avg Amount": f"₹{d.get('avg')}",
                    "Median": f"₹{d.get('median')}",
                    "Max": f"₹{d.get('max'):,}",
                    "Min": f"₹{d.get('min')}",
                    "Fraud Rate": f"{d.get('fraud_rate_pct')}%",
                    "Fail Rate": f"{d.get('fail_rate_pct')}%",
                    "Android Avg": f"₹{dev_avgs.get('Android')}",
                    "iOS Avg": f"₹{dev_avgs.get('iOS')}",
                    "Web Avg": f"₹{dev_avgs.get('Web')}",
                },
                "pattern": f"{cat} avg (₹{d.get('avg')}) is {'well above' if d.get('avg',0)>kb['avg_amount']*1.5 else 'above' if d.get('avg',0)>kb['avg_amount'] else 'below'} the overall avg of ₹{kb['avg_amount']}.",
                "recommendation": f"{'High-value alert thresholds recommended for ' + cat if d.get('avg',0)>2000 else 'Standard controls adequate for ' + cat}.",
                "confidence": 96, "entities_used": [cat],
            }

        # State deep dive
        if entities["states"]:
            state = entities["states"][0]
            d = kb["by_state"].get(state, {})
            return {
                "intent": "ENTITY_DEEP_DIVE",
                "answer": f"{state}: {d.get('count',0):,} transactions, avg ₹{d.get('avg')}, volume {self._fmt_inr(d.get('total_volume',0))}, fraud rate {d.get('fraud_rate_pct')}%.",
                "stats": {
                    "State": state,
                    "Transaction Count": f"{d.get('count',0):,}",
                    "Total Volume": self._fmt_inr(d.get("total_volume",0)),
                    "Avg Amount": f"₹{d.get('avg')}",
                    "Fraud Rate": f"{d.get('fraud_rate_pct')}%",
                    "National Avg Fraud": f"{kb['fraud_rate_pct']}%",
                },
                "pattern": f"{state} is {'a high-fraud zone' if d.get('fraud_rate_pct',0) > kb['fraud_rate_pct'] else 'below national fraud average'}.",
                "recommendation": f"{'Deploy additional fraud detection agents in ' + state if d.get('fraud_rate_pct',0) > 0.2 else state + ' is relatively low-risk — standard monitoring adequate.'}",
                "confidence": 95, "entities_used": [state],
            }

        return self._overview()


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4: MAIN MODEL CLASS
# ══════════════════════════════════════════════════════════════════════════════

class InsightXModel:
    """
    InsightX AI — Conversational BI Model.
    Trained on upi_transactions_2024.csv (250,000 rows, 17 columns).

    Usage:
        model = InsightXModel()
        result = model.query("Which state has the highest fraud rate?")
        print(result['answer'])

    To retrain from CSV:
        model = InsightXModel(csv_path="path/to/upi_transactions_2024.csv")
    """

    VERSION = "1.0.0"

    def __init__(self, csv_path: Optional[str] = None):
        if csv_path:
            print(f"[InsightX] Training from CSV: {csv_path} ...")
            self.kb = self._train_from_csv(csv_path)
            print(f"[InsightX] Training complete. {self.kb['total_transactions']:,} rows processed.")
        else:
            self.kb = KNOWLEDGE_BASE
            print(f"[InsightX] Loaded embedded knowledge base. ({self.kb['total_transactions']:,} transactions)")

        self.nlp = NLPEngine()
        self.responder = ResponseGenerator(self.kb)
        self._history: list[dict] = []

    def _train_from_csv(self, path: str) -> dict:
        """Re-compute the entire knowledge base live from a CSV file."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for CSV training. Run: pip install pandas")

        df = pd.read_csv(path)
        df['month'] = pd.to_datetime(df['timestamp']).dt.month
        MONTH_NAMES = {1:'January',2:'February',3:'March',4:'April',5:'May',6:'June',
                       7:'July',8:'August',9:'September',10:'October',11:'November',12:'December'}

        def safe_dict(series):
            return {str(k): (int(v) if isinstance(v, (int,)) else float(round(v,3)) if isinstance(v, float) else v)
                    for k,v in series.items()}

        kb = {
            "meta": {"source_file": path, "rows": len(df), "trained_by": "InsightXModel.train()"},
            "total_transactions": len(df),
            "total_volume_inr": int(df['amount (INR)'].sum()),
            "avg_amount": round(float(df['amount (INR)'].mean()), 2),
            "median_amount": float(df['amount (INR)'].median()),
            "max_amount": int(df['amount (INR)'].max()),
            "min_amount": int(df['amount (INR)'].min()),
            "std_amount": round(float(df['amount (INR)'].std()), 2),
            "fraud_total": int(df['fraud_flag'].sum()),
            "fraud_rate_pct": round(float(df['fraud_flag'].mean() * 100), 3),
            "success_count": int((df['transaction_status']=='SUCCESS').sum()),
            "failed_count": int((df['transaction_status']=='FAILED').sum()),
            "success_rate_pct": round(float((df['transaction_status']=='SUCCESS').mean()*100), 2),
            "failed_rate_pct": round(float((df['transaction_status']=='FAILED').mean()*100), 2),
            "peak_hour": int(df.groupby('hour_of_day').size().idxmax()),
            "lowest_hour": int(df.groupby('hour_of_day').size().idxmin()),
            "weekend_txns": int(df['is_weekend'].sum()),
            "weekday_txns": int((df['is_weekend']==0).sum()),
        }
        for p in [10,25,50,75,90,95,99]:
            kb[f'p{p}_amount'] = float(df['amount (INR)'].quantile(p/100))

        def build_dim(group_col, agg_device=False):
            out = {}
            for name, g in df.groupby(group_col):
                row = {
                    'count': int(len(g)),
                    'total_volume': int(g['amount (INR)'].sum()),
                    'avg': round(float(g['amount (INR)'].mean()), 2),
                    'median': float(g['amount (INR)'].median()),
                    'max': int(g['amount (INR)'].max()),
                    'min': int(g['amount (INR)'].min()),
                    'fraud_count': int(g['fraud_flag'].sum()),
                    'fraud_rate_pct': round(float(g['fraud_flag'].mean()*100), 3),
                    'fail_rate_pct': round(float((g['transaction_status']=='FAILED').mean()*100), 2),
                }
                if agg_device:
                    row['by_category_avg'] = {cat: round(float(g[g['merchant_category']==cat]['amount (INR)'].mean()),2)
                                              for cat in df['merchant_category'].unique() if len(g[g['merchant_category']==cat]) > 0}
                out[str(name)] = row
            return out

        kb['by_category'] = build_dim('merchant_category')
        kb['by_state']    = build_dim('sender_state')
        kb['by_bank']     = build_dim('sender_bank')
        kb['by_device']   = build_dim('device_type', agg_device=True)
        kb['by_network']  = build_dim('network_type')
        kb['by_tx_type']  = build_dim('transaction type')
        kb['by_age']      = build_dim('sender_age_group')
        kb['by_day']      = build_dim('day_of_week')
        kb['by_hour']     = build_dim('hour_of_day')

        kb['by_month'] = {}
        for m, g in df.groupby('month'):
            kb['by_month'][MONTH_NAMES[m]] = {
                'count': int(len(g)), 'total_volume': int(g['amount (INR)'].sum()),
                'avg': round(float(g['amount (INR)'].mean()), 2),
                'fraud_count': int(g['fraud_flag'].sum()),
                'fraud_rate_pct': round(float(g['fraud_flag'].mean()*100), 3),
            }

        for key, is_wknd in [('weekend',1),('weekday',0)]:
            sub = df[df['is_weekend']==is_wknd]
            kb[key] = {'count': int(len(sub)), 'avg': round(float(sub['amount (INR)'].mean()),2),
                       'total_volume': int(sub['amount (INR)'].sum()),
                       'fraud_rate_pct': round(float(sub['fraud_flag'].mean()*100),3)}

        d = df['amount (INR)']
        kb['amount_distribution'] = {
            'under_100': int((d<100).sum()), '100_to_500': int(((d>=100)&(d<500)).sum()),
            '500_to_1000': int(((d>=500)&(d<1000)).sum()), '1000_to_5000': int(((d>=1000)&(d<5000)).sum()),
            '5000_to_10000': int(((d>=5000)&(d<10000)).sum()), 'above_10000': int((d>=10000).sum()),
        }

        top10 = df.nlargest(10,'amount (INR)')[['amount (INR)','merchant_category','transaction type',
                                                 'sender_state','device_type','network_type',
                                                 'transaction_status','fraud_flag','hour_of_day','day_of_week']]
        kb['top10_transactions'] = [
            {'amount': int(r['amount (INR)']), 'category': r['merchant_category'], 'type': r['transaction type'],
             'state': r['sender_state'], 'device': r['device_type'], 'network': r['network_type'],
             'status': r['transaction_status'], 'fraud': int(r['fraud_flag']),
             'hour': int(r['hour_of_day']), 'day': r['day_of_week']}
            for _, r in top10.iterrows()
        ]

        fdf = df[df['fraud_flag']==1]
        kb['fraud_analysis'] = {
            'total': int(len(fdf)),
            'avg_amount': round(float(fdf['amount (INR)'].mean()), 2),
            'max_amount': int(fdf['amount (INR)'].max()),
            'min_amount': int(fdf['amount (INR)'].min()),
            'top_category': fdf['merchant_category'].value_counts().idxmax(),
            'top_state': fdf['sender_state'].value_counts().idxmax(),
            'top_bank': fdf['sender_bank'].value_counts().idxmax(),
            'top_device': fdf['device_type'].value_counts().idxmax(),
            'top_hour': int(fdf['hour_of_day'].value_counts().idxmax()),
        }
        return kb

    def query(self, question: str) -> dict:
        """
        Process a natural language query and return a structured response.

        Args:
            question: Natural language business question about UPI transactions.

        Returns:
            dict with keys: intent, answer, stats, pattern, recommendation, confidence, entities_used
        """
        intents  = self.nlp.classify_intent(question)
        entities = self.nlp.extract_entities(question)
        response = self.responder.generate(intents, entities, question)

        # Store conversation history
        self._history.append({"question": question, "intents": intents, "response": response})

        return response

    def ask(self, question: str, verbose: bool = True) -> str:
        """Convenience method — returns formatted string output."""
        r = self.query(question)
        if not verbose:
            return r["answer"]

        lines = [
            f"\n{'━'*60}",
            f"🔍 QUERY      : {question}",
            f"🎯 INTENT     : {r.get('intent','–')}",
            f"{'─'*60}",
            f"✅ ANSWER\n{r.get('answer','')}",
            f"{'─'*60}",
            f"📊 STATISTICS",
        ]
        for k, v in (r.get("stats") or {}).items():
            lines.append(f"   {k:<28} {v}")

        lines += [
            f"{'─'*60}",
            f"📈 PATTERN\n{r.get('pattern','')}",
            f"{'─'*60}",
            f"💡 RECOMMENDATION\n{r.get('recommendation','')}",
            f"{'─'*60}",
            f"🎯 CONFIDENCE : {r.get('confidence','–')}%",
            f"{'━'*60}",
        ]
        return "\n".join(lines)

    def save_kb(self, path: str = "insightx_kb.json"):
        """Export the knowledge base to JSON."""
        with open(path, "w") as f:
            json.dump(self.kb, f, indent=2)
        print(f"[InsightX] Knowledge base saved to {path}")

    def history(self) -> list:
        """Return conversation history."""
        return self._history

    def summary(self) -> str:
        """One-line dataset summary."""
        kb = self.kb
        return (f"InsightX Model v{self.VERSION} | "
                f"{kb['total_transactions']:,} transactions | "
                f"₹{kb['total_volume_inr']/1e7:.2f} Cr total | "
                f"{kb['fraud_rate_pct']}% fraud | "
                f"{kb['success_rate_pct']}% success")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5: INTERACTIVE REPL
# ══════════════════════════════════════════════════════════════════════════════

SAMPLE_QUERIES = [
    "Give me an overview of the dataset",
    "Which state has the highest fraud rate?",
    "What is the average transaction amount for Shopping?",
    "Compare Android vs iOS vs Web",
    "Show fraud rate by merchant category",
    "What are the peak transaction hours?",
    "Which bank has the lowest fraud rate?",
    "How many transactions are above ₹10,000?",
    "Show monthly fraud trends",
    "Compare P2P vs P2M transaction patterns",
    "What is the transaction amount distribution?",
    "Show top 10 largest transactions",
    "Which age group spends the most?",
    "What is the WiFi network fraud anomaly?",
    "Rank states by transaction volume",
    "What is the failure rate by category?",
    "Show me fraud analysis",
    "What is the Education category average amount?",
]

def run_repl():
    print("\n" + "═"*60)
    print("  InsightX AI — Conversational BI Model")
    print("  Trained on: upi_transactions_2024.csv (250,000 rows)")
    print("  Type 'demo' for sample queries | 'exit' to quit")
    print("═"*60)

    model = InsightXModel()
    print(f"\n  {model.summary()}\n")

    while True:
        try:
            q = input("❯ ").strip()
            if not q:
                continue
            if q.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break
            if q.lower() == "demo":
                print("\nSample queries:")
                for i, sq in enumerate(SAMPLE_QUERIES, 1):
                    print(f"  {i:>2}. {sq}")
                print()
                continue
            if q.lower() == "history":
                for i, h in enumerate(model.history(), 1):
                    print(f"  {i}. {h['question']}")
                continue
            if q.lower() == "save":
                model.save_kb()
                continue

            print(model.ask(q))

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # CLI mode: python insightx_model.py "your question here"
        # Or: python insightx_model.py --train upi_transactions_2024.csv "question"
        args = sys.argv[1:]
        csv_path = None
        if args[0] == "--train" and len(args) >= 2:
            csv_path = args[1]
            args = args[2:]

        model = InsightXModel(csv_path=csv_path)
        if args:
            print(model.ask(" ".join(args)))
        else:
            run_repl()
    else:
        run_repl()
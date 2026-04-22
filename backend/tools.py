from sqlalchemy.orm import Session
from models import Transaction, Budget, Goal, RecurringExpense
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from collections import defaultdict
import statistics

CATEGORIES = {
    "Food & Dining": ["swiggy", "zomato", "uber eats", "restaurant", "cafe", "biryani", "pizza", "burger", "dominos", "kfc", "mcdonalds", "starbucks"],
    "Transport": ["uber", "ola", "rapido", "irctc", "metro", "petrol", "fuel", "auto", "bus", "flight", "indigo", "air india"],
    "Utilities": ["electricity", "bescom", "tneb", "water", "gas", "internet", "broadband", "airtel", "jio"],
    "Shopping": ["amazon", "flipkart", "myntra", "ajio", "zepto", "blinkit", "instamart", "meesho", "nykaa"],
    "Entertainment": ["netflix", "hotstar", "spotify", "youtube", "prime video", "cinema", "pvr", "inox", "bookmyshow"],
    "Healthcare": ["pharmacy", "hospital", "clinic", "apollo", "medplus", "diagnostic", "lab", "doctor", "medicine"],
    "Education": ["udemy", "coursera", "book", "course", "training", "school", "college", "byju"],
    "Subscriptions": ["subscription", "renewal", "monthly plan", "annual plan", "premium"],
    "Travel": ["oyo", "makemytrip", "goibibo", "booking.com", "airbnb"],
    "Groceries": ["bigbasket", "dmart", "reliance fresh", "more supermarket", "vegetables", "supermarket"],
}

def categorise(merchant: str, description: str = "") -> tuple:
    text = (merchant + " " + description).lower()
    for category, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in text:
                return category, 0.9
    return "Miscellaneous", 0.4

def get_period_dates(period: str) -> tuple:
    today = date.today()
    if period == "today":
        return today, today
    elif period == "this_week":
        return today - timedelta(days=today.weekday()), today
    elif period == "this_month":
        return today.replace(day=1), today
    elif period == "last_month":
        first = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last = today.replace(day=1) - timedelta(days=1)
        return first, last
    elif period == "last_3_months":
        return (today - relativedelta(months=3)).replace(day=1), today
    elif period == "this_year":
        return today.replace(month=1, day=1), today
    return today.replace(day=1), today

def spending_summary(db: Session, period: str = "this_month") -> dict:
    start, end = get_period_dates(period)
    txns = db.query(Transaction).filter(
        Transaction.deleted == False,
        Transaction.date >= start,
        Transaction.date <= end
    ).all()
    by_category = defaultdict(float)
    by_merchant = defaultdict(float)
    for t in txns:
        by_category[t.category] += t.amount
        by_merchant[t.merchant] += t.amount
    top_merchants = sorted(by_merchant.items(), key=lambda x: x[1], reverse=True)[:10]
    return {
        "period": period, "start": str(start), "end": str(end),
        "total": round(sum(by_category.values()), 2),
        "transaction_count": len(txns),
        "by_category": {k: round(v, 2) for k, v in sorted(by_category.items(), key=lambda x: x[1], reverse=True)},
        "top_merchants": [{"merchant": m, "amount": round(a, 2)} for m, a in top_merchants],
    }

def monthly_trend(db: Session, months: int = 6) -> list:
    today = date.today()
    result = []
    for i in range(months - 1, -1, -1):
        d = today - relativedelta(months=i)
        start = d.replace(day=1)
        end = (start + relativedelta(months=1)) - timedelta(days=1)
        txns = db.query(Transaction).filter(
            Transaction.deleted == False,
            Transaction.date >= start, Transaction.date <= end
        ).all()
        by_cat = defaultdict(float)
        for t in txns:
            by_cat[t.category] += t.amount
        result.append({
            "month": start.strftime("%b %Y"),
            "total": round(sum(by_cat.values()), 2),
            "by_category": {k: round(v, 2) for k, v in by_cat.items()}
        })
    return result

def budget_status(db: Session) -> list:
    budgets = db.query(Budget).all()
    today = date.today()
    month_start = today.replace(day=1)
    result = []
    for b in budgets:
        txns = db.query(Transaction).filter(
            Transaction.deleted == False,
            Transaction.category == b.category,
            Transaction.date >= month_start, Transaction.date <= today
        ).all()
        total_spent = sum(t.amount for t in txns)
        pct = round(total_spent / b.monthly_limit, 3) if b.monthly_limit > 0 else 0
        result.append({
            "id": b.id, "category": b.category, "limit": b.monthly_limit,
            "spent": round(total_spent, 2),
            "remaining": round(max(0, b.monthly_limit - total_spent), 2),
            "utilisation_pct": min(pct, 1.0),
            "alert": pct >= b.alert_threshold,
            "over_budget": pct > 1.0,
        })
    return result

def detect_anomalies(db: Session) -> list:
    ninety_days_ago = date.today() - timedelta(days=90)
    txns = db.query(Transaction).filter(
        Transaction.deleted == False, Transaction.date >= ninety_days_ago
    ).all()
    by_category = defaultdict(list)
    for t in txns:
        by_category[t.category].append(t)
    anomalies = []
    for cat, items in by_category.items():
        if len(items) < 5:
            continue
        amounts = [t.amount for t in items]
        mean = statistics.mean(amounts)
        stdev = statistics.stdev(amounts) if len(amounts) > 1 else 0
        if stdev == 0:
            continue
        for t in items:
            z = (t.amount - mean) / stdev
            if z > 2.5:
                anomalies.append({
                    "id": t.id, "merchant": t.merchant, "amount": t.amount,
                    "date": str(t.date), "category": t.category,
                    "z_score": round(z, 2),
                    "message": f"Unusually high: {t.merchant} ₹{t.amount:,.0f} vs avg ₹{mean:,.0f}"
                })
    return sorted(anomalies, key=lambda x: x["z_score"], reverse=True)

def cash_flow_forecast(db: Session, days: int = 30) -> dict:
    today = date.today()
    end = today + timedelta(days=days)
    recurring = db.query(RecurringExpense).filter(
        RecurringExpense.is_active == True,
        RecurringExpense.next_expected <= end
    ).all()
    upcoming = []
    projected_outflow = 0.0
    for r in recurring:
        upcoming.append({
            "merchant": r.merchant, "amount": r.avg_amount,
            "expected_date": str(r.next_expected), "category": r.category
        })
        projected_outflow += r.avg_amount
    avg_monthly = _avg_monthly_spend(db)
    variable = (avg_monthly / 30) * days
    total = projected_outflow + variable
    return {
        "forecast_days": days, "projected_outflow": round(total, 2),
        "recurring_outflow": round(projected_outflow, 2),
        "variable_outflow": round(variable, 2),
        "upcoming_bills": sorted(upcoming, key=lambda x: x["expected_date"]),
        "risk_level": "HIGH" if total > 30000 else "MEDIUM" if total > 15000 else "LOW",
    }

def _avg_monthly_spend(db: Session) -> float:
    three_months_ago = (date.today() - relativedelta(months=3)).replace(day=1)
    txns = db.query(Transaction).filter(
        Transaction.deleted == False,
        Transaction.date >= three_months_ago,
        Transaction.is_recurring == False
    ).all()
    return sum(t.amount for t in txns) / 3 if txns else 5000.0

def detect_recurring(db: Session) -> list:
    six_months_ago = date.today() - relativedelta(months=6)
    txns = db.query(Transaction).filter(
        Transaction.deleted == False, Transaction.date >= six_months_ago
    ).order_by(Transaction.merchant, Transaction.date).all()
    by_merchant = defaultdict(list)
    for t in txns:
        by_merchant[t.merchant.lower().strip()].append(t)
    detected = []
    for merchant, items in by_merchant.items():
        if len(items) < 2:
            continue
        amounts = [t.amount for t in items]
        avg_amount = statistics.mean(amounts)
        dates = sorted([t.date for t in items])
        if len(dates) >= 2:
            intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
            avg_interval = statistics.mean(intervals)
            if 25 <= avg_interval <= 35: freq = "monthly"
            elif 6 <= avg_interval <= 8: freq = "weekly"
            elif 350 <= avg_interval <= 380: freq = "yearly"
            else: continue
            next_exp = dates[-1] + timedelta(days=int(avg_interval))
            detected.append({
                "merchant": items[0].merchant, "avg_amount": round(avg_amount, 2),
                "frequency": freq, "last_seen": str(dates[-1]),
                "next_expected": str(next_exp), "category": items[0].category,
                "occurrences": len(items)
            })
    return detected

def goal_progress(db: Session) -> list:
    goals = db.query(Goal).filter(Goal.status != "deleted").all()
    today = date.today()
    result = []
    for g in goals:
        pct = round(g.current_amount / g.target_amount, 3) if g.target_amount > 0 else 0
        days_left = (g.deadline - today).days if g.deadline else None
        result.append({
            "id": g.id, "name": g.name, "target": g.target_amount,
            "current": g.current_amount,
            "remaining": round(g.target_amount - g.current_amount, 2),
            "pct": min(pct, 1.0), "status": g.status,
            "days_left": days_left,
            "deadline": str(g.deadline) if g.deadline else None,
            "description": g.description,
        })
    return result

def tax_summary(db: Session) -> dict:
    today = date.today()
    fy_start = date(today.year if today.month >= 4 else today.year - 1, 4, 1)
    fy_end = date(fy_start.year + 1, 3, 31)
    deductible = db.query(Transaction).filter(
        Transaction.deleted == False, Transaction.tax_deductible == True,
        Transaction.date >= fy_start, Transaction.date <= fy_end
    ).all()
    by_section = defaultdict(float)
    for t in deductible:
        by_section[t.tax_section or "General"] += t.amount
    return {
        "financial_year": f"{fy_start.year}-{str(fy_end.year)[2:]}",
        "total_deductible": round(sum(by_section.values()), 2),
        "by_section": {k: round(v, 2) for k, v in by_section.items()},
        "transactions": [{"merchant": t.merchant, "amount": t.amount, "date": str(t.date), "section": t.tax_section} for t in deductible]
    }

def get_recent_transactions(db: Session, limit: int = 5) -> list:
    txns = db.query(Transaction).filter(Transaction.deleted == False).order_by(Transaction.id.desc()).limit(limit).all()
    return [{
        "id": t.id, "merchant": t.merchant, "amount": t.amount, 
        "date": str(t.date), "category": t.category, "description": t.description
    } for t in txns]

"""
finance_tools.py  –  Finn Personal Finance Assistant
=====================================================
All data-fetching tools used by the LangGraph agent.
Every tool returns rich, structured dicts that the analyst LLM
can narrate into a helpful, personalised response.

Tool inventory
──────────────
 1.  spending_summary          – period breakdown + all-time snapshot + MoM delta
 2.  monthly_trend             – month-by-month totals (up to 12 months)
 3.  budget_status             – FinancialGoal-based budget health with health scores
 4.  detect_anomalies          – z-score based unusual-transaction detector
 5.  cash_flow_forecast        – upcoming bills + variable spend projection
 6.  goal_progress             – savings / purchase goals with pace analysis
 7.  tax_summary               – tax-deductible expenses by section (Indian FY)
 8.  get_recent_transactions   – latest N transactions with full details
 9.  get_recurring_expenses    – user-defined subscriptions / recurring bills
10.  category_breakdown        – deep dive into one spending category
11.  merchant_insights         – top merchants by spend and visit frequency
12.  daily_spending_pattern    – average spend by day-of-week
13.  detect_recurring          – auto-detect recurring patterns from history
"""

from sqlalchemy.orm import Session
from models import Transaction, Goal, RecurringExpense, FinancialGoal
from typing import Dict, List, Optional, Union
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from collections import defaultdict
import statistics
import json as _json

# ─────────────────────────────────────────────────────────────────────────────
# SHARED CATEGORY CONFIG
# ─────────────────────────────────────────────────────────────────────────────

CATEGORIES: dict[str, list[str]] = {
    "Food": [
        "swiggy", "zomato", "uber eats", "restaurant", "cafe", "biryani",
        "pizza", "burger", "dominos", "kfc", "mcdonalds", "starbucks",
        "hotel", "dhaba", "bakery", "juice", "tea", "coffee", "canteen",
        "mess", "tiffin", "haldiram", "subway", "rolls", "dosa",
    ],
    "Transport": [
        "uber", "ola", "rapido", "irctc", "metro", "petrol", "fuel",
        "auto", "bus", "flight", "indigo", "air india", "spicejet",
        "parking", "toll", "cab", "taxi", "train", "rickshaw", "vistara",
    ],
    "Utilities": [
        "electricity", "bescom", "tneb", "water", "gas", "internet",
        "broadband", "airtel", "jio", "bsnl", "vi ", "vodafone",
        "recharge", "mobile", "dth", "tata sky", "act fibernet",
    ],
    "Shopping": [
        "amazon", "flipkart", "myntra", "ajio", "zepto", "blinkit",
        "instamart", "meesho", "nykaa", "bigbasket", "grofers", "dmart",
        "reliance", "decathlon", "ikea", "croma", "tata cliq", "snapdeal",
    ],
    "Entertainment": [
        "netflix", "hotstar", "spotify", "youtube", "prime video",
        "cinema", "pvr", "inox", "bookmyshow", "apple tv", "zee5",
        "sonyliv", "disney", "gaming", "steam", "mxplayer", "jiocinema",
    ],
    "Healthcare": [
        "pharmacy", "hospital", "clinic", "apollo", "medplus",
        "diagnostic", "lab", "doctor", "medicine", "1mg", "practo",
        "netmeds", "gym", "fitness", "yoga", "chemist", "nursing home",
    ],
    "Education": [
        "udemy", "coursera", "book", "course", "training", "school",
        "college", "byju", "unacademy", "skill", "tuition", "coaching",
        "duolingo", "khan academy", "leetcode", "pluralsight",
    ],
}

VALID_CATEGORIES: list[str] = list(CATEGORIES.keys()) + ["Miscellaneous"]


def categorise(merchant: str, description: str = "") -> tuple[str, float]:
    """Rule-based keyword categoriser.  Returns (category, confidence)."""
    text = (merchant + " " + description).lower()
    for category, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in text:
                return category, 0.9
    return "Miscellaneous", 0.4


# ─────────────────────────────────────────────────────────────────────────────
# PERIOD DATE HELPER
# ─────────────────────────────────────────────────────────────────────────────

def get_period_dates(period: str) -> tuple[date, date]:
    today = date.today()

    if period == "today":
        return today, today
    if period == "this_week":
        return today - timedelta(days=today.weekday()), today
    if period == "this_month":
        return today.replace(day=1), today
    if period == "last_month":
        first = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last = today.replace(day=1) - timedelta(days=1)
        return first, last
    if period == "last_3_months":
        return (today - relativedelta(months=3)).replace(day=1), today
    if period == "last_6_months":
        return (today - relativedelta(months=6)).replace(day=1), today
    if period == "this_year":
        return today.replace(month=1, day=1), today
    if period == "all_time":
        return date(2000, 1, 1), today
    # default → this_month
    return today.replace(day=1), today


# ─────────────────────────────────────────────────────────────────────────────
# 1.  SPENDING SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def spending_summary(db: Session, period: str = "this_month") -> dict:
    """
    Returns spending breakdown for the requested period PLUS an all-time
    summary and a month-on-month comparison delta.

    period values:
        latest | today | this_week | this_month | last_month |
        last_3_months | last_6_months | this_year | all_time
    """
    today = date.today()

    # ── period transactions ─────────────────────────────────────────────────
    if period == "latest":
        last_txn = (
            db.query(Transaction)
            .filter(Transaction.deleted == False)
            .order_by(Transaction.created_at.desc())
            .first()
        )
        if not last_txn:
            return {
                "period": "latest",
                "total": 0,
                "transaction_count": 0,
                "message": "No transactions have been uploaded yet.",
            }
        burst_start = last_txn.created_at - timedelta(seconds=10)
        txns = (
            db.query(Transaction)
            .filter(Transaction.deleted == False, Transaction.created_at >= burst_start)
            .all()
        )
        start = end = last_txn.created_at.date()
    else:
        start, end = get_period_dates(period)
        txns = (
            db.query(Transaction)
            .filter(Transaction.deleted == False, Transaction.date >= start, Transaction.date <= end)
            .all()
        )

    # ── period aggregation ──────────────────────────────────────────────────
    by_category: dict[str, float] = defaultdict(float)
    by_merchant: dict[str, float] = defaultdict(float)
    for t in txns:
        by_category[t.category] += t.amount
        by_merchant[t.merchant] += t.amount

    period_total = round(sum(by_category.values()), 2)
    top_merchants = sorted(by_merchant.items(), key=lambda x: x[1], reverse=True)[:5]

    # ── all-time snapshot ───────────────────────────────────────────────────
    all_txns = db.query(Transaction).filter(Transaction.deleted == False).all()
    all_total = round(sum(t.amount for t in all_txns), 2)
    all_by_cat: dict[str, float] = defaultdict(float)
    for t in all_txns:
        all_by_cat[t.category] += t.amount
    biggest_all_time_category = max(all_by_cat, key=lambda k: all_by_cat[k]) if all_by_cat else None

    # ── month-on-month delta ────────────────────────────────────────────────
    this_month_start = today.replace(day=1)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)

    this_month_total = round(sum(
        t.amount for t in all_txns
        if t.date >= this_month_start and t.date <= today
    ), 2)
    last_month_total = round(sum(
        t.amount for t in all_txns
        if t.date >= last_month_start and t.date <= last_month_end
    ), 2)

    mom_change_pct: float | None = None
    if last_month_total > 0:
        mom_change_pct = round(((this_month_total - last_month_total) / last_month_total) * 100, 1)

    return {
        "period": period,
        "start": str(start),
        "end": str(end),
        "currency": "INR (₹)",
        # ── period result ────────────────────────────────────────────
        "total": period_total,
        "transaction_count": len(txns),
        "by_category": {
            k: round(v, 2)
            for k, v in sorted(by_category.items(), key=lambda x: x[1], reverse=True)
        },
        "top_merchants_in_period": [
            {"merchant": m, "amount": round(a, 2)} for m, a in top_merchants
        ],
        # ── all-time snapshot ─────────────────────────────────────────
        "all_time_summary": {
            "total_ever_spent": all_total,
            "total_transactions": len(all_txns),
            "biggest_category": biggest_all_time_category,
            "biggest_category_amount": round(all_by_cat.get(biggest_all_time_category, 0), 2)
                if biggest_all_time_category else 0,
            "by_category": {
                k: round(v, 2)
                for k, v in sorted(all_by_cat.items(), key=lambda x: x[1], reverse=True)
            },
        },
        # ── month comparison ──────────────────────────────────────────
        "month_comparison": {
            "this_month": this_month_total,
            "last_month": last_month_total,
            "change_pct": mom_change_pct,
            "trend": (
                "up" if mom_change_pct and mom_change_pct > 5
                else "down" if mom_change_pct and mom_change_pct < -5
                else "flat"
            ),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2.  MONTHLY TREND
# ─────────────────────────────────────────────────────────────────────────────

def monthly_trend(db: Session, months: Union[int, str] = 6) -> dict:
    """Month-by-month totals + category breakdown. Use 'all' for full history."""
    today = date.today()
    
    if months == "all":
        # Find first transaction date
        first_txn = db.query(Transaction).filter(Transaction.deleted == False).order_by(Transaction.date.asc()).first()
        if not first_txn:
            return {"months_analysed": 0, "currency": "INR (₹)", "monthly_data": [], "summary": {}}
        
        start_date = first_txn.date.replace(day=1)
        # Calculate months between start_date and today
        diff = relativedelta(today, start_date)
        num_months = (diff.years * 12) + diff.months + 1
    else:
        num_months = max(1, min(int(months), 24)) # cap at 24 for performance
    
    result = []
    totals: list[float] = []

    for i in range(num_months - 1, -1, -1):
        d = today - relativedelta(months=i)
        start = d.replace(day=1)
        end = (start + relativedelta(months=1)) - timedelta(days=1)
        txns = (
            db.query(Transaction)
            .filter(Transaction.deleted == False, Transaction.date >= start, Transaction.date <= end)
            .all()
        )
        by_cat: dict[str, float] = defaultdict(float)
        for t in txns:
            by_cat[t.category] += t.amount
        total = round(sum(by_cat.values()), 2)
        
        # Only add to results if there's data OR if we're doing a fixed month count
        if total > 0 or months != "all" or i < 3: # always show last 3 months
            totals.append(total)
            result.append({
                "month": start.strftime("%b %Y"),
                "total": total,
                "transaction_count": len(txns),
                "by_category": {k: round(v, 2) for k, v in by_cat.items()},
            })

    avg = round(statistics.mean(totals), 2) if totals else 0
    peak = max(result, key=lambda x: x["total"]) if result else None
    lowest = min(result, key=lambda x: x["total"]) if result else None
    # Simple linear trend using first vs last half
    half = len(totals) // 2
    trend_dir = "stable"
    if half > 0:
        first_half_avg = statistics.mean(totals[:half])
        second_half_avg = statistics.mean(totals[half:])
        if second_half_avg > first_half_avg * 1.05:
            trend_dir = "increasing"
        elif second_half_avg < first_half_avg * 0.95:
            trend_dir = "decreasing"

    return {
        "months_analysed": months,
        "currency": "INR (₹)",
        "monthly_data": result,
        "summary": {
            "average_monthly_spend": avg,
            "peak_month": peak["month"] if peak else None,
            "peak_amount": peak["total"] if peak else None,
            "lowest_month": lowest["month"] if lowest else None,
            "lowest_amount": lowest["total"] if lowest else None,
            "trend_direction": trend_dir,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3.  GOAL BUDGET STATUS
# ─────────────────────────────────────────────────────────────────────────────

def budget_status(db: Session) -> dict:
    """
    Health scores for all active FinancialGoals (Spending limits).
    Health = 100 − max(0, spend_pct − time_pct) × 100.
    100 = perfectly on track. Below 70 = needs attention.
    """
    goals = db.query(FinancialGoal).filter(FinancialGoal.status != "deleted").all()
    today = date.today()
    results = []

    for g in goals:
        # 1. Calculate time progress
        total_days = max((g.end_date - g.start_date).days, 1)
        elapsed_days = max((today - g.start_date).days, 0)
        time_pct = min(elapsed_days / total_days, 1.0)

        # 2. Calculate spending in this period
        txns = (
            db.query(Transaction)
            .filter(
                Transaction.deleted == False,
                Transaction.date >= g.start_date,
                Transaction.date <= g.end_date,
            )
            .all()
        )
        total_spent = sum(t.amount for t in txns)
        spend_pct = (total_spent / g.total_budget) if g.total_budget > 0 else 0

        # 3. Calculate health score
        overpace = max(0.0, spend_pct - time_pct)
        health_score = round(max(0, 100 - overpace * 100), 1)

        # 4. Per-category breakdown
        cat_budgets = g.category_budgets or {}
        cat_spent: dict[str, float] = defaultdict(float)
        for t in txns:
            cat_spent[t.category] += t.amount

        cat_breakdown = {}
        for cat, limit in cat_budgets.items():
            spent = round(cat_spent.get(cat, 0), 2)
            cat_breakdown[cat] = {
                "budget": limit,
                "spent": spent,
                "remaining": round(max(0, limit - spent), 2),
                "utilisation_pct": round(spent / limit, 3) if limit > 0 else 0,
                "over_budget": spent > limit,
            }

        results.append({
            "id": g.id,
            "timeline": g.timeline,
            "total_budget": g.total_budget,
            "total_spent": round(total_spent, 2),
            "remaining_budget": round(max(0, g.total_budget - total_spent), 2),
            "spend_pct": round(spend_pct, 3),
            "time_pct": round(time_pct, 3),
            "health_score": health_score,
            "status": (
                "on_track" if health_score >= 80
                else "caution" if health_score >= 60
                else "critical"
            ),
            "over_budget": spend_pct > 1.0,
            "start_date": str(g.start_date),
            "end_date": str(g.end_date),
            "category_breakdown": cat_breakdown,
        })

    return {
        "goals": results,
        "total_active_budgets": len(results),
        "currency": "INR (₹)",
        "summary": {
            "on_track": sum(1 for r in results if r["status"] == "on_track"),
            "caution": sum(1 for r in results if r["status"] == "caution"),
            "critical": sum(1 for r in results if r["status"] == "critical"),
        },
        "message": (
            f"{sum(1 for r in results if r['status'] == 'on_track')} of {len(results)} "
            f"budget goal(s) are on track."
            if results else "No active budgets found."
        ),
    }

# ─────────────────────────────────────────────────────────────────────────────
# 4.  DETECT ANOMALIES
# ─────────────────────────────────────────────────────────────────────────────

def detect_anomalies(db: Session) -> dict:
    """
    Z-score anomaly detection across all categories (last 90 days).
    Flags transactions with z > 2.5. Requires ≥ 5 transactions per category.
    """
    ninety_days_ago = date.today() - timedelta(days=90)
    txns = (
        db.query(Transaction)
        .filter(Transaction.deleted == False, Transaction.date >= ninety_days_ago)
        .all()
    )

    by_category: dict[str, list] = defaultdict(list)
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
                    "id": t.id,
                    "merchant": t.merchant,
                    "amount": t.amount,
                    "date": str(t.date),
                    "category": t.category,
                    "z_score": round(z, 2),
                    "category_avg": round(mean, 2),
                    "overspend_by": round(t.amount - mean, 2),
                    "message": (
                        f"₹{t.amount:,.0f} at {t.merchant} — "
                        f"₹{t.amount - mean:,.0f} above the usual ₹{mean:,.0f} in {cat}"
                    ),
                })

    anomalies.sort(key=lambda x: x["z_score"], reverse=True)

    return {
        "anomaly_count": len(anomalies),
        "period": "last_90_days",
        "anomalies": anomalies[:10],
        "message": (
            f"Found {len(anomalies)} unusual transaction(s) in the last 90 days."
            if anomalies
            else "No unusual transactions detected in the last 90 days. Spending looks normal."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5.  CASH FLOW FORECAST
# ─────────────────────────────────────────────────────────────────────────────

def cash_flow_forecast(db: Session, days: int = 30) -> dict:
    """Projects outflow = known recurring bills + variable spend average."""
    today = date.today()
    end = today + timedelta(days=days)

    recurring = (
        db.query(RecurringExpense)
        .filter(RecurringExpense.is_active == True, RecurringExpense.next_expected <= end)
        .all()
    )

    upcoming = []
    projected_recurring = 0.0
    for r in recurring:
        upcoming.append({
            "merchant": r.merchant,
            "amount": r.avg_amount,
            "expected_date": str(r.next_expected),
            "category": r.category,
            "frequency": r.frequency,
        })
        projected_recurring += r.avg_amount

    avg_monthly = _avg_monthly_spend(db)
    variable = round((avg_monthly / 30) * days, 2)
    total = round(projected_recurring + variable, 2)

    upcoming_sorted_by_date = sorted(upcoming, key=lambda x: x["expected_date"])
    biggest_bills = sorted(upcoming, key=lambda x: x["amount"], reverse=True)[:3]

    all_active_count = db.query(RecurringExpense).filter(RecurringExpense.is_active == True).count()

    return {
        "forecast_days": days,
        "currency": "INR (₹)",
        "projected_total_outflow": total,
        "recurring_outflow": round(projected_recurring, 2),
        "active_recurrence_count": all_active_count,
        "variable_outflow": variable,
        "avg_monthly_variable_spend": round(avg_monthly, 2),
        "upcoming_bills": upcoming_sorted_by_date,
        "biggest_upcoming_bills": biggest_bills,
        "risk_level": "HIGH" if total > 30000 else "MEDIUM" if total > 15000 else "LOW",
        "summary": (
            f"Over the next {days} days you're projected to spend ₹{total:,.0f}: "
            f"₹{projected_recurring:,.0f} in known recurring bills and "
            f"₹{variable:,.0f} in estimated variable spending."
        ),
    }


def _avg_monthly_spend(db: Session) -> float:
    three_months_ago = (date.today() - relativedelta(months=3)).replace(day=1)
    txns = (
        db.query(Transaction)
        .filter(
            Transaction.deleted == False,
            Transaction.date >= three_months_ago,
            Transaction.is_recurring == False,
        )
        .all()
    )
    return sum(t.amount for t in txns) / 3 if txns else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 6.  GOAL PROGRESS  (savings goals)
# ─────────────────────────────────────────────────────────────────────────────

def goal_progress(db: Session) -> dict:
    """Progress on all savings/purchase goals with pace analysis."""
    goals = db.query(Goal).filter(Goal.status != "deleted").all()
    today = date.today()
    results = []

    for g in goals:
        pct = round(g.current_amount / g.target_amount, 3) if g.target_amount > 0 else 0
        remaining = round(g.target_amount - g.current_amount, 2)
        days_left = (g.deadline - today).days if g.deadline else None
        daily_needed = round(remaining / days_left, 2) if (days_left and days_left > 0 and remaining > 0) else None

        results.append({
            "id": g.id,
            "name": g.name,
            "target_amount": g.target_amount,
            "current_amount": g.current_amount,
            "remaining_amount": remaining,
            "progress_pct": min(pct, 1.0),
            "status": g.status,
            "days_left": days_left,
            "deadline": str(g.deadline) if g.deadline else None,
            "daily_savings_needed": daily_needed,
            "description": g.description,
            "currency": "INR (₹)",
        })

    completed = [r for r in results if r["progress_pct"] >= 1.0]
    active = [r for r in results if r["progress_pct"] < 1.0]

    return {
        "total_goals": len(results),
        "active_goals": len(active),
        "completed_goals": len(completed),
        "goals": results,
        "summary": (
            f"You have {len(active)} active savings goal(s) and {len(completed)} completed."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7.  TAX SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def tax_summary(db: Session) -> dict:
    """Tax-deductible expenses for the current Indian financial year (Apr–Mar)."""
    today = date.today()
    fy_start = date(today.year if today.month >= 4 else today.year - 1, 4, 1)
    fy_end = date(fy_start.year + 1, 3, 31)

    deductible = (
        db.query(Transaction)
        .filter(
            Transaction.deleted == False,
            Transaction.tax_deductible == True,
            Transaction.date >= fy_start,
            Transaction.date <= fy_end,
        )
        .all()
    )

    by_section: dict[str, float] = defaultdict(float)
    for t in deductible:
        by_section[t.tax_section or "General"] += t.amount

    return {
        "financial_year": f"FY {fy_start.year}-{str(fy_end.year)[2:]}",
        "currency": "INR (₹)",
        "total_deductible": round(sum(by_section.values()), 2),
        "by_section": {k: round(v, 2) for k, v in by_section.items()},
        "transaction_count": len(deductible),
        "transactions": [
            {
                "merchant": t.merchant,
                "amount": t.amount,
                "date": str(t.date),
                "section": t.tax_section,
                "description": t.description,
            }
            for t in deductible
        ],
        "tip": (
            "Keep receipts for all deductible transactions as documentary proof."
            if deductible
            else "No tax-deductible expenses tagged yet. Mark transactions with tax_deductible=True."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 8.  RECENT TRANSACTIONS
# ─────────────────────────────────────────────────────────────────────────────

def get_recent_transactions(db: Session, limit: int = 10) -> dict:
    """Latest N transactions with full details."""
    limit = min(max(limit, 1), 50)
    txns = (
        db.query(Transaction)
        .filter(Transaction.deleted == False)
        .order_by(Transaction.id.desc())
        .limit(limit)
        .all()
    )
    items = [
        {
            "id": t.id,
            "merchant": t.merchant,
            "amount": t.amount,
            "date": str(t.date),
            "category": t.category,
            "description": t.description,
            "source": getattr(t, "source", "manual"),
            "is_recurring": getattr(t, "is_recurring", False),
        }
        for t in txns
    ]
    return {
        "count": len(items),
        "total_amount": round(sum(i["amount"] for i in items), 2),
        "currency": "INR (₹)",
        "transactions": items,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 9.  RECURRING EXPENSES  (user-managed subscriptions)
# ─────────────────────────────────────────────────────────────────────────────

def get_recurring_expenses(db: Session) -> dict:
    """
    All user-defined recurring expenses / subscriptions with active/inactive tags.
    Active items show days until next due date and overdue flag.
    """
    today = date.today()
    all_recurring = db.query(RecurringExpense).all()

    active = []
    inactive = []

    for r in all_recurring:
        days_until_due: int | None = None
        overdue = False
        if r.next_expected:
            days_until_due = (r.next_expected - today).days
            overdue = days_until_due < 0

        item = {
            "id": r.id,
            "merchant": r.merchant,
            "avg_amount": r.avg_amount,
            "currency": "INR (₹)",
            "frequency": r.frequency,
            "category": r.category,
            "next_expected": str(r.next_expected) if r.next_expected else None,
            "days_until_due": days_until_due,
            "overdue": overdue,
            "occurrences": getattr(r, "occurrences", None),
        }
        if r.is_active:
            active.append(item)
        else:
            inactive.append(item)

    active.sort(key=lambda x: x["next_expected"] or "9999-12-31")

    monthly_cost = sum(r["avg_amount"] for r in active if r["frequency"] == "monthly")
    yearly_cost = (monthly_cost * 12) + sum(
        r["avg_amount"] for r in active if r["frequency"] == "yearly"
    )
    weekly_cost = sum(r["avg_amount"] * 4 for r in active if r["frequency"] == "weekly")

    due_soon = [r for r in active if r["days_until_due"] is not None and 0 <= r["days_until_due"] <= 7]
    overdue_list = [r for r in active if r.get("overdue")]

    return {
        "total_subscriptions": len(all_recurring),
        "active_count": len(active),
        "inactive_count": len(inactive),
        "currency": "INR (₹)",
        "monthly_recurring_cost": round(monthly_cost, 2),
        "yearly_recurring_cost": round(yearly_cost + weekly_cost * 12, 2),
        "due_within_7_days": due_soon,
        "overdue_count": len(overdue_list),
        "overdue_subscriptions": overdue_list,
        "active_subscriptions": active,
        "inactive_subscriptions": inactive,
        "summary": (
            f"You have {len(active)} active subscription(s) costing ₹{monthly_cost:,.0f}/month "
            f"(₹{yearly_cost:,.0f}/year). "
            f"{len(due_soon)} due within 7 days"
            + (f", {len(overdue_list)} overdue." if overdue_list else ".")
            if active
            else "No recurring expenses set up yet."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 10.  CATEGORY DEEP DIVE
# ─────────────────────────────────────────────────────────────────────────────

def category_breakdown(db: Session, category: str, months: int = 3) -> dict:
    """Deep dive into one spending category: trend, top merchants, largest transactions."""
    today = date.today()
    start = (today - relativedelta(months=months)).replace(day=1)

    txns = (
        db.query(Transaction)
        .filter(
            Transaction.deleted == False,
            Transaction.category == category,
            Transaction.date >= start,
        )
        .order_by(Transaction.date.desc())
        .all()
    )

    if not txns:
        return {
            "category": category,
            "message": f"No {category} transactions found in the last {months} months.",
        }

    amounts = [t.amount for t in txns]
    by_merchant: dict[str, float] = defaultdict(float)
    for t in txns:
        by_merchant[t.merchant] += t.amount

    monthly: dict[str, float] = defaultdict(float)
    for t in txns:
        key = t.date.strftime("%b %Y")
        monthly[key] += t.amount

    largest = max(txns, key=lambda t: t.amount)

    return {
        "category": category,
        "period_months": months,
        "currency": "INR (₹)",
        "total_spent": round(sum(amounts), 2),
        "transaction_count": len(txns),
        "avg_per_transaction": round(statistics.mean(amounts), 2),
        "largest_transaction": {
            "merchant": largest.merchant,
            "amount": largest.amount,
            "date": str(largest.date),
        },
        "top_merchants": [
            {"merchant": m, "total": round(a, 2)}
            for m, a in sorted(by_merchant.items(), key=lambda x: x[1], reverse=True)[:5]
        ],
        "monthly_trend": [
            {"month": m, "total": round(v, 2)}
            for m, v in sorted(monthly.items())
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 11.  MERCHANT INSIGHTS
# ─────────────────────────────────────────────────────────────────────────────

def merchant_insights(db: Session, top_n: int = 10) -> dict:
    """Top merchants by total spend and visit frequency — this month vs all time."""
    today = date.today()
    month_start = today.replace(day=1)

    all_txns = db.query(Transaction).filter(Transaction.deleted == False).all()

    all_time: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "count": 0})
    this_month: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "count": 0})

    for t in all_txns:
        all_time[t.merchant]["total"] += t.amount
        all_time[t.merchant]["count"] += 1
        if t.date >= month_start:
            this_month[t.merchant]["total"] += t.amount
            this_month[t.merchant]["count"] += 1

    def format_merchants(data: dict, n: int) -> list:
        return [
            {
                "merchant": m,
                "total_spent": round(d["total"], 2),
                "visit_count": d["count"],
                "avg_per_visit": round(d["total"] / d["count"], 2),
            }
            for m, d in sorted(data.items(), key=lambda x: x[1]["total"], reverse=True)[:n]
        ]

    return {
        "currency": "INR (₹)",
        "top_merchants_all_time": format_merchants(all_time, top_n),
        "top_merchants_this_month": format_merchants(this_month, top_n),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 12.  DAILY SPENDING PATTERN
# ─────────────────────────────────────────────────────────────────────────────

def daily_spending_pattern(db: Session, months: int = 3) -> dict:
    """Average spend by day-of-week to surface spending habits."""
    start = (date.today() - relativedelta(months=months)).replace(day=1)
    txns = (
        db.query(Transaction)
        .filter(Transaction.deleted == False, Transaction.date >= start)
        .all()
    )

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_totals: dict[int, float] = defaultdict(float)
    day_counts: dict[int, int] = defaultdict(int)

    for t in txns:
        dow = t.date.weekday()
        day_totals[dow] += t.amount
        day_counts[dow] += 1

    result = [
        {
            "day": name,
            "total_spent": round(day_totals.get(i, 0), 2),
            "transaction_count": day_counts.get(i, 0),
            "avg_per_transaction": (
                round(day_totals[i] / day_counts[i], 2)
                if day_counts.get(i, 0) > 0 else 0
            ),
        }
        for i, name in enumerate(day_names)
    ]

    heaviest = max(result, key=lambda x: x["total_spent"])
    lightest = min(result, key=lambda x: x["total_spent"])

    return {
        "period_months": months,
        "currency": "INR (₹)",
        "by_day": result,
        "heaviest_spending_day": heaviest["day"],
        "lightest_spending_day": lightest["day"],
        "insight": (
            f"You tend to spend the most on {heaviest['day']}s "
            f"and the least on {lightest['day']}s."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 13.  DETECT RECURRING  (auto-detection from transaction history)
# ─────────────────────────────────────────────────────────────────────────────

def detect_recurring(db: Session) -> list:
    """Auto-detects recurring patterns from the last 6 months of transactions."""
    six_months_ago = date.today() - relativedelta(months=6)
    txns = (
        db.query(Transaction)
        .filter(Transaction.deleted == False, Transaction.date >= six_months_ago)
        .order_by(Transaction.merchant, Transaction.date)
        .all()
    )

    by_merchant: dict[str, list] = defaultdict(list)
    for t in txns:
        by_merchant[t.merchant.lower().strip()].append(t)

    detected = []
    for merchant_key, items in by_merchant.items():
        if len(items) < 2:
            continue
        amounts = [t.amount for t in items]
        avg_amount = statistics.mean(amounts)
        dates = sorted([t.date for t in items])

        intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        avg_interval = statistics.mean(intervals)

        if 25 <= avg_interval <= 35:
            freq = "monthly"
        elif 6 <= avg_interval <= 8:
            freq = "weekly"
        elif 350 <= avg_interval <= 380:
            freq = "yearly"
        else:
            continue

        next_exp = dates[-1] + timedelta(days=int(avg_interval))
        detected.append({
            "merchant": items[0].merchant,
            "avg_amount": round(avg_amount, 2),
            "frequency": freq,
            "last_seen": str(dates[-1]),
            "next_expected": str(next_exp),
            "category": items[0].category,
            "occurrences": len(items),
        })

    return detected

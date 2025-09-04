import re
import pandas as pd
from io import StringIO
import streamlit as st

st.set_page_config(page_title="Petty Cash → QuickBooks IIF", layout="wide")
st.title("💵 Petty Cash → QuickBooks IIF")

# ---------- Helpers ----------
def norm(s: str) -> str:
    """lower, strip, collapse non-alnum to single space"""
    return re.sub(r"[^a-z0-9]+", " ", str(s).strip().lower()).strip()

EXPECTED = {
    "pay type": ["pay type","paytype","type","pay_type"],
    "till no": ["till no","till","till number","till_no","tillno"],
    "transaction date": ["transaction date","date","txn date","trans date","txndate"],
    "detail": ["detail","details","description","memo","narration"],
    "transacted amount": ["transacted amount","amount","amt","value","transaction amount"],
    "user name": ["user name","username","user","cashier","handled by","handledby"]
}

def find_columns(df_cols):
    """Map whatever headers came in to the expected names."""
    normalized = {norm(c): c for c in df_cols}
    mapping = {}
    for target, alts in EXPECTED.items():
        found = None
        for alt in alts:
            if alt in normalized:
                found = normalized[alt]
                break
        if found is None:
            # try fuzzy single-word contains
            for key, orig in normalized.items():
                if all(w in key for w in norm(alts[0]).split()):  # e.g., "pay type"
                    found = orig
                    break
        if found is None:
            mapping[target] = None
        else:
            mapping[target] = found
    return mapping

def qb_date(x):
    try:
        return pd.to_datetime(x, dayfirst=False).strftime("%m/%d/%Y")
    except Exception:
        return str(x)

def clean_text(x):
    return str(x).replace('"', '').replace("\n", " ").strip()

def classify_and_rows(row, seq):
    """
    Return list of (TRNS, SPL) rows for IIF based on business rules.
    Always:
      - Bank/cash account: Cash in Drawer
      - Transfer 'Cash Pickup' -> Diamond Trust Bank
      - Delivery -> Customer Deliveries
      - fare/fair/transport/trasport -> Interbranch Transport Cost
      - else -> Accounts Payable
    Amount handling: assumes positive 'Transacted Amount' means cash paid out.
    """
    pay_type = norm(row["pay type"])
    details_n = norm(row["detail"])
    details_raw = clean_text(row["detail"])
    user = clean_text(row["user name"])
    date_str = qb_date(row["transaction date"])
    till = clean_text(row.get("till no", ""))
    amt = float(row["transacted amount"])
    amt = abs(amt)  # treat as spend/transfer out
    clear = "N"
    docnum = f"{till}-{pd.to_datetime(row['transaction date']).strftime('%Y%m%d')}-{seq:03d}"

    # Build base memos
    memo_petty = f"Petty cash by {user} for {details_raw} on {date_str}"
    memo_deliv = f"Delivery expense on behalf of customer on {date_str}"
    memo_trans = f"Interbranch transport by {user} on {date_str}"
    memo_pick  = f"Cash pick up for deposit on {date_str}"

    # 1) Cash Pickup => TRANSFER Cash in Drawer -> Diamond Trust Bank
    if "cash" in pay_type and "pickup" in pay_type:
        trnstype = "TRANSFER"
        return [
            # credit Cash in Drawer
            ["TRNS", trnstype, date_str, "Cash in Drawer", "Diamond Trust Bank", -amt, memo_pick, docnum, clear],
            # debit DTB
            ["SPL",  trnstype, date_str, "Diamond Trust Bank", "Diamond Trust Bank",  amt, memo_pick, docnum, clear],
        ]

    # 2) Petty cash rules (includes all non-pickup lines)
    trnstype = "CHECK"

    # Delivery (catch typos like 'deivery', 'deliver', 'deliv')
    if "deliv" in details_n:
        return [
            # pay from cash
            ["TRNS", trnstype, date_str, "Cash in Drawer", user, -amt, memo_deliv, docnum, clear],
            # charge to COGS
            ["SPL",  trnstype, date_str, "COGS:Customer Deliveries", user,  amt, memo_deliv, docnum, clear],
        ]

    # Staff transport (handle 'fare', 'fair', 'transport', common typo 'trasport')
    if any(k in details_n for k in ["fare", "fair", "transport", "trasport"]):
        return [
            ["TRNS", trnstype, date_str, "Cash in Drawer", user, -amt, memo_trans, docnum, clear],
            ["SPL",  trnstype, date_str, "Expense:Interbranch Transport Cost", user,  amt, memo_trans, docnum, clear],
        ]

    # Other purchases -> Accounts Payable (use vendor from Detail as NAME)
    vendor_name = details_raw.title() if details_raw else "Vendor"
    return [
        ["TRNS", trnstype, date_str, "Cash in Drawer", vendor_name, -amt, memo_petty, docnum, clear],
        ["SPL",  trnstype, date_str, "Accounts Payable", vendor_name,  amt, memo_petty, docnum, clear],
    ]

def build_iif(df):
    out = StringIO()
    # Header EXACT order matches rows
    out.write("!TRNS\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tMEMO\tDOCNUM\tCLEAR\n")
    out.write("!SPL\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tMEMO\tDOCNUM\tCLEAR\n")
    out.write("!ENDTRNS\n")

    seq = 1
    for _, r in df.iterrows():
        lines = classify_and_rows(r, seq)
        # Write TRNS/SPL lines
        for i, line in enumerate(lines):
            tag = line[0]
            out.write("\t".join([tag] + [str(x) for x in line[1:]]) + "\n")
        out.write("ENDTRNS\n")
        seq += 1
    return out.getvalue()

# ---------- UI ----------
uploaded = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])

if uploaded:
    # Read
    if uploaded.name.lower().endswith(".csv"):
        df_raw = pd.read_csv(uploaded)
    else:
        df_raw = pd.read_excel(uploaded)

    st.subheader("📄 Raw preview")
    st.dataframe(df_raw.head(20), use_container_width=True)

    # Normalize & map columns
    colmap = find_columns(df_raw.columns)
    missing = [k for k, v in colmap.items() if v is None]
    if missing:
        st.error(
            "Missing required columns after normalization: "
            + ", ".join(missing)
            + ".\nFound columns: "
            + ", ".join(df_raw.columns.astype(str))
        )
        st.stop()

    df = pd.DataFrame({
        "pay type": df_raw[colmap["pay type"]],
        "till no": df_raw[colmap["till no"]],
        "transaction date": df_raw[colmap["transaction date"]],
        "detail": df_raw[colmap["detail"]],
        "transacted amount": df_raw[colmap["transacted amount"]],
        "user name": df_raw[colmap["user name"]],
    })

    # Clean values
    for c in ["pay type","till no","detail","user name"]:
        df[c] = df[c].astype(str).fillna("").map(clean_text)
    df["transacted amount"] = pd.to_numeric(df["transacted amount"], errors="coerce").fillna(0)

    st.subheader("✅ Normalized preview")
    st.dataframe(df.head(30), use_container_width=True)

    if st.button("Generate QuickBooks IIF"):
        iif_txt = build_iif(df)
        st.download_button(
            "📥 Download petty_cash.iif",
            data=iif_txt.encode("utf-8"),
            file_name="petty_cash.iif",
            mime="text/plain",
        )

else:
    st.info("Upload your petty cash file (CSV/XLSX) with columns like: Pay Type, Till No, Transaction Date, Detail, Transacted Amount, User Name.")


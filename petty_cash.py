import streamlit as st
import pandas as pd
from io import StringIO

st.set_page_config(page_title="Bank Statement to QuickBooks IIF", layout="wide")

st.title("🏦 Bank Statement ➝ QuickBooks IIF Converter")

uploaded_file = st.file_uploader("📂 Upload your statement (CSV/XLSX)", type=["csv", "xlsx"])

if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    # Rename columns to normalized keys
    df = df.rename(columns={
        "Pay Type": "pay type",
        "Transaction Date": "date",
        "Detail": "details",
        "Transacted Amount": "amount",
        "User Name": "user"
    })

    # Clean up text columns
    df["details"] = df["details"].str.lower().fillna("")
    df["pay type"] = df["pay type"].str.lower().fillna("")

    # Account mapping logic
    def map_accounts(row):
        details = row["details"]
        pay_type = row["pay type"]

        if "cash pickup" in pay_type:
            return ("Cash in Drawer", "Diamond Trust Bank")

        if "petty cash" in pay_type:
            if "delivery" in details:
                return ("Cash in Drawer", "Customer Deliveries")
            elif any(word in details for word in ["fare", "fair", "transport"]):
                return ("Cash in Drawer", "Interbranch Transport Cost")
            else:
                return ("Cash in Drawer", "Accounts Payable")

        return ("Cash in Drawer", "Accounts Payable")

    df[["accnt", "offset_accnt"]] = df.apply(map_accounts, axis=1, result_type="expand")

    # Fix date format for QuickBooks
    def fix_date(x):
        try:
            return pd.to_datetime(x).strftime("%m/%d/%Y")
        except:
            return x

    df["date"] = df["date"].apply(fix_date)

    # Build IIF
    output = StringIO()
    output.write("!TRNS\tTRNSTYPE\tDATE\tACCNT\tNAME\tMEMO\tAMOUNT\n")
    output.write("!SPL\tTRNSTYPE\tDATE\tACCNT\tNAME\tMEMO\tAMOUNT\n")
    output.write("ENDTRNS\n")

    for _, row in df.iterrows():
        amount = float(row["amount"])
        details = row["details"]
        user = row["user"]

        if "cash pickup" in row["pay type"]:
            memo = f"Cash pick up for deposit on {row['date']}"
            # Transfer transaction
            output.write(f"TRNS\tTRANSFER\t{row['date']}\t{row['accnt']}\t{user}\t{memo}\t{-amount}\n")
            output.write(f"SPL\tTRANSFER\t{row['date']}\t{row['offset_accnt']}\t{user}\t{memo}\t{amount}\n")
            output.write("ENDTRNS\n")
        else:
            memo = f"Petty cash by {user} for {details}"
            # Check transaction
            output.write(f"TRNS\tCHECK\t{row['date']}\t{row['accnt']}\t{user}\t{memo}\t{-amount}\n")
            output.write(f"SPL\tCHECK\t{row['date']}\t{row['offset_accnt']}\t{user}\t{memo}\t{amount}\n")
            output.write("ENDTRNS\n")

    st.subheader("✅ IIF Preview")
    st.text(output.getvalue())

    st.download_button(
        label="💾 Download QuickBooks IIF",
        data=output.getvalue(),
        file_name="bank_statement.iif",
        mime="text/plain"
    )

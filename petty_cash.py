import streamlit as st
import pandas as pd
from io import StringIO
from datetime import datetime

st.set_page_config(page_title="Petty Cash to QuickBooks IIF", layout="wide")

st.title("📄 Petty Cash Statement → QuickBooks IIF Converter")

uploaded_file = st.file_uploader("Upload Petty Cash Statement (CSV/Excel)", type=["csv", "xlsx"])

def generate_iif(df):
    output = StringIO()

    # Write headers
    output.write("!TRNS\tTRNSTYPE\tDATE\tACCNT\tNAME\tREASON\tAMOUNT\tDOCNUM\n")
    output.write("!SPL\tTRNSTYPE\tDATE\tACCNT\tNAME\tREASON\tAMOUNT\tDOCNUM\n")
    output.write("ENDTRNS\n")

    # Normalize column names
    df.columns = df.columns.str.strip().str.lower()

    # Ensure required columns exist
    required_cols = {"date", "amount", "pay type", "type", "reason", "name"}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"Missing required columns. Found: {list(df.columns)}. Need: {list(required_cols)}")

    for i, row in df.iterrows():
        try:
            # Format date
            txn_date = pd.to_datetime(row["date"]).strftime("%m/%d/%Y")

            amount = float(row["amount"])
            pay_type = str(row.get("pay type", "")).lower()
            txn_type = str(row.get("type", "")).lower()
            reason = str(row.get("reason", ""))
            name = str(row.get("name", ""))
            docnum = str(i + 1)

            # Default accounts
            bank_account = "Cash in Drawer"
            expense_account = "Petty Cash Expenses"
            deposit_account = "Bank:DTB"

            # Differentiate
            if pay_type == "cash pickup":
                # Cash picked for deposit
                output.write(f"TRNS\tDEPOSIT\t{txn_date}\t{deposit_account}\t{name}\t{reason}\t{amount}\t{docnum}\n")
                output.write(f"SPL\tDEPOSIT\t{txn_date}\t{bank_account}\t{name}\t{reason}\t{-amount}\t{docnum}\n")
                output.write("ENDTRNS\n")
            elif txn_type == "petty cash":
                # Petty cash expenses
                output.write(f"TRNS\tCHECK\t{txn_date}\t{bank_account}\t{name}\t{reason}\t{-amount}\t{docnum}\n")
                output.write(f"SPL\tCHECK\t{txn_date}\t{expense_account}\t{name}\t{reason}\t{amount}\t{docnum}\n")
                output.write("ENDTRNS\n")
            else:
                # Other general transactions
                output.write(f"TRNS\tGENERAL JOURNAL\t{txn_date}\t{bank_account}\t{name}\t{reason}\t{amount}\t{docnum}\n")
                output.write(f"SPL\tGENERAL JOURNAL\t{txn_date}\t{expense_account}\t{name}\t{reason}\t{-amount}\t{docnum}\n")
                output.write("ENDTRNS\n")

        except Exception as e:
            st.warning(f"Skipping row {i+1} due to error: {e}")

    return output.getvalue()

if uploaded_file:
    try:
        # Load file
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        st.subheader("📊 Preview of Uploaded Data")
        st.dataframe(df.head())

        iif_content = generate_iif(df)

        st.subheader("✅ Generated QuickBooks IIF")
        st.code(iif_content, language="plaintext")

        st.download_button(
            label="⬇️ Download IIF File",
            data=iif_content,
            file_name="petty_cash.iif",
            mime="text/plain"
        )

    except Exception as e:
        st.error(f"Error: {e}")

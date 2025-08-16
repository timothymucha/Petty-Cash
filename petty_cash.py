import streamlit as st
import pandas as pd
from io import StringIO
from datetime import datetime

st.set_page_config(page_title="Petty Cash to QuickBooks IIF", layout="wide")

st.title("💵 Petty Cash Statement → QuickBooks IIF")

uploaded_file = st.file_uploader("Upload Petty Cash Statement (CSV or Excel)", type=["csv", "xlsx"])

def generate_iif(df):
    output = StringIO()

    # IIF headers
    output.write("!TRNS\tTRNSTYPE\tDATE\tACCNT\tNAME\tMEMO\tAMOUNT\n")
    output.write("!SPL\tTRNSTYPE\tDATE\tACCNT\tNAME\tMEMO\tAMOUNT\n")
    output.write("ENDHDR\n")

    for idx, row in df.iterrows():
        date = pd.to_datetime(row["Transaction Date"]).strftime("%m/%d/%Y")
        detail = str(row["Detail"]).strip().lower()
        amount = float(row["Transacted Amount"])
        user = str(row["User Name"]).strip()
        pay_type = str(row["Pay Type"]).strip()

        # Default values
        trnstype = "CHECK"
        accnt = "Accounts Payable"
        memo = f"Petty cash by {user} for {row['Detail']} on {date}"
        name = "Walk In"  # default customer/vendor

        # Cash pick up → Transfer
        if "pick" in detail:
            trnstype = "TRANSFER"
            accnt = "Cash in Drawer"
            name = "Diamond Trust Bank"
            memo = f"Cash pick up for deposit on {date}"

            # TRNS line
            output.write(f"TRNS\t{trnstype}\t{date}\t{accnt}\t{name}\t{memo}\t{-amount}\n")
            # SPL line
            output.write(f"SPL\t{trnstype}\t{date}\tDiamond Trust Bank\t{name}\t{memo}\t{amount}\n")

        # Delivery fees
        elif "delivery" in detail:
            accnt = "COGS:Customer Deliveries"
            memo = f"Delivery expense on behalf of customer on {date}"

            output.write(f"TRNS\t{trnstype}\t{date}\t{accnt}\t{name}\t{memo}\t{-amount}\n")
            output.write(f"SPL\t{trnstype}\t{date}\tCash in Drawer\t{name}\t{memo}\t{amount}\n")

        # Staff transport
        elif any(x in detail for x in ["fare", "fair", "transport"]):
            accnt = "Expense:Interbranch Transport Cost"
            memo = f"Interbranch transport by {user} on {date}"

            output.write(f"TRNS\t{trnstype}\t{date}\t{accnt}\t{name}\t{memo}\t{-amount}\n")
            output.write(f"SPL\t{trnstype}\t{date}\tCash in Drawer\t{name}\t{memo}\t{amount}\n")

        # All other petty cash → Accounts Payables
        else:
            accnt = "Accounts Payable"
            memo = f"Petty cash by {user} for {row['Detail']} on {date}"

            output.write(f"TRNS\t{trnstype}\t{date}\t{accnt}\t{name}\t{memo}\t{-amount}\n")
            output.write(f"SPL\t{trnstype}\t{date}\tCash in Drawer\t{name}\t{memo}\t{amount}\n")

        output.write("ENDTRNS\n")

    return output.getvalue()

if uploaded_file:
    # Load file
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.subheader("📊 Preview of Uploaded Data")
    st.dataframe(df.head(20))

    if st.button("Generate QuickBooks IIF"):
        iif_data = generate_iif(df)
        st.download_button("📥 Download IIF File", iif_data, file_name="petty_cash.iif")

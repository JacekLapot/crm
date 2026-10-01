from datetime import datetime
import sqlite3
import pandas as pd
import streamlit as st

# --- KONFIGURACJA STRONY POD TELEFON ---
st.set_page_config(
    page_title="CRM Wizyty", page_icon="📱", layout="centered"
)

# --- BAZA DANYCH ---
conn = sqlite3.connect("crm.db", check_same_thread=False)
c = conn.cursor()

c.execute(
    """
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        last_visit DATE,
        notes TEXT
    )
"""
)
conn.commit()

st.title("📱 Mobilny CRM")

# --- ZAKŁADKI DLA WYGODY NA TELEFONIE ---
tab1, tab2, tab3 = st.tabs(
    ["📋 Lista klientów", "➕ Nowa wizyta", "👤 Dodaj klienta"]
)

# --- TAB 1: LISTA KLIENTÓW ---
with tab1:
    df = pd.read_sql_query("SELECT * FROM clients", conn)

    if not df.empty:
        df["last_visit"] = pd.to_datetime(df["last_visit"]).dt.date
        today = datetime.now().date()
        df["Dni od wizyty"] = (today - df["last_visit"]).dt.days

        # Szybki filtr kategorii
        category_filter = st.multiselect(
            "Filtruj priorytet:",
            ["🥇 Złoty", "🥈 Srebrny", "🥉 Brązowy"],
            default=["🥇 Złoty", "🥈 Srebrny", "🥉 Brązowy"],
        )

        filtered_df = df[df["category"].isin(category_filter)].sort_values(
            by="Dni od wizyty", ascending=False
        )

        st.subheader("Klienci (najdłużej bez wizyty na górze)")

        for _, row in filtered_df.iterrows():
            # Kolorowa ikona priorytetu
            color = (
                "🔴"
                if row["Dni od wizyty"] > 30
                else ("🟡" if row["Dni od wizyty"] > 14 else "🟢")
            )

            with st.expander(
                f"{color} {row['name']} ({row['category']}) — {row['Dni od wizyty']} dni tem"
            ):
                st.write(f"**Ostatnia wizyta:** {row['last_visit']}")
                st.write(
                    f"**Liczba dni od wizyty:** {row['Dni od wizyty']} dni"
                )
                st.write("**Historie notatek:**")
                st.text(
                    row["notes"] if row["notes"] else "Brak wpisanych notatek"
                )
    else:
        st.info("Baza jest pusta. Dodaj pierwszego klienta w zakładce obok.")

# --- TAB 2: ZAKTAUALIZUJ WIZYTĘ ---
with tab2:
    st.subheader("Zapisz nową wizytę")
    df_clients = pd.read_sql_query("SELECT id, name FROM clients", conn)

    if not df_clients.empty:
        with st.form("update_form", clear_on_submit=True):
            selected_client = st.selectbox(
                "Wybierz klienta", df_clients["name"]
            )
            visit_date = st.date_input("Data wizyty", datetime.now())
            visit_note = st.text_area("Notatka ze spotkania")
            submit_update = st.form_submit_button("Zapisz wizytę")

            if submit_update:
                c.execute(
                    "SELECT notes FROM clients WHERE name = ?",
                    (selected_client,),
                )
                old_notes = c.fetchone()[0] or ""
                new_notes = f"[{visit_date}] {visit_note}\n{old_notes}".strip()

                c.execute(
                    "UPDATE clients SET last_visit = ?, notes = ? WHERE name = ?",
                    (visit_date, new_notes, selected_client),
                )
                conn.commit()
                st.success(f"Zaktualizowano dane dla: {selected_client}")
                st.rerun()
    else:
        st.warning("Najpierw dodaj chociaż jednego klienta!")

# --- TAB 3: DODAJ NOWEGO KLIENTA ---
with tab3:
    st.subheader("Formularz nowego klienta")
    with st.form("add_client_form", clear_on_submit=True):
        name = st.text_input("Nazwa firmy / Imię i nazwisko")
        category = st.selectbox(
            "Priorytet", ["🥇 Złoty", "🥈 Srebrny", "🥉 Brązowy"]
        )
        first_visit = st.date_input("Data pierwszej wizyty", datetime.now())
        first_note = st.text_area("Pierwsza notatka (opcjonalnie)")
        submit_new = st.form_submit_button("Dodaj do bazy")

        if submit_new and name:
            initial_note = (
                f"[{first_visit}] {first_note}" if first_note else ""
            )
            c.execute(
                "INSERT INTO clients (name, category, last_visit, notes) VALUES (?, ?, ?, ?)",
                (name, category, first_visit, initial_note),
            )
            conn.commit()
            st.success(f"Dodano klienta {name}!")
            st.rerun()

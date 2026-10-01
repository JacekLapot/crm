from datetime import datetime
import email.mime.multipart
import email.mime.text
import smtplib
import sqlite3
import pandas as pd
import streamlit as st

# --- KONFIGURACJA STRONY POD TELEFON ---
st.set_page_config(
    page_title="CRM Wizyty, Zamówienia i Dane",
    page_icon="📱",
    layout="centered",
)

# --- BAZA DANYCH ---
conn = sqlite3.connect("crm.db", check_same_thread=False)
c = conn.cursor()

# Tabela klientów (rozszerzona o telefon, email i adres)
c.execute(
    """
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        category TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        address TEXT,
        price_list TEXT,
        last_visit DATE,
        notes TEXT,
        total_bought_val REAL DEFAULT 0.0,
        total_returned_val REAL DEFAULT 0.0,
        net_val REAL DEFAULT 0.0,
        return_rate REAL DEFAULT 0.0,
        last_report_date DATE
    )
"""
)

# Tabela cenników
c.execute(
    """
    CREATE TABLE IF NOT EXISTS price_lists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        details TEXT NOT NULL
    )
"""
)

# Tabela pozycji z raportu Excela
c.execute(
    """
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT NOT NULL,
        item_name TEXT,
        bought_qty REAL,
        bought_val REAL,
        returned_qty REAL,
        returned_val REAL,
        net_val REAL,
        report_date DATE
    )
"""
)

# Tabela zamówień
c.execute(
    """
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT NOT NULL,
        order_details TEXT NOT NULL,
        created_at DATETIME,
        status TEXT DEFAULT 'Wysłano'
    )
"""
)
conn.commit()

# Łagodna migracja kolumn dla starych baz
for column, col_type in [
    ("phone", "TEXT"),
    ("email", "TEXT"),
    ("address", "TEXT"),
    ("total_bought_val", "REAL DEFAULT 0.0"),
    ("total_returned_val", "REAL DEFAULT 0.0"),
    ("net_val", "REAL DEFAULT 0.0"),
    ("return_rate", "REAL DEFAULT 0.0"),
    ("last_report_date", "DATE"),
    ("price_list", "TEXT"),
]:
    try:
        c.execute(f"ALTER TABLE clients ADD COLUMN {column} {col_type}")
        conn.commit()
    except sqlite3.OperationalError:
        pass


# Funkcja pomocnicza do wysyłania e-maila
def send_email_via_gmail(
    sender_email, app_password, recipient_email, subject, body_text
):
    msg = email.mime.multipart.MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject

    msg.attach(email.mime.text.MIMEText(body_text, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, app_password)
        server.send_message(msg)


st.title("📱 Mobilny CRM")

# --- ZAKŁADKI ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "📋 Klienci",
        "➕ Nowa wizyta",
        "📊 Raport Excel",
        "👤 Nowy klient",
        "🏷️ Cenniki",
    ]
)

# --- TAB 1: LISTA KLIENTÓW ---
with tab1:
    df = pd.read_sql_query("SELECT * FROM clients", conn)

    if not df.empty:
        df["last_visit"] = pd.to_datetime(df["last_visit"]).dt.date
        today = datetime.now().date()
        df["Dni od wizyty"] = (today - df["last_visit"]).dt.days

        category_filter = st.multiselect(
            "Filtruj priorytet:",
            ["🥇 Złoty", "🥈 Srebrny", "🥉 Brązowy"],
            default=["🥇 Złoty", "🥈 Srebrny", "🥉 Brązowy"],
        )

        filtered_df = df[df["category"].isin(category_filter)].sort_values(
            by="Dni od wizyty", ascending=False
        )

        st.subheader("Lista Klientów")

        for _, row in filtered_df.iterrows():
            color = (
                "🔴"
                if row["Dni od wizyty"] > 30
                else ("🟡" if row["Dni od wizyty"] > 14 else "🟢")
            )

            with st.expander(
                f"{color} {row['name']} ({row['category']}) — {row['Dni od wizyty']} dni"
            ):
                # Dane kontaktowe
                st.markdown("📞 **Dane kontaktowe:**")
                if row["phone"]:
                    st.write(f"• **Telefon:** [{row['phone']}](tel:{row['phone']})")
                if row["email"]:
                    st.write(f"• **E-mail:** [{row['email']}](mailto:{row['email']})")
                if row["address"]:
                    st.write(f"• **Adres:** {row['address']}")
                if not any([row["phone"], row["email"], row["address"]]):
                    st.caption("Brak danych kontaktowych")

                st.write(f"**Ostatnia wizyta:** {row['last_visit']}")
                st.write(
                    f"**Przypisany cennik:** 🏷️ `{row['price_list'] if row['price_list'] else 'Brak'}`"
                )

                if row["price_list"]:
                    c.execute(
                        "SELECT details FROM price_lists WHERE title = ?",
                        (row["price_list"],),
                    )
                    pl_res = c.fetchone()
                    if pl_res:
                        with st.popover("👁️ Pokaż cennik"):
                            st.caption(f"Cennik: {row['price_list']}")
                            st.text(pl_res[0])

                st.markdown("---")
                st.markdown("📈 **Statystyki zakupy/zwroty:**")

                net_val = row["net_val"] or 0.0
                bought_val = row["total_bought_val"] or 0.0
                returned_val = row["total_returned_val"] or 0.0
                ret_rate = row["return_rate"] or 0.0

                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("Wartość dostawy (Netto)", f"{net_val:,.2f} zł")
                    st.metric("Zakupy ogółem", f"{bought_val:,.2f} zł")
                with col_b:
                    st.metric("% Zwrotów", f"{ret_rate:.1f}%")
                    st.metric("Zwroty ogółem", f"{returned_val:,.2f} zł")

                df_items = pd.read_sql_query(
                    "SELECT item_name as Produkt, bought_qty as Zakup_Ilość, bought_val as Zakup_Kwota, returned_qty as Zwrot_Ilość, returned_val as Zwrot_Kwota, net_val as Wartość_Netto FROM purchases WHERE client_name = ?",
                    conn,
                    params=(row["name"],),
                )
                if not df_items.empty:
                    with st.popover("📦 Pokaż zakupiony asortyment"):
                        st.dataframe(df_items, use_container_width=True)

                st.markdown("---")
                st.write("📝 **Prywatne uwagi / Historia wizyt:**")
                st.text(
                    row["notes"] if row["notes"] else "Brak wpisanych uwag"
                )

                # Podgląd historii zamówień
                df_orders = pd.read_sql_query(
                    "SELECT order_details, created_at FROM orders WHERE client_name = ? ORDER BY id DESC LIMIT 3",
                    conn,
                    params=(row["name"],),
                )
                if not df_orders.empty:
                    with st.popover("✉️ Historia wysłanych zamówień"):
                        for _, ord_r in df_orders.iterrows():
                            st.caption(f"Wysłano: {ord_r['created_at']}")
                            st.text(ord_r["order_details"])
                            st.markdown("---")
    else:
        st.info("Baza jest pusta. Dodaj pierwszego klienta.")

# --- TAB 2: NOWA WIZYTA I ZAMÓWIENIE ---
with tab2:
    st.subheader("➕ Nowa Wizyta i Zamówienie")
    df_clients = pd.read_sql_query("SELECT id, name FROM clients", conn)

    if not df_clients.empty:
        with st.form("visit_and_order_form", clear_on_submit=False):
            selected_client = st.selectbox(
                "Wybierz klienta", df_clients["name"]
            )
            visit_date = st.date_input("Data wizyty", datetime.now())

            st.markdown("---")
            st.markdown("### 🛒 1. Zamówienie (Wysyłane do Piekarni)")
            order_text = st.text_area(
                "Treść zamówienia na e-mail:",
                placeholder="Np.\nChleb Hetmański - 30 szt.\nBułka kajzerka - 100 szt.",
                height=120,
            )

            st.markdown("---")
            st.markdown("### 🔒 2. Prywatne uwagi (Zostają tylko w CRM)")
            private_notes = st.text_area(
                "Twoje prywatne notatki z wizyty:",
                placeholder="Np. Rozmowa z kierownikiem, prośba o lepsze wyeksponowanie chleba.",
                height=100,
            )

            st.markdown("---")
            st.caption(
                "Do wysyłki e-maila wymagane jest 16-literowe Hasło Aplikacji Gmail:"
            )
            app_pass = st.text_input(
                "Hasło Aplikacji Gmail (jacek.lapot@gmail.com):",
                type="password",
            )

            submit_all = st.form_submit_button(
                "💾 Zapisz wizytę i wyślij zamówienie"
            )

            if submit_all:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

                c.execute(
                    "SELECT notes FROM clients WHERE name = ?",
                    (selected_client,),
                )
                old_notes = c.fetchone()[0] or ""
                note_entry = f"[{visit_date}] {private_notes}".strip()
                updated_notes = (
                    f"{note_entry}\n{old_notes}"
                    if private_notes
                    else old_notes
                )

                c.execute(
                    "UPDATE clients SET last_visit = ?, notes = ? WHERE name = ?",
                    (visit_date, updated_notes, selected_client),
                )

                if order_text.strip():
                    if not app_pass:
                        st.error(
                            "Notatki zapisano, ale zamówienie NIE zostało wysłane – brak Hasła Aplikacji Gmail!"
                        )
                    else:
                        subject = f"Zamówienie: {selected_client} - {visit_date}"
                        body = (
                            f"Zamówienie złożone dla klienta: {selected_client}\n"
                            f"Data wizyty/zamówienia: {visit_date}\n"
                            f"Przedstawiciel: jacek.lapot@gmail.com\n\n"
                            f"--- TREŚĆ ZAMÓWIENIA ---\n"
                            f"{order_text}\n\n"
                            f"Wysłano z aplikacji CRM."
                        )
                        try:
                            send_email_via_gmail(
                                sender_email="jacek.lapot@gmail.com",
                                app_password=app_pass,
                                recipient_email="piekarnia.zamowienia@spolemkielce.pl",
                                subject=subject,
                                body_text=body,
                            )
                            c.execute(
                                "INSERT INTO orders (client_name, order_details, created_at, status) VALUES (?, ?, ?, ?)",
                                (
                                    selected_client,
                                    order_text,
                                    now_str,
                                    "Wysłano e-mail",
                                ),
                            )
                            st.success(
                                f"Zapisano wizytę i wysłano zamówienie dla {selected_client}!"
                            )
                        except Exception as err:
                            st.error(f"Błąd podczas wysyłki e-maila: {err}")
                else:
                    st.success(
                        f"Zapisano prywatną notatkę z wizyty dla {selected_client} (brak zamówienia do wysłania)."
                    )

                conn.commit()
                st.rerun()
    else:
        st.warning("Najpierw dodaj klienta w zakładce 'Nowy klient'!")

# --- TAB 3: IMPORT EXCELA ---
with tab3:
    st.subheader("📊 Wczytaj dzienny raport z Excela")
    report_date = st.date_input("Data raportu", datetime.now())
    uploaded_file = st.file_uploader(
        "Wybierz plik Excel (.xlsx lub .xls)", type=["xlsx", "xls"]
    )

    if uploaded_file is not None:
        try:
            excel_df = pd.read_excel(uploaded_file)
            st.write("Podgląd wczytanych danych:")
            st.dataframe(excel_df.head(5), use_container_width=True)

            st.markdown("#### Dopasowanie kolumn:")
            cols = ["-- Wybierz kolumnę --"] + list(excel_df.columns)

            col1, col2 = st.columns(2)
            with col1:
                c_client = st.selectbox("Nazwa Klienta", cols)
                c_item = st.selectbox("Asortyment / Produkt", cols)
                c_b_qty = st.selectbox("Ilość zakupiona", cols)
                c_b_val = st.selectbox("Wartość zakupów (zł)", cols)
            with col2:
                c_r_qty = st.selectbox("Ilość zwrócona", cols)
                c_r_val = st.selectbox("Wartość zwrotów (zł)", cols)

            if st.button("🚀 Przetwórz i przypisz do klientów"):
                if c_client == "-- Wybierz kolumnę --":
                    st.error("Musisz wskazać co najmniej kolumnę z Klientem!")
                else:
                    processed_count = 0
                    for _, r in excel_df.iterrows():
                        client_name = str(r[c_client]).strip()
                        item_name = (
                            str(r[c_item])
                            if c_item != "-- Wybierz kolumnę --"
                            else "Ogólne"
                        )
                        b_qty = (
                            float(r[c_b_qty])
                            if c_b_qty != "-- Wybierz kolumnę --"
                            and pd.notnull(r[c_b_qty])
                            else 0.0
                        )
                        b_val = (
                            float(r[c_b_val])
                            if c_b_val != "-- Wybierz kolumnę --"
                            and pd.notnull(r[c_b_val])
                            else 0.0
                        )
                        r_qty = (
                            float(r[c_r_qty])
                            if c_r_qty != "-- Wybierz kolumnę --"
                            and pd.notnull(r[c_r_qty])
                            else 0.0
                        )
                        r_val = (
                            float(r[c_r_val])
                            if c_r_val != "-- Wybierz kolumnę --"
                            and pd.notnull(r[c_r_val])
                            else 0.0
                        )

                        net_item_val = b_val - r_val

                        c.execute(
                            """
                            INSERT INTO purchases (client_name, item_name, bought_qty, bought_val, returned_qty, returned_val, net_val, report_date)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                client_name,
                                item_name,
                                b_qty,
                                b_val,
                                r_qty,
                                r_val,
                                net_item_val,
                                report_date,
                            ),
                        )

                        c.execute(
                            "SELECT COUNT(*) FROM clients WHERE name = ?",
                            (client_name,),
                        )
                        if c.fetchone()[0] == 0:
                            c.execute(
                                "INSERT INTO clients (name, category, last_visit) VALUES (?, ?, ?)",
                                (
                                    client_name,
                                    "🥉 Brązowy",
                                    datetime.now().date(),
                                ),
                            )

                        processed_count += 1

                    c.execute("SELECT DISTINCT client_name FROM purchases")
                    all_clients_in_p = c.fetchall()

                    for (cl_n,) in all_clients_in_p:
                        c.execute(
                            "SELECT SUM(bought_val), SUM(returned_val) FROM purchases WHERE client_name = ?",
                            (cl_n,),
                        )
                        sum_b, sum_r = c.fetchone()
                        sum_b = sum_b or 0.0
                        sum_r = sum_r or 0.0
                        net = sum_b - sum_r
                        ret_rate = (sum_r / sum_b * 100) if sum_b > 0 else 0.0

                        c.execute(
                            """
                            UPDATE clients 
                            SET total_bought_val = ?, total_returned_val = ?, net_val = ?, return_rate = ?, last_report_date = ?
                            WHERE name = ?
                        """,
                            (sum_b, sum_r, net, ret_rate, report_date, cl_n),
                        )

                    conn.commit()
                    st.success(
                        f"Pomyślnie przetworzono {processed_count} pozycji z pliku Excel!"
                    )
                    st.rerun()

        except Exception as e:
            st.error(f"Błąd podczas odczytu pliku Excel: {e}")

# --- TAB 4: DODAJ NOWEGO KLIENTA ---
with tab4:
    st.subheader("Formularz nowego klienta")

    price_lists_df = pd.read_sql_query("SELECT title FROM price_lists", conn)
    available_price_lists = (
        price_lists_df["title"].tolist() if not price_lists_df.empty else []
    )

    with st.form("add_client_form", clear_on_submit=True):
        name = st.text_input("Nazwa firmy / Imię i nazwisko *")
        category = st.selectbox(
            "Priorytet", ["🥇 Złoty", "🥈 Srebrny", "🥉 Brązowy"]
        )

        st.markdown("---")
        st.markdown("📞 **Dane kontaktowe (opcjonalnie)**")
        phone = st.text_input("Numer telefonu", placeholder="np. 600111222")
        email = st.text_input("Adres e-mail", placeholder="np. sklep@klient.pl")
        address = st.text_input(
            "Adres / Lokalizacja", placeholder="np. ul. Główna 5, Kielce"
        )

        st.markdown("---")
        selected_price_list = st.selectbox(
            "Przypisz cennik", available_price_lists
        )
        first_visit = st.date_input("Data pierwszej wizyty", datetime.now())
        first_note = st.text_area("Pierwsza notatka (opcjonalnie)")
        submit_new = st.form_submit_button("Dodaj do bazy")

        if submit_new and name:
            initial_note = (
                f"[{first_visit}] {first_note}" if first_note else ""
            )
            try:
                c.execute(
                    """
                    INSERT INTO clients (name, category, phone, email, address, price_list, last_visit, notes) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        category,
                        phone,
                        email,
                        address,
                        selected_price_list,
                        first_visit,
                        initial_note,
                    ),
                )
                conn.commit()
                st.success(f"Dodano klienta: {name}")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Klient o takiej nazwie już istnieje!")

# --- TAB 5: ZARZĄDZANIE CENNIKAMI ---
with tab5:
    st.subheader("🏷️ Przegląd i dodawanie cenników")

    df_pl = pd.read_sql_query("SELECT * FROM price_lists", conn)

    if not df_pl.empty:
        for _, pl_row in df_pl.iterrows():
            with st.expander(f"Cennik: {pl_row['title']}"):
                st.text(pl_row["details"])

    st.markdown("---")
    st.subheader("Dodaj nowy cennik")
    with st.form("add_pl_form", clear_on_submit=True):
        pl_title = st.text_input("Nazwa cennika (np. Hurtowy 2026)")
        pl_details = st.text_area(
            "Treść cennika / Pozycje i ceny",
            placeholder="Np.\nProdukt X - 50 zł\nProdukt Y - 120 zł",
        )
        submit_pl = st.form_submit_button("Zapisz cennik")

        if submit_pl and pl_title:
            c.execute(
                "INSERT INTO price_lists (title, details) VALUES (?, ?)",
                (pl_title, pl_details),
            )
            conn.commit()
            st.success(f"Dodano cennik: {pl_title}")
            st.rerun()

from datetime import datetime, timedelta
import calendar
import email.mime.multipart
import email.mime.text
import smtplib
import sqlite3
import pandas as pd
import streamlit as st

# --- USTAWIENIA HASŁA DOSTĘPU ---
PIN_CRM = "1136"  # Kod dostępu

# --- KONFIGURACJA STRONY POD TELEFON ---
st.set_page_config(
    page_title="Chlebownik",
    page_icon="🍞",
    layout="centered",
)

# --- MECHANIZM LOGOWANIA ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🍞 Chlebownik")
    st.subheader("Dostęp zastrzeżony")

    pin_input = st.text_input("Wprowadź kod dostępu (PIN):", type="password")
    if st.button("Zaloguj"):
        if pin_input == PIN_CRM:
            st.session_state["authenticated"] = True
            st.success("Dostęp przyznany!")
            st.rerun()
        else:
            st.error("Błędny kod dostępu!")
    st.stop()

# --- BAZA DANYCH ---
conn = sqlite3.connect("crm.db", check_same_thread=False)
c = conn.cursor()

# Tabela klientów
c.execute(
    """
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        category TEXT NOT NULL,
        chain_name TEXT,
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
        report_date DATE,
        report_type TEXT DEFAULT 'Dzienny',
        report_start_date DATE,
        report_end_date DATE
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

# Migracja kolumn dla istniejących baz
for column, col_type in [
    ("chain_name", "TEXT"),
    ("phone", "TEXT"),
    ("email", "TEXT"),
    ("address", "TEXT"),
    ("total_bought_val", "REAL DEFAULT 0.0"),
    ("total_returned_val", "REAL DEFAULT 0.0"),
    ("net_val", "REAL DEFAULT 0.0"),
    ("return_rate", "REAL DEFAULT 0.0"),
    ("last_report_date", "DATE"),
    ("price_list", "TEXT"),
    ("report_type", "TEXT DEFAULT 'Dzienny'"),
    ("report_start_date", "DATE"),
    ("report_end_date", "DATE"),
]:
    try:
        c.execute(f"ALTER TABLE clients ADD COLUMN {column} {col_type}")
        conn.commit()
    except sqlite3.OperationalError:
        pass

for column, col_type in [
    ("report_type", "TEXT DEFAULT 'Dzienny'"),
    ("report_start_date", "DATE"),
    ("report_end_date", "DATE"),
]:
    try:
        c.execute(f"ALTER TABLE purchases ADD COLUMN {column} {col_type}")
        conn.commit()
    except sqlite3.OperationalError:
        pass


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

# Przycisk wylogowania w panelu bocznym
with st.sidebar:
    st.write("👤 **Sesja aktywna**")
    if st.button("🚪 Wyloguj"):
        st.session_state["authenticated"] = False
        st.rerun()

# --- ZAKŁADKI ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "📋 Klienci",
        "➕ Nowa wizyta",
        "📊 Raport Excel",
        "👤 Nowy klient",
        "🏷️️ Cenniki",
    ]
)

# Pobranie listy cenników
price_lists_df = pd.read_sql_query("SELECT title FROM price_lists", conn)
available_price_lists = (
    ["Brak"] + price_lists_df["title"].tolist() if not price_lists_df.empty else ["Brak"]
)

# --- TAB 1: LISTA KLIENTÓW ---
with tab1:
    df = pd.read_sql_query("SELECT * FROM clients", conn)

    if not df.empty:
        df["last_visit_clean"] = pd.to_datetime(df["last_visit"], errors="coerce")
        today = pd.to_datetime("today")
        df["Dni od wizyty"] = (today - df["last_visit_clean"]).dt.days.fillna(0).astype(int)

        col_filter, col_sort = st.columns(2)
        with col_filter:
            category_filter = st.multiselect(
                "Filtruj priorytet:",
                ["🥇 Złoty", "🥈 Srebrny", "🥉 Brązowy"],
                default=["🥇 Złoty", "🥈 Srebrny", "🥉 Brązowy"],
            )

        with col_sort:
            sort_option = st.selectbox(
                "Sortuj według:",
                [
                    "Dni od wizyty (od najdawniejszych)",
                    "Dni od wizyty (od najnowszych)",
                    "Nazwa klienta (A-Z)",
                ],
            )

        filtered_df = df[df["category"].isin(category_filter)]

        if sort_option == "Dni od wizyty (od najdawniejszych)":
            filtered_df = filtered_df.sort_values(by="Dni od wizyty", ascending=False)
        elif sort_option == "Dni od wizyty (od najnowszych)":
            filtered_df = filtered_df.sort_values(by="Dni od wizyty", ascending=True)
        elif sort_option == "Nazwa klienta (A-Z)":
            filtered_df = filtered_df.sort_values(by="name", ascending=True)

        st.subheader("Lista Klientów")

        for _, row in filtered_df.iterrows():
            color = (
                "🔴"
                if row["Dni od wizyty"] > 30
                else ("🟡" if row["Dni od wizyty"] > 14 else "🟢")
            )

            chain_str = f" [{row['chain_name']}]" if row.get("chain_name") else ""
            with st.expander(
                f"{color} {row['name']}{chain_str} ({row['category']}) — {row['Dni od wizyty']} dni"
            ):
                # Dane kontaktowe
                st.markdown("📞 **Dane kontaktowe:**")
                if row.get("chain_name"):
                    st.write(f"• **Nazwa sieci:** {row['chain_name']}")
                if row["phone"]:
                    st.write(f"• **Telefon:** [{row['phone']}](tel:{row['phone']})")
                if row["email"]:
                    st.write(f"• **E-mail:** [{row['email']}](mailto:{row['email']})")
                if row["address"]:
                    st.write(f"• **Adres:** {row['address']}")
                if not any([row.get("chain_name"), row["phone"], row["email"], row["address"]]):
                    st.caption("Brak danych kontaktowych")

                st.write(f"**Ostatnia wizyta:** {row['last_visit']}")
                st.write(
                    f"**Przypisany cennik:** 🏷️ `{row['price_list'] if row['price_list'] else 'Brak'}`"
                )

                if row["price_list"] and row["price_list"] != "Brak":
                    c.execute(
                        "SELECT details FROM price_lists WHERE title = ?",
                        (row["price_list"],),
                    )
                    pl_res = c.fetchone()
                    if pl_res:
                        with st.popover("👁️ Pokaż cennik"):
                            st.caption(f"Cennik: {row['price_list']}")
                            st.text(pl_res[0])

                # --- SEKCJA EDYCYJNA ORAZ USUWANIA ---
                with st.popover("✏️ Edytuj / Usuń klienta"):
                    st.markdown(f"#### Edycja: {row['name']}")
                    with st.form(key=f"edit_form_{row['id']}"):
                        new_name = st.text_input("Nazwa klienta", value=row["name"])
                        new_chain = st.text_input("Nazwa sieci", value=row.get("chain_name") or "")

                        cat_options = ["🥇 Złoty", "🥈 Srebrny", "🥉 Brązowy"]
                        cat_idx = cat_options.index(row["category"]) if row["category"] in cat_options else 0
                        new_cat = st.selectbox("Priorytet", cat_options, index=cat_idx)

                        new_phone = st.text_input("Telefon", value=row["phone"] or "")
                        new_email = st.text_input("E-mail", value=row["email"] or "")
                        new_address = st.text_input("Adres", value=row["address"] or "")

                        current_pl = row["price_list"] if row["price_list"] in available_price_lists else "Brak"
                        pl_idx = available_price_lists.index(current_pl) if current_pl in available_price_lists else 0
                        new_pl = st.selectbox("Cennik", available_price_lists, index=pl_idx)

                        save_changes = st.form_submit_button("💾 Zapisz zmiany")

                        if save_changes:
                            try:
                                if new_name != row["name"]:
                                    c.execute("UPDATE purchases SET client_name = ? WHERE client_name = ?", (new_name, row["name"]))
                                    c.execute("UPDATE orders SET client_name = ? WHERE client_name = ?", (new_name, row["name"]))

                                c.execute(
                                    """
                                    UPDATE clients 
                                    SET name = ?, category = ?, chain_name = ?, phone = ?, email = ?, address = ?, price_list = ?
                                    WHERE id = ?
                                    """,
                                    (new_name, new_cat, new_chain, new_phone, new_email, new_address, new_pl if new_pl != "Brak" else None, row["id"])
                                )
                                conn.commit()
                                st.success("Pomyślnie zaktualizowano dane klienta!")
                                st.rerun()
                            except sqlite3.IntegrityError:
                                st.error("Klient o takiej nazwie już istnieje!")

                    st.markdown("---")
                    st.markdown("🚨 **Usuwanie kartoteki:**")
                    confirm_delete = st.checkbox(f"Potwierdzam chęć usunięcia klienta {row['name']}", key=f"confirm_del_{row['id']}")
                    if st.button("🗑️ Usuń kartotekę klienta", key=f"delete_btn_{row['id']}", type="primary"):
                        if confirm_delete:
                            c.execute("DELETE FROM clients WHERE id = ?", (row["id"],))
                            c.execute("DELETE FROM purchases WHERE client_name = ?", (row["name"],))
                            c.execute("DELETE FROM orders WHERE client_name = ?", (row["name"],))
                            conn.commit()
                            st.success(f"Usunięto kartotekę klienta: {row['name']}")
                            st.rerun()
                        else:
                            st.warning("Zaznacz pole potwierdzenia, aby usunąć klienta.")

                st.markdown("---")
                st.markdown("📈 **Statystyki zakupy/zwroty:**")

                # WYBÓR OKRESU RAPORTOWANIA DLA KARTOTEKI
                period_choice = st.selectbox(
                    "📅 Wybierz okres raportu:",
                    ["Wszystko", "Ostatni 1 dzień", "Ostatni tydzień (7 dni)", "Ostatni miesiąc (30 dni)"],
                    key=f"period_sel_{row['id']}"
                )

                query_p = "SELECT * FROM purchases WHERE client_name = ?"
                params_p = [row["name"]]

                if period_choice == "Ostatni 1 dzień":
                    date_limit = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                    query_p += " AND (report_end_date >= ? OR report_date >= ?)"
                    params_p.extend([date_limit, date_limit])
                elif period_choice == "Ostatni tydzień (7 dni)":
                    date_limit = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                    query_p += " AND (report_end_date >= ? OR report_date >= ?)"
                    params_p.extend([date_limit, date_limit])
                elif period_choice == "Ostatni miesiąc (30 dni)":
                    date_limit = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
                    query_p += " AND (report_end_date >= ? OR report_date >= ?)"
                    params_p.extend([date_limit, date_limit])

                df_client_purchases = pd.read_sql_query(query_p, conn, params=params_p)

                if not df_client_purchases.empty:
                    bought_val = df_client_purchases["bought_val"].sum()
                    returned_val = df_client_purchases["returned_val"].sum()
                    net_val = bought_val - returned_val
                    ret_rate = (returned_val / bought_val * 100) if bought_val > 0 else 0.0

                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.metric("Wartość dostawy (Netto)", f"{net_val:,.2f} zł")
                        st.metric("Zakupy ogółem", f"{bought_val:,.2f} zł")
                    with col_b:
                        st.metric("% Zwrotów", f"{ret_rate:.1f}%")
                        st.metric("Zwroty ogółem", f"{returned_val:,.2f} zł")

                    df_items_display = df_client_purchases.groupby("item_name").agg({
                        "bought_qty": "sum",
                        "bought_val": "sum",
                        "returned_qty": "sum",
                        "returned_val": "sum",
                        "net_val": "sum"
                    }).reset_index().rename(columns={
                        "item_name": "Produkt",
                        "bought_qty": "Zakup_Ilość",
                        "bought_val": "Zakup_Kwota",
                        "returned_qty": "Zwrot_Ilość",
                        "returned_val": "Zwrot_Kwota",
                        "net_val": "Wartość_Netto"
                    })

                    with st.popover("📦 Pokaż zakupiony asortyment"):
                        st.dataframe(df_items_display, use_container_width=True)
                else:
                    st.caption("Brak danych o zakupach/zwrotach dla wybranego okresu.")

                st.markdown("---")
                st.write("📝 **Prywatne uwagi / Historia wizyt:**")
                st.text(
                    row["notes"] if row["notes"] else "Brak wpisanych uwag"
                )

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
                visit_date_str = visit_date.strftime("%Y-%m-%d")

                c.execute(
                    "SELECT notes FROM clients WHERE name = ?",
                    (selected_client,),
                )
                old_notes = c.fetchone()[0] or ""
                note_entry = f"[{visit_date_str}] {private_notes}".strip()
                updated_notes = (
                    f"{note_entry}\n{old_notes}"
                    if private_notes
                    else old_notes
                )

                c.execute(
                    "UPDATE clients SET last_visit = ?, notes = ? WHERE name = ?",
                    (visit_date_str, updated_notes, selected_client),
                )

                if order_text.strip():
                    if not app_pass:
                        st.error(
                            "Notatki zapisano, ale zamówienie NIE zostało wysłane – brak Hasła Aplikacji Gmail!"
                        )
                    else:
                        subject = f"Zamówienie: {selected_client} - {visit_date_str}"
                        body = (
                            f"Hej,
                            f
                            f"proszę o wprowadzenie jak poniżej:
                            f" "
                            f"{selected_client}\n:"
                            f" "
                            f"{order_text}\n\n"
                            f" "
                            f" "
                            f"Dziękuję :)"
                            f" "
                            f" "
                            f" "                    
                            f"Pozdrawiam"                    
                            f"Jacek Łapot"
                        )
                        try:
                            send_email_via_gmail(
                                sender_email="jacek.lapot@gmail.com",
                                app_password=app_pass,
                                recipient_email="jacek.lapot@gmail.com",
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

# --- TAB 3: IMPORT EXCELA (RAPORTY DZIENNE, TYGODNIOWE, MIESIĘCZNE) ---
with tab3:
    st.subheader("📊 Wczytaj raport ze sprzedaży z Excela")

    report_type = st.radio(
        "Wybierz typ raportu:",
        ["Dzienny", "Tygodniowy", "Miesięczny"],
        horizontal=True
    )

    if report_type == "Dzienny":
        report_date = st.date_input("Data raportu dziennego", datetime.now())
        start_d = report_date.strftime("%Y-%m-%d")
        end_d = start_d
    elif report_type == "Tygodniowy":
        selected_d = st.date_input("Wybierz dowolny dzień z tygodnia", datetime.now())
        monday = selected_d - timedelta(days=selected_d.weekday())
        sunday = monday + timedelta(days=6)
        st.info(f"Tydzień: **{monday.strftime('%Y-%m-%d')}** do **{sunday.strftime('%Y-%m-%d')}**")
        start_d = monday.strftime("%Y-%m-%d")
        end_d = sunday.strftime("%Y-%m-%d")
    else: # Miesięczny
        col_m, col_y = st.columns(2)
        with col_m:
            month_num = st.selectbox("Miesiąc", list(range(1, 13)), index=datetime.now().month - 1)
        with col_y:
            year_num = st.number_input("Rok", value=datetime.now().year, step=1)
        
        last_day = calendar.monthrange(year_num, month_num)[1]
        start_d = f"{year_num:04d}-{month_num:02d}-01"
        end_d = f"{year_num:04d}-{month_num:02d}-{last_day:02d}"
        st.info(f"Miesiąc: **{start_d}** do **{end_d}**")

    uploaded_file = st.file_uploader(
        "Wybierz plik Excel (.xlsx lub .xls)", type=["xlsx", "xls"], key="excel_sales"
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
                        if not client_name or client_name == "nan":
                            continue

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
                            INSERT INTO purchases (
                                client_name, item_name, bought_qty, bought_val, returned_qty, returned_val, net_val, report_date, report_type, report_start_date, report_end_date
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                client_name,
                                item_name,
                                b_qty,
                                b_val,
                                r_qty,
                                r_val,
                                net_item_val,
                                end_d,
                                report_type,
                                start_d,
                                end_d,
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
                                    end_d,
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
                            (sum_b, sum_r, net, ret_rate, end_d, cl_n),
                        )

                    conn.commit()
                    st.success(
                        f"Pomyślnie przetworzono {processed_count} pozycji z raportu ({report_type.lower()})!"
                    )
                    st.rerun()

        except Exception as e:
            st.error(f"Błąd podczas odczytu pliku Excel: {e}")

# --- TAB 4: DODAJ NOWEGO KLIENTA / IMPORT KLIENTÓW ---
with tab4:
    st.subheader("👤 Zgłaszanie nowych klientów")

    mode = st.radio("Wybierz sposób dodania:", ["Wpis ręczny (jeden klient)", "📥 Masowy import z pliku Excel"], horizontal=True)

    if mode == "Wpis ręczny (jeden klient)":
        with st.form("add_client_form", clear_on_submit=True):
            name = st.text_input("Nazwa firmy / Imię i nazwisko *")
            chain_name = st.text_input("Nazwa sieci (opcjonalnie)", placeholder="np. Społem, Lewiatan, Biedronka")
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
                first_visit_str = first_visit.strftime("%Y-%m-%d")
                initial_note = (
                    f"[{first_visit_str}] {first_note}" if first_note else ""
                )
                try:
                    c.execute(
                        """
                        INSERT INTO clients (name, category, chain_name, phone, email, address, price_list, last_visit, notes) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            name,
                            category,
                            chain_name,
                            phone,
                            email,
                            address,
                            selected_price_list if selected_price_list != "Brak" else None,
                            first_visit_str,
                            initial_note,
                        ),
                    )
                    conn.commit()
                    st.success(f"Dodano klienta: {name}")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Klient o takiej nazwie już istnieje!")

    else:
        st.markdown("#### 📁 Wczytaj plik Excel z bazą klientów")
        client_file = st.file_uploader(
            "Wybierz plik z kartotekami (.xlsx lub .xls)", type=["xlsx", "xls"], key="excel_clients"
        )

        if client_file is not None:
            try:
                c_df = pd.read_excel(client_file)
                st.write("Podgląd arkusza:")
                st.dataframe(c_df.head(5), use_container_width=True)

                st.markdown("#### Mapowanie kolumn z Excela na dane w CRM:")
                excel_cols = ["-- Brak / Nie przypisuj --"] + list(c_df.columns)

                col_x, col_y = st.columns(2)
                with col_x:
                    col_name = st.selectbox("Nazwa Klienta / Firmy *", list(c_df.columns))
                    col_chain = st.selectbox("Nazwa sieci", excel_cols)
                    col_cat = st.selectbox("Priorytet / Kategoria", excel_cols)
                    col_phone = st.selectbox("Numer telefonu", excel_cols)
                with col_y:
                    col_email = st.selectbox("E-mail", excel_cols)
                    col_addr = st.selectbox("Adres", excel_cols)
                    col_pl = st.selectbox("Cennik", excel_cols)
                    col_visit = st.selectbox("Data wizyty", excel_cols)
                    col_notes = st.selectbox("Uwagi / Notatka", excel_cols)

                if st.button("🚀 Utwórz kartoteki klientów"):
                    added_cnt = 0
                    updated_cnt = 0

                    for _, r in c_df.iterrows():
                        c_name = str(r[col_name]).strip()
                        if not c_name or c_name == "nan":
                            continue

                        c_chain = str(r[col_chain]).strip() if col_chain != "-- Brak / Nie przypisuj --" and pd.notnull(r[col_chain]) else None

                        c_cat = str(r[col_cat]).strip() if col_cat != "-- Brak / Nie przypisuj --" and pd.notnull(r[col_cat]) else "🥉 Brązowy"
                        if c_cat not in ["🥇 Złoty", "🥈 Srebrny", "🥉 Brązowy"]:
                            c_cat = "🥉 Brązowy"

                        c_phone = str(r[col_phone]).strip() if col_phone != "-- Brak / Nie przypisuj --" and pd.notnull(r[col_phone]) else None
                        c_email = str(r[col_email]).strip() if col_email != "-- Brak / Nie przypisuj --" and pd.notnull(r[col_email]) else None
                        c_addr = str(r[col_addr]).strip() if col_addr != "-- Brak / Nie przypisuj --" and pd.notnull(r[col_addr]) else None
                        c_pl = str(r[col_pl]).strip() if col_pl != "-- Brak / Nie przypisuj --" and pd.notnull(r[col_pl]) else None

                        v_date = str(r[col_visit]).split(" ")[0] if col_visit != "-- Brak / Nie przypisuj --" and pd.notnull(r[col_visit]) else datetime.now().strftime("%Y-%m-%d")
                        c_notes = str(r[col_notes]).strip() if col_notes != "-- Brak / Nie przypisuj --" and pd.notnull(r[col_notes]) else ""

                        c.execute("SELECT COUNT(*) FROM clients WHERE name = ?", (c_name,))
                        exists = c.fetchone()[0] > 0

                        if exists:
                            c.execute(
                                """
                                UPDATE clients 
                                SET category = COALESCE(?, category),
                                    chain_name = COALESCE(?, chain_name),
                                    phone = COALESCE(?, phone),
                                    email = COALESCE(?, email),
                                    address = COALESCE(?, address),
                                    price_list = COALESCE(?, price_list)
                                WHERE name = ?
                                """,
                                (c_cat, c_chain, c_phone, c_email, c_addr, c_pl, c_name)
                            )
                            updated_cnt += 1
                        else:
                            c.execute(
                                """
                                INSERT INTO clients (name, category, chain_name, phone, email, address, price_list, last_visit, notes)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (c_name, c_cat, c_chain, c_phone, c_email, c_addr, c_pl, v_date, c_notes)
                            )
                            added_cnt += 1

                    conn.commit()
                    st.success(f"Gotowe! Dodano {added_cnt} nowych kartotek, zaktualizowano {updated_cnt} istniejących.")
                    st.rerun()

            except Exception as ex:
                st.error(f"Błąd podczas odczytu pliku: {ex}")

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

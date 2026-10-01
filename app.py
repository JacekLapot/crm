from datetime import datetime, timedelta
import calendar
import email.mime.multipart
import email.mime.text
import smtplib
import sqlite3
import pandas as pd
import streamlit as st
import urllib.parse

# --- USTAWIENIA HASŁA DOSTĘPU ---
PIN_CRM = "1136"  # Kod dostępu

# --- KONFIGURACJA STRONY POD TELEFON ---
st.set_page_config(
    page_title="Chlebownik",
    page_icon="🍞",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# --- CUSTOM HEADER & MANIFEST PWA DLA TELEFONU Z SERVICE WORKEREM ---
st.markdown(
    """
    <head>
        <title>Chlebownik</title>
        <link rel="manifest" href="manifest.json">
        <meta name="apple-mobile-web-app-title" content="Chlebownik">
        <meta name="application-name" content="Chlebownik">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black">
        <meta name="theme-color" content="#0e1117">
        <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🍞</text></svg>">
        <link rel="apple-touch-icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🍞</text></svg>">
        <script>
            if ('serviceWorker' in navigator) {
                window.addEventListener('load', function() {
                    navigator.serviceWorker.register('/sw.js').then(function(registration) {
                        console.log('ServiceWorker registration successful');
                    }, function(err) {
                        console.log('ServiceWorker registration failed: ', err);
                    });
                });
            }
        </script>
    </head>
    <style>
        .stApp, [data-testid="stSidebar"] {
            background-color: #0e1117 !important;
            color: #ffffff !important;
        }
        h1, h2, h3, h4, h5, h6, p, label, span, div {
            color: #e0e0e0 !important;
        }
        .stExpander, [data-testid="stPopoverBody"], [data-testid="stForm"] {
            background-color: #161b22 !important;
            border: 1px solid #30363d !important;
            border-radius: 8px !important;
        }
        div[data-baseweb="input"], div[data-baseweb="select"], textarea {
            background-color: #21262d !important;
            color: #ffffff !important;
            border-color: #30363d !important;
        }
        button {
            background-color: #21262d !important;
            color: #ffffff !important;
            border: 1px solid #30363d !important;
        }
        button:hover {
            background-color: #30363d !important;
            border-color: #8b949e !important;
        }
        div[data-testid="stDataFrame"] {
            background-color: #161b22 !important;
        }
        div[data-testid="stMetricValue"] {
            color: #58a6ff !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
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
        sub_category TEXT DEFAULT 'Standardowy',
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

# Tabela produktów
c.execute(
    """
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        category TEXT,
        price REAL DEFAULT 0.0,
        description TEXT,
        image_url TEXT
    )
"""
)

# Tabela zakupów
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

# Tabela wizyt
c.execute(
    """
    CREATE TABLE IF NOT EXISTS visits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT NOT NULL,
        visit_date DATE NOT NULL,
        notes TEXT,
        order_details TEXT,
        created_at DATETIME
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

# Tabela zadań (To-Do)
c.execute(
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        due_date DATE,
        status TEXT DEFAULT 'Do zrobienia',
        updates TEXT,
        created_at DATETIME
    )
"""
)
conn.commit()

# Migracja kolumn
for column, col_type in [
    ("sub_category", "TEXT DEFAULT 'Standardowy'"),
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


def recalculate_client_scores():
    c.execute("SELECT name FROM clients")
    all_clients = c.fetchall()
    
    for (cl_name,) in all_clients:
        date_limit = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        c.execute(
            "SELECT SUM(net_val) FROM purchases WHERE client_name = ? AND report_date >= ?",
            (cl_name, date_limit)
        )
        res = c.fetchone()[0]
        monthly_val = res if res is not None else 0.0
        
        if monthly_val == 0.0:
            c.execute("SELECT net_val FROM clients WHERE name = ?", (cl_name,))
            r_net = c.fetchone()
            monthly_val = r_net[0] if r_net and r_net[0] else 0.0

        if monthly_val >= 7800.0:
            new_cat = "🥇 Złoty"
        elif monthly_val >= 3900.0:
            new_cat = "🥈 Srebrny"
        else:
            new_cat = "🥉 Brązowy"
            
        c.execute("UPDATE clients SET category = ? WHERE name = ?", (new_cat, cl_name))
    conn.commit()


def render_client_card(row, key_prefix="card"):
    today = pd.to_datetime("today")
    last_v_dt = pd.to_datetime(row["last_visit"], errors="coerce")
    days_from_visit = (today - last_v_dt).days if pd.notnull(last_v_dt) else 999
    days_str = f"{days_from_visit} dni temu" if days_from_visit != 999 else "Brak wizyt"
    
    color = (
        "⚪" if days_from_visit == 999 else
        ("🔴" if days_from_visit > 30 else ("🟡" if days_from_visit > 14 else "🟢"))
    )

    chain_str = f" [{row['chain_name']}]" if row.get("chain_name") else ""
    sub_cat_str = f" (Podgrupa: {row.get('sub_category', 'Standardowy')})" if row.get('sub_category') else ""
    st.markdown(f"### {color} {row['name']}{chain_str} ({row['category']}){sub_cat_str}")
    st.caption(f"Ostatnia wizyta: {row['last_visit'] if row['last_visit'] else 'Brak'} ({days_str})")

    st.markdown("📞 **Dane kontaktowe i lokalizacja:**")
    if row.get("chain_name"):
        st.write(f"• **Nazwa sieci:** {row['chain_name']}")
    
    if row["phone"]:
        phone_entries = str(row["phone"]).split("\n")
        for p_entry in phone_entries:
            p_entry_str = p_entry.strip()
            if p_entry_str:
                if ":" in p_entry_str:
                    owner_name, phone_num = p_entry_str.split(":", 1)
                    phone_clean = phone_num.strip()
                    st.write(f"• **{owner_name.strip()}:** [{phone_clean}](tel:{phone_clean})")
                else:
                    st.write(f"• **Telefon:** [{p_entry_str}](tel:{p_entry_str})")
    
    if row["email"]:
        st.write(f"• **E-mail:** [{row['email']}](mailto:{row['email']})")
    
    if row["address"]:
        st.write(f"• **Adres:** {row['address']}")
        encoded_address = urllib.parse.quote(row['address'])
        map_url = f"https://www.google.com/maps/search/?api=1&query={encoded_address}"
        st.markdown(f"🚗 [Otwórz trasę w mapach Google]({map_url})", unsafe_allow_html=True)
    else:
        st.caption("Brak adresu (brak możliwości wyznaczenia trasy)")

    if not any([row.get("chain_name"), row["phone"], row["email"], row["address"]]):
        st.caption("Brak danych kontaktowych")

    st.write(f"**Przypisany cennik:** 🏷️ `{row['price_list'] if row['price_list'] else 'Brak'}`")

    if row["price_list"] and row["price_list"] != "Brak":
        c.execute("SELECT details FROM price_lists WHERE title = ?", (row["price_list"],))
        pl_res = c.fetchone()
        if pl_res:
            with st.popover("👁 Pokaż cennik", key=f"{key_prefix}_pl_{row['id']}"):
                st.caption(f"Cennik: {row['price_list']}")
                st.text(pl_res[0])

    with st.popover("✏️ Edytuj / Usuń klienta", key=f"{key_prefix}_edit_{row['id']}"):
        st.markdown(f"#### Edycja: {row['name']}")
        with st.form(key=f"{key_prefix}_edit_form_{row['id']}"):
            new_name = st.text_input("Nazwa klienta", value=row["name"])
            new_chain = st.text_input("Nazwa sieci", value=row.get("chain_name") or "")

            cat_options = ["🥇 Złoty", "🥈 Srebrny", "🥉 Brązowy"]
            cat_idx = cat_options.index(row["category"]) if row["category"] in cat_options else 0
            new_cat = st.selectbox("Priorytet / Scoring", cat_options, index=cat_idx)

            sub_cat_options = ["Standardowy", "Nowy klient"]
            current_sub = row.get("sub_category", "Standardowy")
            sub_idx = sub_cat_options.index(current_sub) if current_sub in sub_cat_options else 0
            new_sub_cat = st.selectbox("Podgrupa w Klienci", sub_cat_options, index=sub_idx)

            new_phone = st.text_area(
                "Numery telefonów (Wpisz w osobnych liniach)", 
                value=row["phone"] or "",
                height=100
            )
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
                        c.execute("UPDATE visits SET client_name = ? WHERE client_name = ?", (new_name, row["name"]))
                        c.execute("UPDATE orders SET client_name = ? WHERE client_name = ?", (new_name, row["name"]))

                    c.execute(
                        """
                        UPDATE clients 
                        SET name = ?, category = ?, sub_category = ?, chain_name = ?, phone = ?, email = ?, address = ?, price_list = ?
                        WHERE id = ?
                        """,
                        (new_name, new_cat, new_sub_cat, new_chain, new_phone, new_email, new_address, new_pl if new_pl != "Brak" else None, row["id"])
                    )
                    conn.commit()
                    st.success("Pomyślnie zaktualizowano dane klienta!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Klient o takiej nazwie już istnieje!")

        st.markdown("---")
        st.markdown("🚨 **Usuwanie kartoteki:**")
        confirm_delete = st.checkbox(f"Potwierdzam chęć usunięcia klienta {row['name']}", key=f"{key_prefix}_confirm_del_{row['id']}")
        if st.button("🗑️ Usuń kartotekę klienta", key=f"{key_prefix}_del_btn_{row['id']}", type="primary"):
            if confirm_delete:
                c.execute("DELETE FROM clients WHERE id = ?", (row["id"],))
                c.execute("DELETE FROM purchases WHERE client_name = ?", (row["name"],))
                c.execute("DELETE FROM visits WHERE client_name = ?", (row["name"],))
                c.execute("DELETE FROM orders WHERE client_name = ?", (row["name"],))
                conn.commit()
                st.success(f"Usunięto kartotekę klienta: {row['name']}")
                st.rerun()
            else:
                st.warning("Zaznacz pole potwierdzenia, aby usunąć klienta.")

    st.markdown("---")
    st.markdown("📈 **Statystyki zakupy/zwroty:**")

    period_choice = st.selectbox(
        "📅 Wybierz okres raportu:",
        ["Wszystko", "Ostatni 1 dzień", "Ostatni tydzień (7 dni)", "Ostatni miesiąc (30 dni)"],
        key=f"{key_prefix}_period_{row['id']}"
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

        with st.popover("📦 Pokaż zakupiony asortyment", key=f"{key_prefix}_asort_{row['id']}"):
            st.dataframe(df_items_display, use_container_width=True)
    else:
        st.caption("Brak danych o zakupach/zwrotach dla wybranego okresu.")

    st.markdown("---")
    st.markdown("🗓️ **Historia wizyt i zamówień:**")

    df_visits = pd.read_sql_query(
        "SELECT id, visit_date, notes, order_details, created_at FROM visits WHERE client_name = ? ORDER BY id DESC",
        conn,
        params=(row["name"],),
    )

    if not df_visits.empty:
        for _, v_row in df_visits.iterrows():
            v_id = v_row["id"]
            v_date_str = v_row["visit_date"]
            with st.expander(f"📍 Wizyta: {v_date_str}"):
                if v_row["notes"]:
                    st.markdown("**📝 Uwagi:**")
                    st.write(v_row["notes"])
                else:
                    st.caption("Brak uwag z tej wizyty.")

                if v_row["order_details"]:
                    st.markdown("**🛒 Zamówienie:**")
                    st.code(v_row["order_details"], language="text")
                else:
                    st.caption("Brak złożonego zamówienia podczas tej wizyty.")
                
                if v_row["created_at"]:
                    st.caption(f"Zapisano: {v_row['created_at']}")

                st.markdown("---")
                confirm_del_v = st.checkbox(f"Potwierdzam usunięcie wizyty z dnia {v_date_str}", key=f"{key_prefix}_conf_del_visit_{v_id}")
                if st.button("🗑 Usuń tę wizytę", key=f"{key_prefix}_del_visit_btn_{v_id}", type="primary"):
                    if confirm_del_v:
                        c.execute("DELETE FROM visits WHERE id = ?", (v_id,))
                        
                        c.execute("SELECT MAX(visit_date) FROM visits WHERE client_name = ?", (row["name"],))
                        new_last_v = c.fetchone()[0]
                        c.execute("UPDATE clients SET last_visit = ? WHERE name = ?", (new_last_v, row["name"]))
                        
                        conn.commit()
                        st.success("Pomyślnie usunięto wizyty!")
                        st.rerun()
                    else:
                        st.warning("Zaznacz pole potwierdzenia, aby usunąć tę wizytę.")
    else:
        st.caption("Brak zarejestrowanych wizyt dla tego klienta.")


st.title("📱 Mobilny CRM")

# Przycisk wylogowania w panelu bocznym
with st.sidebar:
    st.write("👤 **Sesja aktywna**")
    if st.button("🚪 Wyloguj"):
        st.session_state["authenticated"] = False
        st.rerun()

# Pobranie listy cenników
price_lists_df = pd.read_sql_query("SELECT title FROM price_lists", conn)
available_price_lists = (
    ["Brak"] + price_lists_df["title"].tolist() if not price_lists_df.empty else ["Brak"]
)

# --- ZAKŁADKI ---
tab_home, tab_new_visit, tab_visits, tab_clients, tab_products, tab_excel, tab_pl = st.tabs(
    [
        "🏠 Strona główna",
        "➕ Nowa wizyta",
        "📋 Wizyty",
        "👥 Klienci",
        "📦 Produkty",
        "📊 Raport Excel",
        "🏷️️ Cenniki",
    ]
)

# --- TAB HOME: STRONA GŁÓWNA ---
with tab_home:
    st.subheader("🔍 Wyszukaj Klienta")
    
    all_clients_df = pd.read_sql_query("SELECT * FROM clients ORDER BY name ASC", conn)
    
    if not all_clients_df.empty:
        client_names = ["-- Wybierz lub wpisz nazwę klienta --"] + all_clients_df["name"].tolist()
        search_selection = st.selectbox(
            "Wpisz lub wybierz klienta z listy:",
            client_names,
            index=0
        )
        
        st.markdown("---")
        
        if search_selection != "-- Wybierz lub wpisz nazwę klienta --":
            selected_row = all_clients_df[all_clients_df["name"] == search_selection].iloc[0]
            render_client_card(selected_row, key_prefix="home")
        else:
            st.info("💡 Wpisz nazwę klienta w polu powyżej, aby wywołać jego kartotekę.")
    else:
        st.info("Baza klientów jest pusta. Dodaj pierwszego klienta w zakładce 'Klienci' (opcja ➕ Nowy klient).")

    # --- SEKCJA: NOTATKI / ZADANIA (TO-DO) Z HISTORIĄ ---
    st.markdown("---")
    
    # Nagłówek sekcji z odnośnikiem / przyciskiem "Historia zadań" po prawej stronie
    col_t_title, col_t_link = st.columns([3, 1])
    with col_t_title:
        st.subheader("📌 Zadania i Notatki (To-Do)")
    with col_t_link:
        if "show_task_history" not in st.session_state:
            st.session_state["show_task_history"] = False
            
        history_btn_label = "🔙 Powrót do zadań" if st.session_state["show_task_history"] else "📜 Historia zadań"
        if st.button(history_btn_label, key="toggle_task_history_btn"):
            st.session_state["show_task_history"] = not st.session_state["show_task_history"]
            st.rerun()

    # Jeśli włączony widok historii zadań
    if st.session_state["show_task_history"]:
        st.markdown("#### 📜 Archiwum / Historia zadań")
        st.caption("Wszystkie zadania zapisane w systemie (bieżące oraz ukończone):")
        
        df_all_tasks_history = pd.read_sql_query("SELECT * FROM tasks ORDER BY due_date DESC, id DESC", conn)
        
        if not df_all_tasks_history.empty:
            for _, h_row in df_all_tasks_history.iterrows():
                h_status = h_row["status"]
                h_status_icon = "✅" if h_status == "Zrobione" else "📌"
                with st.expander(f"{h_status_icon} {h_row['title']} (Termin: {h_row['due_date']}) — [{h_status}]"):
                    if h_row["description"]:
                        st.markdown(f"**Opis:** {h_row['description']}")
                    st.markdown(f"**Utworzono:** {h_row['created_at']}")
                    st.markdown("---")
                    st.markdown("**🔄 Historia / Aktualizacje:**")
                    if h_row["updates"]:
                        for upd_line in h_row["updates"].split("\n"):
                            if upd_line.strip():
                                st.write(f"• {upd_line}")
                    else:
                        st.caption("Brak wpisanych aktualizacji.")
                        
                    st.markdown("---")
                    confirm_del_task = st.checkbox(f"Potwierdź usunięcie zadania z archiwum", key=f"conf_del_hist_{h_row['id']}")
                    if st.button("🗑️ Usuń trwale zadanie", key=f"del_hist_btn_{h_row['id']}", type="primary"):
                        if confirm_del_task:
                            c.execute("DELETE FROM tasks WHERE id = ?", (h_row['id'],))
                            conn.commit()
                            st.success("Usunięto zadanie z bazy!")
                            st.rerun()
                        else:
                            st.warning("Zaznacz pole potwierdzenia.")
        else:
            st.info("Brak jakichkolwiek zadań w historii.")
            
    else:
        # Standardowy widok zadań aktywnych
        with st.expander("➕ Dodaj nowe zadanie"):
            with st.form("new_task_form", clear_on_submit=True):
                t_title = st.text_input("Tytuł zadania / krótkie polecenie *", placeholder="Np. Oddzwonić w sprawie reklamacji do sklepu X")
                t_desc = st.text_area("Szczegóły / Opis zadania (opcjonalnie)", placeholder="Dodatkowe informacje...")
                t_due = st.date_input("Termin realizacji", datetime.now())
                submit_task = st.form_submit_button("💾 Zapisz zadanie")

                if submit_task and t_title:
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                    due_str = t_due.strftime("%Y-%m-%d")
                    initial_update = f"[{now_str}] Utworzono zadanie."
                    
                    c.execute(
                        """
                        INSERT INTO tasks (title, description, due_date, status, updates, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (t_title, t_desc if t_desc.strip() else None, due_str, "Do zrobienia", initial_update, now_str)
                    )
                    conn.commit()
                    st.success("Dodano nowe zadanie!")
                    st.rerun()

        # Pobranie aktywnych zadań
        df_tasks = pd.read_sql_query("SELECT * FROM tasks WHERE status != 'Zrobione' ORDER BY due_date ASC, id DESC", conn)

        if not df_tasks.empty:
            st.caption("Rozwiń zadanie, aby dopisać aktualizację lub je oznaczyć jako wykonane:")
            for _, task_row in df_tasks.iterrows():
                t_id = task_row["id"]
                t_title_str = task_row["title"]
                t_due_date = task_row["due_date"]
                
                with st.expander(f"📌 {t_title_str} (Termin: {t_due_date})"):
                    if task_row["description"]:
                        st.markdown(f"**Opis:** {task_row['description']}")
                    
                    st.markdown("---")
                    st.markdown("**🔄 Historia / Aktualizacje:**")
                    if task_row["updates"]:
                        for upd_line in task_row["updates"].split("\n"):
                            if upd_line.strip():
                                st.write(f"• {upd_line}")
                    else:
                        st.caption("Brak wpisanych aktualizacji.")

                    st.markdown("---")
                    new_upd_text = st.text_input("Dopisz nową aktualizację co się wydarzyło:", key=f"upd_input_{t_id}", placeholder="Np. Klient prosił o telefon w poniedziałek")
                    
                    col_btn_upd, col_btn_done = st.columns(2)
                    with col_btn_upd:
                        if st.button("➕ Dodaj aktualizację", key=f"btn_add_upd_{t_id}"):
                            if new_upd_text.strip():
                                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                                formatted_update = f"[{now_str}] {new_upd_text.strip()}"
                                
                                existing_updates = task_row["updates"] if task_row["updates"] else ""
                                updated_history = f"{existing_updates}\n{formatted_update}".strip()
                                
                                c.execute("UPDATE tasks SET updates = ? WHERE id = ?", (updated_history, t_id))
                                conn.commit()
                                st.success("Dopisano aktualizację!")
                                st.rerun()
                            else:
                                st.warning("Wpisz treść aktualizacji.")

                    with col_btn_done:
                        if st.button("✅ Oznacz jako zrobione", key=f"btn_done_{t_id}", type="primary"):
                            # Zamiast usuwać, zmieniamy status na 'Zrobione', aby zachować w historii
                            c.execute("UPDATE tasks SET status = 'Zrobione' WHERE id = ?", (t_id,))
                            conn.commit()
                            st.success("Zadanie ukończone i przeniesione do historii!")
                            st.rerun()
        else:
            st.info("Brak aktywnych zadań. Dodaj nowe za pomocą przycisku powyżej.")

    # --- SEKCJA: ZŁOCI KLIENCI POSORTOWANI OD NAJDAWNIEJSZEJ WIZYTY ---
    st.markdown("---")
    st.subheader("🥇 Złoci Klienci (wymagający uwagi)")
    st.caption("Posortowani od klientów u których wizyta była najdawniej:")

    gold_df = all_clients_df[all_clients_df["category"] == "🥇 Złoty"].copy()

    if not gold_df.empty:
        gold_df["last_visit_clean"] = pd.to_datetime(gold_df["last_visit"], errors="coerce")
        today = pd.to_datetime("today")
        gold_df["Dni od wizyty"] = (today - gold_df["last_visit_clean"]).dt.days.fillna(999).astype(int)
        
        gold_df = gold_df.sort_values(by="Dni od wizyty", ascending=False)

        for _, g_row in gold_df.iterrows():
            g_days_str = f"{g_row['Dni od wizyty']} dni temu" if g_row['Dni od wizyty'] != 999 else "Brak wizyt"
            g_color = "🔴" if g_row['Dni od wizyty'] > 30 else ("🟡" if g_row['Dni od wizyty'] > 14 else "🟢")
            if g_row['Dni od wizyty'] == 999:
                g_color = "⚪"

            g_chain = f" [{g_row['chain_name']}]" if g_row.get("chain_name") else ""
            g_title = f"{g_color} {g_row['name']}{g_chain} — Ostatnia wizyta: {g_row['last_visit'] if g_row['last_visit'] else 'Brak'} ({g_days_str})"

            with st.expander(g_title):
                render_client_card(g_row, key_prefix=f"gold_{g_row['id']}")
    else:
        st.info("Brak klientów w kategorii 🥇 Złoty.")

# --- TAB 2: NOWA WIZYTA I ZAMÓWIENIE ---
with tab_new_visit:
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
                    """
                    INSERT INTO visits (client_name, visit_date, notes, order_details, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (selected_client, visit_date_str, private_notes if private_notes.strip() else None, order_text if order_text.strip() else None, now_str)
                )

                c.execute(
                    "UPDATE clients SET last_visit = ? WHERE name = ?",
                    (visit_date_str, selected_client),
                )

                if order_text.strip():
                    if not app_pass:
                        st.error(
                            "Wizytę zapisano w historii, ale zamówienie NIE zostało wysłane – brak Hasła Aplikacji Gmail!"
                        )
                    else:
                        subject = f"Zamówienie: {selected_client} - {visit_date_str}"
                        body = (
                            f"Zamówienie złożone dla klienta: {selected_client}\n"
                            f"Data wizyty/zamówienia: {visit_date_str}\n"
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
                        f"Zapisano wizytę dla {selected_client}."
                    )

                conn.commit()
                st.rerun()
    else:
        st.warning("Najpierw dodaj klienta w zakładce 'Klienci' (opcja ➕ Nowy klient)!")

# --- TAB 3: WIZYTY ---
with tab_visits:
    st.subheader("📋 Historia Wszystkich Wizyt")
    st.caption("Chronologiczna lista ostatnich wizyt u klientów:")

    df_all_visits = pd.read_sql_query(
        "SELECT id, client_name, visit_date, notes, order_details, created_at FROM visits ORDER BY visit_date DESC, id DESC",
        conn
    )

    if not df_all_visits.empty:
        for _, v_row in df_all_visits.iterrows():
            v_id = v_row["id"]
            v_client = v_row["client_name"]
            v_date = v_row["visit_date"]
            
            expander_title = f"📍 {v_client} — Data wizyty: {v_date}"
            
            with st.expander(expander_title):
                if v_row["notes"]:
                    st.markdown("**📝 Prywatne uwagi:**")
                    st.write(v_row["notes"])
                else:
                    st.caption("Brak prywatnych uwag z tej wizyty.")

                if v_row["order_details"]:
                    st.markdown("**🛒 Zamówienie:**")
                    st.code(v_row["order_details"], language="text")
                else:
                    st.caption("Brak złożonego zamówienia podczas tej wizyty.")
                
                if v_row["created_at"]:
                    st.caption(f"Zapisano w systemie: {v_row['created_at']}")

                st.markdown("---")
                confirm_del_v = st.checkbox(f"Potwierdzam usunięcie tej wizyty", key=f"tab_vis_conf_{v_id}")
                if st.button("🗑️️ Usuń tę wizytę", key=f"tab_vis_btn_{v_id}", type="primary"):
                    if confirm_del_v:
                        c.execute("DELETE FROM visits WHERE id = ?", (v_id,))
                        
                        c.execute("SELECT MAX(visit_date) FROM visits WHERE client_name = ?", (v_client,))
                        new_last_v = c.fetchone()[0]
                        c.execute("UPDATE clients SET last_visit = ? WHERE name = ?", (new_last_v, v_client))
                        
                        conn.commit()
                        st.success("Pomyślnie usunięto wizytę!")
                        st.rerun()
                    else:
                        st.warning("Zaznacz pole potwierdzenia, aby usunąć tę wizytę.")
    else:
        st.info("Brak zarejestrowanych wizyt w systemie.")

# --- TAB 4: LISTA KLIENTÓW ---
with tab_clients:
    with st.expander("➕ Nowy klient", expanded=False):
        st.subheader("👤 Zgłaszanie nowych klientów")

        mode = st.radio("Wybierz sposób dodania:", ["Wpis ręczny (jeden klient)", "📥 Masowy import z pliku Excel"], horizontal=True)

        if mode == "Wpis ręczny (jeden klient)":
            with st.form("add_client_form", clear_on_submit=True):
                name = st.text_input("Nazwa firmy / Imię i nazwisko *")
                chain_name = st.text_input("Nazwa sieci (opcjonalnie)", placeholder="np. Społem, Lewiatan, Biedronka")
                category = st.selectbox(
                    "Początkowa kategoria / Scoring", ["🥇 Złoty", "🥈 Srebrny", "🥉 Brązowy"]
                )
                sub_category = st.selectbox(
                    "Podgrupa", ["Nowy klient", "Standardowy"]
                )

                st.markdown("---")
                st.markdown("📞 **Dane kontaktowe i lokalizacja (opcjonalnie)**")
                phone = st.text_area(
                    "Numery telefonów (Wpisz w osobnych liniach)",
                    placeholder="Jan (Właściciel): 600111222\nKierownik: 600333444",
                    height=100
                )
                email = st.text_input("Adres e-mail", placeholder="np. sklep@klient.pl")
                address = st.text_input(
                    "Adres / Lokalizacja (do nawigacji)", placeholder="np. ul. Sienkiewicza 10, Kielce"
                )

                st.markdown("---")
                selected_price_list = st.selectbox(
                    "Przypisz cennik", available_price_lists
                )
                submit_new = st.form_submit_button("Dodaj do bazy")

                if submit_new and name:
                    try:
                        c.execute(
                            """
                            INSERT INTO clients (name, category, sub_category, chain_name, phone, email, address, price_list) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                name,
                                category,
                                sub_category,
                                chain_name,
                                phone,
                                email,
                                address,
                                selected_price_list if selected_price_list != "Brak" else None,
                            ),
                        )
                        conn.commit()
                        st.success(f"Dodano klienta: {name} (Podgrupa: {sub_category})")
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
                        col_sub = st.selectbox("Podgrupa (np. Nowy klient)", excel_cols)
                    with col_y:
                        col_phone = st.selectbox("Numer telefonu", excel_cols)
                        col_email = st.selectbox("E-mail", excel_cols)
                        col_addr = st.selectbox("Adres", excel_cols)
                        col_pl = st.selectbox("Cennik", excel_cols)

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

                            c_sub = str(r[col_sub]).strip() if col_sub != "-- Brak / Nie przypisuj --" and pd.notnull(r[col_sub]) else "Nowy klient"

                            c_phone = str(r[col_phone]).strip() if col_phone != "-- Brak / Nie przypisuj --" and pd.notnull(r[col_phone]) else None
                            c_email = str(r[col_email]).strip() if col_email != "-- Brak / Nie przypisuj --" and pd.notnull(r[col_email]) else None
                            c_addr = str(r[col_addr]).strip() if col_addr != "-- Brak / Nie przypisuj --" and pd.notnull(r[col_addr]) else None
                            c_pl = str(r[col_pl]).strip() if col_pl != "-- Brak / Nie przypisuj --" and pd.notnull(r[col_pl]) else None

                            c.execute("SELECT COUNT(*) FROM clients WHERE name = ?", (c_name,))
                            exists = c.fetchone()[0] > 0

                            if exists:
                                c.execute(
                                    """
                                    UPDATE clients 
                                    SET category = COALESCE(?, category),
                                        sub_category = COALESCE(?, sub_category),
                                        chain_name = COALESCE(?, chain_name),
                                        phone = COALESCE(?, phone),
                                        email = COALESCE(?, email),
                                        address = COALESCE(?, address),
                                        price_list = COALESCE(?, price_list)
                                    WHERE name = ?
                                    """,
                                    (c_cat, c_sub, c_chain, c_phone, c_email, c_addr, c_pl, c_name)
                                )
                                updated_cnt += 1
                            else:
                                c.execute(
                                    """
                                    INSERT INTO clients (name, category, sub_category, chain_name, phone, email, address, price_list)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (c_name, c_cat, c_sub, c_chain, c_phone, c_email, c_addr, c_pl)
                                )
                                added_cnt += 1

                        conn.commit()
                        st.success(f"Gotowe! Dodano {added_cnt} nowych kartotek, zaktualizowano {updated_cnt} istniejących.")
                        st.rerun()

                except Exception as ex:
                    st.error(f"Błąd podczas odczytu pliku: {ex}")

    st.markdown("---")
    
    df = pd.read_sql_query("SELECT * FROM clients", conn)

    if not df.empty:
        total_count = len(df)
        gold_count = len(df[df["category"] == "🥇 Złoty"])
        silver_count = len(df[df["category"] == "🥈 Srebrny"])
        bronze_count = len(df[df["category"] == "🥉 Brązowy"])
        new_cli_count = len(df[df["sub_category"] == "Nowy klient"])

        st.markdown(f"👥 **Ogółem:** `{total_count}` | 🥇 Złote: `{gold_count}` | 🥈 Srebrne: `{silver_count}` | 🥉 Brązowe: `{bronze_count}` | 🆕 Nowi klienci: `{new_cli_count}`")
        st.markdown("---")

        if st.button("🔄 Przelicz scoring klientów wg obrotów"):
            recalculate_client_scores()
            st.success("Zaktualizowano scoring klientów (Złoty: >=7800 zł, Srebrny: >=3900 zł, Brązowy: <3900 zł)")
            st.rerun()

        df["last_visit_clean"] = pd.to_datetime(df["last_visit"], errors="coerce")
        today = pd.to_datetime("today")
        df["Dni od wizyty"] = (today - df["last_visit_clean"]).dt.days.fillna(999).astype(int)

        col_filter, col_sub_filter, col_sort = st.columns(3)
        with col_filter:
            category_filter = st.multiselect(
                "Filtruj priorytet / scoring:",
                ["🥇 Złoty", "🥈 Srebrny", "🥉 Brązowy"],
                default=["🥇 Złoty", "🥈 Srebrny", "🥉 Brązowy"],
            )

        with col_sub_filter:
            sub_category_filter = st.multiselect(
                "Podgrupa kliencka:",
                ["Standardowy", "Nowy klient"],
                default=["Standardowy", "Nowy klient"],
            )

        with col_sort:
            sort_option = st.selectbox(
                "Sortuj według:",
                [
                    "Nazwa klienta (A-Z)",
                    "Dni od wizyty (od najdawniejszych)",
                    "Dni od wizyty (od najnowszych)",
                ],
                index=0
            )

        filtered_df = df[(df["category"].isin(category_filter)) & (df["sub_category"].isin(sub_category_filter))]

        if sort_option == "Dni od wizyty (od najdawniejszych)":
            filtered_df = filtered_df.sort_values(by="Dni od wizyty", ascending=False)
        elif sort_option == "Dni od wizyty (od najnowszych)":
            filtered_df = filtered_df.sort_values(by="Dni od wizyty", ascending=True)
        elif sort_option == "Nazwa klienta (A-Z)":
            filtered_df = filtered_df.sort_values(by="name", ascending=True)

        col_hdr_title, col_hdr_btn = st.columns([2, 1])
        with col_hdr_title:
            st.subheader("Lista Klientów")
        with col_hdr_btn:
            multi_select_active = st.toggle("☑️ Zaznacz wiele", key="toggle_multi_select")

        if "clients_to_delete" not in st.session_state:
            st.session_state["clients_to_delete"] = []

        clients_to_delete = []

        if multi_select_active:
            st.markdown("---")
            col_info, col_del_action = st.columns([2, 1])
            with col_info:
                st.caption("Zaznacz wybrane pozycje na liście poniżej:")
            
            for _, r_item in filtered_df.iterrows():
                if st.checkbox(f"Zaznacz: {r_item['name']}", key=f"multi_del_{r_item['id']}"):
                    clients_to_delete.append(r_item["name"])

            if clients_to_delete:
                with col_del_action:
                    confirm_bulk = st.checkbox("Potwierdź usunięcie", key="confirm_bulk_del")
                    if st.button("🗑️ Usuń", type="primary", key="btn_bulk_del"):
                        if confirm_bulk:
                            for cl_del in clients_to_delete:
                                c.execute("DELETE FROM clients WHERE name = ?", (cl_del,))
                                c.execute("DELETE FROM purchases WHERE client_name = ?", (cl_del,))
                                c.execute("DELETE FROM visits WHERE client_name = ?", (cl_del,))
                                c.execute("DELETE FROM orders WHERE client_name = ?", (cl_del,))
                            conn.commit()
                            st.success("Pomyślnie usunięto zaznaczonych klientów!")
                            st.rerun()
                        else:
                            st.error("Zaznacz pole potwierdzenia!")

        st.markdown("---")

        for _, row in filtered_df.iterrows():
            days_str = f"{row['Dni od wizyty']} dni" if row['Dni od wizyty'] != 999 else "Brak wizyt"
            color = (
                "⚪" if row["Dni od wizyty"] == 999 else
                ("🔴" if row["Dni od wizyty"] > 30 else ("🟡" if row["Dni od wizyty"] > 14 else "🟢"))
            )

            chain_str = f" [{row['chain_name']}]" if row.get("chain_name") else ""
            sub_str = f" [Nowy]" if row.get("sub_category") == "Nowy klient" else ""
            expander_title = f"{color} {row['name']}{chain_str}{sub_str} ({row['category']}) — {days_str}"
            
            with st.expander(expander_title):
                render_client_card(row, key_prefix="list")

    else:
        st.info("Baza jest pusta. Dodaj pierwszego klienta używając przycisku '➕ Nowy klient' powyżej.")

# --- TAB 5: PRODUKTY ---
with tab_products:
    st.subheader("📦 Katalog Produktów")
    
    prod_mode = st.radio(
        "Wybierz tryb:",
        ["Przeglądaj produkty", "Dodaj pojedynczy produkt", "📥 Masowy import z pliku Excel", "📈 Analiza sprzedaży (Top produkty)"],
        horizontal=True,
        key="prod_mode_radio"
    )

    if prod_mode == "Przeglądaj produkty":
        df_products = pd.read_sql_query("SELECT * FROM products ORDER BY name ASC", conn)
        
        if not df_products.empty:
            st.caption(f"Łącznie produktów w bazie: {len(df_products)}")
            
            search_prod = st.text_input("🔍 Szukaj produktu po nazwie:", placeholder="Wpisz nazwę...")
            if search_prod.strip():
                df_products = df_products[df_products["name"].str.contains(search_prod, case=False, na=False)]

            for _, p_row in df_products.iterrows():
                p_id = p_row["id"]
                p_name = p_row["name"]
                p_cat = p_row["category"] if p_row["category"] else "Ogólna"
                p_price = p_row["price"] if p_row["price"] else 0.0
                
                with st.expander(f"🍞 {p_name} ({p_cat}) — {p_price:,.2f} zł"):
                    col_p1, col_p2 = st.columns([2, 1])
                    
                    with col_p1:
                        st.markdown(f"**Kategoria:** {p_cat}")
                        st.markdown(f"**Cena bazowa:** {p_price:,.2f} zł")
                        if p_row["description"]:
                            st.markdown(f"**Opis:**\n{p_row['description']}")
                        else:
                            st.caption("Brak opisu produktu.")
                    
                    with col_p2:
                        if p_row["image_url"]:
                            try:
                                st.image(p_row["image_url"], caption=p_name, use_container_width=True)
                            except Exception:
                                st.caption("Nie udało się załadować zdjęcia (błędny link/ścieżka).")
                        else:
                            st.caption("Brak zdjęcia")

                    st.markdown("---")
                    with st.popover("✏️ Edytuj / Usuń produkt", key=f"edit_prod_{p_id}"):
                        with st.form(f"edit_prod_form_{p_id}"):
                            ep_name = st.text_input("Nazwa produktu", value=p_name)
                            ep_cat = st.text_input("Kategoria", value=p_row["category"] or "")
                            ep_price = st.number_input("Cena (zł)", value=float(p_price), step=0.5)
                            ep_desc = st.text_area("Opis", value=p_row["description"] or "")
                            ep_img = st.text_input("Link / ścieżka do zdjęcia", value=p_row["image_url"] or "")
                            
                            save_p = st.form_submit_button("💾 Zapisz zmiany")
                            if save_p:
                                c.execute(
                                    "UPDATE products SET name = ?, category = ?, price = ?, description = ?, image_url = ? WHERE id = ?",
                                    (ep_name, ep_cat if ep_cat else None, ep_price, ep_desc if ep_desc else None, ep_img if ep_img else None, p_id)
                                )
                                conn.commit()
                                st.success("Zaktualizowano produkt!")
                                st.rerun()

                        if st.button("🗑️ Usuń produkt", key=f"del_prod_{p_id}", type="primary"):
                            c.execute("DELETE FROM products WHERE id = ?", (p_id,))
                            conn.commit()
                            st.success("Usunięto produkt!")
                            st.rerun()
        else:
            st.info("Katalog produktów jest pusty. Dodaj produkty ręcznie lub zaimportuj je z pliku Excel.")

    elif prod_mode == "Dodaj pojedynczy produkt":
        with st.form("add_single_product_form", clear_on_submit=True):
            p_name = st.text_input("Nazwa produktu *")
            p_cat = st.text_input("Kategoria", placeholder="np. Pieczywo jasne, Ciastka, Bułki")
            p_price = st.number_input("Cena (zł)", min_value=0.0, value=0.0, step=0.5)
            p_desc = st.text_area("Opis produktu", placeholder="Skład, waga, cechy szczególne...")
            p_img = st.text_input("Link lub ścieżka do zdjęcia", placeholder="https://... lub lokalna ścieżka")
            
            submitted_p = st.form_submit_button("💾 Dodaj produkt")
            if submitted_p and p_name:
                try:
                    c.execute(
                        "INSERT INTO products (name, category, price, description, image_url) VALUES (?, ?, ?, ?, ?)",
                        (p_name, p_cat if p_cat else None, p_price, p_desc if p_desc else None, p_img if p_img else None)
                    )
                    conn.commit()
                    st.success(f"Dodano produkt: {p_name}")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Produkt o takiej nazwie już istnieje w bazie!")

    elif prod_mode == "📥 Masowy import z pliku Excel":
        st.markdown("#### 📥 Masowy import produktów z pliku Excel")
        prod_file = st.file_uploader("Wybierz plik Excel z produktami (.xlsx lub .xls)", type=["xlsx", "xls"], key="excel_products_file")

        if prod_file is not None:
            try:
                p_df = pd.read_excel(prod_file)
                st.write("Podgląd wczytanego pliku:")
                st.dataframe(p_df.head(5), use_container_width=True)

                st.markdown("#### Mapowanie kolumn:")
                p_cols = ["-- Brak / Nie przypisuj --"] + list(p_df.columns)

                col_px, col_py = st.columns(2)
                with col_px:
                    map_name = st.selectbox("Nazwa produktu *", list(p_df.columns))
                    map_cat = st.selectbox("Kategoria", p_cols)
                    map_price = st.selectbox("Cena", p_cols)
                with col_py:
                    map_desc = st.selectbox("Opis", p_cols)
                    map_img = st.selectbox("Link do zdjęcia", p_cols)

                if st.button("🚀 Importuj produkty"):
                    added_prod = 0
                    updated_prod = 0

                    for _, r in p_df.iterrows():
                        prod_n = str(r[map_name]).strip()
                        if not prod_n or prod_n == "nan":
                            continue

                        prod_c = str(r[map_cat]).strip() if map_cat != "-- Brak / Nie przypisuj --" and pd.notnull(r[map_cat]) else None
                        
                        try:
                            prod_pr = float(r[map_price]) if map_price != "-- Brak / Nie przypisuj --" and pd.notnull(r[map_price]) else 0.0
                        except Exception:
                            prod_pr = 0.0

                        prod_d = str(r[map_desc]).strip() if map_desc != "-- Brak / Nie przypisuj --" and pd.notnull(r[map_desc]) else None
                        prod_i = str(r[map_img]).strip() if map_img != "-- Brak / Nie przypisuj --" and pd.notnull(r[map_img]) else None

                        c.execute("SELECT COUNT(*) FROM products WHERE name = ?", (prod_n,))
                        p_exists = c.fetchone()[0] > 0

                        if p_exists:
                            c.execute(
                                """
                                UPDATE products 
                                SET category = COALESCE(?, category),
                                    price = COALESCE(?, price),
                                    description = COALESCE(?, description),
                                    image_url = COALESCE(?, image_url)
                                WHERE name = ?
                                """,
                                (prod_c, prod_pr, prod_d, prod_i, prod_n)
                            )
                            updated_prod += 1
                        else:
                            c.execute(
                                """
                                INSERT INTO products (name, category, price, description, image_url)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (prod_n, prod_c, prod_pr, prod_d, prod_i)
                            )
                            added_prod += 1

                    conn.commit()
                    st.success(f"Zaimportowano pomyślnie! Dodano nowych: {added_prod}, zaktualizowano istniejących: {updated_prod}")
                    st.rerun()

            except Exception as p_err:
                st.error(f"Błąd podczas wczytywania pliku Excel: {p_err}")

    else:
        st.markdown("#### 📈 Analiza sprzedaży produktów w miesiącu")
        st.caption("Zestawienie najlepiej sprzedających się artykułów na podstawie wgranych raportów ze sprzedaży:")

        col_m_sel, col_y_sel = st.columns(2)
        with col_m_sel:
            anal_month = st.selectbox("Wybierz miesiąc", list(range(1, 13)), index=datetime.now().month - 1, format_func=lambda x: calendar.month_name[x], key="anal_m")
        with col_y_sel:
            anal_year = st.number_input("Rok", value=datetime.now().year, step=1, key="anal_y")

        last_d_anal = calendar.monthrange(anal_year, anal_month)[1]
        start_anal_str = f"{anal_year:04d}-{anal_month:02d}-01"
        end_anal_str = f"{anal_year:04d}-{anal_month:02d}-{last_d_anal:02d}"

        query_anal = """
            SELECT item_name, 
                   SUM(bought_qty) as total_bought_qty, 
                   SUM(bought_val) as total_bought_val,
                   SUM(returned_qty) as total_returned_qty,
                   SUM(returned_val) as total_returned_val,
                   SUM(net_val) as total_net_val
            FROM purchases 
            WHERE report_start_date >= ? AND report_end_date <= ?
            GROUP BY item_name
            ORDER BY total_bought_qty DESC
        """
        df_anal = pd.read_sql_query(query_anal, conn, params=(start_anal_str, end_anal_str))

        if not df_anal.empty:
            st.success(f"Analiza dla okresu: **{start_anal_str}** do **{end_anal_str}**")
            
            df_anal_display = df_anal.rename(columns={
                "item_name": "Produkt",
                "total_bought_qty": "Zakupiona Ilość (Szt./Kg)",
                "total_bought_val": "Wartość Zakupów (zł)",
                "total_returned_qty": "Zwrócona Ilość",
                "total_returned_val": "Wartość Zwrotów (zł)",
                "total_net_val": "Wartość Netto (zł)"
            })
            
            st.dataframe(df_anal_display, use_container_width=True)

            st.markdown("---")
            st.markdown("🏆 **Top 5 produktów (największa ilość):**")
            top_5 = df_anal.head(5)
            for idx, row in top_5.iterrows():
                st.write(f"{idx+1}. **{row['item_name']}** — Zakupiono: **{row['total_bought_qty']:,.1f}** | Wartość netto: **{row['total_net_val']:,.2f} zł**")
        else:
            st.info(f"Brak danych sprzedażowych w bazie dla wybranego miesiąca ({calendar.month_name[anal_month]} {anal_year}). Wgraj raporty w zakładce 'Raport Excel'.")

# --- TAB 6: IMPORT EXCELA ---
with tab_excel:
    st.subheader("📊 Wczytaj raport ze sprzedaży z Excela (Miesiąc / Tydzień / Dzień)")

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
    else:
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
        "Wybierz plik Excel ze sprzedaży (.xlsx lub .xls)", type=["xlsx", "xls"], key="excel_sales"
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

            if st.button("🚀 Przetwórz i zaciągnij dane"):
                if c_client == "-- Wybierz kolumnę --":
                    st.error("Musisz wskazać co najmniej kolumnę z Klientem!")
                else:
                    processed_count = 0
                    new_products_added = 0

                    for _, r in excel_df.iterrows():
                        client_name = str(r[c_client]).strip()
                        if not client_name or client_name == "nan":
                            continue

                        item_name = (
                            str(r[c_item]).strip()
                            if c_item != "-- Wybierz kolumnę --" and pd.notnull(r[c_item])
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

                        if item_name and item_name != "Ogólne":
                            c.execute("SELECT COUNT(*) FROM products WHERE name = ?", (item_name,))
                            if c.fetchone()[0] == 0:
                                unit_price = (b_val / b_qty) if b_qty > 0 else 0.0
                                c.execute(
                                    "INSERT INTO products (name, category, price) VALUES (?, ?, ?)",
                                    (item_name, "Z raportu Excel", unit_price)
                                )
                                new_products_added += 1

                        c.execute(
                            "SELECT COUNT(*) FROM clients WHERE name = ?",
                            (client_name,),
                        )
                        if c.fetchone()[0] == 0:
                            c.execute(
                                "INSERT INTO clients (name, category, sub_category) VALUES (?, ?, ?)",
                                (
                                    client_name,
                                    "🥉 Brązowy",
                                    "Nowy klient",
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
                    recalculate_client_scores()

                    st.success(
                        f"Pomyślnie przetworzono {processed_count} pozycji, automatycznie zaciągnięto {new_products_added} nowych produktów do katalogu oraz zaktualizowano klientów!"
                    )
                    st.rerun()

        except Exception as e:
            st.error(f"Błąd podczas odczytu pliku Excel: {e}")

# --- TAB 7: ZARZĄDZANIE CENNIKAMI ---
with tab_pl:
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

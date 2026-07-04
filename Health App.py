import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from datetime import datetime, date, timedelta, time as dt_time
import mysql.connector
from mysql.connector import errorcode, IntegrityError

# -------------------- PASTEL THEME COLORS --------------------
PASTEL_BG = "#fdeef4"
PASTEL_FRAME = "#fff7fb"
PASTEL_BUTTON = "#f7cfe3"
PASTEL_BUTTON_ACTIVE = "#f4b7d1"
PASTEL_TEXT = "#444444"

label_style = {
    "bg": PASTEL_BG,
    "fg": PASTEL_TEXT
}

button_style = {
    "bg": PASTEL_BUTTON,
    "fg": PASTEL_TEXT,
    "activebackground": PASTEL_BUTTON_ACTIVE,
    "activeforeground": PASTEL_TEXT,
    "font": ("Arial", 11, "bold"),
    "bd": 1,
    "relief": "ridge",
    "padx": 6,
    "pady": 4
}

# -------------------- MySQL Config --------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Vinuthasb@7",  
    "database": "health_app"
}

# -------------------- Vaccine & Disease Data --------------------
VACCINES = {
    "BCG": {"info": "Protects against Tuberculosis", "interval_weeks": 0, "age_limit": "At birth", "doses": 1, "gap_weeks": 0},
    "HepB1": {"info": "Hepatitis-B", "interval_weeks": 0, "age_limit": "At birth", "doses": 3, "gap_weeks": 4},
    "OPV": {"info": "Oral Polio Vaccine", "interval_weeks": 4, "age_limit": "6 weeks+", "doses": 3, "gap_weeks": 4},
    "DTwP/DTaP1": {"info": "Diphtheria/Tetanus/Pertussis", "interval_weeks": 4, "age_limit": "6 weeks+", "doses": 3, "gap_weeks": 4},
    "Hib-1": {"info": "Haemophilus influenzae type b", "interval_weeks": 4, "age_limit": "6 weeks+", "doses": 3, "gap_weeks": 4},
    "IPV-1": {"info": "Injectable Polio Vaccine", "interval_weeks": 4, "age_limit": "6 weeks+", "doses": 1, "gap_weeks": 0},
    "COVID-19": {"info": "COVID-19 Vaccine", "interval_weeks": 12, "age_limit": "18+", "doses": 2, "gap_weeks": 12}
}

COMMON_DISEASES = {
    "Cold": {"meds": ["Paracetamol", "Cough syrup"], "when_to_see_doctor": "Fever >3 days"},
    "Fever": {"meds": ["Paracetamol", "Ibuprofen"], "when_to_see_doctor": "Very high fever >48 hours"},
    "Headache": {"meds": ["Paracetamol"], "when_to_see_doctor": "Severe sudden headache"},
    "Stomach Pain": {"meds": ["Antacids", "Probiotics"], "when_to_see_doctor": "Vomiting / blood in stool"},
}

# -------------------- Helper Functions --------------------

def parse_dob(date_str):
    for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"]:
        try:
            return datetime.strptime(date_str, fmt).date()
        except:
            pass
    return None

def calculate_interval(birth_date, weeks):
    return birth_date + timedelta(weeks=weeks)

def normalize_time_str(tstr):
    try:
        return datetime.strptime(tstr.strip(), "%H:%M").time()
    except:
        return None

# -------------------- DB Init + Migration --------------------
db_conn = None

def ensure_vaccines_taken_schema(cur):
    """
    Ensure vaccines_taken has columns (username, vaccine, dose)
    If an older schema exists, attempt to ALTER it to include dose and adjust PK.
    """
    # Check if table exists
    cur.execute("SHOW TABLES LIKE 'vaccines_taken'")
    exists = cur.fetchone()
    if not exists:
        # create fresh table with dose
        cur.execute("""
            CREATE TABLE vaccines_taken (
                username VARCHAR(50),
                vaccine VARCHAR(100),
                dose INT,
                PRIMARY KEY (username, vaccine, dose)
            )
        """)
        return

    # Check whether dose column exists
    cur.execute("SHOW COLUMNS FROM vaccines_taken LIKE 'dose'")
    dose_col = cur.fetchone()
    if dose_col:
        # already has dose - ensure PK includes dose
        # we'll not attempt heavy PK checks here beyond existence
        return
    else:
        # Add dose column with default 1
        try:
            cur.execute("ALTER TABLE vaccines_taken ADD COLUMN dose INT DEFAULT 1")
        except Exception as e:
            # if this fails, raise so higher level can inform user
            raise

        # Try to change primary key from (username,vaccine) to (username,vaccine,dose)
        try:
            # drop PRIMARY KEY then add new one
            cur.execute("ALTER TABLE vaccines_taken DROP PRIMARY KEY")
            cur.execute("ALTER TABLE vaccines_taken ADD PRIMARY KEY (username, vaccine, dose)")
        except Exception as e:
            # If altering primary key failed (e.g., duplicate rows), inform user but continue.
            raise

def init_db():
    global db_conn
    cfg = DB_CONFIG.copy()
    dbname = cfg.pop("database")

    try:
        db_conn = mysql.connector.connect(database=dbname, **cfg)
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_BAD_DB_ERROR:
            temp = mysql.connector.connect(**cfg)
            cur = temp.cursor()
            cur.execute(f"CREATE DATABASE `{dbname}`")
            temp.close()
            db_conn = mysql.connector.connect(database=dbname, **cfg)
        else:
            raise

    cur = db_conn.cursor()
    # users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username VARCHAR(50) PRIMARY KEY,
            password VARCHAR(255),
            dob DATE
        )
    """)
    # reminders
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50),
            type VARCHAR(20),
            item VARCHAR(200),
            time DATETIME,
            info TEXT
        )
    """)
    # vaccines_taken - ensure schema with dose; function will create or alter as needed
    try:
        ensure_vaccines_taken_schema(cur)
    except Exception as e:
        # If migration fails (e.g., due to duplicate rows when changing PK), notify user clearly.
        messagebox.showwarning(
            "DB Migration Warning",
            "Automatic migration of vaccines_taken table partially failed.\n"
            "This usually happens if your database has duplicate (username,vaccine) rows.\n"
            "Please inspect the vaccines_taken table and resolve duplicates, then re-run the app.\n\n"
            f"Lower-level error: {e}"
        )
    db_conn.commit()
    cur.close()

def get_user(username):
    cur = db_conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE username=%s", (username,))
    row = cur.fetchone()
    cur.close()
    return row

# -------------------- Login State --------------------
current_user = None

# -------------------- GUI ROOT --------------------
root = tk.Tk()
root.title("Health App — Pastel Theme")
try:
    root.state('zoomed')
except:
    root.attributes('-zoomed', True)
root.configure(bg=PASTEL_BG)

# -------------------- Status Label --------------------
status_var = tk.StringVar(value="Not Logged In")
tk.Label(root, textvariable=status_var, font=("Arial", 13, "bold"), **label_style).pack(pady=10)

def refresh_status():
    if current_user:
        status_var.set(f"Logged in: {current_user}")
    else:
        status_var.set("Not Logged In")

# -------------------- Login Logic --------------------

def login_flow(callback):
    def attempt():
        global current_user
        u = username_entry.get().strip()
        p = password_entry.get().strip()

        row = get_user(u)
        if row and row["password"] == p:
            current_user = u
            refresh_status()
            win.destroy()
            callback(u)
        else:
            messagebox.showerror("Error", "Invalid login")

    win = tk.Toplevel(root)
    win.title("Login")
    win.configure(bg=PASTEL_BG)

    tk.Label(win, text="Phone:", **label_style).grid(row=0, column=0, padx=8, pady=6)
    username_entry = tk.Entry(win); username_entry.grid(row=0, column=1, padx=8, pady=6)

    tk.Label(win, text="Password:", **label_style).grid(row=1, column=0, padx=8, pady=6)
    password_entry = tk.Entry(win, show="*"); password_entry.grid(row=1, column=1, padx=8, pady=6)

    tk.Button(win, text="Login", command=attempt, **button_style).grid(row=2, column=0, columnspan=2, pady=12)

# -------------------- Create Account --------------------

def create_account():
    win = tk.Toplevel(root)
    win.title("Create Account")
    win.configure(bg=PASTEL_BG)

    tk.Label(win, text="Phone:", **label_style).grid(row=0, column=0, padx=8, pady=6)
    e_phone = tk.Entry(win); e_phone.grid(row=0, column=1, padx=8, pady=6)

    tk.Label(win, text="Password:", **label_style).grid(row=1, column=0, padx=8, pady=6)
    e_pwd = tk.Entry(win, show="*"); e_pwd.grid(row=1, column=1, padx=8, pady=6)

    tk.Label(win, text="DOB (YYYY-MM-DD):", **label_style).grid(row=2, column=0, padx=8, pady=6)
    e_dob = tk.Entry(win); e_dob.grid(row=2, column=1, padx=8, pady=6)

    def save():
        dob = parse_dob(e_dob.get())

        cur = db_conn.cursor()
        try:
            cur.execute("INSERT INTO users VALUES (%s,%s,%s)",
                        (e_phone.get().strip(), e_pwd.get().strip(), dob))
            db_conn.commit()
            messagebox.showinfo("Done", "Account created")
            win.destroy()
        except IntegrityError:
            messagebox.showerror("Error", "Account may already exist")
        finally:
            cur.close()

    tk.Button(win, text="Create", command=save, **button_style).grid(row=3, column=0, columnspan=2, pady=10)

# -------------------- View Vaccines (tabular) --------------------

def view_vaccines():
    win = tk.Toplevel(root)
    win.title("Vaccine Information")
    win.configure(bg=PASTEL_BG)
    win.geometry("760x420")

    # Changed header: Age Limit -> Age
    cols = ("Vaccine", "Age", "Doses", "Gap (Weeks)", "Info")
    tv = ttk.Treeview(win, columns=cols, show="headings", height=14)

    widths = [200, 120, 80, 100, 240]
    for c, w in zip(cols, widths):
        tv.heading(c, text=c)
        tv.column(c, width=w)

    tv.pack(fill="both", expand=True, padx=10, pady=10)

    for v, data in VACCINES.items():
        age = data.get("age_limit", "")

        # ---- NEW AGE FORMAT LOGIC ----
        # If it is a number with + (example 18+), add "yrs"
        cleaned = (age or "").replace(" ", "")
        if cleaned.endswith("+") and cleaned[:-1].isdigit():
            # preserve original spacing but append ' yrs'
            age = age.strip() + " yrs"

        doses = data.get("doses", "")
        gap = data.get("gap_weeks", data.get("interval_weeks", ""))
        info = data.get("info", "")
        tv.insert("", "end", values=(v, age, doses, gap, info))

# -------------------- Vaccine Tracker (per-dose checkboxes) --------------------

def vaccine_tracker(username):
    user = get_user(username)
    if not user or not user.get("dob"):
        messagebox.showerror("DOB Missing", "Please update your DOB.")
        return

    dob = user["dob"]

    win = tk.Toplevel(root)
    win.title("Vaccine Tracker")
    win.configure(bg=PASTEL_BG)
    win.geometry("920x560")

    # Load previously taken vaccines (per-dose)
    cur = db_conn.cursor()
    cur.execute("SELECT vaccine, dose FROM vaccines_taken WHERE username=%s", (username,))
    taken_rows = cur.fetchall()
    cur.close()
    taken = {(row[0], row[1]) for row in taken_rows} if taken_rows else set()

    vars_check = {}  # (vaccine, dose) -> BooleanVar

    # Left: Scrollable per-dose checkboxes
    left_frame = tk.Frame(win, bg=PASTEL_BG)
    left_frame.pack(side="left", fill="both", expand=False, padx=10, pady=10)
    canvas = tk.Canvas(left_frame, bg=PASTEL_BG, highlightthickness=0, width=420)
    frame = tk.Frame(canvas, bg=PASTEL_BG)
    vsb = tk.Scrollbar(left_frame, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    canvas.create_window((0,0), window=frame, anchor="nw")
    def on_frame_config(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
    frame.bind("<Configure>", on_frame_config)

    # Build per-dose checkboxes
    for v, data in VACCINES.items():
        doses = data.get("doses", 1)
        container = tk.LabelFrame(frame, text=f"{v} — {data.get('info','')}", bg=PASTEL_FRAME, fg=PASTEL_TEXT, padx=6, pady=6)
        container.pack(fill="x", pady=6, padx=6)
        dose_row = tk.Frame(container, bg=PASTEL_FRAME)
        dose_row.pack(fill="x")
        for d in range(1, doses+1):
            var = tk.BooleanVar(value=((v, d) in taken))
            vars_check[(v, d)] = var
            cb = tk.Checkbutton(dose_row, text=f"Dose {d}", variable=var, bg=PASTEL_FRAME, anchor="w")
            cb.pack(side="left", padx=6, pady=2)

    # Right: Summary treeview (no recommended date column)
    right_frame = tk.Frame(win, bg=PASTEL_BG)
    right_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

    cols = ("Vaccine", "Doses Remaining / Completed")
    tv = ttk.Treeview(right_frame, columns=cols, show="headings", height=18)
    for c in cols:
        tv.heading(c, text=c)
        if c == "Vaccine":
            tv.column(c, width=260)
        else:
            tv.column(c, width=220)
    tv.pack(fill="both", expand=True, padx=6, pady=6)

    def populate_summary():
        for i in tv.get_children():
            tv.delete(i)
        for v, data in VACCINES.items():
            doses = data.get("doses", 1)
            taken_count = sum(1 for d in range(1, doses+1) if vars_check.get((v,d)) and vars_check[(v,d)].get())
            remaining = doses - taken_count
            status = f"{remaining} remaining / {taken_count} completed"
            tv.insert("", "end", values=(v, status))

    populate_summary()

    # When user saves, persist per-dose taken state and create/remove reminders per dose
    def save_vaccines():
        cur = db_conn.cursor()
        # remove previous vaccine taken entries for this user then reinsert
        cur.execute("DELETE FROM vaccines_taken WHERE username=%s", (username,))
        # remove previous vaccine reminders for this user (we'll recreate pending ones)
        cur.execute("DELETE FROM reminders WHERE username=%s AND type='vaccine'", (username,))

        # For each vaccine and dose, if checked -> insert into vaccines_taken
        for (v, d), var in vars_check.items():
            if var.get():
                try:
                    cur.execute("INSERT INTO vaccines_taken (username,vaccine,dose) VALUES (%s,%s,%s)", (username, v, d))
                except IntegrityError:
                    pass

        # For any dose not taken, create a reminder entry (time set using dob+interval by dose index if provided, otherwise now+1 day)
        for v, data in VACCINES.items():
            doses = data.get("doses", 1)
            base_weeks = data.get("interval_weeks", 0)
            gap = data.get("gap_weeks", 0)
            for d in range(1, doses+1):
                if not (vars_check.get((v,d)) and vars_check[(v,d)].get()):
                    # approximate recommended date: base_weeks + gap*(dose-1)
                    weeks = base_weeks + gap*(d-1)
                    try:
                        rec_date = calculate_interval(dob, weeks)
                        rem_dt = datetime.combine(rec_date, datetime.min.time())
                    except Exception:
                        rem_dt = datetime.now() + timedelta(days=1)
                    item = f"{v} - Dose {d}"
                    cur.execute("INSERT INTO reminders (username,type,item,time,info) VALUES (%s,'vaccine',%s,%s,%s)", (username, item, rem_dt, data.get("info","")))
        db_conn.commit()
        cur.close()
        populate_summary()
        messagebox.showinfo("Saved", "Vaccine tracker updated and reminders refreshed!")

    btn_frame = tk.Frame(left_frame, bg=PASTEL_BG)
    btn_frame.pack(fill="x", pady=8, padx=8)
    tk.Button(btn_frame, text="Save", command=save_vaccines, **button_style).pack(side="left", padx=6)
    tk.Button(btn_frame, text="Refresh Summary", command=populate_summary, **button_style).pack(side="left", padx=6)

# -------------------- Common Diseases --------------------

def open_common_diseases():
    win = tk.Toplevel(root)
    win.title("Common Diseases")
    win.configure(bg=PASTEL_BG)
    win.geometry("560x480")

    for d in COMMON_DISEASES:
        f = tk.LabelFrame(win, text=d, bg=PASTEL_FRAME, fg=PASTEL_TEXT, padx=10, pady=10)
        f.pack(fill="x", pady=6, padx=6)

        tk.Label(f, text="Medicines: " + ", ".join(COMMON_DISEASES[d]["meds"]),
                 bg=PASTEL_FRAME, fg=PASTEL_TEXT).pack(anchor="w")

        tk.Label(f, text="When to see doctor: " + COMMON_DISEASES[d]["when_to_see_doctor"],
                 bg=PASTEL_FRAME, fg=PASTEL_TEXT).pack(anchor="w")

        def add_rem(disease=d):
            if not current_user:
                messagebox.showerror("Login", "Please login.")
                return

            dt = datetime.now() + timedelta(hours=1)

            cur = db_conn.cursor()
            cur.execute("""
                INSERT INTO reminders (username,type,item,time,info)
                VALUES (%s,'disease',%s,%s,%s)
            """, (current_user, disease, dt, "Monitor symptoms"))
            db_conn.commit()
            cur.close()

            messagebox.showinfo("Added", f"Reminder added for {disease}")

        tk.Button(f, text="Add Reminder", **button_style, command=add_rem).pack(anchor="e", pady=6)

# -------------------- Tablet Tracker (scheduling options) --------------------

def tablet_tracker(username):
    win = tk.Toplevel(root)
    win.title("Tablet Tracker")
    win.configure(bg=PASTEL_BG)
    win.geometry("920x620")

    top_frame = tk.Frame(win, bg=PASTEL_BG)
    top_frame.pack(fill="x", padx=10, pady=8)

    tk.Label(top_frame, text="Enter tablets (one per line):", **label_style).pack(anchor="w")
    txt = tk.Text(win, height=6)
    txt.pack(fill="x", padx=12, pady=6)

    time_frame = tk.Frame(win, bg=PASTEL_BG)
    time_frame.pack(fill="x", padx=12, pady=4)

    tk.Label(time_frame, text="Times (HH:MM) — comma separated for multiple times:", **label_style).pack(anchor="w")
    times_entry = tk.Entry(time_frame, width=30)
    times_entry.insert(0, "09:00")  # default
    times_entry.pack(side="left", padx=6)

    # Frequency options
    freq_frame = tk.Frame(win, bg=PASTEL_BG)
    freq_frame.pack(fill="x", padx=12, pady=6)
    tk.Label(freq_frame, text="Frequency:", **label_style).pack(side="left")
    freq_var = tk.StringVar(value="Once")
    freq_combo = ttk.Combobox(freq_frame, textvariable=freq_var, values=["Once", "Daily", "Duration", "Twice a day"], state="readonly", width=18)
    freq_combo.pack(side="left", padx=6)

    duration_frame = tk.Frame(win, bg=PASTEL_BG)
    duration_frame.pack(fill="x", padx=12, pady=4)
    tk.Label(duration_frame, text="For Duration: Start (YYYY-MM-DD):", **label_style).pack(side="left")
    start_entry = tk.Entry(duration_frame, width=12); start_entry.pack(side="left", padx=6)
    tk.Label(duration_frame, text="End (YYYY-MM-DD):", **label_style).pack(side="left")
    end_entry = tk.Entry(duration_frame, width=12); end_entry.pack(side="left", padx=6)

    presc_path = tk.StringVar()
    def upload_prescription():
        file = filedialog.askopenfilename(
            title="Select Prescription Image",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
        )
        if file:
            presc_path.set(file)
            messagebox.showinfo("Uploaded", "Prescription image added!")
    tk.Button(freq_frame, text="Upload Prescription", command=upload_prescription, **button_style).pack(side="left", padx=8)

    def load_tablets_from_db():
        cur = db_conn.cursor()
        cur.execute("SELECT item FROM reminders WHERE username=%s AND type='tablet'", (username,))
        rows = cur.fetchall()
        cur.close()
        return [r[0] for r in rows] if rows else []

    prev = load_tablets_from_db()
    if prev:
        txt.insert("1.0", "\n".join(prev))

    def create_rems_from_text():
        meds = [m.strip() for m in txt.get("1.0", "end").splitlines() if m.strip()]
        times_raw = times_entry.get().strip()
        times = []
        for part in times_raw.split(","):
            t = normalize_time_str(part)
            if t:
                times.append(t)
        if not meds:
            messagebox.showerror("No tablets", "Enter at least one tablet.")
            return
        if not times and freq_var.get() != "Duration":
            messagebox.showerror("No times", "Enter at least one valid time (HH:MM).")
            return

        # Delete existing tablet reminders for user (we'll recreate)
        cur = db_conn.cursor()
        cur.execute("DELETE FROM reminders WHERE username=%s AND type='tablet'", (username,))

        freq = freq_var.get()
        now = datetime.now()

        for m in meds:
            if freq == "Once":
                # take first time as today's/next occurrence
                if times:
                    t = times[0]
                    dt_comb = datetime.combine(now.date(), t)
                    if dt_comb < now:
                        dt_comb += timedelta(days=1)
                else:
                    dt_comb = now + timedelta(hours=1)
                cur.execute("INSERT INTO reminders (username,type,item,time,info) VALUES (%s,'tablet',%s,%s,%s)", (username, m, dt_comb, presc_path.get()))
            elif freq == "Daily":
                # create one reminder for today at each time (UI's notifications will show each occurrence)
                for t in times:
                    dt_comb = datetime.combine(now.date(), t)
                    if dt_comb < now:
                        dt_comb += timedelta(days=1)
                    cur.execute("INSERT INTO reminders (username,type,item,time,info) VALUES (%s,'tablet',%s,%s,%s)", (username, m, dt_comb, presc_path.get()))
            elif freq == "Twice a day":
                # if user provided two times use them, else duplicate the first at 09:00 and 21:00
                tlist = times if len(times)>=2 else [dt_time(9,0), dt_time(21,0)]
                for t in tlist[:2]:
                    dt_comb = datetime.combine(now.date(), t)
                    if dt_comb < now:
                        dt_comb += timedelta(days=1)
                    cur.execute("INSERT INTO reminders (username,type,item,time,info) VALUES (%s,'tablet',%s,%s,%s)", (username, m, dt_comb, presc_path.get()))
            elif freq == "Duration":
                # requires start and end
                s = parse_dob(start_entry.get().strip())
                e = parse_dob(end_entry.get().strip())
                if not s or not e or s > e:
                    messagebox.showerror("Invalid dates", "Provide valid start and end dates (YYYY-MM-DD) for duration.")
                    cur.close()
                    return
                # For duration, if times provided use them, else schedule midday
                tlist = times if times else [dt_time(9,0)]
                day = s
                while day <= e:
                    for t in tlist:
                        dt_comb = datetime.combine(day, t)
                        cur.execute("INSERT INTO reminders (username,type,item,time,info) VALUES (%s,'tablet',%s,%s,%s)", (username, m, dt_comb, presc_path.get()))
                    day += timedelta(days=1)
            else:
                # fallback single reminder
                cur.execute("INSERT INTO reminders (username,type,item,time,info) VALUES (%s,'tablet',%s,%s,%s)", (username, m, now + timedelta(hours=1), presc_path.get()))

        db_conn.commit()
        cur.close()
        refresh_tablet_list()
        messagebox.showinfo("Saved", "Tablet tracker updated with reminders & prescription!")

    btns = tk.Frame(win, bg=PASTEL_BG)
    btns.pack(fill="x", padx=12, pady=6)
    tk.Button(btns, text="Save", command=create_rems_from_text, **button_style).pack(side="left", padx=6)

    # Bottom: show saved tablets + scheduled times
    bottom_frame = tk.Frame(win, bg=PASTEL_BG)
    bottom_frame.pack(fill="both", expand=True, padx=12, pady=6)

    cols = ("Tablet", "Scheduled At")
    tv = ttk.Treeview(bottom_frame, columns=cols, show="headings", selectmode="browse")
    for c in cols:
        tv.heading(c, text=c)
        tv.column(c, width=420 if c=="Tablet" else 300)
    tv.pack(side="left", fill="both", expand=True)

    sv = tk.Scrollbar(bottom_frame, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=sv.set)
    sv.pack(side="left", fill="y")

    def refresh_tablet_list():
        for item in tv.get_children():
            tv.delete(item)
        cur = db_conn.cursor(dictionary=True)
        cur.execute("SELECT id, item, time FROM reminders WHERE username=%s AND type='tablet' ORDER BY time", (username,))
        rows = cur.fetchall()
        cur.close()
        for r in rows:
            tstr = r["time"].strftime("%Y-%m-%d %H:%M") if r["time"] else ""
            tv.insert("", "end", iid=str(r["id"]), values=(r["item"], tstr))

    def delete_selected_tablet():
        sel = tv.selection()
        if not sel:
            messagebox.showwarning("Select", "Please select a tablet reminder to delete.")
            return
        iid = sel[0]
        cur = db_conn.cursor()
        cur.execute("DELETE FROM reminders WHERE id=%s AND username=%s AND type='tablet'", (int(iid), username))
        db_conn.commit()
        cur.close()
        refresh_tablet_list()
        messagebox.showinfo("Deleted", "Selected tablet reminder removed.")

    right_btns = tk.Frame(win, bg=PASTEL_BG)
    right_btns.pack(fill="x", padx=12, pady=8)
    tk.Button(right_btns, text="Delete Selected", command=delete_selected_tablet, **button_style).pack(side="left", padx=6)
    tk.Button(right_btns, text="Refresh List", command=refresh_tablet_list, **button_style).pack(side="left", padx=6)

    refresh_tablet_list()

# -------------------- Notification Box (checkbox list, minimal columns) --------------------

def notification_box():
    if not current_user:
        messagebox.showerror("Login", "Please login.")
        return

    win = tk.Toplevel(root)
    win.title("Notifications")
    win.configure(bg=PASTEL_BG)
    win.geometry("820x520")

    top = tk.Frame(win, bg=PASTEL_BG)
    top.pack(fill="x", padx=10, pady=6)
    tk.Label(top, text="Search reminders (type/item):", **label_style).pack(side="left", padx=(0,6))
    search_var = tk.StringVar()
    search_entry = tk.Entry(top, textvariable=search_var)
    search_entry.pack(side="left", padx=6)
    def do_search():
        load_notifications(query=search_var.get().strip())
    tk.Button(top, text="Search", command=do_search, **button_style).pack(side="left", padx=6)
    tk.Button(top, text="Clear", command=lambda: [search_var.set(""), load_notifications()], **button_style).pack(side="left", padx=6)

    # Scrollable frame for reminders with checkboxes (we remove ID, time and info from the main columns view)
    container = tk.Frame(win, bg=PASTEL_BG)
    container.pack(fill="both", expand=True, padx=10, pady=10)
    canvas = tk.Canvas(container, bg=PASTEL_BG, highlightthickness=0)
    checklist_frame = tk.Frame(canvas, bg=PASTEL_BG)
    vsb = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    canvas.create_window((0,0), window=checklist_frame, anchor="nw")
    def on_cf_config(e):
        canvas.configure(scrollregion=canvas.bbox("all"))
    checklist_frame.bind("<Configure>", on_cf_config)

    # Hold references for checkbox vars: id -> var
    reminder_vars = {}

    def clear_checklist():
        for w in checklist_frame.winfo_children():
            w.destroy()
        reminder_vars.clear()

    def load_notifications(query=None):
        clear_checklist()
        cur = db_conn.cursor(dictionary=True)
        if query:
            q = f"%{query}%"
            cur.execute("""SELECT * FROM reminders WHERE username=%s AND
                           (item LIKE %s OR type LIKE %s)
                           ORDER BY time DESC""", (current_user, q, q))
        else:
            cur.execute("SELECT * FROM reminders WHERE username=%s ORDER BY time DESC", (current_user,))
        rows = cur.fetchall()
        cur.close()

        for r in rows:
            rid = r["id"]
            rtype = r["type"]
            item = r["item"]
            time_str = r["time"].strftime("%Y-%m-%d %H:%M") if r["time"] else ""
            row = tk.Frame(checklist_frame, bg=PASTEL_BG, pady=4)
            row.pack(fill="x", padx=6, pady=2)
            var = tk.BooleanVar(value=False)
            reminder_vars[rid] = var
            cb = tk.Checkbutton(row, variable=var, bg=PASTEL_BG)
            cb.pack(side="left")
            lbl = tk.Label(row, text=f"[{rtype}] {item}", bg=PASTEL_BG, fg=PASTEL_TEXT, anchor="w", justify="left")
            lbl.pack(side="left", padx=6)
            if time_str:
                tlabel = tk.Label(row, text=f"  ({time_str})", bg=PASTEL_BG, fg="#666666")
                tlabel.pack(side="left", padx=8)

            # direct 'Mark taken' button per reminder
            def make_mark_func(rem_id=rid, rem_type=rtype, rem_item=item):
                def mark_taken():
                    cur2 = db_conn.cursor()
                    if rem_type == "vaccine" and " - Dose " in rem_item:
                        try:
                            vname, dosepart = rem_item.split(" - Dose ")
                            dose_num = int(dosepart.strip())
                            try:
                                cur2.execute("INSERT INTO vaccines_taken (username,vaccine,dose) VALUES (%s,%s,%s)", (current_user, vname, dose_num))
                            except IntegrityError:
                                pass
                        except Exception:
                            pass
                    cur2.execute("DELETE FROM reminders WHERE id=%s AND username=%s", (rem_id, current_user))
                    db_conn.commit()
                    cur2.close()
                    load_notifications()
                    messagebox.showinfo("Marked", "Marked as taken and removed from reminders.")
                return mark_taken

            tk.Button(row, text="Mark taken", command=make_mark_func(), **button_style).pack(side="right", padx=6)

    # Bulk action: check all marked checkboxes and mark taken
    def mark_selected_bulk():
        selected = [rid for rid, var in reminder_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("Select", "Tick the reminders you took (checkboxes) then click Mark Selected.")
            return
        cur = db_conn.cursor()
        for rid in selected:
            cur2 = db_conn.cursor(dictionary=True)
            cur2.execute("SELECT * FROM reminders WHERE id=%s AND username=%s", (rid, current_user))
            row = cur2.fetchone()
            cur2.close()
            if not row:
                continue
            rem_type = row["type"]
            rem_item = row["item"]
            if rem_type == "vaccine" and " - Dose " in rem_item:
                try:
                    vname, dosepart = rem_item.split(" - Dose ")
                    dose_num = int(dosepart.strip())
                    try:
                        cur.execute("INSERT INTO vaccines_taken (username,vaccine,dose) VALUES (%s,%s,%s)", (current_user, vname, dose_num))
                    except IntegrityError:
                        pass
                except:
                    pass
            cur.execute("DELETE FROM reminders WHERE id=%s AND username=%s", (rid, current_user))
        db_conn.commit()
        cur.close()
        load_notifications()
        messagebox.showinfo("Done", "Selected reminders marked as taken and removed.")

    bulk_frame = tk.Frame(win, bg=PASTEL_BG)
    bulk_frame.pack(fill="x", padx=10, pady=6)
    tk.Button(bulk_frame, text="Mark Selected", command=mark_selected_bulk, **button_style).pack(side="left", padx=6)
    tk.Button(bulk_frame, text="Refresh", command=lambda: load_notifications(query=search_var.get().strip()), **button_style).pack(side="left", padx=6)

    load_notifications()

# -------------------- Buttons Layout --------------------

frm = tk.Frame(root, bg=PASTEL_BG)
frm.pack(pady=20)

btn_cfg = {"width": 40}

tk.Button(frm, text="Vaccine Tracker",
          command=lambda: vaccine_tracker(current_user) if current_user else login_flow(vaccine_tracker),
          **button_style, **btn_cfg).pack(pady=6)

tk.Button(frm, text="Tablet Tracker",
          command=lambda: tablet_tracker(current_user) if current_user else login_flow(tablet_tracker),
          **button_style, **btn_cfg).pack(pady=6)

tk.Button(frm, text="View Vaccines",
          command=view_vaccines,
          **button_style, **btn_cfg).pack(pady=6)

tk.Button(frm, text="Common Diseases",
          command=open_common_diseases,
          **button_style, **btn_cfg).pack(pady=6)

tk.Button(frm, text="Notification Box",
          command=notification_box,
          **button_style, **btn_cfg).pack(pady=6)

tk.Button(frm, text="Create Account",
          command=create_account,
          **button_style, **btn_cfg).pack(pady=6)

tk.Button(frm, text="Logout / Login",
          command=lambda: [globals().__setitem__('current_user', None), refresh_status(), login_flow(lambda u: None)],
          **button_style, **btn_cfg).pack(pady=6)

# -------------------- START APP --------------------
init_db()
refresh_status()
root.mainloop()

import csv
import sqlite3
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    import pandas as pd
except Exception:  # pandas is optional at runtime for export fallback
    pd = None


DB_FILE = "dgx_tds_manager.db"
APP_TITLE = "DGx TDS Manager Pro"
FONT_FAMILY = "Segoe UI"


class DatabaseManager:
    """Handle all database operations for employees and payroll."""

    def __init__(self, db_file: str = DB_FILE):
        self.db_file = db_file
        self.conn = sqlite3.connect(self.db_file)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._create_tables()

    def _create_tables(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                designation TEXT,
                pan TEXT,
                employee_type TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS payroll (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                gross_salary REAL NOT NULL,
                tds_percent REAL NOT NULL,
                tds_amount REAL NOT NULL,
                net_salary REAL NOT NULL,
                date_created TEXT NOT NULL,
                FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
                UNIQUE(employee_id, month)
            )
            """
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # Employee operations
    def add_employee(self, name: str, designation: str, pan: str, employee_type: str) -> None:
        self.conn.execute(
            "INSERT INTO employees (name, designation, pan, employee_type) VALUES (?, ?, ?, ?)",
            (name.strip(), designation.strip(), pan.strip().upper(), employee_type.strip()),
        )
        self.conn.commit()

    def update_employee(self, employee_id: int, name: str, designation: str, pan: str, employee_type: str) -> None:
        self.conn.execute(
            """
            UPDATE employees
            SET name = ?, designation = ?, pan = ?, employee_type = ?
            WHERE id = ?
            """,
            (name.strip(), designation.strip(), pan.strip().upper(), employee_type.strip(), employee_id),
        )
        self.conn.commit()

    def delete_employee(self, employee_id: int) -> None:
        self.conn.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
        self.conn.commit()

    def fetch_employees(self):
        cur = self.conn.cursor()
        cur.execute("SELECT id, name, designation, pan, employee_type FROM employees ORDER BY name")
        return cur.fetchall()

    # Payroll operations
    def add_payroll_entry(
        self,
        employee_id: int,
        month: str,
        gross_salary: float,
        tds_percent: float,
        tds_amount: float,
        net_salary: float,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO payroll
            (employee_id, month, gross_salary, tds_percent, tds_amount, net_salary, date_created)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                employee_id,
                month,
                gross_salary,
                tds_percent,
                tds_amount,
                net_salary,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        self.conn.commit()

    def fetch_payroll_ledger(self, employee_id=None, month=None):
        query = (
            """
            SELECT p.id, e.name, p.month, p.gross_salary, p.tds_percent, p.tds_amount, p.net_salary, p.date_created
            FROM payroll p
            JOIN employees e ON p.employee_id = e.id
            WHERE 1 = 1
            """
        )
        params = []
        if employee_id:
            query += " AND e.id = ?"
            params.append(employee_id)
        if month:
            query += " AND p.month = ?"
            params.append(month)
        query += " ORDER BY p.month DESC, e.name"
        cur = self.conn.cursor()
        cur.execute(query, params)
        return cur.fetchall()

    def dashboard_summary(self):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM employees")
        total_employees = cur.fetchone()[0]

        current_month = datetime.now().strftime("%m-%Y")
        cur.execute(
            "SELECT COALESCE(SUM(gross_salary), 0), COALESCE(SUM(tds_amount), 0) FROM payroll WHERE month = ?",
            (current_month,),
        )
        total_payroll, total_tds = cur.fetchone()
        return total_employees, float(total_payroll), float(total_tds), current_month


class EmployeeEditDialog(tk.Toplevel):
    def __init__(self, parent, employee_data, on_save):
        super().__init__(parent)
        self.title("Edit Employee")
        self.geometry("420x280")
        self.resizable(False, False)
        self.configure(bg="#f4f6f8")
        self.transient(parent)
        self.grab_set()

        self.employee_id = employee_data[0]
        self.on_save = on_save

        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Name *").grid(row=0, column=0, sticky="w", pady=6)
        self.name_var = tk.StringVar(value=employee_data[1])
        ttk.Entry(frm, textvariable=self.name_var).grid(row=0, column=1, sticky="ew", pady=6)

        ttk.Label(frm, text="Designation").grid(row=1, column=0, sticky="w", pady=6)
        self.desig_var = tk.StringVar(value=employee_data[2])
        ttk.Entry(frm, textvariable=self.desig_var).grid(row=1, column=1, sticky="ew", pady=6)

        ttk.Label(frm, text="PAN Number").grid(row=2, column=0, sticky="w", pady=6)
        self.pan_var = tk.StringVar(value=employee_data[3])
        ttk.Entry(frm, textvariable=self.pan_var).grid(row=2, column=1, sticky="ew", pady=6)

        ttk.Label(frm, text="Employee Type").grid(row=3, column=0, sticky="w", pady=6)
        self.type_var = tk.StringVar(value=employee_data[4] or "Full-Time")
        ttk.Combobox(frm, textvariable=self.type_var, values=["Full-Time", "Freelancer"], state="readonly").grid(
            row=3, column=1, sticky="ew", pady=6
        )

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right", padx=6)
        ttk.Button(btns, text="Save", command=self._save).pack(side="right")
        frm.columnconfigure(1, weight=1)

    def _save(self):
        if not self.name_var.get().strip():
            messagebox.showerror(APP_TITLE, "Name is required.")
            return
        self.on_save(
            self.employee_id,
            self.name_var.get(),
            self.desig_var.get(),
            self.pan_var.get(),
            self.type_var.get(),
        )
        self.destroy()


class DGxTDSManagerPro(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1180x760")
        self.minsize(1080, 680)
        self.configure(bg="#f4f6f8")

        self.db = DatabaseManager()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._apply_theme()
        self._build_ui()
        self.refresh_all()

    def _apply_theme(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TFrame", background="#f4f6f8")
        style.configure("TLabel", font=(FONT_FAMILY, 10), background="#f4f6f8", foreground="#1f2937")
        style.configure("Header.TLabel", font=(FONT_FAMILY, 18, "bold"), foreground="#111827")
        style.configure("CardTitle.TLabel", font=(FONT_FAMILY, 11, "bold"), foreground="#374151")
        style.configure("CardValue.TLabel", font=(FONT_FAMILY, 16, "bold"), foreground="#111827")
        style.configure("TButton", font=(FONT_FAMILY, 10), padding=6)
        style.configure("TEntry", padding=4)
        style.configure("TNotebook", background="#f4f6f8", borderwidth=0)
        style.configure("TNotebook.Tab", font=(FONT_FAMILY, 10, "bold"), padding=(16, 8))
        style.map("TNotebook.Tab", background=[("selected", "#e5e7eb"), ("!selected", "#f4f6f8")])

        style.configure(
            "Treeview",
            font=(FONT_FAMILY, 10),
            rowheight=28,
            background="white",
            fieldbackground="white",
            foreground="#111827",
        )
        style.configure("Treeview.Heading", font=(FONT_FAMILY, 10, "bold"), background="#e5e7eb")

    def _build_ui(self):
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        ttk.Label(root, text=APP_TITLE, style="Header.TLabel").pack(anchor="w", pady=(0, 8))

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)

        self.dashboard_tab = ttk.Frame(self.notebook, padding=14)
        self.employees_tab = ttk.Frame(self.notebook, padding=14)
        self.payroll_tab = ttk.Frame(self.notebook, padding=14)
        self.reports_tab = ttk.Frame(self.notebook, padding=14)

        self.notebook.add(self.dashboard_tab, text="Dashboard")
        self.notebook.add(self.employees_tab, text="Employees")
        self.notebook.add(self.payroll_tab, text="Payroll Entry")
        self.notebook.add(self.reports_tab, text="Reports")

        self._build_dashboard_tab()
        self._build_employees_tab()
        self._build_payroll_tab()
        self._build_reports_tab()

    def _build_dashboard_tab(self):
        cards = ttk.Frame(self.dashboard_tab)
        cards.pack(fill="x")

        self.card_total_employees = self._create_card(cards, "Total Employees", "0")
        self.card_total_payroll = self._create_card(cards, "Total Payroll (This Month)", "₹0.00")
        self.card_total_tds = self._create_card(cards, "Total TDS Deducted (This Month)", "₹0.00")
        self.card_month = self._create_card(cards, "Current Payroll Month", "-")

        for i in range(4):
            cards.columnconfigure(i, weight=1)

    def _create_card(self, parent, title, value):
        card = tk.Frame(parent, bg="#ffffff", bd=1, relief="solid")
        card.grid(row=0, column=len(parent.grid_slaves(row=0)), sticky="nsew", padx=8, pady=8)
        box = ttk.Frame(card, padding=16)
        box.pack(fill="both", expand=True)
        ttk.Label(box, text=title, style="CardTitle.TLabel").pack(anchor="w")
        lbl = ttk.Label(box, text=value, style="CardValue.TLabel")
        lbl.pack(anchor="w", pady=(8, 0))
        return lbl

    def _build_employees_tab(self):
        form = ttk.LabelFrame(self.employees_tab, text="Add Employee", padding=12)
        form.pack(fill="x")

        self.emp_name_var = tk.StringVar()
        self.emp_desig_var = tk.StringVar()
        self.emp_pan_var = tk.StringVar()
        self.emp_type_var = tk.StringVar(value="Full-Time")

        ttk.Label(form, text="Name *").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(form, textvariable=self.emp_name_var).grid(row=0, column=1, sticky="ew", pady=5, padx=6)
        ttk.Label(form, text="Designation").grid(row=0, column=2, sticky="w", pady=5)
        ttk.Entry(form, textvariable=self.emp_desig_var).grid(row=0, column=3, sticky="ew", pady=5, padx=6)

        ttk.Label(form, text="PAN Number").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(form, textvariable=self.emp_pan_var).grid(row=1, column=1, sticky="ew", pady=5, padx=6)
        ttk.Label(form, text="Employee Type").grid(row=1, column=2, sticky="w", pady=5)
        ttk.Combobox(form, textvariable=self.emp_type_var, values=["Full-Time", "Freelancer"], state="readonly").grid(
            row=1, column=3, sticky="ew", pady=5, padx=6
        )

        ttk.Button(form, text="Add Employee", command=self.add_employee).grid(row=0, column=4, rowspan=2, padx=8)
        for i in range(4):
            form.columnconfigure(i, weight=1)

        controls = ttk.Frame(self.employees_tab)
        controls.pack(fill="x", pady=(10, 6))
        ttk.Button(controls, text="Edit Selected", command=self.edit_selected_employee).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Delete Selected", command=self.delete_selected_employee).pack(side="left")

        self.emp_tree = ttk.Treeview(
            self.employees_tab,
            columns=("id", "name", "designation", "pan", "employee_type"),
            show="headings",
            height=17,
        )
        for col, text, w in [
            ("id", "ID", 70),
            ("name", "Name", 240),
            ("designation", "Designation", 220),
            ("pan", "PAN", 170),
            ("employee_type", "Type", 140),
        ]:
            self.emp_tree.heading(col, text=text)
            self.emp_tree.column(col, width=w, anchor="w")
        self.emp_tree.pack(fill="both", expand=True)

    def _build_payroll_tab(self):
        form = ttk.LabelFrame(self.payroll_tab, text="Payroll Entry", padding=12)
        form.pack(fill="x")

        self.pay_emp_var = tk.StringVar()
        self.pay_month_var = tk.StringVar(value=datetime.now().strftime("%m-%Y"))
        self.pay_gross_var = tk.StringVar()
        self.pay_tds_percent_var = tk.StringVar(value="10")
        self.pay_tds_amount_var = tk.StringVar(value="0.00")
        self.pay_net_var = tk.StringVar(value="0.00")

        ttk.Label(form, text="Employee").grid(row=0, column=0, sticky="w", pady=5)
        self.pay_emp_combo = ttk.Combobox(form, textvariable=self.pay_emp_var, state="readonly")
        self.pay_emp_combo.grid(row=0, column=1, sticky="ew", padx=6, pady=5)

        ttk.Label(form, text="Month (MM-YYYY)").grid(row=0, column=2, sticky="w", pady=5)
        ttk.Entry(form, textvariable=self.pay_month_var).grid(row=0, column=3, sticky="ew", padx=6, pady=5)

        ttk.Label(form, text="Gross Salary").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(form, textvariable=self.pay_gross_var).grid(row=1, column=1, sticky="ew", padx=6, pady=5)

        ttk.Label(form, text="TDS %").grid(row=1, column=2, sticky="w", pady=5)
        ttk.Entry(form, textvariable=self.pay_tds_percent_var).grid(row=1, column=3, sticky="ew", padx=6, pady=5)

        ttk.Button(form, text="Calculate", command=self.calculate_payroll).grid(row=2, column=2, pady=10)
        ttk.Button(form, text="Save Entry", command=self.save_payroll).grid(row=2, column=3, pady=10, sticky="e")

        breakdown = ttk.LabelFrame(self.payroll_tab, text="Calculation Breakdown", padding=10)
        breakdown.pack(fill="x", pady=10)
        self.breakdown_label = ttk.Label(
            breakdown,
            text="TDS Amount = Gross Salary × (TDS % / 100)\nNet Salary = Gross Salary − TDS Amount",
            justify="left",
        )
        self.breakdown_label.pack(anchor="w")

        result = ttk.Frame(self.payroll_tab)
        result.pack(fill="x", pady=(2, 8))
        ttk.Label(result, text="TDS Amount:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Label(result, textvariable=self.pay_tds_amount_var).grid(row=0, column=1, sticky="w")
        ttk.Label(result, text="Net Salary:").grid(row=0, column=2, sticky="w", padx=(24, 8))
        ttk.Label(result, textvariable=self.pay_net_var).grid(row=0, column=3, sticky="w")

        for i in range(4):
            form.columnconfigure(i, weight=1)

    def _build_reports_tab(self):
        flt = ttk.LabelFrame(self.reports_tab, text="Filters", padding=10)
        flt.pack(fill="x")

        self.rep_emp_var = tk.StringVar(value="All")
        self.rep_month_var = tk.StringVar(value="")

        ttk.Label(flt, text="Employee").grid(row=0, column=0, sticky="w", pady=4)
        self.rep_emp_combo = ttk.Combobox(flt, textvariable=self.rep_emp_var, state="readonly")
        self.rep_emp_combo.grid(row=0, column=1, sticky="ew", padx=6, pady=4)

        ttk.Label(flt, text="Month (MM-YYYY)").grid(row=0, column=2, sticky="w", pady=4)
        ttk.Entry(flt, textvariable=self.rep_month_var).grid(row=0, column=3, sticky="ew", padx=6, pady=4)

        ttk.Button(flt, text="Apply Filters", command=self.refresh_reports).grid(row=0, column=4, padx=6)
        ttk.Button(flt, text="Export CSV", command=self.export_report_csv).grid(row=0, column=5, padx=6)

        for i in range(4):
            flt.columnconfigure(i, weight=1)

        self.rep_tree = ttk.Treeview(
            self.reports_tab,
            columns=("id", "employee", "month", "gross", "tds_percent", "tds", "net", "date"),
            show="headings",
            height=16,
        )
        for col, text, w in [
            ("id", "ID", 60),
            ("employee", "Employee", 210),
            ("month", "Month", 110),
            ("gross", "Gross", 120),
            ("tds_percent", "TDS %", 90),
            ("tds", "TDS Amount", 120),
            ("net", "Net Salary", 120),
            ("date", "Created On", 180),
        ]:
            self.rep_tree.heading(col, text=text)
            self.rep_tree.column(col, width=w, anchor="w")
        self.rep_tree.pack(fill="both", expand=True, pady=8)

        totals = ttk.Frame(self.reports_tab)
        totals.pack(fill="x", pady=(0, 4))

        self.total_gross_var = tk.StringVar(value="₹0.00")
        self.total_tds_var = tk.StringVar(value="₹0.00")
        self.total_net_var = tk.StringVar(value="₹0.00")

        ttk.Label(totals, text="Total Gross:").pack(side="left", padx=(0, 6))
        ttk.Label(totals, textvariable=self.total_gross_var).pack(side="left", padx=(0, 16))
        ttk.Label(totals, text="Total TDS:").pack(side="left", padx=(0, 6))
        ttk.Label(totals, textvariable=self.total_tds_var).pack(side="left", padx=(0, 16))
        ttk.Label(totals, text="Total Net:").pack(side="left", padx=(0, 6))
        ttk.Label(totals, textvariable=self.total_net_var).pack(side="left")

    def refresh_all(self):
        self.refresh_employees()
        self.refresh_payroll_employee_dropdown()
        self.refresh_reports_employee_dropdown()
        self.refresh_reports()
        self.refresh_dashboard()

    def refresh_dashboard(self):
        total_emp, total_payroll, total_tds, month = self.db.dashboard_summary()
        self.card_total_employees.config(text=str(total_emp))
        self.card_total_payroll.config(text=f"₹{total_payroll:,.2f}")
        self.card_total_tds.config(text=f"₹{total_tds:,.2f}")
        self.card_month.config(text=month)

    def refresh_employees(self):
        for row in self.emp_tree.get_children():
            self.emp_tree.delete(row)
        for row in self.db.fetch_employees():
            self.emp_tree.insert("", "end", values=row)

    def refresh_payroll_employee_dropdown(self):
        employees = self.db.fetch_employees()
        self.employee_map = {f"{eid} - {name}": eid for eid, name, *_ in employees}
        names = list(self.employee_map.keys())
        self.pay_emp_combo["values"] = names
        if names and self.pay_emp_var.get() not in names:
            self.pay_emp_var.set(names[0])

    def refresh_reports_employee_dropdown(self):
        employees = self.db.fetch_employees()
        self.report_employee_map = {"All": None}
        for eid, name, *_ in employees:
            self.report_employee_map[f"{eid} - {name}"] = eid
        values = list(self.report_employee_map.keys())
        self.rep_emp_combo["values"] = values
        if self.rep_emp_var.get() not in values:
            self.rep_emp_var.set("All")

    def add_employee(self):
        try:
            name = self.emp_name_var.get().strip()
            if not name:
                messagebox.showerror(APP_TITLE, "Employee name is required.")
                return
            self.db.add_employee(name, self.emp_desig_var.get(), self.emp_pan_var.get(), self.emp_type_var.get())
            messagebox.showinfo(APP_TITLE, "Employee added successfully.")
            self.emp_name_var.set("")
            self.emp_desig_var.set("")
            self.emp_pan_var.set("")
            self.emp_type_var.set("Full-Time")
            self.refresh_all()
        except Exception as err:
            messagebox.showerror(APP_TITLE, f"Failed to add employee.\n{err}")

    def _get_selected_employee(self):
        sel = self.emp_tree.selection()
        if not sel:
            return None
        return self.emp_tree.item(sel[0], "values")

    def edit_selected_employee(self):
        row = self._get_selected_employee()
        if not row:
            messagebox.showwarning(APP_TITLE, "Please select an employee to edit.")
            return

        def on_save(employee_id, name, designation, pan, employee_type):
            try:
                self.db.update_employee(employee_id, name, designation, pan, employee_type)
                messagebox.showinfo(APP_TITLE, "Employee updated successfully.")
                self.refresh_all()
            except Exception as err:
                messagebox.showerror(APP_TITLE, f"Failed to update employee.\n{err}")

        EmployeeEditDialog(self, row, on_save)

    def delete_selected_employee(self):
        row = self._get_selected_employee()
        if not row:
            messagebox.showwarning(APP_TITLE, "Please select an employee to delete.")
            return
        employee_id, name = int(row[0]), row[1]
        confirm = messagebox.askyesno(APP_TITLE, f"Delete employee '{name}' and linked payroll records?")
        if not confirm:
            return
        try:
            self.db.delete_employee(employee_id)
            messagebox.showinfo(APP_TITLE, "Employee deleted successfully.")
            self.refresh_all()
        except Exception as err:
            messagebox.showerror(APP_TITLE, f"Failed to delete employee.\n{err}")

    def calculate_payroll(self):
        try:
            gross = float(self.pay_gross_var.get())
            percent = float(self.pay_tds_percent_var.get())
            if gross < 0 or percent < 0:
                raise ValueError("Gross salary and TDS percent must be non-negative.")
            tds_amount = gross * (percent / 100)
            net_salary = gross - tds_amount
            self.pay_tds_amount_var.set(f"₹{tds_amount:,.2f}")
            self.pay_net_var.set(f"₹{net_salary:,.2f}")
            self.breakdown_label.config(
                text=(
                    f"TDS Amount = {gross:,.2f} × ({percent:.2f}/100) = {tds_amount:,.2f}\n"
                    f"Net Salary = {gross:,.2f} − {tds_amount:,.2f} = {net_salary:,.2f}"
                )
            )
            return tds_amount, net_salary
        except Exception as err:
            messagebox.showerror(APP_TITLE, f"Invalid payroll inputs.\n{err}")
            return None

    @staticmethod
    def _is_valid_month(month_text: str) -> bool:
        try:
            datetime.strptime(month_text, "%m-%Y")
            return True
        except ValueError:
            return False

    def save_payroll(self):
        try:
            selected_emp = self.pay_emp_var.get()
            if not selected_emp or selected_emp not in self.employee_map:
                messagebox.showerror(APP_TITLE, "Please select a valid employee.")
                return

            month = self.pay_month_var.get().strip()
            if not self._is_valid_month(month):
                messagebox.showerror(APP_TITLE, "Month must be in MM-YYYY format.")
                return

            calc_result = self.calculate_payroll()
            if calc_result is None:
                return
            tds_amount, net_salary = calc_result
            gross = float(self.pay_gross_var.get())
            percent = float(self.pay_tds_percent_var.get())

            self.db.add_payroll_entry(
                self.employee_map[selected_emp],
                month,
                gross,
                percent,
                tds_amount,
                net_salary,
            )
            messagebox.showinfo(APP_TITLE, "Payroll entry saved successfully.")
            self.pay_gross_var.set("")
            self.pay_tds_percent_var.set("10")
            self.pay_tds_amount_var.set("0.00")
            self.pay_net_var.set("0.00")
            self.breakdown_label.config(
                text="TDS Amount = Gross Salary × (TDS % / 100)\nNet Salary = Gross Salary − TDS Amount"
            )
            self.refresh_all()
        except sqlite3.IntegrityError:
            messagebox.showerror(APP_TITLE, "Duplicate entry: payroll for this employee and month already exists.")
        except Exception as err:
            messagebox.showerror(APP_TITLE, f"Failed to save payroll entry.\n{err}")

    def refresh_reports(self):
        for row in self.rep_tree.get_children():
            self.rep_tree.delete(row)

        employee_id = self.report_employee_map.get(self.rep_emp_var.get()) if hasattr(self, "report_employee_map") else None
        month = self.rep_month_var.get().strip() or None
        if month and not self._is_valid_month(month):
            messagebox.showwarning(APP_TITLE, "Month filter ignored. Use MM-YYYY format.")
            month = None

        rows = self.db.fetch_payroll_ledger(employee_id, month)
        total_gross = total_tds = total_net = 0.0

        for r in rows:
            total_gross += float(r[3])
            total_tds += float(r[5])
            total_net += float(r[6])
            self.rep_tree.insert(
                "",
                "end",
                values=(
                    r[0],
                    r[1],
                    r[2],
                    f"₹{r[3]:,.2f}",
                    f"{r[4]:.2f}",
                    f"₹{r[5]:,.2f}",
                    f"₹{r[6]:,.2f}",
                    r[7],
                ),
            )

        self.total_gross_var.set(f"₹{total_gross:,.2f}")
        self.total_tds_var.set(f"₹{total_tds:,.2f}")
        self.total_net_var.set(f"₹{total_net:,.2f}")

    def export_report_csv(self):
        employee_id = self.report_employee_map.get(self.rep_emp_var.get()) if hasattr(self, "report_employee_map") else None
        month = self.rep_month_var.get().strip() or None
        if month and not self._is_valid_month(month):
            messagebox.showerror(APP_TITLE, "Month must be in MM-YYYY format.")
            return

        rows = self.db.fetch_payroll_ledger(employee_id, month)
        if not rows:
            messagebox.showwarning(APP_TITLE, "No report data to export.")
            return

        path = filedialog.asksaveasfilename(
            title="Export Report to CSV",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            initialfile="dgx_tds_report.csv",
        )
        if not path:
            return

        columns = [
            "id",
            "employee_name",
            "month",
            "gross_salary",
            "tds_percent",
            "tds_amount",
            "net_salary",
            "date_created",
        ]
        try:
            if pd is not None:
                df = pd.DataFrame(rows, columns=columns)
                df.to_csv(path, index=False)
            else:
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(columns)
                    writer.writerows(rows)
            messagebox.showinfo(APP_TITLE, f"Report exported successfully to:\n{path}")
        except Exception as err:
            messagebox.showerror(APP_TITLE, f"Failed to export report.\n{err}")

    def on_close(self):
        if messagebox.askokcancel(APP_TITLE, "Exit DGx TDS Manager Pro?"):
            try:
                self.db.close()
            finally:
                self.destroy()


def main():
    app = DGxTDSManagerPro()
    app.mainloop()


if __name__ == "__main__":
    main()

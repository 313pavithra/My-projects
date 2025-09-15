#!/usr/bin/env python3
"""
Task Manager App (single-file)
- Tkinter GUI
- SQLite persistence (tasks.db)
- Add / Edit / Delete / Complete / Search / Export CSV / Clear Completed
Run: python task_manager.py
"""

import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime
import csv
import os

DB_FILE = "tasks.db"
DATE_FORMAT = "%Y-%m-%d"  # ISO date format for due date

# ----------------- Database helpers -----------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        due_date TEXT,
        priority TEXT,
        completed INTEGER DEFAULT 0,
        created_at TEXT
    );
    """)
    conn.commit()
    conn.close()

def add_task_db(title, description, due_date, priority):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO tasks (title, description, due_date, priority, completed, created_at)
        VALUES (?, ?, ?, ?, 0, ?)
    """, (title, description, due_date, priority, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def update_task_db(task_id, title, description, due_date, priority, completed):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        UPDATE tasks
        SET title=?, description=?, due_date=?, priority=?, completed=?
        WHERE id=?
    """, (title, description, due_date, priority, int(bool(completed)), task_id))
    conn.commit()
    conn.close()

def delete_task_db(task_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()

def fetch_tasks_db(filter_text=None, sort_by="id", order="ASC"):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    q = "SELECT id, title, description, due_date, priority, completed, created_at FROM tasks"
    params = ()
    if filter_text:
        q += " WHERE title LIKE ? OR description LIKE ?"
        ft = f"%{filter_text}%"
        params = (ft, ft)
    # sanitize column names: allow only known columns
    allowed = {"id","title","description","due_date","priority","completed","created_at"}
    if sort_by not in allowed:
        sort_by = "id"
    if order.upper() not in ("ASC","DESC"):
        order = "ASC"
    q += f" ORDER BY {sort_by} {order}"
    cur.execute(q, params)
    rows = cur.fetchall()
    conn.close()
    return rows

def export_tasks_csv(path):
    rows = fetch_tasks_db()
    with open(path, "w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id","title","description","due_date","priority","completed","created_at"])
        writer.writerows(rows)

def clear_completed_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE completed=1")
    conn.commit()
    conn.close()

# ----------------- GUI helpers -----------------
class TaskDialog(simpledialog.Dialog):
    """
    Modal dialog for Add / Edit Task
    """
    def __init__(self, parent, title=None, initial=None):
        self.initial = initial or {}
        super().__init__(parent, title=title)

    def body(self, master):
        tk.Label(master, text="Title *").grid(row=0, column=0, sticky="w")
        self.title_var = tk.StringVar(value=self.initial.get("title",""))
        self.title_entry = tk.Entry(master, textvariable=self.title_var, width=48)
        self.title_entry.grid(row=0, column=1, pady=4)

        tk.Label(master, text="Description").grid(row=1, column=0, sticky="nw")
        self.desc_text = tk.Text(master, width=36, height=6)
        self.desc_text.grid(row=1, column=1, pady=4)
        self.desc_text.insert("1.0", self.initial.get("description",""))

        tk.Label(master, text="Due Date (YYYY-MM-DD)").grid(row=2, column=0, sticky="w")
        self.due_var = tk.StringVar(value=self.initial.get("due_date",""))
        self.due_entry = tk.Entry(master, textvariable=self.due_var)
        self.due_entry.grid(row=2, column=1, pady=4, sticky="w")

        tk.Label(master, text="Priority").grid(row=3, column=0, sticky="w")
        self.priority_var = tk.StringVar(value=self.initial.get("priority","Medium"))
        self.prio_cb = ttk.Combobox(master, textvariable=self.priority_var, values=["Low","Medium","High"], state="readonly", width=15)
        self.prio_cb.grid(row=3, column=1, sticky="w")

        self.completed_var = tk.IntVar(value=self.initial.get("completed",0))
        # If editing, allow marking completed
        if self.initial:
            self.completed_chk = tk.Checkbutton(master, text="Completed", variable=self.completed_var)
            self.completed_chk.grid(row=4, column=1, sticky="w", pady=(6,0))

        return self.title_entry

    def validate(self):
        title = self.title_var.get().strip()
        if not title:
            messagebox.showerror("Validation error", "Title is required.")
            return False
        due = self.due_var.get().strip()
        if due:
            try:
                datetime.strptime(due, DATE_FORMAT)
            except Exception:
                messagebox.showerror("Validation error", f"Due date must be in {DATE_FORMAT} format or empty.")
                return False
        return True

    def apply(self):
        self.result = {
            "title": self.title_var.get().strip(),
            "description": self.desc_text.get("1.0","end").strip(),
            "due_date": self.due_var.get().strip(),
            "priority": self.priority_var.get(),
            "completed": self.completed_var.get() if hasattr(self,'completed_var') else 0
        }

# ----------------- Main Application -----------------
class TaskManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Task Manager — Pavithra")
        self.geometry("980x640")
        self.minsize(760, 520)
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        # Treeview columns and sort state
        self.columns = ("id","title","description","due_date","priority","completed")
        self.sort_by = "id"
        self.sort_order = "ASC"

        self._build_ui()
        self._bind_events()
        self.refresh_tasks()

    def _build_ui(self):
        # Top frame: controls
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", padx=12, pady=8)

        self.add_btn = ttk.Button(top_frame, text="Add Task", command=self.add_task)
        self.add_btn.pack(side="left", padx=(0,8))

        self.edit_btn = ttk.Button(top_frame, text="Edit Task", command=self.edit_task)
        self.edit_btn.pack(side="left", padx=(0,8))

        self.delete_btn = ttk.Button(top_frame, text="Delete Task", command=self.delete_task)
        self.delete_btn.pack(side="left", padx=(0,8))

        self.complete_btn = ttk.Button(top_frame, text="Toggle Complete", command=self.toggle_complete)
        self.complete_btn.pack(side="left", padx=(0,8))

        ttk.Separator(top_frame, orient="vertical").pack(side="left", fill="y", padx=6)

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(top_frame, textvariable=self.search_var, width=28)
        self.search_entry.pack(side="left", padx=(6,4))
        self.search_btn = ttk.Button(top_frame, text="Search", command=self.search_tasks)
        self.search_btn.pack(side="left", padx=(0,8))

        self.clear_search_btn = ttk.Button(top_frame, text="Clear", command=self.clear_search)
        self.clear_search_btn.pack(side="left", padx=(0,8))

        ttk.Separator(top_frame, orient="vertical").pack(side="left", fill="y", padx=6)

        self.export_btn = ttk.Button(top_frame, text="Export CSV", command=self.export_csv)
        self.export_btn.pack(side="left", padx=(6,8))

        self.clear_completed_btn = ttk.Button(top_frame, text="Clear Completed", command=self.clear_completed)
        self.clear_completed_btn.pack(side="left", padx=(0,8))

        # Middle frame: treeview
        mid_frame = ttk.Frame(self)
        mid_frame.pack(fill="both", expand=True, padx=12, pady=(0,12))

        columns = self.columns
        self.tree = ttk.Treeview(mid_frame, columns=columns, show="headings", selectmode="browse")
        # define headings
        self.tree.heading("id", text="ID", anchor="center", command=lambda: self.sort_column("id"))
        self.tree.heading("title", text="Title", anchor="w", command=lambda: self.sort_column("title"))
        self.tree.heading("description", text="Description", anchor="w", command=lambda: self.sort_column("description"))
        self.tree.heading("due_date", text="Due Date", anchor="center", command=lambda: self.sort_column("due_date"))
        self.tree.heading("priority", text="Priority", anchor="center", command=lambda: self.sort_column("priority"))
        self.tree.heading("completed", text="Done", anchor="center", command=lambda: self.sort_column("completed"))

        # column sizes
        self.tree.column("id", width=60, anchor="center")
        self.tree.column("title", width=220, anchor="w")
        self.tree.column("description", width=360, anchor="w")
        self.tree.column("due_date", width=110, anchor="center")
        self.tree.column("priority", width=80, anchor="center")
        self.tree.column("completed", width=60, anchor="center")

        vsb = ttk.Scrollbar(mid_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(mid_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        mid_frame.rowconfigure(0, weight=1)
        mid_frame.columnconfigure(0, weight=1)

        # bottom status
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=12, pady=(0,12))
        self.status_label = ttk.Label(bottom, text="Ready")
        self.status_label.pack(side="left")

    # ----------------- Actions -----------------
    def refresh_tasks(self, filter_text=None):
        for r in self.tree.get_children():
            self.tree.delete(r)
        rows = fetch_tasks_db(filter_text=filter_text, sort_by=self.sort_by, order=self.sort_order)
        for row in rows:
            tid, title, desc, due, prio, completed, created = row
            due_disp = due if due else ""
            completed_disp = "✓" if completed else ""
            # shorten description for grid display
            desc_short = (desc[:180] + '...') if desc and len(desc) > 180 else (desc or "")
            self.tree.insert("", "end", iid=str(tid), values=(tid, title, desc_short, due_disp, prio, completed_disp))
        self.status_label.config(text=f"{len(rows)} tasks shown")

    def add_task(self):
        dlg = TaskDialog(self, title="Add Task")
        if getattr(dlg, "result", None):
            r = dlg.result
            add_task_db(r["title"], r["description"], r["due_date"], r["priority"])
            self.refresh_tasks()
            messagebox.showinfo("Success", "Task added.")

    def edit_task(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Please select a task to edit.")
            return
        tid = int(sel[0])
        # fetch full record
        rows = fetch_tasks_db()
        rec = None
        for row in rows:
            if row[0] == tid:
                rec = row; break
        if not rec:
            messagebox.showerror("Error", "Selected task not found.")
            return
        initial = {
            "title": rec[1],
            "description": rec[2] or "",
            "due_date": rec[3] or "",
            "priority": rec[4] or "Medium",
            "completed": rec[5]
        }
        dlg = TaskDialog(self, title="Edit Task", initial=initial)
        if getattr(dlg, "result", None):
            r = dlg.result
            update_task_db(tid, r["title"], r["description"], r["due_date"], r["priority"], r["completed"])
            self.refresh_tasks()
            messagebox.showinfo("Success", "Task updated.")

    def delete_task(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Please select a task to delete.")
            return
        tid = int(sel[0])
        if messagebox.askyesno("Confirm", "Delete the selected task?"):
            delete_task_db(tid)
            self.refresh_tasks()

    def toggle_complete(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a task to toggle completion.")
            return
        tid = int(sel[0])
        # get current completed value
        rows = fetch_tasks_db()
        rec = None
        for row in rows:
            if row[0] == tid:
                rec = row; break
        if not rec:
            return
        current = bool(rec[5])
        # flip
        update_task_db(tid, rec[1], rec[2], rec[3], rec[4], not current)
        self.refresh_tasks()

    def search_tasks(self):
        q = self.search_var.get().strip()
        self.refresh_tasks(filter_text=q)

    def clear_search(self):
        self.search_var.set("")
        self.refresh_tasks()

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files","*.csv")], title="Export tasks to CSV")
        if not path:
            return
        try:
            export_tasks_csv(path)
            messagebox.showinfo("Exported", f"Tasks exported to {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")

    def clear_completed(self):
        if messagebox.askyesno("Confirm", "Delete all completed tasks?"):
            clear_completed_db()
            self.refresh_tasks()

    def sort_column(self, col):
        # toggle order if same column
        if self.sort_by == col:
            self.sort_order = "DESC" if self.sort_order == "ASC" else "ASC"
        else:
            self.sort_by = col
            self.sort_order = "ASC"
        self.refresh_tasks()

    def _bind_events(self):
        self.tree.bind("<Double-1>", lambda e: self.edit_task())
        self.bind("<Control-f>", lambda e: self.search_entry.focus_set())
        # allow Delete key to remove task
        self.bind("<Delete>", lambda e: self.delete_task())

# ----------------- Run -----------------
def main():
    init_db()
    app = TaskManagerApp()
    app.mainloop()

if __name__ == "__main__":
    main()

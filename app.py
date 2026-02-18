import os
import threading
import time
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image

# Opcional: icona barra de tasques Windows (només Windows)
try:
    import ctypes
except Exception:
    ctypes = None

import core

# ---------- Theme ----------
UPC_BLUE = "#0066A1"
BG = "#FFFFFF"
LIGHT_PANEL = "#F3F4F6"
TEXT_MUTED = "#4B5563"

ctk.set_appearance_mode("light")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Fix icona barra de tasques Windows (més fiable a l'EXE)
        if ctypes:
            try:
                myappid = "upc.faq.scraper.v1"
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass

        self.title("UPC FAQ Scraper")
        self.geometry("1100x760")
        self.minsize(980, 680)
        self.configure(fg_color=BG)

        # Taskbar icon
        try:
            self.iconbitmap("assets/upc_logo.ico")
        except Exception:
            pass

        # ---------- State ----------
        # INPUT: sempre CSV
        self.input_mode = ctk.StringVar(value="csv")

        # OUTPUT: "csv" | "sheets_oauth" | "genweb_json"
        self.output_mode = ctk.StringVar(value="csv")

        # Input CSV
        self.sources_csv_path = ctk.StringVar()

        # Output file (csv/json)
        self.output_file_path = ctk.StringVar()

        # Output sheets
        self.output_sheet_title = ctk.StringVar(value="UPC FAQ Export")
        self.output_sheet_tab = ctk.StringVar(value="FAQs")

        # OAuth files (Sheets)
        self.oauth_client_json = ctk.StringVar(value="oauth_client.json")
        self.token_file = ctk.StringVar(value="token.json")

        # ---------- Layout ----------
        self._build_header()
        self._build_body()
        self._refresh_ui()

        self.println("Quan hagis seleccionat la ruta d’entrada i sortida, prem «Executa».")

    # ================= UI BUILD =================
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=UPC_BLUE, corner_radius=0, height=92)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Logo
        try:
            logo_image = ctk.CTkImage(
                light_image=Image.open("assets/upc_logo.png"),
                size=(58, 58)
            )
            ctk.CTkLabel(header, image=logo_image, text="").pack(side="left", padx=(18, 10))
        except Exception:
            ctk.CTkLabel(
                header, text="UPC", text_color="white",
                font=ctk.CTkFont(size=18, weight="bold")
            ).pack(side="left", padx=(18, 10))

        ctk.CTkLabel(
            header,
            text="UNIVERSITAT POLITÈCNICA DE CATALUNYA",
            text_color="white",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left", padx=6)

        ctk.CTkLabel(
            header,
            text="FAQ Scraper",
            text_color="white",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(side="right", padx=18)

    def _build_body(self):
        body = ctk.CTkScrollableFrame(self, fg_color=BG)
        body.pack(fill="both", expand=True, padx=18, pady=18)
        body.grid_columnconfigure(0, weight=1)

        # Help box (compacte)
        help_box = ctk.CTkFrame(body, fg_color=LIGHT_PANEL, corner_radius=8)
        help_box.grid(row=0, column=0, sticky="ew", padx=6, pady=(0, 10))

        help_text = (
            "📌 Funcionament\n"
            "• Entrada: CSV (URL | topic)\n"
            "• Procés: s’extreuen les PMF/FAQs de cada URL\n"
            "• Sortida: CSV, Google Sheets o JSON (Genweb)"
        )

        ctk.CTkLabel(
            help_box,
            text=help_text,
            justify="left",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=12, pady=8)

        # ---------- Card ENTRADA ----------
        self.in_card = ctk.CTkFrame(body, fg_color=LIGHT_PANEL, corner_radius=10)
        self.in_card.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 10))
        self.in_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self.in_card, text="ENTRADA",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, columnspan=3, padx=12, pady=(10, 6), sticky="w")

        self.in_csv_row = ctk.CTkFrame(self.in_card, fg_color="transparent")
        self.in_csv_row.grid(row=1, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 10))
        self.in_csv_row.grid_columnconfigure(1, weight=1)

        self._file_row_with_hint(
            parent=self.in_csv_row,
            row=0,
            title="Fitxer CSV d’entrada",
            hint="• Columna 1: URL de la pàgina amb les PMF\n• Columna 2: topic/tema (identificador intern)",
            var=self.sources_csv_path,
            save=False,
            types=[("CSV", "*.csv")],
        )

        # ---------- Card SORTIDA ----------
        self.out_card = ctk.CTkFrame(body, fg_color=LIGHT_PANEL, corner_radius=10)
        self.out_card.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 10))
        self.out_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self.out_card, text="SORTIDA",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, columnspan=3, padx=12, pady=(10, 6), sticky="w")

        # Ràdios output
        out_mode_frame = ctk.CTkFrame(self.out_card, fg_color="transparent")
        out_mode_frame.grid(row=1, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 6))

        ctk.CTkRadioButton(
            out_mode_frame, text="CSV", variable=self.output_mode, value="csv",
            command=self._refresh_ui
        ).pack(side="left", padx=(0, 18))

        ctk.CTkRadioButton(
            out_mode_frame, text="Google Sheets", variable=self.output_mode, value="sheets_oauth",
            command=self._refresh_ui
        ).pack(side="left", padx=(0, 18))

        ctk.CTkRadioButton(
            out_mode_frame, text="JSON (Genweb)", variable=self.output_mode, value="genweb_json",
            command=self._refresh_ui
        ).pack(side="left")

        # Output file row (CSV/JSON)
        self.out_file_row = ctk.CTkFrame(self.out_card, fg_color="transparent")
        self.out_file_row.grid(row=2, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 10))
        self.out_file_row.grid_columnconfigure(1, weight=1)

        self._file_row(
            parent=self.out_file_row,
            row=0,
            label="Fitxer de sortida",
            var=self.output_file_path,
            save=True,
            types=[("CSV", "*.csv"), ("JSON", "*.json")],
        )

        # Output Sheets rows
        self.out_sheets_row = ctk.CTkFrame(self.out_card, fg_color="transparent")
        self.out_sheets_row.grid(row=3, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 10))
        self.out_sheets_row.grid_columnconfigure(1, weight=1)

        self._text_row(self.out_sheets_row, 0, "Títol del Google Sheet", self.output_sheet_title)
        self._text_row(self.out_sheets_row, 1, "Nom de la pestanya", self.output_sheet_tab)

        # OAuth row (només si Sheets)
        self.oauth_row = ctk.CTkFrame(self.out_card, fg_color="transparent")
        self.oauth_row.grid(row=4, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 10))
        self.oauth_row.grid_columnconfigure(1, weight=1)

        self._file_row(
            parent=self.oauth_row,
            row=0,
            label="OAuth client (oauth_client.json)",
            var=self.oauth_client_json,
            save=False,
            types=[("JSON", "*.json")],
            button_text="Explora…",
        )

        # Buttons
        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.grid(row=3, column=0, sticky="w", padx=6, pady=(4, 6))

        self.run_btn = ctk.CTkButton(btns, text="Executa", command=self.run_clicked, width=140)
        self.run_btn.pack(side="left")

        self.sample_btn = ctk.CTkButton(btns, text="Crear CSV d’exemple", command=self.create_sample_csv, width=180)
        self.sample_btn.pack(side="left", padx=10)

        self.progress = ctk.CTkProgressBar(body)
        self.progress.grid(row=4, column=0, sticky="ew", padx=6, pady=(6, 10))
        self.progress.set(0)

        # Log
        self.log = ctk.CTkTextbox(body, height=320)
        self.log.grid(row=5, column=0, padx=6, pady=10, sticky="nsew")

    # ================= UI HELPERS =================
    def _file_row(self, parent, row, label, var, save, types, button_text="Navega…"):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, padx=6, pady=10, sticky="w")
        ctk.CTkEntry(parent, textvariable=var).grid(row=row, column=1, padx=6, pady=10, sticky="ew")

        def browse():
            if save:
                mode = self.output_mode.get()
                if mode == "csv":
                    default_ext = ".csv"
                    filetypes = [("CSV", "*.csv")]
                elif mode == "genweb_json":
                    default_ext = ".json"
                    filetypes = [("JSON", "*.json")]
                else:
                    # Sheets: en teoria aquest camp no es mostra, però per seguretat
                    default_ext = ".csv"
                    filetypes = [("CSV", "*.csv")]

                path = filedialog.asksaveasfilename(
                    defaultextension=default_ext,
                    filetypes=filetypes
                )
            else:
                path = filedialog.askopenfilename(filetypes=types)

            if path:
                var.set(path)

        ctk.CTkButton(parent, text=button_text, width=110, command=browse).grid(
            row=row, column=2, padx=6, pady=10
        )

    def _file_row_with_hint(self, parent, row, title, hint, var, save, types):
        # Columna 0: títol + hint
        left = ctk.CTkFrame(parent, fg_color="transparent")
        left.grid(row=row, column=0, padx=6, pady=10, sticky="nw")

        ctk.CTkLabel(left, text=title).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text=hint,
            justify="left",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 0))

        # Entry
        ctk.CTkEntry(parent, textvariable=var).grid(row=row, column=1, padx=6, pady=10, sticky="ew")

        def browse():
            if save:
                default_ext = ".csv"
                path = filedialog.asksaveasfilename(defaultextension=default_ext, filetypes=types)
            else:
                path = filedialog.askopenfilename(filetypes=types)
            if path:
                var.set(path)

        ctk.CTkButton(parent, text="Explora…", width=110, command=browse).grid(
            row=row, column=2, padx=6, pady=10, sticky="ne"
        )

    def _text_row(self, parent, row, label, var):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, padx=10, pady=6, sticky="w")
        ctk.CTkEntry(parent, textvariable=var).grid(row=row, column=1, padx=6, pady=6, sticky="ew")
        ctk.CTkLabel(parent, text="").grid(row=row, column=2, padx=6, pady=6)  # spacer

    def println(self, msg):
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    def ui_log(self, msg: str):
        self.after(0, lambda: self.println(msg))

    def _needs_oauth(self) -> bool:
        return self.output_mode.get() == "sheets_oauth"

    def _refresh_ui(self):
        # Output: mostrar fitxer o camps sheets
        if self.output_mode.get() == "sheets_oauth":
            self.out_file_row.grid_remove()
            self.out_sheets_row.grid()
            self.oauth_row.grid()
        else:
            self.out_sheets_row.grid_remove()
            self.oauth_row.grid_remove()
            self.out_file_row.grid()

    # ================= ACTIONS =================
    def create_sample_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        sample = (
            "URL,topic\n"
            "https://eseiaat.upc.edu/ca/proves-eugeni/prova-faqs-1,tfe\n"
        )
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write(sample)
        self.sources_csv_path.set(path)
        self.println(f"✅ CSV d’exemple creat: {path}")

    def validate_inputs(self):
        # INPUT (CSV)
        src = self.sources_csv_path.get().strip()
        if not src or not os.path.exists(src):
            return False, "Selecciona un CSV d’entrada existent."

        # OUTPUT
        mode = self.output_mode.get()
        if mode in ("csv", "genweb_json"):
            out = self.output_file_path.get().strip()
            if not out:
                return False, "Selecciona un fitxer de sortida."
            if mode == "csv" and not out.lower().endswith(".csv"):
                return False, "En mode CSV, el fitxer de sortida ha d’acabar en .csv"
            if mode == "genweb_json" and not out.lower().endswith(".json"):
                return False, "En mode JSON, el fitxer de sortida ha d’acabar en .json"
        else:
            if not self.output_sheet_title.get().strip():
                return False, "Omple el títol del Google Sheet."
            if not self.output_sheet_tab.get().strip():
                return False, "Omple el nom de la pestanya."

        # OAuth files
        if self._needs_oauth():
            oauth_file = self.oauth_client_json.get().strip() or "oauth_client.json"
            if not os.path.exists(oauth_file):
                return False, f"Falta el fitxer OAuth: {oauth_file}"

        return True, ""

    def run_clicked(self):
        ok, err = self.validate_inputs()
        if not ok:
            messagebox.showerror("Error", err)
            return

        # UI state
        self.run_btn.configure(state="disabled")
        self.sample_btn.configure(state="disabled")
        self.progress.configure(mode="indeterminate")
        self.progress.start()

        self.println("\n▶ Executant…")

        t = threading.Thread(target=self._run_background, daemon=True)
        t.start()

    def _run_background(self):
        start_time = time.time()
        try:
            input_mode = self.input_mode.get()          # sempre csv
            output_mode = self.output_mode.get()

            stats = core.run_pipeline(
                input_mode=input_mode,
                output_mode=output_mode,

                sources_csv_path=self.sources_csv_path.get().strip(),

                output_file_path=self.output_file_path.get().strip()
                if output_mode in ("csv", "genweb_json") else None,

                output_sheet_title=self.output_sheet_title.get().strip()
                if output_mode == "sheets_oauth" else None,

                output_sheet_tab=self.output_sheet_tab.get().strip()
                if output_mode == "sheets_oauth" else None,

                oauth_client_json=self.oauth_client_json.get().strip() or "oauth_client.json",
                token_file=self.token_file.get().strip() or "token.json",

                log=self.ui_log
            )

            elapsed = round(time.time() - start_time, 2)

            summary_lines = [
                "\n" + "─" * 52,
                "✅ PROCESSAMENT FINALITZAT",
                "─" * 52,
                f"🌐 URLs processades: {stats.get('total_urls', 0)}",
                f"❓ FAQs trobades: {stats.get('total_faqs', 0)}",
                f"📝 Files generades: {stats.get('total_rows', 0)}",
            ]

            if stats.get("total_errors"):
                summary_lines.append(f"⚠️ Errors: {stats.get('total_errors')}")

            summary_lines.append(f"⏱ Temps total: {elapsed} s")
            summary_lines.append("─" * 52)

            self.after(0, lambda: self.println("\n".join(summary_lines)))

        except Exception as e:
            error_msg = str(e)
            self.after(0, lambda: self.println(f"❌ Error: {error_msg}"))
            self.after(0, lambda: messagebox.showerror("Error", error_msg))
        finally:
            self.after(0, self._reset_ui)

    def _reset_ui(self):
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(0)
        self.run_btn.configure(state="normal")
        self.sample_btn.configure(state="normal")


if __name__ == "__main__":
    App().mainloop()

import os,sys,threading,time,core
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image


TOPICS_UI = ["TFE", "Mobilitat", "Empresa", "Acte de graduació", "graus", "masters"]

def resource_path(relative_path: str) -> str:
    """Retorna una ruta absoluta tant si s'executa en dev com si s'executa dins PyInstaller."""
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)

# Opcional: icona barra de tasques Windows (només Windows)
try:
    import ctypes
except Exception:
    ctypes = None


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
            self.iconbitmap(resource_path("assets/upc_logo.ico"))
        except Exception as e:
            print("No s'ha pogut carregar .ico:", e)

        # ---------- State ----------
        # INPUT: sempre CSV
        self.input_mode = ctk.StringVar(value="ui")
        self.output_mode = ctk.StringVar(value="csv")

        # Input CSV
        # Input UI rows: each row = {"url_var": StringVar, "topic_var": StringVar, "frame": Frame}
        self.source_rows = []

        # Output file (csv)
        self.output_file_path = ctk.StringVar()

        # Output sheets
        self.output_sheet_title = ctk.StringVar()
        self.output_sheet_tab = ctk.StringVar()

        # OAuth files (Sheets)
        self.oauth_client_json = ctk.StringVar(value="")
        self.token_file = ctk.StringVar(value="")

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
            self.logo_image = ctk.CTkImage(
                light_image=Image.open(resource_path("assets/upc_logo.png")),
                size=(58, 58),
            )
            ctk.CTkLabel(header, image=self.logo_image, text="").pack(side="left", padx=(18, 10))
        except Exception as e:
            print("No s'ha pogut carregar PNG:", e)
            ctk.CTkLabel(header, text="UPC", text_color="white",
                         font=ctk.CTkFont(size=18, weight="bold")).pack(side="left", padx=(18, 10))

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

        # Help box (a dalt, fora dels tabs)
        help_box = ctk.CTkFrame(body, fg_color=LIGHT_PANEL, corner_radius=8)
        help_box.grid(row=0, column=0, sticky="ew", padx=6, pady=(0, 10))

        help_text = (
            "📌 Funcionament\n"
            "• Utilitat 1: Scrape → exporta CSV o Google Sheets\n"
            "• Utilitat 2: Importa CSV/Sheets editat → filtra Estat=Aprobat → genera HTML"
        )
        ctk.CTkLabel(
            help_box,
            text=help_text,
            justify="left",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=12, pady=10)

        # Tabs
        tabs = ctk.CTkTabview(body)
        tabs.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 10))

        tab_scrape = tabs.add("1) Scrape i exporta")
        tab_html = tabs.add("2) Aprovats → HTML")

        tab_scrape.grid_columnconfigure(0, weight=1)
        tab_html.grid_columnconfigure(0, weight=1)

        # =========================
        # TAB 1: SCRAPE I EXPORTA
        # =========================

        # --- ENTRADA card ---
        self.in_card = ctk.CTkFrame(tab_scrape, fg_color=LIGHT_PANEL, corner_radius=10)
        self.in_card.grid(row=0, column=0, sticky="ew", padx=6, pady=(0, 10))
        self.in_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.in_card, text="ENTRADA",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, padx=12, pady=(10, 6), sticky="w")

        self.in_sources_row = ctk.CTkFrame(self.in_card, fg_color="transparent")
        self.in_sources_row.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 10))
        self.in_sources_row.grid_columnconfigure(0, weight=1)

        hint = ctk.CTkLabel(
            self.in_sources_row,
            text="Afegeix una o més URLs i assigna un tema a cada una.",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
            justify="left",
        )
        hint.grid(row=0, column=0, sticky="w", padx=6, pady=(0, 6))

        self.sources_list = ctk.CTkFrame(self.in_sources_row, fg_color="transparent")
        self.sources_list.grid(row=1, column=0, sticky="ew", padx=0, pady=0)
        self.sources_list.grid_columnconfigure(0, weight=1)

        controls = ctk.CTkFrame(self.in_sources_row, fg_color="transparent")
        controls.grid(row=2, column=0, sticky="w", padx=6, pady=(10, 0))
        ctk.CTkButton(controls, text="➕ Afegir URL", width=140, command=self.add_source_row).pack(side="left")

        # Primera fila
        self.add_source_row()

        # --- SORTIDA card ---
        self.out_card = ctk.CTkFrame(tab_scrape, fg_color=LIGHT_PANEL, corner_radius=10)
        self.out_card.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 10))
        self.out_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self.out_card, text="SORTIDA",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, columnspan=3, padx=12, pady=(10, 6), sticky="w")

        out_mode_frame = ctk.CTkFrame(self.out_card, fg_color="transparent")
        out_mode_frame.grid(row=1, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 6))

        ctk.CTkRadioButton(
            out_mode_frame, text="CSV",
            variable=self.output_mode, value="csv",
            command=self._refresh_ui
        ).pack(side="left", padx=(0, 18))

        ctk.CTkRadioButton(
            out_mode_frame, text="Google Sheets",
            variable=self.output_mode, value="sheets_oauth",
            command=self._refresh_ui
        ).pack(side="left")

        # CSV output row
        self.out_file_row = ctk.CTkFrame(self.out_card, fg_color="transparent")
        self.out_file_row.grid(row=2, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 10))
        self.out_file_row.grid_columnconfigure(1, weight=1)

        self._file_row(
            parent=self.out_file_row,
            row=0,
            label="Fitxer de sortida (CSV)",
            var=self.output_file_path,
            save=True,
            types=[("CSV", "*.csv")],
        )

        # Sheets rows
        self.out_sheets_row = ctk.CTkFrame(self.out_card, fg_color="transparent")
        self.out_sheets_row.grid(row=3, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 10))
        self.out_sheets_row.grid_columnconfigure(1, weight=1)

        self._text_row(self.out_sheets_row, 0, "Títol del Google Sheet", self.output_sheet_title)
        self._text_row(self.out_sheets_row, 1, "Nom de la pestanya", self.output_sheet_tab)

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

        # --- Botó + progress + log (tab 1) ---
        btns = ctk.CTkFrame(tab_scrape, fg_color="transparent")
        btns.grid(row=2, column=0, sticky="w", padx=6, pady=(4, 6))

        self.run_btn = ctk.CTkButton(btns, text="Executa", command=self.run_clicked, width=140)
        self.run_btn.pack(side="left")

        self.progress = ctk.CTkProgressBar(tab_scrape)
        self.progress.grid(row=3, column=0, sticky="ew", padx=6, pady=(6, 10))
        self.progress.set(0)

        self.log = ctk.CTkTextbox(tab_scrape, height=260)
        self.log.grid(row=4, column=0, padx=6, pady=10, sticky="nsew")

        # =========================
        # TAB 2: APROVATS → HTML
        # =========================

        # (variables ja les tens definides en altres llocs? si no, aquí també val)
        self.html_input_mode = ctk.StringVar(value="csv")
        self.html_input_csv_path = ctk.StringVar()
        self.html_sheet_title = ctk.StringVar()
        self.html_sheet_tab = ctk.StringVar()
        self.html_output_path = ctk.StringVar()

        card2 = ctk.CTkFrame(tab_html, fg_color=LIGHT_PANEL, corner_radius=10)
        card2.grid(row=0, column=0, sticky="ew", padx=6, pady=(0, 10))
        card2.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card2, text="IMPORTA I GENERA HTML (només Estat = Aprobat)",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, columnspan=3, padx=12, pady=(10, 6), sticky="w")

        mode_frame2 = ctk.CTkFrame(card2, fg_color="transparent")
        mode_frame2.grid(row=1, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 6))

        ctk.CTkRadioButton(
            mode_frame2, text="CSV editat",
            variable=self.html_input_mode, value="csv",
            command=self._refresh_html_ui
        ).pack(side="left", padx=(0, 18))

        ctk.CTkRadioButton(
            mode_frame2, text="Google Sheets editat",
            variable=self.html_input_mode, value="sheets_oauth",
            command=self._refresh_html_ui
        ).pack(side="left")

        self.html_csv_row = ctk.CTkFrame(card2, fg_color="transparent")
        self.html_csv_row.grid(row=2, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 10))
        self.html_csv_row.grid_columnconfigure(1, weight=1)

        self._file_row(
            parent=self.html_csv_row,
            row=0,
            label="CSV d’entrada (editat)",
            var=self.html_input_csv_path,
            save=False,
            types=[("CSV", "*.csv")],
            button_text="Explora…",
        )

        self.html_sheets_row = ctk.CTkFrame(card2, fg_color="transparent")
        self.html_sheets_row.grid(row=3, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 10))
        self.html_sheets_row.grid_columnconfigure(1, weight=1)

        self._text_row(self.html_sheets_row, 0, "Títol del Google Sheet", self.html_sheet_title)
        self._text_row(self.html_sheets_row, 1, "Nom de la pestanya", self.html_sheet_tab)

        self.html_oauth_row = ctk.CTkFrame(card2, fg_color="transparent")
        self.html_oauth_row.grid(row=4, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 10))
        self.html_oauth_row.grid_columnconfigure(1, weight=1)

        self._file_row(
            parent=self.html_oauth_row,
            row=0,
            label="OAuth client (oauth_client.json)",
            var=self.oauth_client_json,
            save=False,
            types=[("JSON", "*.json")],
            button_text="Explora…",
        )

        out2 = ctk.CTkFrame(tab_html, fg_color=LIGHT_PANEL, corner_radius=10)
        out2.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 10))
        out2.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            out2, text="SORTIDA",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, columnspan=3, padx=12, pady=(10, 6), sticky="w")

        self._file_row(
            parent=out2,
            row=1,
            label="Fitxer HTML/TXT de sortida",
            var=self.html_output_path,
            save=True,
            types=[("HTML", "*.html"), ("TXT", "*.txt")],
            button_text="Desa…",
        )

        btns2 = ctk.CTkFrame(tab_html, fg_color="transparent")
        btns2.grid(row=2, column=0, sticky="w", padx=6, pady=(4, 6))

        self.gen_btn = ctk.CTkButton(btns2, text="Genera HTML", command=self.generate_html_clicked, width=160)
        self.gen_btn.pack(side="left")

        self.log2 = ctk.CTkTextbox(tab_html, height=260)
        self.log2.grid(row=3, column=0, padx=6, pady=10, sticky="nsew")

        # Refresh inicials (important)
        self._refresh_ui()
        self._refresh_html_ui()


    def log2_println(self, msg):
        self.log2.insert("end", msg + "\n")
        self.log2.see("end")

    def ui_log2(self, msg: str):
        self.after(0, lambda: self.log2_println(msg))

    def validate_html_inputs(self):
        mode = self.html_input_mode.get()

        if mode == "csv":
            path = self.html_input_csv_path.get().strip()
            if not path:
                return False, "Selecciona el CSV d’entrada."
            if not os.path.exists(path):
                return False, "El CSV d’entrada no existeix."
        else:
            if not self.html_sheet_title.get().strip():
                return False, "Omple el títol del Google Sheet."
            if not self.html_sheet_tab.get().strip():
                return False, "Omple el nom de la pestanya."
            oauth_file = self.oauth_client_json.get().strip() or "oauth_client.json"
            if not os.path.exists(oauth_file):
                return False, f"Falta el fitxer OAuth: {oauth_file}"

        out = self.html_output_path.get().strip()
        if not out:
            return False, "Selecciona un fitxer de sortida (.html o .txt)."
        if not (out.lower().endswith(".html") or out.lower().endswith(".txt")):
            return False, "La sortida ha d’acabar en .html o .txt"

        return True, ""

    def generate_html_clicked(self):
        ok, err = self.validate_html_inputs()
        if not ok:
            messagebox.showerror("Error", err)
            return

        self.gen_btn.configure(state="disabled")
        self.ui_log2("\n▶ Generant HTML d’aprovats…")

        t = threading.Thread(target=self._generate_html_background, daemon=True)
        t.start()

    def _generate_html_background(self):
        try:
            mode = self.html_input_mode.get()
            stats = core.run_approved_to_html_pipeline(
                input_mode=mode,
                input_csv_path=self.html_input_csv_path.get().strip() if mode == "csv" else None,
                sheet_title=self.html_sheet_title.get().strip() if mode == "sheets_oauth" else None,
                sheet_tab=self.html_sheet_tab.get().strip() if mode == "sheets_oauth" else None,
                oauth_client_json=self.oauth_client_json.get().strip() or "oauth_client.json",
                token_file=self.token_file.get().strip() or "token.json",
                output_path=self.html_output_path.get().strip(),
                log=self.ui_log2,
            )
            self.ui_log2(
                f"\n✅ Fet! Files llegides: {stats.get('total_rows', 0)} | "
                f"Aprovades: {stats.get('approved_rows', 0)} | Temes: {stats.get('topics', 0)}"
            )
        except Exception as e:
            msg = str(e)
            self.ui_log2(f"❌ Error: {msg}")
            self.after(0, lambda: messagebox.showerror("Error", msg))
        finally:
            self.after(0, lambda: self.gen_btn.configure(state="normal"))

    # ================= UI HELPERS =================

    def add_source_row(self, url_value: str = "", topic_value: str = "TFE"):
        row_frame = ctk.CTkFrame(self.sources_list, fg_color="transparent")
        row_frame.pack(fill="x", padx=6, pady=4)

        row_frame.grid_columnconfigure(0, weight=1)

        url_var = ctk.StringVar(value=url_value)
        topic_var = ctk.StringVar(value=topic_value if topic_value in TOPICS_UI else TOPICS_UI[0])

        url_entry = ctk.CTkEntry(row_frame, textvariable=url_var, placeholder_text="https://...")
        url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        topic_menu = ctk.CTkOptionMenu(row_frame, values=TOPICS_UI, variable=topic_var, width=190)
        topic_menu.grid(row=0, column=1, sticky="e", padx=(0, 8))

        del_btn = ctk.CTkButton(
            row_frame,
            text="🗑️",
            width=44,
            command=lambda: self.remove_source_row(row_frame)
        )
        del_btn.grid(row=0, column=2, sticky="e")

        self.source_rows.append({
            "frame": row_frame,
            "url_var": url_var,
            "topic_var": topic_var,
        })

    def remove_source_row(self, frame):
        # Elimina de UI
        frame.destroy()
        # Elimina de estado
        self.source_rows = [r for r in self.source_rows if r["frame"] != frame]

    def _file_row(self, parent, row, label, var, save, types, button_text="Navega…"):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, padx=6, pady=10, sticky="w")
        ctk.CTkEntry(parent, textvariable=var).grid(row=row, column=1, padx=6, pady=10, sticky="ew")

        def browse():
            if save:
                path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=types)
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

    def _refresh_html_ui(self):
        if self.html_input_mode.get() == "sheets_oauth":
            self.html_csv_row.grid_remove()
            self.html_sheets_row.grid()
            self.html_oauth_row.grid()
        else:
            self.html_sheets_row.grid_remove()
            self.html_oauth_row.grid_remove()
            self.html_csv_row.grid()

    # ================= ACTIONS =================

    def validate_inputs(self):

        # INPUT (UI rows)
        sources = self.get_sources_from_ui()
        if not sources:
            return False, "Afegeix almenys una URL vàlida a l’entrada."

        # OUTPUT
        mode = self.output_mode.get()
        if mode == "csv":
            out = self.output_file_path.get().strip()
            if not out:
                return False, "Selecciona un fitxer de sortida."
            if mode == "csv" and not out.lower().endswith(".csv"):
                return False, "En mode CSV, el fitxer de sortida ha d’acabar en .csv"
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

            sources = self.get_sources_from_ui()

            stats = core.run_pipeline(
                input_mode="ui",
                output_mode=output_mode,

                sources=sources,

                output_sheet_title=self.output_sheet_title.get().strip()
                if output_mode == "sheets_oauth" else None,

                output_sheet_tab=self.output_sheet_tab.get().strip()
                if output_mode == "sheets_oauth" else None,

                output_file_path=self.output_file_path.get().strip() if output_mode == "csv" else None,

                oauth_client_json=self.oauth_client_json.get().strip() or "oauth_client.json",
                token_file=self.token_file.get().strip() or "token.json",

                log=self.ui_log

            )

            elapsed = round(time.time() - start_time, 2)

            summary_lines = [
                "\n" + "─" * 52,
                "✅ PROCESSAMENT FINALITZAT",
                "─" * 52,
                f"URLs processades: {stats.get('total_urls', 0)}",
                f"FAQs trobades: {stats.get('total_faqs', 0)}",
                f"Files generades: {stats.get('total_rows', 0)}",
            ]

            if stats.get("total_errors"):
                summary_lines.append(f"Errors: {stats.get('total_errors')}")

            summary_lines.append(f"Temps total: {elapsed} s")
            summary_lines.append("─" * 52)

            self.after(0, lambda: self.println("\n".join(summary_lines)))

        except Exception as e:
            error_msg = str(e)
            self.after(0, lambda: self.println(f"Error: {error_msg}"))
            self.after(0, lambda: messagebox.showerror("Error", error_msg))
        finally:
            self.after(0, self._reset_ui)

    def _reset_ui(self):
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(0)
        self.run_btn.configure(state="normal")

    def get_sources_from_ui(self):
        out = []
        for r in self.source_rows:
            url = (r["url_var"].get() or "").strip()
            topic = (r["topic_var"].get() or "").strip()
            if not url:
                continue
            # validación básica de URL
            if not (url.startswith("http://") or url.startswith("https://")):
                continue
            if topic not in TOPICS_UI:
                topic = TOPICS_UI[0]
            out.append((url, topic))
        return out

if __name__ == "__main__":
    App().mainloop()

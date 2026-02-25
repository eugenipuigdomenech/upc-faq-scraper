# IMPORTS
import os
import sys
import threading
import time
import core
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image
from dataclasses import dataclass
import hashlib

# CONSTANTS DE CONFIGURACIÓ
TOPICS_UI = ["Graus", "Masters", "TFE", "Mobilitat", "Empresa", "Acte de graduació"]
OAUTH_HELP_TEXT = (
        "Com aconseguir oauth_client.json (Google OAuth):\n\n"
        "1) Ves a Google Cloud Console.\n"
        "2) Crea un Projecte (o usa’n un existent).\n"
        "3) APIs & Services → Library:\n"
        "   - Habilita Google Sheets API\n"
        "   - Habilita Google Drive API\n"
        "4) APIs & Services → OAuth consent screen:\n"
        "   - Tipus: External (normalment)\n"
        "   - Omple dades bàsiques\n"
        "   - Afegeix el teu usuari com a Test user (si està en mode Testing)\n"
        "5) APIs & Services → Credentials → Create credentials → OAuth client ID:\n"
        "   - Application type: Desktop app\n"
        "6) Descarrega el JSON i guarda’l com: oauth_client.json\n\n"
        "Notes:\n"
        "- La primera vegada que executis, s’obrirà el navegador per autoritzar.\n"
        "- Es crearà un fitxer token.json al costat del programa (no el perdis)."
    )
FAQ_FORMAT_HELP_TEXT = (
    "Quines pàgines puc extreure?\n\n"
    "Aquest programa detecta automàticament aquests formats de FAQs:\n"
    "• UPC antic: #collapse-base (enllaços que obren respostes)\n"
    "• Bootstrap 5: .accordion-item / .accordion-body\n"
    "• UPC/Plone nou: #faqAccordion (botons amb data-bs-target=\"#cX\")\n"
    "• Genweb GW4: .accordion.accordion-gw4 (links open-accordionX + .accordion-content)\n\n"
    "Si una pàgina té un format diferent, pot donar 0 resultats.\n"
    "En aquest cas cal afegir un selector nou al scraper."
)
    # Theme
UPC_BLUE = "#0066A1"
UPC_BLUE_TAB = "#1E7FBE"  # blau UPC més suau per tabs
BG = "#F5F6F8"
LIGHT_PANEL = "#d2d5d9"
TEXT_MUTED = "#4B5563"
ctk.set_appearance_mode("light")
@dataclass
class FaqItem:
    id: str
    topic: str
    question: str
    answer: str
    source: str
    approved_var: ctk.BooleanVar

# HELPERS
def resource_path(relative_path: str) -> str:
    """Retorna una ruta absoluta tant si s'executa en dev com si s'executa dins PyInstaller."""
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)
    # Windows taskbar icon (optional)
try:
    import ctypes
except Exception:
    ctypes = None

# COMPONENTS UI
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None

        widget.bind("<Enter>", self.show_tooltip)
        widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tip_window or not self.text:
            return

        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6

        self.tip_window = tw = ctk.CTkToplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)

        label = ctk.CTkLabel(
            tw,
            text=self.text,
            justify="left",
            wraplength=420,
            fg_color="#111827",
            text_color="white",
            corner_radius=8,
            padx=10,
            pady=8
        )
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

# CLASSE PRINCIPAL
class App(ctk.CTk):

    # ====Lifecycle / init
    def __init__(self):
        super().__init__()

        self.scraped_items: list[FaqItem] = []
        self.review_filter_only_approved = ctk.BooleanVar(value=False)

        # Fix icona barra de tasques Windows (més fiable a l'EXE)
        if ctypes:
            try:
                myappid = "upc.faq.scraper.v1"
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass

        self.title("UPC FAQ Scraper")
        self.geometry("1250x880")
        self.minsize(1100, 780)
        self.configure(fg_color=BG)

        # Taskbar icon
        try:
            self.iconbitmap(resource_path("assets/upc_logo.ico"))
        except Exception as e:
            print("No s'ha pogut carregar .ico:", e)

        # INPUT: sempre CSV
        self.input_mode = ctk.StringVar(value="ui")
        self.output_mode = ctk.StringVar(value="ui")

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

    # ====Build UI
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
        body = ctk.CTkFrame(self, fg_color=BG)
        body.pack(fill="both", expand=True, padx=18, pady=18)

        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        tabs = ctk.CTkTabview(body)
        tabs.grid(row=0, column=0, sticky="nsew", padx=6, pady=(6, 12))  # 👈 CANVIA row=1 → row=0
        self._style_tabview(tabs)
        self.after(50, lambda: self._fix_tab_text_colors(tabs))

        tab_scrape = tabs.add("1) Descarregar FAQs per revisar")
        tab_review = tabs.add("2) Revisar i aprovar (UI)")
        tab_html = tabs.add("3) Convertir / Exportar")

        tab_scrape.grid_rowconfigure(4, weight=1)  # perquè el log s’expandeixi

        # IMPORTANT: només cridem la que sí existeix
        self._build_tab_review(tab_review)

        tab_scrape.grid_columnconfigure(0, weight=1)
        tab_html.grid_columnconfigure(0, weight=1)
        tab_html.grid_rowconfigure(3, weight=1)  # la fila del log2


        tabs.configure(command=lambda: self._fix_tab_text_colors(tabs))

        # TAB 1: SCRAPE I EXPORTA
        self.in_card = ctk.CTkFrame(tab_scrape, fg_color=LIGHT_PANEL, corner_radius=10)
        self.in_card.grid(row=0, column=0, sticky="ew", padx=6, pady=(0, 10))
        self.in_card.grid_columnconfigure(0, weight=1)

        title_row = ctk.CTkFrame(self.in_card, fg_color="transparent")
        title_row.grid(row=0, column=0, padx=12, pady=(10, 6), sticky="w")

        title_label = ctk.CTkLabel(
            title_row,
            text="Introdueix la URL de la pàgina d’on extreure les FAQs",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        title_label.pack(side="left")


        q = self._help_icon(title_row, FAQ_FORMAT_HELP_TEXT)
        q.pack(side="left", padx=(6, 0))

        self.in_sources_row = ctk.CTkFrame(self.in_card, fg_color="transparent")
        self.in_sources_row.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 10))
        self.in_sources_row.grid_columnconfigure(0, weight=1)
        self.sources_list = ctk.CTkFrame(self.in_sources_row, fg_color="transparent")
        self.sources_list.grid(row=1, column=0, sticky="ew", padx=0, pady=0)
        self.sources_list.grid_columnconfigure(0, weight=1)

        # Primera fila
        self.add_source_row()

        # Botó per afegir més URLs
        self.add_url_btn = ctk.CTkButton(
            self.in_sources_row,
            text="Afegeix una nova URL",
            command=self.add_source_row,
            width=180
        )
        self.add_url_btn.grid(row=2, column=0, sticky="w", padx=6, pady=(0, 6))

        # --- SORTIDA card ---
        self.out_card = ctk.CTkFrame(tab_scrape, fg_color=LIGHT_PANEL, corner_radius=10)
        self.out_card.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 16))
        self.out_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self.out_card, text="Tria on vols revisar i aprobar les FAQs",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, columnspan=3, padx=12, pady=(10, 6), sticky="w")

        out_mode_frame = ctk.CTkFrame(self.out_card, fg_color="transparent")
        out_mode_frame.grid(row=1, column=0, columnspan=3, sticky="w", padx=12, pady=(6, 14))

        ctk.CTkRadioButton(
            out_mode_frame, text="Aprovar via UI",
            variable=self.output_mode, value="ui",
            command=self._refresh_ui
        ).pack(side="left", padx=(0, 18))

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

        # --- OAuth row (TAB 1) ---
        oauth_title_row = ctk.CTkFrame(self.oauth_row, fg_color="transparent")
        oauth_title_row.grid(row=0, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 0))

        ctk.CTkLabel(oauth_title_row, text="OAuth client (oauth_client.json)").pack(side="left")

        oauth_q1 = self._help_icon(oauth_title_row, OAUTH_HELP_TEXT)
        oauth_q1.pack(side="left", padx=(6, 0))

        self._file_row(
            parent=self.oauth_row,
            row=0,
            label="OAuth client (oauth_client.json)",
            var=self.oauth_client_json,
            save=False,
            types=[("JSON", "*.json")],
            button_text="Explora…",
            tooltip_text=OAUTH_HELP_TEXT,
        )

        # --- Botó + progress + log (tab 1) ---
        btns = ctk.CTkFrame(tab_scrape, fg_color="transparent")
        btns.grid(row=2, column=0, sticky="w", padx=6, pady=(4, 6))

        self.run_btn = ctk.CTkButton(btns, text="Executa", command=self.run_clicked, width=140)
        self.run_btn.pack(side="left")

        self.progress = ctk.CTkProgressBar(tab_scrape)
        self.progress.grid(row=3, column=0, sticky="ew", padx=6, pady=(6, 10))
        self.progress.set(0)


        # --- LOG card (gris) ---
        self.log_card = ctk.CTkFrame(tab_scrape, fg_color=LIGHT_PANEL, corner_radius=10)
        self.log_card.grid(row=4, column=0, sticky="nsew", padx=6, pady=(0, 10))
        self.log_card.grid_columnconfigure(0, weight=1)
        self.log_card.grid_rowconfigure(0, weight=1)

        self.log = ctk.CTkTextbox(self.log_card)
        self.println(
            "Aquesta eina té dues funcions:\n\n"
            "1) Descarregador de FAQs: introdueix una URL amb preguntes freqüents "
            "i genera un fitxer per revisar-les i marcar-les com aprovades.\n\n"
            "2) Generador de codi per Genweb: importa el fitxer amb les FAQs "
            "aprovades i obté el codi font llest per enganxar a la web."
        )
        self.log.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)




        # TAB 2: APROVATS → HTML
        # (variables ja les tens definides en altres llocs? si no, aquí també val)
        self.html_input_mode = ctk.StringVar(value="ui")
        self.html_input_csv_path = ctk.StringVar()
        self.html_sheet_title = ctk.StringVar()
        self.html_sheet_tab = ctk.StringVar()
        self.html_output_path = ctk.StringVar()

        card2 = ctk.CTkFrame(tab_html, fg_color=LIGHT_PANEL, corner_radius=10)
        card2.grid(row=0, column=0, sticky="ew", padx=6, pady=(0, 10))
        card2.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card2, text="Selecciona el fitxer revisat (agafarà només les faqs aprovades)",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, columnspan=3, padx=12, pady=(10, 6), sticky="w")

        mode_frame2 = ctk.CTkFrame(card2, fg_color="transparent")
        mode_frame2.grid(row=1, column=0, columnspan=3, sticky="w", padx=12, pady=(6, 14))

        ctk.CTkRadioButton(
            mode_frame2, text="Aprovades a la UI (recomanat)",
            variable=self.html_input_mode, value="ui",
            command=self._refresh_html_ui
        ).pack(side="left", padx=(0, 18))

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
            # NO tooltip aquí
        )

        self.html_sheets_row = ctk.CTkFrame(card2, fg_color="transparent")
        self.html_sheets_row.grid(row=3, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 10))
        self.html_sheets_row.grid_columnconfigure(1, weight=1)

        self._text_row(self.html_sheets_row, 0, "Títol del Google Sheet", self.html_sheet_title)
        self._text_row(self.html_sheets_row, 1, "Nom de la pestanya", self.html_sheet_tab)

        self.html_oauth_row = ctk.CTkFrame(card2, fg_color="transparent")
        self.html_oauth_row.grid(row=4, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 10))
        self.html_oauth_row.grid_columnconfigure(1, weight=1)

        # --- OAuth row (TAB 2) ---
        oauth_title_row2 = ctk.CTkFrame(self.html_oauth_row, fg_color="transparent")
        oauth_title_row2.grid(row=0, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 0))

        ctk.CTkLabel(oauth_title_row2, text="OAuth client (oauth_client.json)").pack(side="left")

        oauth_q2 = self._help_icon(oauth_title_row2, OAUTH_HELP_TEXT)
        oauth_q2.pack(side="left", padx=(6, 0))

        self._file_row(
            parent=self.html_oauth_row,
            row=0,
            label="OAuth client (oauth_client.json)",
            var=self.oauth_client_json,
            save=False,
            types=[("JSON", "*.json")],
            button_text="Explora…",
            tooltip_text=OAUTH_HELP_TEXT,
        )

        btns2 = ctk.CTkFrame(tab_html, fg_color="transparent")
        btns2.grid(row=2, column=0, sticky="w", padx=6, pady=(4, 6))

        self.gen_btn = ctk.CTkButton(btns2, text="Generar codi font per Genweb", command=self.generate_html_clicked, width=160)
        self.gen_btn.pack(side="left")

        self.code_card = ctk.CTkFrame(tab_html, fg_color=LIGHT_PANEL, corner_radius=10)
        self.code_card.grid(row=3, column=0, sticky="nsew", padx=6, pady=10)
        self.code_card.grid_columnconfigure(0, weight=1)
        self.code_card.grid_rowconfigure(0, weight=1)

        self.log2 = ctk.CTkTextbox(self.code_card)
        self.log2.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

        copy_row = ctk.CTkFrame(tab_html, fg_color="transparent")
        copy_row.grid(row=4, column=0, sticky="w", padx=6, pady=(0, 10))

        ctk.CTkButton(
            copy_row,
            text="📋 Copiar tot el codi",
            command=self.copy_generated_code,
            width=180
        ).pack(side="left")

        # Refresh inicials (important)
        self._refresh_ui()
        self._refresh_html_ui()

        # --- DEBUG: veure què hi ha a tab_scrape ---
        def _dump(parent, name="parent"):
            print("\n=== DUMP", name, "===")
            for w in parent.winfo_children():
                cls = w.__class__.__name__
                try:
                    gi = w.grid_info()
                except Exception:
                    gi = {}
                # només els que estan amb grid
                if gi:
                    print(f"- {cls:20s} row={gi.get('row')} col={gi.get('column')} sticky={gi.get('sticky')} -> {w}")

        _dump(tab_scrape, "tab_scrape")

    # ====UI component helpers
    def add_source_row(self, url_value: str = "", topic_value: str = "Graus", custom_topic_value: str = ""):
        row_frame = ctk.CTkFrame(self.sources_list, fg_color="transparent")
        row_frame.pack(fill="x", padx=6, pady=6)

        # 3 columnes: URL | desplegable | text lliure | (botó paperera a la dreta)
        row_frame.grid_columnconfigure(0, weight=1)  # URL ample
        row_frame.grid_columnconfigure(1, weight=0)  # dropdown fixed
        row_frame.grid_columnconfigure(2, weight=0)  # custom topic ample
        row_frame.grid_columnconfigure(3, weight=0)  # delete fixed

        url_var = ctk.StringVar(value=url_value)
        topic_var = ctk.StringVar(value=topic_value if topic_value in TOPICS_UI else TOPICS_UI[0])
        custom_topic_var = ctk.StringVar(value=custom_topic_value)

        # ---------- Labels (fila 0) ----------
        ctk.CTkLabel(row_frame, text="URL").grid(row=0, column=0, sticky="w", pady=(0, 4))

        ctk.CTkLabel(row_frame, text="Tria el tòpic").grid(row=0, column=1, sticky="w", pady=(0, 4), padx=(8, 0))

        ctk.CTkLabel(row_frame, text="O escriu-lo aquí").grid(row=0, column=2, sticky="w", pady=(0, 4), padx=(8, 0))

        # (col 3 és la paperera, no cal label)

        # ---------- Inputs (fila 1) ----------
        url_entry = ctk.CTkEntry(row_frame, textvariable=url_var, placeholder_text="https://...")
        url_entry.grid(row=1, column=0, sticky="ew", padx=(0, 8))

        topic_menu = ctk.CTkOptionMenu(row_frame, values=TOPICS_UI, variable=topic_var, width=190)
        topic_menu.grid(row=1, column=1, sticky="w", padx=(0, 8))

        custom_entry = ctk.CTkEntry(row_frame, textvariable=custom_topic_var, placeholder_text="Tòpic personalitzat")
        custom_entry.grid(row=1, column=2, sticky="ew", padx=(0, 8))

        del_btn = ctk.CTkButton(row_frame, text="🗑️", width=44, command=lambda: self.remove_source_row(row_frame))
        del_btn.grid(row=1, column=3, sticky="e")

        self.source_rows.append({
            "frame": row_frame,
            "url_var": url_var,
            "topic_var": topic_var,
            "custom_topic_var": custom_topic_var,
        })
    def remove_source_row(self, frame):
        # Elimina de UI
        frame.destroy()
        # Elimina de estado
        self.source_rows = [r for r in self.source_rows if r["frame"] != frame]
    def _help_icon(self, parent, text):
        icon = ctk.CTkLabel(
            parent,
            text="?",
            width=18,
            height=18,
            corner_radius=9,
            fg_color=UPC_BLUE,
            text_color="white",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="center",
            cursor="hand2"
        )
        ToolTip(icon, text)
        return icon
    def _file_row(self, parent, row, label, var, save, types, button_text="Navega…", tooltip_text: str | None = None):
        # --- Columna 0: label + (opcional) icona "?"
        label_frame = ctk.CTkFrame(parent, fg_color="transparent")
        label_frame.grid(row=row, column=0, padx=6, pady=10, sticky="w")

        ctk.CTkLabel(label_frame, text=label).pack(side="left")

        # IMPORTANT: el "?" només es crea si tooltip_text existeix
        if tooltip_text:
            qbtn = self._help_icon(label_frame, tooltip_text)
            qbtn.pack(side="left", padx=(6, 0))

        # --- Columna 1: entry
        ctk.CTkEntry(parent, textvariable=var).grid(row=row, column=1, padx=6, pady=10, sticky="ew")

        def browse():
            if save:
                # si és "save", deixem que types mani (més simple i evita errors entre tabs)
                path = filedialog.asksaveasfilename(defaultextension=types[0][1].replace("*", ""), filetypes=types)
            else:
                path = filedialog.askopenfilename(filetypes=types)

            if path:
                var.set(path)

        # --- Columna 2: botó
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

    def _load_scraped_into_ui(self, flat_items: list[tuple[str, str, str, str]]):
        """
        flat_items: [(topic, question, answer, source), ...]
        Aquesta funció s'executa al fil principal (UI).
        """
        items = []
        for topic, question, answer, source in flat_items:
            fid = self._make_id(topic, question, source)
            items.append(
                FaqItem(
                    id=fid,
                    topic=topic,
                    question=question,
                    answer=answer,
                    source=source,
                    approved_var=ctk.BooleanVar(value=False),
                )
            )

        self.scraped_items = items
        self.review_filter_only_approved.set(False)
        self._refresh_review_list()

    # ====UI Logging / output
    def println(self, msg):
        self.log.insert("end", msg + "\n")
        self.log.see("end")
    def log2_println(self, msg):
        self.log2.insert("end", msg + "\n")
        self.log2.see("end")
    def ui_log2(self, msg: str):
        self.after(0, lambda: self.log2_println(msg))
    def ui_log(self, msg: str):
        self.after(0, lambda: self.println(msg))
    def _show_generated_code(self, code: str):
        self.log2.delete("1.0", "end")
        self.log2.insert("1.0", code)
        self.log2.see("1.0")

    # ====UI state / refresh
    def _refresh_ui(self):
        mode = self.output_mode.get()

        if mode == "ui":
            # No cal mostrar cap sortida: només omplirem la Tab 2
            self.out_file_row.grid_remove()
            self.out_sheets_row.grid_remove()
            self.oauth_row.grid_remove()

        elif mode == "sheets_oauth":
            self.out_file_row.grid_remove()
            self.out_sheets_row.grid()
            self.oauth_row.grid()

        else:  # csv
            self.out_sheets_row.grid_remove()
            self.oauth_row.grid_remove()
            self.out_file_row.grid()

    def _refresh_html_ui(self):
        mode = self.html_input_mode.get()

        if mode == "ui":
            self.html_csv_row.grid_remove()
            self.html_sheets_row.grid_remove()
            self.html_oauth_row.grid_remove()

        elif mode == "sheets_oauth":
            self.html_csv_row.grid_remove()
            self.html_sheets_row.grid()
            self.html_oauth_row.grid()

        else:  # csv
            self.html_sheets_row.grid_remove()
            self.html_oauth_row.grid_remove()
            self.html_csv_row.grid()
    def _needs_oauth(self) -> bool:
        return self.output_mode.get() == "sheets_oauth"

    # ====Validations
    def validate_inputs(self):

        # INPUT (UI rows)
        sources = self.get_sources_from_ui()
        if not sources:
            return False, "Afegeix almenys una URL vàlida a l’entrada."

        # OUTPUT
        mode = self.output_mode.get()

        if mode == "ui":
            pass  # no validem res de sortida
        elif mode == "csv":
            out = self.output_file_path.get().strip()
            if not out:
                return False, "Selecciona un fitxer de sortida."
            if not out.lower().endswith(".csv"):
                return False, "En mode CSV, el fitxer de sortida ha d’acabar en .csv"
        else:  # sheets_oauth
            if not self.output_sheet_title.get().strip():
                return False, "Omple el títol del Google Sheet."
            if not self.output_sheet_tab.get().strip():
                return False, "Omple el nom de la pestanya."

        # OAuth files
        def _needs_oauth(self) -> bool:
            return self.output_mode.get() == "sheets_oauth"

        return True, ""

    def validate_html_inputs(self):
        mode = self.html_input_mode.get()

        if mode == "ui":
            if not self._get_approved_rows():
                return False, "No has aprovat cap FAQ a la pestanya 2."
            return True, ""

        if mode == "csv":
            path = self.html_input_csv_path.get().strip()
            if not path:
                return False, "Selecciona el CSV d’entrada."
            if not os.path.exists(path):
                return False, "El CSV d’entrada no existeix."
            return True, ""

        if mode == "sheets_oauth":
            if not self.html_sheet_title.get().strip():
                return False, "Omple el títol del Google Sheet."
            if not self.html_sheet_tab.get().strip():
                return False, "Omple el nom de la pestanya."
            oauth_file = self.oauth_client_json.get().strip() or "oauth_client.json"
            if not os.path.exists(oauth_file):
                return False, f"Falta el fitxer OAuth: {oauth_file}"
            return True, ""

        return False, "Mode d’entrada desconegut."

    # ====Actions
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
    def generate_html_clicked(self):
        ok, err = self.validate_html_inputs()
        if not ok:
            messagebox.showerror("Error", err)
            return

        self.gen_btn.configure(state="disabled")
        self.ui_log2("\n▶ Generant HTML d’aprovats…")

        t = threading.Thread(target=self._generate_html_background, daemon=True)
        t.start()
    def _reset_ui(self):
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(0)
        self.run_btn.configure(state="normal")

    # ====Background workers (threads)
    def _run_background(self):
        start_time = time.time()
        try:
            output_mode = self.output_mode.get()
            sources = self.get_sources_from_ui()

            if output_mode == "ui":
                rows, blocks, stats, errors = core.build_outputs(sources, log=self.ui_log, debug=False)

                flat_items: list[tuple[str, str, str, str]] = []
                for b in blocks:
                    topic = b.get("topic", "")
                    source = b.get("source_url", "")
                    for it in b.get("items", []) or []:
                        question = it.get("q", "")
                        answer = it.get("a", "")
                        flat_items.append((topic, question, answer, source))

                # carregar a la UI al fil principal
                self.after(0, lambda: self._load_scraped_into_ui(flat_items))
                self.ui_log(f"✅ Carregades a la UI: {len(flat_items)} FAQs")

            else:
                stats = core.run_pipeline(
                    input_mode="ui",
                    output_mode=output_mode,
                    sources=sources,
                    output_sheet_title=self.output_sheet_title.get().strip()
                    if output_mode == "sheets_oauth" else None,
                    output_sheet_tab=self.output_sheet_tab.get().strip()
                    if output_mode == "sheets_oauth" else None,
                    output_file_path=self.output_file_path.get().strip()
                    if output_mode == "csv" else None,
                    oauth_client_json=self.oauth_client_json.get().strip() or "oauth_client.json",
                    token_file=self.token_file.get().strip() or "token.json",
                    log=self.ui_log,
                    debug=False,
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

    def _generate_html_background(self):
        try:
            mode = self.html_input_mode.get()

            if mode == "ui":
                approved_rows = self._get_approved_rows()

                if not approved_rows:
                    raise RuntimeError("No hi ha cap FAQ aprovada a la pestanya 2.")

                # 👇 ARA cridem una funció nova de core
                html_text = core.approved_rows_to_html(approved_rows, log=self.ui_log2)

                self.after(0, lambda: self._show_generated_code(html_text))
                return

            # --- MODE CSV / SHEETS (com abans) ---
            stats = core.run_approved_to_html_pipeline(
                input_mode=mode,
                input_csv_path=self.html_input_csv_path.get().strip() if mode == "csv" else None,
                sheet_title=self.html_sheet_title.get().strip() if mode == "sheets_oauth" else None,
                sheet_tab=self.html_sheet_tab.get().strip() if mode == "sheets_oauth" else None,
                oauth_client_json=self.oauth_client_json.get().strip() or "oauth_client.json",
                token_file=self.token_file.get().strip() or "token.json",
                log=self.ui_log2,
            )

            html_code = stats.get("html_text", "")
            self.after(0, lambda: self._show_generated_code(html_code))

        except Exception as e:
            msg = str(e)
            self.ui_log2(f"❌ Error: {msg}")
            self.after(0, lambda: messagebox.showerror("Error", msg))
        finally:
            self.after(0, lambda: self.gen_btn.configure(state="normal"))

    # ====Data extraction from UI
    def get_sources_from_ui(self):
        out = []
        for r in self.source_rows:
            url = (r["url_var"].get() or "").strip()
            if not url:
                continue
            if not (url.startswith("http://") or url.startswith("https://")):
                continue

            custom = (r.get("custom_topic_var").get() or "").strip()
            topic = custom if custom else (r["topic_var"].get() or "").strip()

            if not topic:
                topic = TOPICS_UI[0]

            out.append((url, topic))
        return out

    def _build_tab_review(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))

        ctk.CTkButton(top, text="Aprovar totes", command=self._approve_all).pack(side="left")
        ctk.CTkButton(top, text="Desmarcar totes", command=self._unapprove_all).pack(side="left", padx=(8, 0))

        ctk.CTkCheckBox(
            top,
            text="Mostrar només aprovades",
            variable=self.review_filter_only_approved,
            command=self._refresh_review_list,
        ).pack(side="left", padx=(12, 0))

        self.review_list = ctk.CTkScrollableFrame(parent)
        self.review_list.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self._refresh_review_list()

    def _refresh_review_list(self):
        if not hasattr(self, "review_list"):
            return

        for w in self.review_list.winfo_children():
            w.destroy()

        if not self.scraped_items:
            ctk.CTkLabel(self.review_list, text="Encara no hi ha FAQs. Fes scraping a la pestanya 1.").pack(pady=10)
            return

        only_approved = self.review_filter_only_approved.get()

        for item in self.scraped_items:
            if only_approved and not item.approved_var.get():
                continue
            self._add_review_row(self.review_list, item)

    def _add_review_row(self, parent, item: FaqItem):
        row = ctk.CTkFrame(parent)
        row.pack(fill="x", pady=6, padx=6)

        cb = ctk.CTkCheckBox(row, text="", variable=item.approved_var)
        cb.grid(row=0, column=0, rowspan=2, padx=(8, 8), pady=8, sticky="n")

        # Pregunta
        q = ctk.CTkLabel(
            row,
            text=item.question,
            anchor="w",
            justify="left",
            wraplength=780,  # una mica més ample perquè ara hi ha columna extra
        )
        q.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(8, 2))

        # Resposta
        a = ctk.CTkLabel(
            row,
            text=item.answer,
            anchor="w",
            justify="left",
            wraplength=780,
            text_color="#4B5563",
        )
        a.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 8))

        # Tema (columna petita a la dreta)
        topic = ctk.CTkLabel(
            row,
            text=item.topic,
            width=140,
            anchor="e",
            text_color="#6B7280",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        topic.grid(row=0, column=2, rowspan=2, padx=(6, 12), pady=8, sticky="ne")

        row.grid_columnconfigure(1, weight=1)  # el text ocupa el que pot
        row.grid_columnconfigure(2, weight=0)  # tema fixet


    def _approve_all(self):
        for it in self.scraped_items:
            it.approved_var.set(True)
        self._refresh_review_list()


    def _unapprove_all(self):
        for it in self.scraped_items:
            it.approved_var.set(False)
        self._refresh_review_list()


    def _get_approved_rows(self) -> list[list[str]]:
        rows = []
        for it in self.scraped_items:
            if it.approved_var.get():
                rows.append([it.topic, it.question, it.answer, it.source])
        return rows


    def _make_id(self, topic: str, question: str, source: str) -> str:
        s = f"{topic}|{question}|{source}".encode("utf-8")
        return hashlib.sha1(s).hexdigest()[:12]

    def copy_generated_code(self):
        try:
            text = self.log2.get("1.0", "end-1c")  # tot menys l'últim salt de línia
            if not text.strip():
                messagebox.showinfo("Copiar", "No hi ha cap codi per copiar.")
                return

            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()  # assegura que queda al clipboard
            messagebox.showinfo("Copiat", "Codi copiat al porta-retalls ✅")
        except Exception as e:
            messagebox.showerror("Error", f"No s'ha pogut copiar: {e}")

    def _style_tabview(self, tabview: ctk.CTkTabview):
        tabview.configure(
            fg_color=BG,

            segmented_button_fg_color="#E5E7EB",
            segmented_button_selected_color=UPC_BLUE_TAB,
            segmented_button_selected_hover_color=UPC_BLUE_TAB,
            segmented_button_unselected_color="#F3F4F6",
            segmented_button_unselected_hover_color="#E5E7EB",

            # IMPORTANT: aquí NO posem blanc, posem fosc perquè les no seleccionades es llegeixin
            text_color="#111827",
            text_color_disabled="#9CA3AF",
        )

        try:
            sb = tabview._segmented_button
            sb.configure(
                corner_radius=12,
                border_width=0,
                height=38,
                font=ctk.CTkFont(size=13, weight="bold"),

                # Algunes versions permeten aquests camps i arreglen del tot el tema del text:
                text_color="#111827",
                text_color_disabled="#9CA3AF",
            )
        except Exception:
            pass

    def _fix_tab_text_colors(self, tabview: ctk.CTkTabview):
        """Força colors de text: selected blanc, unselected fosc (per versions de CTk que ho liïn)."""
        try:
            sb = tabview._segmented_button
            current = tabview.get()

            # Posa totes fosques
            for name, btn in sb._buttons_dict.items():
                btn.configure(text_color="#111827")

            # La seleccionada en blanc
            if current in sb._buttons_dict:
                sb._buttons_dict[current].configure(text_color="white")
        except Exception:
            pass

# ENTRY POINT
if __name__ == "__main__":
    App().mainloop()
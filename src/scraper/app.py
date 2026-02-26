# IMPORTS
import os
import sys
import threading
import time
import webbrowser
import json
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image
import hashlib
from bs4 import BeautifulSoup, NavigableString

try:
    from . import core
except ImportError:
    import core

try:
    from .models import FaqItem
    from .ui.widgets import file_row, help_icon, text_row
except ImportError:
    from models import FaqItem
    from ui.widgets import file_row, help_icon, text_row

try:
    from .settings import (
        BG,
        FAQ_FORMAT_HELP_TEXT,
        LIGHT_PANEL,
        OAUTH_HELP_TEXT,
        TOPICS_UI,
        UPC_BLUE,
        UPC_BLUE_TAB,
    )
except ImportError:
    from settings import (
        BG,
        FAQ_FORMAT_HELP_TEXT,
        LIGHT_PANEL,
        OAUTH_HELP_TEXT,
        TOPICS_UI,
        UPC_BLUE,
        UPC_BLUE_TAB,
    )

ctk.set_appearance_mode("light")



# HELPERS
def resource_path(relative_path: str) -> str:
    """Retorna una ruta absoluta tant si s'executa en dev com si s'executa dins PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        # Project root from this file (src/scraper/app.py -> project root)
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(base_path, relative_path)
    # Windows taskbar icon (optional)
try:
    import ctypes
except Exception:
    ctypes = None

# CLASSE PRINCIPAL
class App(ctk.CTk):

    # ====Lifecycle / init
    def __init__(self):
        super().__init__()

        self.scraped_items: list[FaqItem] = []
        self.review_filter_only_approved = ctk.BooleanVar(value=False)
        self.review_filter_only_approved.trace_add("write", lambda *_: self._schedule_save_ui_state())
        self.generated_code_cache = ""
        self._state_write_job = None
        self._is_restoring_state = False

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
        self.output_mode.trace_add("write", lambda *_: self._schedule_save_ui_state())

        # Input UI grouped by topic
        self.topic_groups = []
        self.topic_seq = 0

        # Output file (csv)
        self.output_file_path = ctk.StringVar()
        self.output_file_path.trace_add("write", lambda *_: self._schedule_save_ui_state())

        # Output sheets
        self.output_sheet_title = ctk.StringVar()
        self.output_sheet_tab = ctk.StringVar()
        self.output_sheet_title.trace_add("write", lambda *_: self._schedule_save_ui_state())
        self.output_sheet_tab.trace_add("write", lambda *_: self._schedule_save_ui_state())

        # OAuth files (Sheets)
        self.oauth_client_json = ctk.StringVar(value="")
        self.token_file = ctk.StringVar(value="")
        self.oauth_client_json.trace_add("write", lambda *_: self._schedule_save_ui_state())
        self.token_file.trace_add("write", lambda *_: self._schedule_save_ui_state())

        # ---------- Layout ----------
        self._build_header()
        self._build_body()
        self._refresh_ui()
        self._restore_ui_state()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ====Build UI
    # CONSTRUCCIO UI
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
        tabs.grid(row=0, column=0, sticky="nsew", padx=6, pady=(6, 12))  # ðŸ‘ˆ CANVIA row=1 → row=0
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
        title_row.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")

        title_label = ctk.CTkLabel(
            title_row,
            text="Introdueix la URL de la pàgina d'on extreure les FAQs",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        title_label.pack(side="left")


        q = help_icon(title_row, FAQ_FORMAT_HELP_TEXT, UPC_BLUE)
        q.pack(side="left", padx=(6, 0))
        self.selection_summary_label = ctk.CTkLabel(title_row, text="")
        self.selection_summary_label.pack(side="right")
        self.topics_list = ctk.CTkFrame(self.in_card, fg_color="transparent", height=8)
        self.topics_list.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))
        # Controlem manualment l'alçada per evitar espais buits grans.
        self.topics_list.grid_propagate(False)
        self.topics_list.grid_columnconfigure(0, weight=1)

        actions_row = ctk.CTkFrame(self.in_card, fg_color="transparent")
        actions_row.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 8))

        ctk.CTkButton(
            actions_row,
            text="Afegeix topic",
            command=self.add_topic_group,
            width=150
        ).pack(side="left")

        self.add_topic_group(topic_name=TOPICS_UI[0], add_initial_url=True)

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

        file_row(
            parent=self.out_file_row,
            row=0,
            label="Fitxer de sortida (CSV)",
            var=self.output_file_path,
            save=True,
            types=[("CSV", "*.csv")],
            icon_color=UPC_BLUE,
        )

        # Sheets rows
        self.out_sheets_row = ctk.CTkFrame(self.out_card, fg_color="transparent")
        self.out_sheets_row.grid(row=3, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 10))
        self.out_sheets_row.grid_columnconfigure(1, weight=1)

        text_row(self.out_sheets_row, 0, "Títol del Google Sheet", self.output_sheet_title)
        text_row(self.out_sheets_row, 1, "Nom de la pestanya", self.output_sheet_tab)

        self.oauth_row = ctk.CTkFrame(self.out_card, fg_color="transparent")
        self.oauth_row.grid(row=4, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 10))
        self.oauth_row.grid_columnconfigure(1, weight=1)

        # --- OAuth row (TAB 1) ---
        oauth_title_row = ctk.CTkFrame(self.oauth_row, fg_color="transparent")
        oauth_title_row.grid(row=0, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 0))

        ctk.CTkLabel(oauth_title_row, text="OAuth client (oauth_client.json)").pack(side="left")

        oauth_q1 = help_icon(oauth_title_row, OAUTH_HELP_TEXT, UPC_BLUE)
        oauth_q1.pack(side="left", padx=(6, 0))

        file_row(
            parent=self.oauth_row,
            row=0,
            label="OAuth client (oauth_client.json)",
            var=self.oauth_client_json,
            save=False,
            types=[("JSON", "*.json")],
            icon_color=UPC_BLUE,
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
        self.html_input_mode.trace_add("write", lambda *_: self._schedule_save_ui_state())
        self.html_input_csv_path.trace_add("write", lambda *_: self._schedule_save_ui_state())
        self.html_sheet_title.trace_add("write", lambda *_: self._schedule_save_ui_state())
        self.html_sheet_tab.trace_add("write", lambda *_: self._schedule_save_ui_state())

        card2 = ctk.CTkFrame(tab_html, fg_color=LIGHT_PANEL, corner_radius=10)
        card2.grid(row=0, column=0, sticky="ew", padx=6, pady=(0, 10))
        card2.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card2, text="Selecciona el fitxer revisat (agafarà només les FAQs aprovades)",
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

        file_row(
            parent=self.html_csv_row,
            row=0,
            label="CSV d’entrada (editat)",
            var=self.html_input_csv_path,
            save=False,
            types=[("CSV", "*.csv")],
            icon_color=UPC_BLUE,
            button_text="Explora…",
            # NO tooltip aquí
        )

        self.html_sheets_row = ctk.CTkFrame(card2, fg_color="transparent")
        self.html_sheets_row.grid(row=3, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 10))
        self.html_sheets_row.grid_columnconfigure(1, weight=1)

        text_row(self.html_sheets_row, 0, "Títol del Google Sheet", self.html_sheet_title)
        text_row(self.html_sheets_row, 1, "Nom de la pestanya", self.html_sheet_tab)

        self.html_oauth_row = ctk.CTkFrame(card2, fg_color="transparent")
        self.html_oauth_row.grid(row=4, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 10))
        self.html_oauth_row.grid_columnconfigure(1, weight=1)

        # --- OAuth row (TAB 2) ---
        oauth_title_row2 = ctk.CTkFrame(self.html_oauth_row, fg_color="transparent")
        oauth_title_row2.grid(row=0, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 0))

        ctk.CTkLabel(oauth_title_row2, text="OAuth client (oauth_client.json)").pack(side="left")

        oauth_q2 = help_icon(oauth_title_row2, OAUTH_HELP_TEXT, UPC_BLUE)
        oauth_q2.pack(side="left", padx=(6, 0))

        file_row(
            parent=self.html_oauth_row,
            row=0,
            label="OAuth client (oauth_client.json)",
            var=self.oauth_client_json,
            save=False,
            types=[("JSON", "*.json")],
            icon_color=UPC_BLUE,
            button_text="Explora…",
            tooltip_text=OAUTH_HELP_TEXT,
        )

        btns2 = ctk.CTkFrame(tab_html, fg_color="transparent")
        btns2.grid(row=2, column=0, sticky="w", padx=6, pady=(4, 6))

        self.gen_btn = ctk.CTkButton(
            btns2,
            text="Generar codi font per la Genweb",
            command=self.generate_html_clicked,
            width=260,
        )
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

    # ====UI component helpers
    # ARBRE TOPICS / URLS
    def _get_state_file_path(self) -> str:
        appdata = os.getenv("APPDATA")
        if appdata:
            base_dir = os.path.join(appdata, "UPCFAQScraper")
        else:
            base_dir = os.path.join(os.path.expanduser("~"), ".upc_faq_scraper")
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, "ui_state.json")

    def _serialize_sources_state(self) -> dict:
        groups = []
        for g in self.topic_groups:
            groups.append(
                {
                    "topic": (g["topic_var"].get() or "").strip(),
                    "selected": bool(g["selected_var"].get()),
                    "expanded": bool(g["expanded_var"].get()),
                    "urls": [
                        {
                            "url": (r["url_var"].get() or "").strip(),
                            "selected": bool(r["selected_var"].get()),
                        }
                        for r in g["url_rows"]
                    ],
                }
            )
        scraped_items = []
        for it in self.scraped_items:
            scraped_items.append(
                {
                    "id": it.id,
                    "topic": it.topic,
                    "question": it.question,
                    "answer": it.answer,
                    "source": it.source,
                    "approved": bool(it.approved_var.get()),
                }
            )

        return {
            "version": 3,
            "groups": groups,
            "review_filter_only_approved": bool(self.review_filter_only_approved.get()),
            "scraped_items": scraped_items,
            "generated_code": self.generated_code_cache or self.log2.get("1.0", "end-1c"),
            "scrape_config": {
                "output_mode": self.output_mode.get(),
                "output_file_path": (self.output_file_path.get() or "").strip(),
                "output_sheet_title": (self.output_sheet_title.get() or "").strip(),
                "output_sheet_tab": (self.output_sheet_tab.get() or "").strip(),
                "oauth_client_json": (self.oauth_client_json.get() or "").strip(),
                "token_file": (self.token_file.get() or "").strip(),
            },
            "export_config": {
                "html_input_mode": self.html_input_mode.get(),
                "html_input_csv_path": (self.html_input_csv_path.get() or "").strip(),
                "html_sheet_title": (self.html_sheet_title.get() or "").strip(),
                "html_sheet_tab": (self.html_sheet_tab.get() or "").strip(),
            },
        }

    def _save_ui_state(self):
        if self._is_restoring_state:
            return
        try:
            path = self._get_state_file_path()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._serialize_sources_state(), f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _schedule_save_ui_state(self):
        if self._is_restoring_state:
            return
        if self._state_write_job is not None:
            try:
                self.after_cancel(self._state_write_job)
            except Exception:
                pass
        self._state_write_job = self.after(300, self._save_ui_state)

    def _clear_all_topic_groups(self):
        for g in self.topic_groups:
            try:
                g["frame"].destroy()
            except Exception:
                pass
        self.topic_groups = []
        self.topic_seq = 0

    def _restore_ui_state(self):
        path = self._get_state_file_path()
        if not os.path.exists(path):
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return

        groups = data.get("groups") if isinstance(data, dict) else None
        scraped_items = data.get("scraped_items") if isinstance(data, dict) else None
        review_filter_only_approved = (
            bool(data.get("review_filter_only_approved", False)) if isinstance(data, dict) else False
        )
        generated_code = (data.get("generated_code") or "") if isinstance(data, dict) else ""
        scrape_config = data.get("scrape_config") if isinstance(data, dict) else None
        export_config = data.get("export_config") if isinstance(data, dict) else None

        self._is_restoring_state = True
        try:
            if isinstance(scrape_config, dict):
                output_mode = (scrape_config.get("output_mode") or "ui").strip()
                if output_mode not in {"ui", "csv", "sheets_oauth"}:
                    output_mode = "ui"
                self.output_mode.set(output_mode)
                self.output_file_path.set((scrape_config.get("output_file_path") or "").strip())
                self.output_sheet_title.set((scrape_config.get("output_sheet_title") or "").strip())
                self.output_sheet_tab.set((scrape_config.get("output_sheet_tab") or "").strip())
                self.oauth_client_json.set((scrape_config.get("oauth_client_json") or "").strip())
                self.token_file.set((scrape_config.get("token_file") or "").strip())

            if isinstance(export_config, dict):
                html_input_mode = (export_config.get("html_input_mode") or "ui").strip()
                if html_input_mode not in {"ui", "csv", "sheets_oauth"}:
                    html_input_mode = "ui"
                self.html_input_mode.set(html_input_mode)
                self.html_input_csv_path.set((export_config.get("html_input_csv_path") or "").strip())
                self.html_sheet_title.set((export_config.get("html_sheet_title") or "").strip())
                self.html_sheet_tab.set((export_config.get("html_sheet_tab") or "").strip())

            if groups:
                self._clear_all_topic_groups()

                for g in groups:
                    topic_name = (g.get("topic") or "").strip() if isinstance(g, dict) else ""
                    group = self.add_topic_group(topic_name=topic_name, add_initial_url=False)

                    urls = g.get("urls") if isinstance(g, dict) else None
                    if urls:
                        for u in urls:
                            url_value = (u.get("url") or "").strip() if isinstance(u, dict) else ""
                            self.add_url_to_topic(group, url_value=url_value)
                            row = group["url_rows"][-1]
                            row["selected_var"].set(bool(u.get("selected", True)) if isinstance(u, dict) else True)
                    else:
                        self.add_url_to_topic(group)

                    group["selected_var"].set(bool(g.get("selected", True)) if isinstance(g, dict) else True)

                    expanded = bool(g.get("expanded", True)) if isinstance(g, dict) else True
                    if not expanded and group["expanded_var"].get():
                        self.toggle_topic_group(group)

                if not self.topic_groups:
                    self.add_topic_group(topic_name=TOPICS_UI[0], add_initial_url=True)

            if scraped_items and isinstance(scraped_items, list):
                items: list[FaqItem] = []
                for it in scraped_items:
                    if not isinstance(it, dict):
                        continue
                    items.append(
                        self._make_faq_item(
                            topic=(it.get("topic") or "").strip(),
                            question=(it.get("question") or "").strip(),
                            answer=(it.get("answer") or "").strip(),
                            source=(it.get("source") or "").strip(),
                            approved=bool(it.get("approved", False)),
                            forced_id=(it.get("id") or "").strip(),
                        )
                    )
                self.scraped_items = items
                self.review_filter_only_approved.set(review_filter_only_approved)
                self._refresh_review_list()

            if isinstance(generated_code, str) and generated_code.strip():
                self.generated_code_cache = generated_code
                self._show_generated_code(generated_code)

            self._refresh_ui()
            self._refresh_html_ui()
            self._update_source_selection_summary()
        finally:
            self._is_restoring_state = False

    def _on_close(self):
        self._save_ui_state()
        self.destroy()

    def add_topic_group(self, topic_name: str = "", add_initial_url: bool = False):
        self.topic_seq += 1

        group_frame = ctk.CTkFrame(self.topics_list, fg_color="#E5E7EB", corner_radius=8)
        group_frame.pack(fill="x", padx=6, pady=6)
        # Evita alçades fixes grans dels CTkFrame i ajusta al contingut real.
        group_frame.pack_propagate(True)
        group_frame.grid_propagate(True)
        group_frame.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(group_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        header.grid_columnconfigure(2, weight=1)

        expanded_var = ctk.BooleanVar(value=True)
        selected_var = ctk.BooleanVar(value=True)
        topic_var = ctk.StringVar(value=topic_name or f"Topic {self.topic_seq}")
        selected_var.trace_add("write", lambda *_: self._schedule_save_ui_state())
        topic_var.trace_add("write", lambda *_: self._schedule_save_ui_state())

        toggle_btn = ctk.CTkButton(
            header,
            text="-",
            width=28,
            command=lambda: self.toggle_topic_group(group),
        )
        toggle_btn.grid(row=0, column=0, padx=(0, 6))

        ctk.CTkCheckBox(
            header,
            text="",
            variable=selected_var,
            width=20,
            command=lambda: self._on_topic_selected_changed(group),
        ).grid(row=0, column=1, padx=(0, 6))

        ctk.CTkEntry(header, textvariable=topic_var, placeholder_text="Nom del topic").grid(
            row=0, column=2, sticky="ew", padx=(0, 8)
        )

        count_label = ctk.CTkLabel(header, text="0 URLs")
        count_label.grid(row=0, column=3, padx=(0, 8))

        ctk.CTkButton(
            header,
            text="+ URL",
            width=70,
            command=lambda: self.add_url_to_topic(group),
        ).grid(row=0, column=4, padx=(0, 6))

        ctk.CTkButton(
            header,
            text="X",
            width=34,
            fg_color="#B91C1C",
            hover_color="#991B1B",
            command=lambda: self.remove_topic_group(group_frame),
        ).grid(row=0, column=5)

        body = ctk.CTkFrame(group_frame, fg_color="transparent", height=1)
        body.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        body.grid_propagate(True)
        body.grid_columnconfigure(0, weight=1)

        urls_frame = ctk.CTkFrame(body, fg_color="transparent", height=1)
        urls_frame.grid(row=0, column=0, sticky="ew")
        urls_frame.grid_propagate(True)
        urls_frame.grid_columnconfigure(1, weight=1)

        group = {
            "frame": group_frame,
            "body": body,
            "urls_frame": urls_frame,
            "topic_var": topic_var,
            "selected_var": selected_var,
            "expanded_var": expanded_var,
            "toggle_btn": toggle_btn,
            "count_label": count_label,
            "url_rows": [],
        }
        self.topic_groups.append(group)

        if add_initial_url:
            self.add_url_to_topic(group)

        self._update_topic_count(group)
        self._update_source_selection_summary()
        self._schedule_save_ui_state()
        return group

    def toggle_topic_group(self, group):
        is_open = group["expanded_var"].get()
        if is_open:
            group["body"].grid_remove()
            group["toggle_btn"].configure(text="+")
            group["expanded_var"].set(False)
        else:
            group["body"].grid()
            group["toggle_btn"].configure(text="-")
            group["expanded_var"].set(True)
        self._schedule_save_ui_state()

    def remove_topic_group(self, frame):
        frame.destroy()
        self.topic_groups = [g for g in self.topic_groups if g["frame"] != frame]
        self._update_source_selection_summary()
        self._schedule_save_ui_state()

    def add_url_to_topic(self, group, url_value: str = ""):
        row_frame = ctk.CTkFrame(group["urls_frame"], fg_color="transparent")
        row_frame.pack(fill="x", pady=4)
        row_frame.grid_columnconfigure(1, weight=1)

        selected_var = ctk.BooleanVar(value=group["selected_var"].get())
        url_var = ctk.StringVar(value=url_value)
        selected_var.trace_add("write", lambda *_: self._schedule_save_ui_state())
        url_var.trace_add("write", lambda *_: self._schedule_save_ui_state())

        ctk.CTkCheckBox(
            row_frame,
            text="",
            variable=selected_var,
            width=20,
            command=lambda: self._on_url_selected_changed(group),
        ).grid(row=0, column=0, padx=(0, 6), sticky="w")

        ctk.CTkEntry(row_frame, textvariable=url_var, placeholder_text="https://...").grid(
            row=0, column=1, sticky="ew", padx=(0, 8)
        )

        ctk.CTkButton(
            row_frame,
            text="X",
            width=34,
            fg_color="#B91C1C",
            hover_color="#991B1B",
            command=lambda: self.remove_url_row(group, row_frame),
        ).grid(row=0, column=2)

        group["url_rows"].append({
            "frame": row_frame,
            "url_var": url_var,
            "selected_var": selected_var,
        })

        self._update_topic_count(group)
        self._update_source_selection_summary()
        self._schedule_save_ui_state()

    def remove_url_row(self, group, frame):
        frame.destroy()
        group["url_rows"] = [r for r in group["url_rows"] if r["frame"] != frame]
        self._sync_topic_with_children(group)
        self._update_topic_count(group)
        self._update_source_selection_summary()
        self._schedule_save_ui_state()

    def _on_topic_selected_changed(self, group):
        selected = group["selected_var"].get()
        for row in group["url_rows"]:
            row["selected_var"].set(selected)
        self._update_topic_count(group)
        self._update_source_selection_summary()
        self._schedule_save_ui_state()

    def _on_url_selected_changed(self, group):
        self._sync_topic_with_children(group)
        self._update_topic_count(group)
        self._update_source_selection_summary()
        self._schedule_save_ui_state()

    def _sync_topic_with_children(self, group):
        rows = group["url_rows"]
        if not rows:
            return
        any_selected = any(r["selected_var"].get() for r in rows)
        group["selected_var"].set(any_selected)

    def _update_topic_count(self, group):
        total = len(group["url_rows"])
        selected = sum(1 for r in group["url_rows"] if r["selected_var"].get())
        group["count_label"].configure(text=f"{selected}/{total} URLs")

    def _update_source_selection_summary(self):
        total_topics = len(self.topic_groups)
        selected_topics = sum(1 for g in self.topic_groups if g["selected_var"].get())

        total_urls = 0
        selected_urls = 0
        for g in self.topic_groups:
            self._update_topic_count(g)
            total_urls += len(g["url_rows"])
            selected_urls += sum(1 for r in g["url_rows"] if r["selected_var"].get())

        msg = f"Seleccionat: {selected_topics}/{total_topics} topics, {selected_urls}/{total_urls} URLs"

        if hasattr(self, "selection_summary_label"):
            self.selection_summary_label.configure(text=msg)
        self._refresh_topics_list_height()

    def _refresh_topics_list_height(self):
        if not hasattr(self, "topics_list"):
            return

        if not self.topic_groups:
            self.topics_list.configure(height=8)
            return

        estimated_height = 0
        for g in self.topic_groups:
            # Header topic
            estimated_height += 54

            # Cos amb URLs (només si expandit)
            if g["expanded_var"].get():
                url_count = len(g["url_rows"])
                if url_count > 0:
                    estimated_height += url_count * 44
                else:
                    estimated_height += 4

            # Marges del grup
            estimated_height += 18

        # Manté compacte però evita que rebenti tota la pantalla.
        estimated_height = max(8, min(estimated_height, 420))
        self.topics_list.configure(height=estimated_height)
    # CARREGA DE DADES A LA UI
    def _make_faq_item(
        self,
        topic: str,
        question: str,
        answer: str,
        source: str,
        approved: bool = False,
        forced_id: str = "",
    ) -> FaqItem:
        fid = forced_id or self._make_id(topic, question, source)
        approved_var = ctk.BooleanVar(value=approved)
        approved_var.trace_add("write", lambda *_: self._schedule_save_ui_state())
        return FaqItem(
            id=fid,
            topic=topic,
            question=question,
            answer=answer,
            source=source,
            approved_var=approved_var,
        )

    def _load_scraped_into_ui(self, flat_items: list[tuple[str, str, str, str]]):
        """
        flat_items: [(topic, question, answer, source), ...]
        Aquesta funció s'executa al fil principal (UI).
        """
        items = [
            self._make_faq_item(topic=topic, question=question, answer=answer, source=source, approved=False)
            for topic, question, answer, source in flat_items
        ]

        self.scraped_items = items
        self.review_filter_only_approved.set(False)
        self._refresh_review_list()
        self._schedule_save_ui_state()

    # ====UI Logging / output
    # LOGGING UI
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
        self.generated_code_cache = code or ""
        code = self._format_code_for_preview(code)
        self.log2.delete("1.0", "end")
        self.log2.insert("1.0", code)
        self.log2.see("1.0")
        self._schedule_save_ui_state()

    def _format_code_for_preview(self, code: str) -> str:
        text = (code or "").strip()
        if not text:
            return ""

        if "<" in text and ">" in text:
            try:
                return BeautifulSoup(text, "html.parser").prettify()
            except Exception:
                return text
        return text

    # ====UI state / refresh
    # REFRESH D'ESTAT UI
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
            self.gen_btn.configure(text="Generar codi font per la Genweb", width=260)

        elif mode == "sheets_oauth":
            self.html_csv_row.grid_remove()
            self.html_sheets_row.grid()
            self.html_oauth_row.grid()
            self.gen_btn.configure(text="Executa", width=160)
            self.log2.delete("1.0", "end")

        else:  # csv
            self.html_sheets_row.grid_remove()
            self.html_oauth_row.grid_remove()
            self.html_csv_row.grid()
            self.gen_btn.configure(text="Executa", width=160)
            self.log2.delete("1.0", "end")
    def _needs_oauth(self) -> bool:
        return self.output_mode.get() == "sheets_oauth"

    # ====Validations
    # VALIDACIONS
    def validate_inputs(self):

        # INPUT (UI rows)
        sources = self.get_sources_from_ui()
        if not sources:
            return False, "Afegeix almenys una URL vàlida a l'entrada."

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
            oauth_file = self.oauth_client_json.get().strip() or "oauth_client.json"
            if not os.path.exists(oauth_file):
                return False, f"Falta el fitxer OAuth: {oauth_file}"

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
    # ACCIONS (BOTO EXECUTA / GENERA)
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
        self.ui_log2(f"\n▶ Executant ({self.html_input_mode.get()})…")

        t = threading.Thread(target=self._generate_html_background, daemon=True)
        t.start()
    def _reset_ui(self):
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(0)
        self.run_btn.configure(state="normal")

    # ====Background workers (threads)
    # TREBALL EN SEGON PLA (THREADS)
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
                self.ui_log(f"Carregades a la UI: {len(flat_items)} FAQs")

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

                # ðŸ‘‡ ARA cridem una funció nova de core
                html_text = core.approved_rows_to_html(approved_rows, log=self.ui_log2)

                self.after(0, lambda: self._show_generated_code(html_text))
                return

            if mode == "sheets_oauth":
                approved_rows = self._get_approved_rows()
                if approved_rows:
                    sheet_rows = self._approved_rows_to_sheets_rows(approved_rows)
                    self.ui_log2(
                        f"FAQs aprovades a la UI: {len(approved_rows)}. Exportant a Google Sheets…"
                    )
                    core.export_rows_to_google_sheets_oauth(
                        rows=sheet_rows,
                        spreadsheet_title=self.html_sheet_title.get().strip(),
                        worksheet_name=self.html_sheet_tab.get().strip(),
                        oauth_client_json=self.oauth_client_json.get().strip() or "oauth_client.json",
                        token_file=self.token_file.get().strip() or "token.json",
                        log=self.ui_log2,
                    )
                    self.ui_log2(
                        "Procés completat. FAQs aprovades exportades al Google Sheets."
                    )
                    return

            # --- MODE CSV / SHEETS (com abans) ---
            core.run_approved_to_html_pipeline(
                input_mode=mode,
                input_csv_path=self.html_input_csv_path.get().strip() if mode == "csv" else None,
                sheet_title=self.html_sheet_title.get().strip() if mode == "sheets_oauth" else None,
                sheet_tab=self.html_sheet_tab.get().strip() if mode == "sheets_oauth" else None,
                oauth_client_json=self.oauth_client_json.get().strip() or "oauth_client.json",
                token_file=self.token_file.get().strip() or "token.json",
                log=self.ui_log2,
            )

            self.ui_log2(
                "Procés completat. En aquest mode no es mostra el codi font a la UI."
            )

        except Exception as e:
            msg = str(e)
            self.ui_log2(f"Error: {msg}")
            self.after(0, lambda: messagebox.showerror("Error", msg))
        finally:
            self.after(0, lambda: self.gen_btn.configure(state="normal"))

    # ====Data extraction from UI
    # EXTRACCIO DE DADES DES DE LA UI
    def get_sources_from_ui(self):
        out = []

        for g in self.topic_groups:
            topic = (g["topic_var"].get() or "").strip() or TOPICS_UI[0]
            topic_selected = g["selected_var"].get()
            if not topic_selected:
                continue

            for r in g["url_rows"]:
                url = (r["url_var"].get() or "").strip()
                if not url:
                    continue
                if not (url.startswith("http://") or url.startswith("https://")):
                    continue
                if not r["selected_var"].get():
                    continue

                out.append((url, topic))

        return out

    # TAB DE REVISIO / APROVACIO
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
            try:
                self._add_review_row(self.review_list, item)
            except Exception:
                # Fallback perquè un ítem mal format no trenqui tota la llista.
                row = ctk.CTkFrame(self.review_list)
                row.pack(fill="x", pady=6, padx=6)
                ctk.CTkLabel(
                    row,
                    text=item.question,
                    anchor="w",
                    justify="left",
                    wraplength=900,
                ).pack(fill="x", padx=12, pady=(8, 2))
                plain = BeautifulSoup(item.answer or "", "html.parser").get_text(" ", strip=True)
                ctk.CTkLabel(
                    row,
                    text=plain,
                    anchor="w",
                    justify="left",
                    wraplength=900,
                    text_color="#4B5563",
                ).pack(fill="x", padx=12, pady=(0, 8))

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

        # Resposta (render HTML: enllaços clicables, negreta i llistes)
        a = ctk.CTkTextbox(row, height=86, wrap="word")
        a.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 8))
        a.configure(fg_color="transparent", text_color="#4B5563", border_width=0)
        self._render_html_to_textbox(a, item.answer)

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

    def _render_html_to_textbox(self, textbox: ctk.CTkTextbox, html_text: str):
        text = (html_text or "").strip()
        tk_text = getattr(textbox, "_textbox", textbox)
        textbox.configure(state="normal")
        textbox.delete("1.0", "end")

        if not text:
            textbox.configure(state="disabled")
            return

        if "<" not in text or ">" not in text:
            textbox.insert("1.0", text)
            textbox.configure(state="disabled")
            return

        soup = BeautifulSoup(text, "html.parser")
        link_count = 0

        tk_text.tag_configure("bold", font=ctk.CTkFont(size=13, weight="bold"))

        def _insert(t: str, tags=()):
            if t:
                textbox.insert("end", t, tags)

        def _walk(node, active_tags=()):
            nonlocal link_count

            if isinstance(node, NavigableString):
                _insert(str(node), active_tags)
                return

            name = getattr(node, "name", None)
            if not name:
                return
            name = name.lower()

            next_tags = list(active_tags)
            if name in {"b", "strong"}:
                next_tags.append("bold")

            if name == "a":
                href = (node.get("href") or "").strip()
                if href:
                    tag_name = f"link_{link_count}"
                    link_count += 1
                    tk_text.tag_configure(tag_name, foreground="#1D4ED8", underline=True)
                    tk_text.tag_bind(
                        tag_name, "<Button-1>", lambda _e, u=href: webbrowser.open_new_tab(u)
                    )
                    next_tags.append(tag_name)

            if name == "br":
                _insert("\n", active_tags)
                return

            if name == "li":
                _insert("• ", active_tags)

            for child in getattr(node, "children", []):
                _walk(child, tuple(next_tags))

            if name in {"p", "div", "ul", "ol", "li"}:
                _insert("\n", active_tags)

        for n in soup.contents:
            _walk(n)

        # Manté els tags (bold/enllaços): no reescriure el contingut.
        # Només traiem salts finals sobrants.
        if textbox.compare("end-1c", ">", "1.0"):
            end_text = textbox.get("end-2c", "end-1c")
            while end_text == "\n" and textbox.compare("end-2c", ">", "1.0"):
                textbox.delete("end-2c", "end-1c")
                end_text = textbox.get("end-2c", "end-1c")
        try:
            tk_text.configure(disabledforeground="#4B5563")
        except Exception:
            pass
        textbox.configure(state="disabled")


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

    def _approved_rows_to_sheets_rows(self, approved_rows: list[list[str]]) -> list[list[str]]:
        rows: list[list[str]] = []
        for topic, question, answer, source in approved_rows:
            rows.append(
                [
                    topic or "",
                    question or "",
                    answer or "",
                    "aprovat",
                    "",
                    "",
                    "",
                    "",
                    source or "",
                ]
            )
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

    # ESTILS DE TABS
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


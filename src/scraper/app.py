# IMPORTS
import base64
import hashlib
import json
import os
import re
import sys
import threading
import time
import unicodedata
import webbrowser
from tkinter import font as tkfont
from tkinter import messagebox
from urllib.parse import urlparse

import customtkinter as ctk
from bs4 import BeautifulSoup, NavigableString
from PIL import Image

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)
PACKAGE_PARENT = os.path.dirname(MODULE_DIR)
if PACKAGE_PARENT not in sys.path:
    sys.path.insert(0, PACKAGE_PARENT)

try:
    from scraper import core
    from scraper.models import FaqItem
    from scraper.settings import (
        BG,
        BORDER,
        DANGER,
        DANGER_BG,
        DANGER_BORDER,
        DANGER_HOVER,
        DANGER_TEXT,
        INFO_PANEL,
        INPUT_BG,
        LIGHT_PANEL,
        LINK,
        PLACEHOLDER,
        SCROLLBAR,
        SCROLLBAR_HOVER,
        STATUS_NEUTRAL,
        SUCCESS,
        SUCCESS_BG,
        SUCCESS_BORDER,
        SUCCESS_HOVER,
        SUCCESS_TEXT,
        SURFACE,
        SURFACE_SUBTLE,
        TEXT_MUTED,
        TEXT_PRIMARY,
        TOPICS_UI,
        UPC_BLUE,
        UPC_BLUE_TAB,
    )
except ImportError:
    try:
        from . import core
        from .models import FaqItem
        from .settings import (
            BG,
            BORDER,
            DANGER,
            DANGER_BG,
            DANGER_BORDER,
            DANGER_HOVER,
            DANGER_TEXT,
            INFO_PANEL,
            INPUT_BG,
            LIGHT_PANEL,
            LINK,
            PLACEHOLDER,
            SCROLLBAR,
            SCROLLBAR_HOVER,
            STATUS_NEUTRAL,
            SUCCESS,
            SUCCESS_BG,
            SUCCESS_BORDER,
            SUCCESS_HOVER,
            SUCCESS_TEXT,
            SURFACE,
            SURFACE_SUBTLE,
            TEXT_MUTED,
            TEXT_PRIMARY,
            TOPICS_UI,
            UPC_BLUE,
            UPC_BLUE_TAB,
        )
    except ImportError:
        import core
        from models import FaqItem
        from settings import (
            BG,
            BORDER,
            DANGER,
            DANGER_BG,
            DANGER_BORDER,
            DANGER_HOVER,
            DANGER_TEXT,
            INFO_PANEL,
            INPUT_BG,
            LIGHT_PANEL,
            LINK,
            PLACEHOLDER,
            SCROLLBAR,
            SCROLLBAR_HOVER,
            STATUS_NEUTRAL,
            SUCCESS,
            SUCCESS_BG,
            SUCCESS_BORDER,
            SUCCESS_HOVER,
            SUCCESS_TEXT,
            SURFACE,
            SURFACE_SUBTLE,
            TEXT_MUTED,
            TEXT_PRIMARY,
            TOPICS_UI,
            UPC_BLUE,
            UPC_BLUE_TAB,
        )

ctk.set_appearance_mode("light")


def _patch_ctk_entry_placeholder_with_textvariable():
    """Workaround per CustomTkinter: permet placeholder_text amb textvariable buit."""
    if getattr(ctk.CTkEntry, "_placeholder_textvariable_patch_applied", False):
        return

    def _activate_placeholder(self):
        textvar_empty = self._textvariable is None or self._textvariable == ""
        if not textvar_empty:
            try:
                textvar_empty = self._textvariable.get() == ""
            except Exception:
                textvar_empty = False

        if self._entry.get() == "" and self._placeholder_text is not None and textvar_empty:
            self._placeholder_text_active = True
            self._pre_placeholder_arguments = {
                "show": self._entry.cget("show"),
                "textvariable_obj": self._textvariable,
            }
            if self._textvariable is not None and self._textvariable != "":
                # Evita contaminar el StringVar amb el text del placeholder.
                self._entry.configure(textvariable="")
            self._entry.config(
                fg=self._apply_appearance_mode(self._placeholder_text_color),
                disabledforeground=self._apply_appearance_mode(self._placeholder_text_color),
                show="",
            )
            self._entry.delete(0, "end")
            self._entry.insert(0, self._placeholder_text)

    def _deactivate_placeholder(self):
        if self._placeholder_text_active and self._entry.cget("state") != "readonly":
            self._placeholder_text_active = False
            self._entry.config(
                fg=self._apply_appearance_mode(self._text_color),
                disabledforeground=self._apply_appearance_mode(self._text_color),
            )
            self._entry.delete(0, "end")
            if isinstance(self._pre_placeholder_arguments, dict):
                show_value = self._pre_placeholder_arguments.get("show", "")
                self._entry.configure(show=show_value)
                tv_obj = self._pre_placeholder_arguments.get("textvariable_obj", None)
                if tv_obj is not None and tv_obj != "":
                    self._entry.configure(textvariable=tv_obj)
                else:
                    self._entry.configure(textvariable="")

    def _textvariable_callback(self, var_name, index, mode):
        try:
            current = self._textvariable.get()
        except Exception:
            current = None
        if current == "":
            if not getattr(self, "_is_focused", False):
                self._activate_placeholder()
        elif getattr(self, "_placeholder_text_active", False):
            self._deactivate_placeholder()

    def _entry_focus_in(self, event=None):
        if (
            getattr(self, "_placeholder_text", None) is not None
            and self._entry.get() == self._placeholder_text
            and not getattr(self, "_placeholder_text_active", False)
        ):
            self._placeholder_text_active = True
        self._deactivate_placeholder()
        self._is_focused = True

    def _entry_focus_out(self, event=None):
        self._activate_placeholder()
        self._is_focused = False

    ctk.CTkEntry._activate_placeholder = _activate_placeholder
    ctk.CTkEntry._deactivate_placeholder = _deactivate_placeholder
    ctk.CTkEntry._textvariable_callback = _textvariable_callback
    ctk.CTkEntry._entry_focus_in = _entry_focus_in
    ctk.CTkEntry._entry_focus_out = _entry_focus_out
    ctk.CTkEntry._placeholder_textvariable_patch_applied = True


_patch_ctk_entry_placeholder_with_textvariable()



# HELPERS
def resource_path(relative_path: str) -> str:
    """Retorna una ruta absoluta tant si s'executa en dev com si s'executa dins PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        # Project root from this file (src/scraper/app.py -> project root)
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(base_path, relative_path)


def runtime_base_dir() -> str:
    """Directori base on l'usuari espera trobar fitxers externs quan executa l'app."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.getcwd()


def first_existing_path(*candidates: str) -> str:
    for candidate in candidates:
        path = (candidate or "").strip()
        if path and os.path.exists(path):
            return path
    return ""
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
        self._run_started_at = 0.0
        self._state_write_job = None
        self._is_restoring_state = False
        self._action_btn_font = ctk.CTkFont(size=13, weight="bold")
        self._action_btn_height = 38
        self._action_btn_width = 200
        self._compact_form_width = 560
        self._topic_form_width = 200
        self._url_form_width = 560
        self._input_italic_font = ctk.CTkFont(size=13, slant="italic")
        self._page_title_font = ctk.CTkFont(size=28, weight="bold")
        self._section_tag_font = ctk.CTkFont(size=15, weight="bold")
        self._field_label_font = ctk.CTkFont(size=13, weight="bold")
        self._body_font = ctk.CTkFont(size=13)
        self._eyebrow_font = ctk.CTkFont(size=12, weight="bold")
        self._section_padx = 10
        self._section_pady = 10
        self._card_inner_padx = 18
        self._card_inner_pady = 14
        self._form_row_gap = 8
        self._panel_content_width = 720
        self._surface_color = SURFACE
        self._surface_border = BORDER
        self._subtle_panel = SURFACE_SUBTLE
        self._text_color = TEXT_PRIMARY
        self._muted_text_color = TEXT_MUTED
        self._input_bg_color = INPUT_BG
        self._placeholder_color = PLACEHOLDER
        self._scrollbar_color = SCROLLBAR
        self._scrollbar_hover_color = SCROLLBAR_HOVER
        self._content_max_width = 960
        self._centered_content_areas = []
        self._home_shadow_job = None
        self._restoring_visible_section = False
        self._last_configured_size = None

        # Fix icona barra de tasques Windows (més fiable a l'EXE)
        if ctypes:
            try:
                myappid = "upc.faq.scraper.v1"
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass

        self.title("FAQs Manager · UPC")
        screen_w = max(1, int(self.winfo_screenwidth() or 1))
        default_w = min(980, max(900, int(screen_w * 0.64)))
        default_h = 760
        self.geometry(f"{default_w}x{default_h}")
        self._base_min_w = 900
        self._base_min_h = 680
        self._collapsed_height_fixed = default_h
        self._details_extra_h = 140
        self._expanded_height_fixed = self._collapsed_height_fixed + self._details_extra_h
        self._collapsed_width = default_w
        self.minsize(self._base_min_w, self._base_min_h)
        self.configure(fg_color=BG)

        # Taskbar icon
        try:
            self.iconbitmap(resource_path("assets/upc_logo.ico"))
        except Exception as e:
            print("No s'ha pogut carregar .ico:", e)

        # INPUT: sempre CSV
        self.input_mode = ctk.StringVar(value="ui")
        self.output_mode = ctk.StringVar(value="sheets_oauth")
        self.output_mode.trace_add("write", lambda *_: self._schedule_save_ui_state())

        # Input UI grouped by topic
        self.topic_groups = []
        self.topic_seq = 0

        # Output file (csv)
        self.output_file_path = ctk.StringVar()
        self.output_file_path.trace_add("write", lambda *_: self._schedule_save_ui_state())

        # Output sheets
        self.output_sheet_title = ctk.StringVar()
        self.output_sheet_tab = ctk.StringVar(value="FAQs")
        self._selected_output_sheet_id = ""
        self._selected_html_sheet_id = ""
        self.output_sheet_title.trace_add("write", lambda *_: self._schedule_save_ui_state())
        self.output_sheet_tab.trace_add("write", lambda *_: self._schedule_save_ui_state())
        self.recent_sheets_titles: list[str] = []
        self.recent_sheets_tabs: dict[str, str] = {}
        self.sheet_target_mode = ctk.StringVar(value="Examinar")
        self.html_sheet_target_mode = ctk.StringVar(value="Examinar")
        self._last_sheet_target_mode = "Examinar"
        self._last_html_sheet_target_mode = "Examinar"
        self.sheet_target_mode.trace_add("write", lambda *_: self._schedule_save_ui_state())
        self.html_sheet_target_mode.trace_add("write", lambda *_: self._schedule_save_ui_state())

        # OAuth files (Sheets)
        runtime_dir = runtime_base_dir()
        oauth_candidates = [
            os.path.join(runtime_dir, "oauth_client.json"),
            os.path.join(os.getcwd(), "oauth_client.json"),
            resource_path("oauth_client.json"),
            os.path.join(runtime_dir, "tests", "oauth_client.json"),
            os.path.join(os.getcwd(), "tests", "oauth_client.json"),
            resource_path("tests/oauth_client.json"),
        ]
        self._default_oauth_client_json = first_existing_path(*oauth_candidates) or oauth_candidates[0]
        self._default_token_file = "token.json"
        self.oauth_client_json = ctk.StringVar(value=self._default_oauth_client_json)
        self.token_file = ctk.StringVar(value=self._default_token_file)
        self.google_auth_status = ctk.StringVar(value="")
        self._google_auth_in_progress = False
        self._google_profile_name = ""
        self._google_profile_email = ""
        self.google_session_summary = ctk.StringVar(value="")
        self._is_home_visible = True
        self.oauth_client_json.trace_add("write", lambda *_: self._schedule_save_ui_state())
        self.token_file.trace_add("write", lambda *_: self._schedule_save_ui_state())

        # ---------- Layout ----------
        self._build_header()
        self._build_body()
        self._refresh_ui()
        self._restore_ui_state()
        self.bind("<Configure>", self._on_window_configure)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_google_logo_image(self):
        size = (28, 28)
        try:
            img = Image.open(resource_path("assets/Google_logo.png"))
            return ctk.CTkImage(light_image=img, size=size)
        except Exception:
            # Fallback discret per si falta l'asset.
            img = Image.new("RGBA", size, (0, 0, 0, 0))
            return ctk.CTkImage(light_image=img, size=size)

    def _create_upc_logo_image(self, target_h: int):
        target_h = max(1, int(target_h))
        try:
            img = Image.open(resource_path("assets/upc_logo.png"))
            w, h = img.size
            target_w = max(1, int(w * (target_h / max(1, h))))
            return ctk.CTkImage(light_image=img, size=(target_w, target_h))
        except Exception:
            fallback_w = max(1, int(target_h * 4))
            img = Image.new("RGBA", (fallback_w, target_h), (0, 0, 0, 0))
            return ctk.CTkImage(light_image=img, size=(fallback_w, target_h))

    def _create_home_nav_icon_image(self, target_h: int = 20):
        target_h = max(1, int(target_h))
        try:
            img = Image.open(resource_path("assets/home_logo.png"))
            w, h = img.size
            target_w = max(1, int(w * (target_h / max(1, h))))
            return ctk.CTkImage(light_image=img, size=(target_w, target_h))
        except Exception:
            img = Image.new("RGBA", (target_h, target_h), (0, 0, 0, 0))
            return ctk.CTkImage(light_image=img, size=(target_h, target_h))

    def _create_home_action_icon(self, relative_path: str, size: tuple[int, int] = (120, 120)):
        try:
            img = Image.open(resource_path(relative_path))
            return ctk.CTkImage(light_image=img, size=size)
        except Exception:
            img = Image.new("RGBA", size, (0, 0, 0, 0))
            return ctk.CTkImage(light_image=img, size=size)

    def _create_folder_section_tag(self, parent, row: int, text: str, padx: int = 8):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.grid(row=row, column=0, padx=padx, pady=(0, 0))
        tag = ctk.CTkFrame(
            wrap,
            fg_color=self._surface_color,
            corner_radius=12,
            border_width=1,
            border_color=self._surface_border,
        )
        tag.pack(side="left")
        ctk.CTkLabel(
            tag,
            text=text,
            font=self._section_tag_font,
            text_color=self._text_color,
        ).pack(padx=18, pady=(8, 8))
        return wrap

    def _create_centered_content_area(self, parent, max_width: int | None = None):
        content = ctk.CTkFrame(parent, fg_color="transparent")
        content.grid(row=0, column=0, padx=0, pady=0)
        content.grid_columnconfigure(0, weight=1)
        self._centered_content_areas.append({
            "parent": parent,
            "content": content,
            "max_width": max_width or self._content_max_width,
        })
        self.after(0, self._refresh_centered_content_areas)
        return content

    def _refresh_centered_content_areas(self):
        for area in getattr(self, "_centered_content_areas", []):
            parent = area.get("parent")
            content = area.get("content")
            max_w = int(area.get("max_width") or self._content_max_width)
            if not parent or not content:
                continue
            try:
                available = int(parent.winfo_width() or 0)
                target = max(760, min(max_w, max(0, available - 28)))
                content.configure(width=target)
            except Exception:
                pass

    def _refresh_responsive_form_widths(self):
        try:
            window_w = int(self.winfo_width() or 0)
        except Exception:
            window_w = 0
        if window_w <= 0:
            return

        sheet_entry_w = max(260, min(520, window_w - 520))
        sheet_picker_w = max(220, min(300, window_w - 640))

        for entry_name in (
            "output_sheet_title_entry",
            "output_sheet_tab_entry",
            "html_sheet_title_entry",
            "html_sheet_tab_entry",
        ):
            entry = getattr(self, entry_name, None)
            if not entry:
                continue
            try:
                entry.configure(width=sheet_entry_w)
            except Exception:
                pass

        for widget_name in (
            "browse_sheets_btn_1",
            "new_sheets_btn_1",
            "recent_sheets_menu",
            "browse_sheets_btn_2",
            "new_sheets_btn_2",
            "html_recent_sheets_menu",
        ):
            widget = getattr(self, widget_name, None)
            if not widget:
                continue
            try:
                widget.configure(width=sheet_picker_w)
            except Exception:
                pass

    # ====Build UI
    # CONSTRUCCIO UI
    def _build_header(self):
        self.header = ctk.CTkFrame(self, fg_color=self._subtle_panel, corner_radius=0, height=78)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        self.header.grid_columnconfigure(0, weight=0)
        self.header.grid_columnconfigure(1, weight=0)
        self.header.grid_columnconfigure(2, weight=1)
        self.home_nav_icon_image = self._create_home_nav_icon_image(20)
        self.tab_switch_genweb_icon = self._create_home_action_icon("assets/html-source-code.png", size=(24, 24))
        self.tab_switch_download_icon = self._create_home_action_icon("assets/download.png", size=(24, 24))

        self.home_nav_btn = ctk.CTkButton(
            self.header,
            text="Inici",
            image=self.home_nav_icon_image,
            compound="left",
            width=150,
            height=48,
            corner_radius=16,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._show_home,
            fg_color=self._surface_color,
            hover_color=self._subtle_panel,
            text_color=self._text_color,
            border_width=1,
            border_color=self._surface_border,
        )
        self.home_nav_btn._keep_custom_color = True
        self.home_nav_btn.grid(row=0, column=0, sticky="w", padx=(20, 10), pady=8)
        self.tab_switch_btn = ctk.CTkButton(
            self.header,
            text="Generador de codi Genweb",
            image=self.tab_switch_genweb_icon,
            compound="left",
            width=300,
            height=48,
            corner_radius=16,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._go_to_other_workspace_tab,
            fg_color=self._surface_color,
            hover_color=self._subtle_panel,
            text_color=self._text_color,
            border_width=1,
            border_color=self._surface_border,
        )
        self.tab_switch_btn._keep_custom_color = True
        self.tab_switch_btn.grid(row=0, column=1, sticky="w", padx=(0, 10), pady=8)
        self.tab_switch_btn.grid_remove()
        self.upc_header_logo_image = self._create_upc_logo_image(42)
        self.upc_header_logo_label = ctk.CTkLabel(
            self.header,
            text="",
            image=self.upc_header_logo_image,
        )
        self.upc_header_logo_label.grid(row=0, column=2, sticky="e", padx=(10, 18), pady=8)
        self.upc_header_logo_label.grid_remove()

    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color=BG)
        self.body = body
        body.pack(fill="both", expand=True, padx=22, pady=(0, 0))

        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.home_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.home_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.home_frame.grid_columnconfigure(0, weight=1)
        self.home_frame.grid_rowconfigure(0, weight=1)  # espai superior flexible
        self.home_frame.grid_rowconfigure(1, weight=0)  # titol
        self.home_frame.grid_rowconfigure(2, weight=1)  # espai entre titol i cards (igual al superior)
        self.home_frame.grid_rowconfigure(3, weight=0)  # cards
        self.home_frame.grid_rowconfigure(4, weight=1)  # espai inferior flexible
        self.home_frame.grid_rowconfigure(5, weight=0)  # credits/logo
        self.upc_home_logo_image = self._create_upc_logo_image(42)

        home_title_wrap = ctk.CTkFrame(self.home_frame, fg_color="transparent")
        home_title_wrap.grid(row=1, column=0, sticky="n")
        home_title_tag = ctk.CTkFrame(
            home_title_wrap,
            fg_color=self._surface_color,
            corner_radius=6,
            border_width=1,
            border_color=self._surface_border,
        )
        home_title_tag.pack()
        self.home_title_logo_icon = self._create_home_action_icon("assets/faqs1_logo.png", size=(52, 52))
        ctk.CTkLabel(
            home_title_tag,
            text="  FAQs Manager de la UPC",
            image=self.home_title_logo_icon,
            compound="left",
            font=ctk.CTkFont(size=30, weight="normal"),
            text_color=self._text_color,
        ).pack(padx=22, pady=(10, 10))

        home_card = ctk.CTkFrame(self.home_frame, fg_color="transparent")
        home_card.grid(row=3, column=0, padx=0, pady=(0, 26))
        home_card.grid_columnconfigure((0, 1), weight=1, uniform="home_btn")
        self.home_download_icon = self._create_home_action_icon("assets/download.png")
        self.home_source_icon = self._create_home_action_icon("assets/html-source-code.png")
        self.tab_download_title_icon = self._create_home_action_icon("assets/download.png", size=(30, 30))
        self.tab_export_title_icon = self._create_home_action_icon("assets/html-source-code.png", size=(30, 30))

        self.home_download_wrap = ctk.CTkFrame(home_card, fg_color="transparent", width=396, height=336)
        self.home_download_wrap.grid(row=0, column=0, padx=(16, 16), pady=(12, 12), sticky="nsew")
        self.home_download_wrap.grid_propagate(False)
        self.home_download_shadow_soft = ctk.CTkFrame(
            self.home_download_wrap, fg_color=self._subtle_panel, corner_radius=8, width=382, height=322
        )
        self.home_download_shadow = ctk.CTkFrame(
            self.home_download_wrap, fg_color=self._surface_border, corner_radius=9, width=384, height=324
        )

        self.home_download_btn = ctk.CTkButton(
            self.home_download_wrap,
            text="Descarregar FAQs",
            image=self.home_download_icon,
            compound="top",
            width=380,
            height=320,
            corner_radius=6,
            font=ctk.CTkFont(size=30, weight="normal"),
            command=self._open_section_download,
            fg_color=self._surface_color,
            hover_color=self._surface_color,
            text_color=self._text_color,
            border_width=1,
            border_color=self._surface_border,
        )
        self.home_download_btn.place(x=0, y=0)
        self._bind_home_card_shadow(
            self.home_download_btn,
            (self.home_download_shadow_soft, self.home_download_shadow),
            self.home_download_wrap,
        )

        self.home_export_wrap = ctk.CTkFrame(home_card, fg_color="transparent", width=396, height=336)
        self.home_export_wrap.grid(row=0, column=1, padx=(16, 16), pady=(12, 12), sticky="nsew")
        self.home_export_wrap.grid_propagate(False)
        self.home_export_shadow_soft = ctk.CTkFrame(
            self.home_export_wrap, fg_color=self._subtle_panel, corner_radius=8, width=382, height=322
        )
        self.home_export_shadow = ctk.CTkFrame(
            self.home_export_wrap, fg_color=self._surface_border, corner_radius=9, width=384, height=324
        )
        self.home_export_btn = ctk.CTkButton(
            self.home_export_wrap,
            text="Generar codi per\nGenweb",
            image=self.home_source_icon,
            compound="top",
            width=380,
            height=320,
            corner_radius=6,
            font=ctk.CTkFont(size=30, weight="normal"),
            command=self._open_section_export,
            fg_color=self._surface_color,
            hover_color=self._surface_color,
            text_color=self._text_color,
            border_width=1,
            border_color=self._surface_border,
        )
        self.home_export_btn.place(x=0, y=0)
        self._bind_home_card_shadow(
            self.home_export_btn,
            (self.home_export_shadow_soft, self.home_export_shadow),
            self.home_export_wrap,
        )

        home_footer = ctk.CTkFrame(self.home_frame, fg_color="transparent")
        home_footer.grid(row=5, column=0, sticky="s", pady=(0, 6))
        home_footer.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            home_footer,
            text="",
            image=self.upc_home_logo_image,
        ).grid(row=0, column=0, sticky="w", padx=(0, 10))
        ctk.CTkLabel(
            home_footer,
            text=(
                "Credits: UPC ESEIAAT\n"
                "Eina desenvolupada en el marc del projecte Genweb de la Universitat "
                "Politecnica de Catalunya (UPC) per a la gestio i publicacio de continguts FAQ."
            ),
            text_color=self._muted_text_color,
            font=ctk.CTkFont(size=11),
            justify="left",
            anchor="w",
        ).grid(row=0, column=1, sticky="w")

        self.workspace_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.workspace_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.workspace_frame.grid_columnconfigure(0, weight=1)
        self.workspace_frame.grid_rowconfigure(0, weight=1)
        self.workspace_frame.grid_remove()

        tabs = ctk.CTkTabview(self.workspace_frame)
        tabs.grid(row=0, column=0, sticky="nsew", pady=(0, 0))
        self.tabs = tabs
        self.tab_name_scrape = "Fonts i descàrrega"
        self.tab_name_export = "Exporta codi font per Genweb"
        self.current_tab_name = self.tab_name_scrape
        self._style_tabview(tabs)
        self.after(50, lambda: self._fix_tab_text_colors(tabs))

        tab_scrape = tabs.add(self.tab_name_scrape)
        tab_html = tabs.add(self.tab_name_export)
        try:
            # Evita la franja superior que CTkTabview reserva pel selector de pestanyes.
            tabs._outer_spacing = 0
            tabs._outer_button_overhang = 0
            tabs._button_height = 0
            tabs._configure_grid()
            tabs._set_grid_canvas()
            tabs._segmented_button.grid_remove()
            tabs._segmented_button.pack_forget()
            tabs._segmented_button.place_forget()
        except Exception:
            pass

        tab_scrape.grid_columnconfigure(0, weight=1)
        tab_scrape.grid_rowconfigure(0, weight=1)
        self.tab_scrape_scroll = ctk.CTkScrollableFrame(
            tab_scrape,
            fg_color="transparent",
            scrollbar_button_color=self._scrollbar_color,
            scrollbar_button_hover_color=self._scrollbar_hover_color,
        )
        self.tab_scrape_scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.tab_scrape_scroll.grid_columnconfigure(0, weight=1)
        self._setup_auto_scrollbar(self.tab_scrape_scroll)
        scrape_parent = self._create_centered_content_area(self.tab_scrape_scroll)

        tab_html.grid_columnconfigure(0, weight=1)
        tab_html.grid_rowconfigure(5, weight=1)  # espai flexible al final (evita "flotar" la sortida)
        html_parent = self._create_centered_content_area(tab_html)


        tabs.configure(command=lambda: self._on_tab_changed())

        # TAB 1: SCRAPE I EXPORTA
        tab1_header = ctk.CTkFrame(scrape_parent, fg_color="transparent")
        tab1_header.grid(row=0, column=0, sticky="ew", padx=8, pady=(0, 22))
        tab1_header.grid_columnconfigure(0, weight=1)
        tab1_title_card = ctk.CTkFrame(
            tab1_header,
            fg_color=self._surface_color,
            corner_radius=14,
            border_width=1,
            border_color=self._surface_border,
        )
        tab1_title_card.grid(row=0, column=0)
        ctk.CTkLabel(
            tab1_title_card,
            text="Descarregador de FAQs",
            image=self.tab_download_title_icon,
            compound="left",
            font=self._page_title_font,
            text_color="#0F172A",
        ).pack(padx=18, pady=(10, 10))

        self._create_folder_section_tag(
            scrape_parent,
            row=1,
            text="Entrada · Introdueix la URL de la pagina d'on extreure les FAQs",
            padx=self._section_padx,
        )

        self.in_card = ctk.CTkFrame(
            scrape_parent,
            fg_color=self._surface_color,
            corner_radius=18,
            border_width=1,
            border_color=self._surface_border,
        )
        self.in_card.grid(row=2, column=0, sticky="ew", padx=self._section_padx, pady=(0, 18))
        self.in_card.grid_columnconfigure(0, weight=1)
        self.topics_list = ctk.CTkFrame(self.in_card, fg_color="transparent", height=8)
        self.topics_list.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=self._card_inner_padx,
            pady=(self._card_inner_pady, self._card_inner_pady),
        )
        # Controlem manualment l'alçada per evitar espais buits grans.
        self.topics_list.grid_propagate(False)
        self.topics_list.grid_columnconfigure(0, weight=1)

        self.add_topic_group(topic_name="", add_initial_url=True)

        self._create_folder_section_tag(
            scrape_parent,
            row=3,
            text="Sortida · Tria on descarregar les FAQs",
            padx=self._section_padx,
        )

        # --- SORTIDA card ---
        self.out_card = ctk.CTkFrame(
            scrape_parent,
            fg_color=self._surface_color,
            corner_radius=18,
            border_width=1,
            border_color=self._surface_border,
        )
        self.out_card.grid(row=4, column=0, sticky="ew", padx=self._section_padx, pady=(0, 8))
        self.out_card.grid_columnconfigure(0, weight=1)
        self.out_card.grid_columnconfigure(1, weight=1)
        self.out_card.grid_columnconfigure(2, weight=1)

        out_mode_frame = ctk.CTkFrame(self.out_card, fg_color="transparent")
        out_mode_frame.grid(
            row=0,
            column=1,
            padx=self._card_inner_padx,
            pady=(self._card_inner_pady, 12),
        )


        self.google_logo_image = self._create_google_logo_image()
        self.google_session_card_1 = ctk.CTkFrame(
            out_mode_frame,
            fg_color=self._surface_color,
            corner_radius=10,
            border_width=1,
            border_color=self._surface_border,
        )
        self.google_session_card_1.pack(anchor="center", pady=(10, 0))
        self.google_session_card_1.pack_forget()
        self.google_session_card_1.grid_columnconfigure(0, weight=0)
        self.google_session_card_1.grid_columnconfigure(1, weight=0)

        self.google_session_info_label_1 = ctk.CTkLabel(
            self.google_session_card_1,
            textvariable=self.google_session_summary,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self._text_color,
            anchor="w",
            justify="left",
            image=self.google_logo_image,
            compound="left",
        )
        self.google_session_info_label_1.grid(row=0, column=0, padx=(16, 12), pady=14, sticky="w")
        self.google_logout_btn_1 = ctk.CTkButton(
            self.google_session_card_1,
            text="Tancar sessió",
            command=self.google_logout_clicked,
            width=136,
            height=38,
            font=self._action_btn_font,
            fg_color=self._surface_color,
            hover_color=self._subtle_panel,
            text_color=self._text_color,
            border_width=1,
            border_color=self._surface_border,
            corner_radius=10,
        )
        self.google_logout_btn_1.grid(row=0, column=1, padx=(0, 14), pady=10)

        self.google_login_btn_1 = ctk.CTkButton(
            out_mode_frame,
            text="Iniciar sessió amb Google",
            command=self.google_login_clicked,
            width=230,
            height=46,
            font=self._action_btn_font,
            image=self.google_logo_image,
            fg_color=self._surface_color,
            hover_color=self._subtle_panel,
            text_color=self._text_color,
            border_width=1,
            border_color=self._surface_border,
            corner_radius=10,
        )
        self.google_login_btn_1.pack(anchor="w", pady=(10, 0))

        # Sheets rows
        self.out_sheets_row = ctk.CTkFrame(self.out_card, fg_color="transparent")
        self.out_sheets_row.grid(
            row=1,
            column=1,
            padx=self._card_inner_padx,
            pady=(0, 12),
        )
        self.out_sheets_row.grid_columnconfigure(0, weight=0)
        self.out_sheets_row.grid_columnconfigure(1, weight=0)

        self.sheet_target_panel = ctk.CTkFrame(
            self.out_sheets_row,
            fg_color=self._subtle_panel,
            corner_radius=14,
            border_width=1,
            border_color=self._surface_border,
        )
        self.sheet_target_panel.grid(row=0, column=0, columnspan=2, padx=6, pady=(0, 4))
        self.sheet_target_panel.grid_columnconfigure(0, weight=1)

        self.sheet_browse_wrap = ctk.CTkFrame(self.sheet_target_panel, fg_color="transparent")
        self.sheet_browse_wrap.grid(row=0, column=0, padx=12, pady=12, sticky="ew")
        self.sheet_browse_wrap.grid_columnconfigure(0, weight=1)
        self.sheet_browse_wrap.grid_columnconfigure(1, weight=1)

        self.browse_sheets_btn_1 = ctk.CTkButton(
            self.sheet_browse_wrap,
            text="Examinar Google Sheets",
            width=220,
            command=self.browse_google_sheets_scrape_clicked,
        )
        self.browse_sheets_btn_1.grid(row=0, column=0, padx=(0, 8), pady=0, sticky="ew")

        self.new_sheets_btn_1 = ctk.CTkButton(
            self.sheet_browse_wrap,
            text="Nou Google Sheets",
            width=220,
            command=self.new_google_sheets_scrape_clicked,
        )
        self.new_sheets_btn_1.grid(row=0, column=1, padx=(8, 0), pady=0, sticky="ew")

        self.sheet_new_wrap = ctk.CTkFrame(self.sheet_target_panel, fg_color="transparent")
        self.sheet_new_wrap.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="ew")
        self.sheet_new_wrap.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.sheet_new_wrap, text="Títol del nou Google Sheet", font=self._eyebrow_font, text_color=self._muted_text_color).grid(
            row=0, column=0, padx=(4, 10), pady=(0, 6), sticky="w"
        )
        self.output_sheet_title_entry = ctk.CTkEntry(
            self.sheet_new_wrap,
            textvariable=self.output_sheet_title,
            placeholder_text="Nom del nou Google Sheet",
            placeholder_text_color=self._placeholder_color,
            font=self._input_italic_font,
            width=self._compact_form_width,
            height=34,
        )
        self.output_sheet_title_entry.grid(row=0, column=1, padx=(0, 6), pady=(0, 6), sticky="w")
        ctk.CTkLabel(self.sheet_new_wrap, text="Pestanya on es desarà", font=self._eyebrow_font, text_color=self._muted_text_color).grid(
            row=1, column=0, padx=(4, 10), pady=(0, 0), sticky="w"
        )
        self.output_sheet_tab_entry = ctk.CTkEntry(
            self.sheet_new_wrap,
            textvariable=self.output_sheet_tab,
            placeholder_text="Nom de la pestanya de destí",
            placeholder_text_color=self._placeholder_color,
            font=self._input_italic_font,
            width=self._compact_form_width,
            height=34,
        )
        self.output_sheet_tab_entry.grid(row=1, column=1, padx=(0, 6), pady=(0, 0), sticky="w")
        self.sheet_new_wrap.grid_remove()

        self.google_auth_row = ctk.CTkFrame(self.out_card, fg_color="transparent")
        self.google_auth_row.grid(
            row=2,
            column=1,
            padx=self._card_inner_padx,
            pady=(0, 4),
        )
        self.google_auth_row.grid_columnconfigure(0, weight=0)

        self.google_auth_status_label_1 = ctk.CTkLabel(
            self.google_auth_row,
            textvariable=self.google_auth_status,
            font=self._body_font,
            text_color=self._muted_text_color,
            anchor="w",
            justify="left",
        )
        self.google_auth_status_label_1.grid(row=0, column=0, padx=(12, 12), pady=(0, 0))

        # --- Progress + botó + log (tab 1) ---
        progress_wrap = ctk.CTkFrame(self.out_card, fg_color="transparent")
        progress_wrap.grid(
            row=3,
            column=1,
            padx=self._card_inner_padx,
            pady=(6, 8),
        )
        progress_wrap.configure(width=self._panel_content_width)
        progress_wrap.grid_columnconfigure(0, weight=1)
        progress_wrap.grid_columnconfigure(1, weight=0)

        self.progress = ctk.CTkProgressBar(progress_wrap, height=12)
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.progress.configure(progress_color=UPC_BLUE_TAB, fg_color=self._subtle_panel)
        self.progress.set(0)
        self.progress_status = ctk.CTkLabel(progress_wrap, text="0% · Preparat", font=self._body_font)
        self.progress_status.grid(row=0, column=1, sticky="e")

        btns = ctk.CTkFrame(self.out_card, fg_color="transparent")
        btns.grid(row=4, column=1, padx=self._card_inner_padx, pady=(8, 10))

        self.run_btn = ctk.CTkButton(
            btns,
            text="Descarregar FAQs",
            command=self.run_clicked,
            width=self._action_btn_width,
            height=self._action_btn_height,
            font=self._action_btn_font,
        )
        self.run_btn.pack(side="left")

        self.log_toggle_btn = ctk.CTkButton(
            btns,
            text="Veure més detalls",
            width=self._action_btn_width,
            height=self._action_btn_height,
            font=self._action_btn_font,
            command=self._toggle_log_details,
        )
        self.log_toggle_btn.pack(side="left", padx=(10, 0))

        # --- LOG card (gris) ---
        self.log_card = ctk.CTkFrame(
            self.out_card,
            fg_color=self._subtle_panel,
            corner_radius=12,
            border_width=1,
            border_color=self._surface_border,
        )
        self.log_card.grid(row=5, column=1, sticky="ew", padx=8, pady=(0, 4))
        self.log_card.configure(width=self._panel_content_width)
        self.log_card.configure(height=250)
        self.log_card.grid_propagate(False)
        self.log_card.grid_columnconfigure(0, weight=1)
        self.log_card.grid_rowconfigure(0, weight=1)

        self.log = ctk.CTkTextbox(
            self.log_card,
            corner_radius=10,
            fg_color=self._input_bg_color,
            border_width=1,
            border_color=self._surface_border,
            scrollbar_button_color=self._scrollbar_color,
            scrollbar_button_hover_color=self._scrollbar_hover_color,
        )
        self.log.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        # Forcem estat inicial amagat.
        self._log_details_open = True
        self._set_log_details_visible(False)




        # TAB 2: APROVATS -> HTML
        # (variables ja les tens definides en altres llocs? si no, aquí també val)
        self.html_input_mode = ctk.StringVar(value="sheets_oauth")
        self.html_input_csv_path = ctk.StringVar()
        self.html_sheet_title = ctk.StringVar()
        self.html_sheet_tab = ctk.StringVar(value="FAQs")
        self.html_output_path = ctk.StringVar()
        self.html_input_mode.trace_add("write", lambda *_: self._schedule_save_ui_state())
        self.html_input_csv_path.trace_add("write", lambda *_: self._schedule_save_ui_state())
        self.html_sheet_title.trace_add("write", lambda *_: self._schedule_save_ui_state())
        self.html_sheet_tab.trace_add("write", lambda *_: self._schedule_save_ui_state())

        card2 = ctk.CTkFrame(
            html_parent,
            fg_color=self._surface_color,
            corner_radius=18,
            border_width=1,
            border_color=self._surface_border,
        )
        card2.grid_columnconfigure(0, weight=1)
        card2.grid_columnconfigure(1, weight=1)
        card2.grid_columnconfigure(2, weight=1)

        tab2_header = ctk.CTkFrame(html_parent, fg_color="transparent")
        tab2_header.grid(row=0, column=0, sticky="ew", padx=8, pady=(0, 22))
        tab2_header.grid_columnconfigure(0, weight=1)
        tab2_title_card = ctk.CTkFrame(
            tab2_header,
            fg_color=self._surface_color,
            corner_radius=14,
            border_width=1,
            border_color=self._surface_border,
        )
        tab2_title_card.grid(row=0, column=0)
        ctk.CTkLabel(
            tab2_title_card,
            text="Generador de codi font per Genweb",
            image=self.tab_export_title_icon,
            compound="left",
            font=self._page_title_font,
            text_color=self._text_color,
        ).pack(padx=18, pady=(10, 10))

        self._create_folder_section_tag(
            html_parent,
            row=1,
            text="Entrada · Selecciona el fitxer amb les FAQs a convertir (nomes agafara les aprovades)",
            padx=self._section_padx,
        )

        card2.grid(row=2, column=0, sticky="ew", padx=self._section_padx, pady=(0, 18))

        mode_frame2 = ctk.CTkFrame(card2, fg_color="transparent")
        mode_frame2.grid(row=0, column=1, padx=self._card_inner_padx, pady=(self._card_inner_pady, 10))

        self.google_login_btn_2 = ctk.CTkButton(
            mode_frame2,
            text="Iniciar sessió amb Google",
            command=self.google_login_clicked,
            width=230,
            height=46,
            font=self._action_btn_font,
            image=self.google_logo_image,
            fg_color=self._surface_color,
            hover_color=self._subtle_panel,
            text_color=self._text_color,
            border_width=1,
            border_color=self._surface_border,
            corner_radius=10,
        )

        self.google_session_card_2 = ctk.CTkFrame(
            mode_frame2,
            fg_color=self._surface_color,
            corner_radius=10,
            border_width=1,
            border_color=self._surface_border,
        )
        self.google_session_card_2.pack(anchor="center", pady=(10, 0))
        self.google_session_card_2.pack_forget()
        self.google_session_card_2.grid_columnconfigure(0, weight=0)
        self.google_session_card_2.grid_columnconfigure(1, weight=0)

        self.google_session_info_label_2 = ctk.CTkLabel(
            self.google_session_card_2,
            textvariable=self.google_session_summary,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self._text_color,
            anchor="w",
            justify="left",
            image=self.google_logo_image,
            compound="left",
        )
        self.google_session_info_label_2.grid(row=0, column=0, padx=(16, 12), pady=14, sticky="w")
        self.google_logout_btn_2 = ctk.CTkButton(
            self.google_session_card_2,
            text="Tancar sessió",
            command=self.google_logout_clicked,
            width=136,
            height=38,
            font=self._action_btn_font,
            fg_color=self._surface_color,
            hover_color=self._subtle_panel,
            text_color=self._text_color,
            border_width=1,
            border_color=self._surface_border,
            corner_radius=10,
        )
        self.google_logout_btn_2.grid(row=0, column=1, padx=(0, 14), pady=10)
        self.google_login_btn_2.pack(anchor="w", pady=(10, 0))

        self.html_sheets_row = ctk.CTkFrame(card2, fg_color="transparent")
        self.html_sheets_row.grid(row=3, column=1, padx=self._card_inner_padx, pady=(0, 6))
        self.html_sheets_row.grid_columnconfigure(0, weight=0)
        self.html_sheets_row.grid_columnconfigure(1, weight=0)

        self.html_sheet_target_panel = ctk.CTkFrame(
            self.html_sheets_row,
            fg_color=self._subtle_panel,
            corner_radius=14,
            border_width=1,
            border_color=self._surface_border,
        )
        self.html_sheet_target_panel.grid(row=1, column=0, columnspan=2, padx=6, pady=(0, 4))
        self.html_sheet_target_panel.grid_columnconfigure(0, weight=1)

        self.html_sheet_browse_wrap = ctk.CTkFrame(self.html_sheet_target_panel, fg_color="transparent")
        self.html_sheet_browse_wrap.grid(row=0, column=0, padx=12, pady=12, sticky="ew")
        self.html_sheet_browse_wrap.grid_columnconfigure(0, weight=1)
        self.browse_sheets_btn_2 = ctk.CTkButton(
            self.html_sheet_browse_wrap,
            text="Examinar Google Sheets",
            width=220,
            command=self.browse_google_sheets_html_clicked,
        )
        self.browse_sheets_btn_2.grid(row=0, column=0, padx=0, pady=0, sticky="ew")

        self.html_google_auth_row = ctk.CTkFrame(card2, fg_color="transparent")
        self.html_google_auth_row.grid(row=4, column=1, padx=self._card_inner_padx, pady=(0, 4))
        self.html_google_auth_row.grid_columnconfigure(0, weight=0)

        self.google_auth_status_label_2 = ctk.CTkLabel(
            self.html_google_auth_row,
            textvariable=self.google_auth_status,
            text_color=self._muted_text_color,
            anchor="w",
            justify="left",
        )
        self.google_auth_status_label_2.grid(row=0, column=0, padx=(12, 12), pady=(0, 0))

        self._create_folder_section_tag(
            html_parent,
            row=3,
            text="Sortida · Codi font per a Genweb",
            padx=self._section_padx,
        )

        self.output_html_card = ctk.CTkFrame(
            html_parent,
            fg_color=self._surface_color,
            corner_radius=18,
            border_width=1,
            border_color=self._surface_border,
        )
        self.output_html_card.grid(row=4, column=0, sticky="ew", padx=self._section_padx, pady=(0, 4))
        self.output_html_card.grid_columnconfigure(0, weight=1)
        self.output_html_card.grid_columnconfigure(1, weight=1)
        self.output_html_card.grid_columnconfigure(2, weight=1)
        self.output_html_card.grid_rowconfigure(1, weight=0)

        btns2 = ctk.CTkFrame(self.output_html_card, fg_color="transparent")
        btns2.grid(row=0, column=1, padx=self._card_inner_padx, pady=(10, 10))

        ctk.CTkLabel(
            btns2,
            text=(
                "Per enganxar aquest codi a Genweb: si crees una pàgina nova ves a "
                "'Afegeix > Contingut UPC'. Si vols actualitzar-lo després, ves a "
                "'Edita > Codi font'."
            ),
            text_color=self._muted_text_color,
            justify="left",
            wraplength=700,
        ).pack(anchor="center", pady=(0, 6))

        self.show_code_btn = ctk.CTkButton(
            btns2,
            text="Generar codi font",
            command=self.show_source_code_clicked,
            width=self._action_btn_width,
            height=self._action_btn_height,
            font=self._action_btn_font,
        )
        self.show_code_btn.pack(side="left")

        self.copy_code_btn = ctk.CTkButton(
            btns2,
            text="Copiar tot el codi",
            command=self.copy_generated_code,
            width=self._action_btn_width,
            height=self._action_btn_height,
            font=self._action_btn_font,
        )
        self.copy_code_btn.pack(side="left", padx=(10, 0))

        self.code_card = ctk.CTkFrame(
            self.output_html_card,
            fg_color=INFO_PANEL,
            corner_radius=12,
            border_width=1,
            border_color=self._surface_border,
        )
        self.code_card.grid(row=1, column=1, sticky="ew", padx=12, pady=(4, 4))
        self.code_card.configure(width=self._panel_content_width)
        self.code_card.grid_columnconfigure(0, weight=1)
        self.code_card.grid_rowconfigure(0, weight=0)

        self.log2 = ctk.CTkTextbox(
            self.code_card,
            height=170,
            corner_radius=10,
            fg_color=self._input_bg_color,
            border_width=1,
            border_color=self._surface_border,
            scrollbar_button_color=self._scrollbar_color,
            scrollbar_button_hover_color=self._scrollbar_hover_color,
        )
        self.log2.grid(row=0, column=0, sticky="ew", padx=12, pady=12)

        self.scrape_validation_label = ctk.CTkLabel(
            scrape_parent,
            text="",
            text_color="#B91C1C",
            anchor="w",
            justify="left",
            font=ctk.CTkFont(size=12),
        )
        self.scrape_validation_label.grid(row=5, column=0, sticky="ew", padx=8, pady=(0, 2))
        self.scrape_validation_label.grid_remove()

        self.export_validation_label = ctk.CTkLabel(
            html_parent, text="", text_color="#B91C1C", anchor="w"
        )
        self.export_validation_label.grid(row=7, column=0, sticky="ew", padx=8, pady=(0, 4))
        self.export_validation_label.grid_remove()

        # Refresh inicials (important)
        self._refresh_ui()
        self._refresh_html_ui()
        self._setup_live_validation()
        self._apply_white_button_theme()
        self._apply_tab2_visual_style()
        self._show_home()

    def _show_home(self):
        self._is_home_visible = True
        if hasattr(self, "workspace_frame"):
            self.workspace_frame.grid_remove()
        if hasattr(self, "home_frame"):
            self.home_frame.grid()
        self._refresh_home_nav_button_state()

    def _open_section(self, tab_name: str):
        self._is_home_visible = False
        if hasattr(self, "home_frame"):
            self.home_frame.grid_remove()
        for shadow_name in ("home_download_shadow", "home_export_shadow"):
            shadow = getattr(self, shadow_name, None)
            if shadow:
                try:
                    shadow.place_forget()
                except Exception:
                    pass
        if hasattr(self, "workspace_frame"):
            self.workspace_frame.grid()
        if hasattr(self, "tabs"):
            self.tabs.set(tab_name)
            self.current_tab_name = tab_name
            self._fix_tab_text_colors(self.tabs)
        self._refresh_home_nav_button_state()

    def _open_section_download(self):
        self._open_section(self.tab_name_scrape)

    def _open_section_export(self):
        self._open_section(self.tab_name_export)

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

    def _oauth_client_path(self) -> str:
        configured = (self.oauth_client_json.get() or "").strip()
        if configured and os.path.exists(configured):
            return configured
        runtime_dir = runtime_base_dir()
        fallback = first_existing_path(
            os.path.join(runtime_dir, "oauth_client.json"),
            os.path.join(os.getcwd(), "oauth_client.json"),
            self._default_oauth_client_json,
            resource_path("oauth_client.json"),
            os.path.join(runtime_dir, "tests", "oauth_client.json"),
            os.path.join(os.getcwd(), "tests", "oauth_client.json"),
            resource_path("tests/oauth_client.json"),
        )
        return fallback or configured or os.path.join(runtime_dir, "oauth_client.json")

    def _token_file_path(self) -> str:
        return (self.token_file.get() or "").strip() or self._default_token_file

    def _resolve_token_storage_path(self, token_file: str) -> str:
        p = (token_file or "").strip() or self._default_token_file
        if os.path.isabs(p):
            return p
        appdata = os.getenv("APPDATA")
        if appdata:
            base_dir = os.path.join(appdata, "UPCFAQScraper")
        else:
            base_dir = os.path.join(os.path.expanduser("~"), ".upc_faq_scraper")
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, p)

    def _is_google_session_available(self) -> bool:
        token_path = self._resolve_token_storage_path(self._token_file_path())
        return os.path.exists(token_path)

    def _decode_jwt_payload(self, token: str) -> dict:
        parts = (token or "").split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        try:
            raw = base64.urlsafe_b64decode(payload.encode())
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _load_google_profile_data(self):
        token_path = self._resolve_token_storage_path(self._token_file_path())
        if not os.path.exists(token_path):
            self._google_profile_name = ""
            self._google_profile_email = ""
            return "", ""
        try:
            with open(token_path, encoding="utf-8") as f:
                token_data = json.load(f)
        except Exception:
            self._google_profile_name = ""
            self._google_profile_email = ""
            return "", ""

        fallback_name = ""
        fallback_email = ""
        id_token_data = self._decode_jwt_payload((token_data.get("id_token") or "").strip())
        if id_token_data:
            fallback_name = (id_token_data.get("name") or "").strip()
            fallback_email = (
                (id_token_data.get("email") or "").strip()
            )

        name = fallback_name
        email = fallback_email
        self._google_profile_name = name
        self._google_profile_email = email
        return name, email

    def _refresh_home_nav_button_state(self):
        btn = getattr(self, "home_nav_btn", None)
        header_logo = getattr(self, "upc_header_logo_label", None)
        tab_switch_btn = getattr(self, "tab_switch_btn", None)
        header = getattr(self, "header", None)
        if not btn:
            return
        showing_home = bool(getattr(self, "_is_home_visible", False))
        if showing_home:
            if header and header.winfo_manager():
                header.pack_forget()
            btn.grid_remove()
            if header_logo:
                header_logo.grid_remove()
            if tab_switch_btn:
                tab_switch_btn.grid_remove()
        else:
            if header and not header.winfo_manager():
                header.pack(fill="x", before=getattr(self, "body", None))
            btn.grid(row=0, column=0, sticky="w", padx=(20, 10), pady=8)
            btn.configure(
                state="normal",
                fg_color=self._surface_color,
                hover_color=self._subtle_panel,
                text_color=self._text_color,
                border_color=self._surface_border,
            )
            if tab_switch_btn:
                self._refresh_tab_switch_button()
                tab_switch_btn.grid(row=0, column=1, sticky="w", padx=(0, 10), pady=8)
            if header_logo:
                header_logo.grid(row=0, column=2, sticky="e", padx=(10, 18), pady=8)

    def _go_to_other_workspace_tab(self):
        current = getattr(self, "current_tab_name", "")
        if current == getattr(self, "tab_name_scrape", ""):
            self._open_section_export()
        else:
            self._open_section_download()

    def _refresh_tab_switch_button(self):
        btn = getattr(self, "tab_switch_btn", None)
        if not btn:
            return
        current = getattr(self, "current_tab_name", "")
        if current == getattr(self, "tab_name_scrape", ""):
            btn.configure(
                text="Generador de codi Genweb",
                image=self.tab_switch_genweb_icon,
                compound="left",
                width=300,
            )
        else:
            btn.configure(
                text="Descarregar FAQs",
                image=self.tab_switch_download_icon,
                compound="left",
                width=240,
            )

    def _update_google_action_buttons(self):
        session_active = self._is_google_session_available()
        in_progress = self._google_auth_in_progress
        profile_name = ""
        profile_email = ""
        if session_active:
            profile_name, profile_email = self._load_google_profile_data()
        session_summary = profile_email or profile_name or "Sessio de Google activa"
        self.google_session_summary.set(session_summary)
        for btn_name in ("google_login_btn_1", "google_login_btn_2"):
            btn = getattr(self, btn_name, None)
            if not btn:
                continue
            try:
                btn.configure(
                    text="Iniciar sessió amb Google" if not in_progress else "Processant...",
                    command=self.google_login_clicked,
                    image=self.google_logo_image,
                    fg_color=self._surface_color,
                    hover_color=self._subtle_panel,
                    text_color=self._text_color,
                    border_color=self._surface_border,
                )
            except Exception:
                pass
            try:
                if session_active and btn.winfo_manager():
                    btn.pack_forget()
                elif not session_active and not btn.winfo_manager():
                    btn.pack(anchor="w", pady=(10, 0))
            except Exception:
                pass
        for row_name, mode_name, mode_value in (
            ("google_session_card_1", "output_mode", "sheets_oauth"),
            ("google_session_card_2", "html_input_mode", "sheets_oauth"),
        ):
            row = getattr(self, row_name, None)
            mode_var = getattr(self, mode_name, None)
            if not row or not mode_var:
                continue
            visible = (
                session_active
                and not in_progress
                and mode_var.get() == mode_value
            )
            if visible and not row.winfo_manager():
                row.pack(anchor="center", pady=(10, 0))
            elif not visible and row.winfo_manager():
                row.pack_forget()

        for btn_name in ("google_logout_btn_1", "google_logout_btn_2"):
            btn = getattr(self, btn_name, None)
            if not btn:
                continue
            try:
                btn.configure(state="normal" if session_active and not in_progress else "disabled")
            except Exception:
                pass

    def _style_button_white(self, btn):
        try:
            if getattr(btn, "_keep_custom_color", False):
                return
            is_home_card = btn in {
                getattr(self, "home_download_btn", None),
                getattr(self, "home_export_btn", None),
            }
            btn.configure(
                fg_color=self._surface_color,
                hover_color=self._subtle_panel,
                text_color=self._text_color if is_home_card else self._text_color,
                border_width=1,
                border_color=self._surface_border,
            )
        except Exception:
            pass

    def _apply_tab2_visual_style(self):
        styled_entries = (
            getattr(self, "output_file_entry", None),
            getattr(self, "output_sheet_title_entry", None),
            getattr(self, "output_sheet_tab_entry", None),
            getattr(self, "html_csv_entry", None),
            getattr(self, "html_sheet_title_entry", None),
            getattr(self, "html_sheet_tab_entry", None),
        )
        for entry in styled_entries:
            if not entry:
                continue
            try:
                entry.configure(
                    height=38,
                    corner_radius=10,
                    border_width=1,
                    fg_color=self._input_bg_color,
                    border_color=self._surface_border,
                    text_color=self._text_color,
                )
            except Exception:
                pass

        for radio in ("mode_radio_sheets_1", "mode_radio_csv_1", "mode_radio_sheets_2", "mode_radio_csv_2"):
            widget = getattr(self, radio, None)
            if not widget:
                continue
            try:
                widget.configure(
                    text_color=self._text_color,
                    border_color=UPC_BLUE,
                    fg_color=UPC_BLUE,
                    hover_color=UPC_BLUE_TAB,
                )
            except Exception:
                pass

        for login_btn in ("google_login_btn_1", "google_login_btn_2"):
            btn = getattr(self, login_btn, None)
            if not btn:
                continue
            try:
                btn.configure(
                    width=230,
                    height=44,
                    corner_radius=10,
                    border_color=self._surface_border,
                    hover_color=self._subtle_panel,
                )
            except Exception:
                pass

        for secondary_btn in (
            "browse_sheets_btn_1",
            "new_sheets_btn_1",
            "browse_sheets_btn_2",
            "new_sheets_btn_2",
            "log_toggle_btn",
            "copy_code_btn",
        ):
            btn = getattr(self, secondary_btn, None)
            if not btn:
                continue
            try:
                btn.configure(
                    height=self._action_btn_height,
                    corner_radius=10,
                    fg_color=self._surface_color,
                    hover_color=self._subtle_panel,
                    text_color=self._text_color,
                    border_width=1,
                    border_color=self._surface_border,
                )
            except Exception:
                pass

        for primary_btn in ("run_btn", "show_code_btn"):
            btn = getattr(self, primary_btn, None)
            if not btn:
                continue
            try:
                btn.configure(
                    height=self._action_btn_height,
                    corner_radius=10,
                    fg_color=UPC_BLUE,
                    hover_color=UPC_BLUE_TAB,
                    text_color="white",
                    border_width=0,
                )
            except Exception:
                pass

        if hasattr(self, "progress"):
            try:
                self.progress.configure(progress_color=UPC_BLUE_TAB, fg_color=self._subtle_panel)
            except Exception:
                pass

        if hasattr(self, "log2"):
            try:
                self.log2.configure(
                    font=ctk.CTkFont(family="Consolas", size=13),
                    text_color=self._text_color,
                )
            except Exception:
                pass
        if hasattr(self, "log"):
            try:
                self.log.configure(
                    font=ctk.CTkFont(family="Consolas", size=13),
                    text_color=self._text_color,
                )
            except Exception:
                pass

    def _is_widget_descendant(self, widget, root) -> bool:
        current = widget
        while current is not None:
            if current == root:
                return True
            try:
                parent_name = current.winfo_parent()
            except Exception:
                return False
            if not parent_name:
                return False
            try:
                current = current.nametowidget(parent_name)
            except Exception:
                return False
        return False

    def _bind_home_card_shadow(self, button, shadows, hover_root):
        soft_shadow = shadows[0] if len(shadows) > 0 else None
        main_shadow = shadows[1] if len(shadows) > 1 else None

        def _show(_event=None):
            try:
                if soft_shadow:
                    soft_shadow.place(x=3, y=3)
                if main_shadow:
                    main_shadow.place(x=6, y=6)
                button.lift()
            except Exception:
                pass

        def _hide(_event=None):
            try:
                px, py = button.winfo_pointerxy()
                under = button.winfo_containing(px, py)
                if under is None or not self._is_widget_descendant(under, hover_root):
                    if main_shadow:
                        main_shadow.place_forget()
                    if soft_shadow:
                        soft_shadow.place_forget()
            except Exception:
                try:
                    if main_shadow:
                        main_shadow.place_forget()
                    if soft_shadow:
                        soft_shadow.place_forget()
                except Exception:
                    pass

        candidates = [
            button,
            getattr(button, "_canvas", None),
            getattr(button, "_text_label", None),
            getattr(button, "_image_label", None),
            hover_root,
        ]
        for w in candidates:
            if not w:
                continue
            try:
                w.bind("<Enter>", _show, add="+")
                w.bind("<Leave>", _hide, add="+")
            except Exception:
                pass

    def _is_pointer_inside_widget(self, widget) -> bool:
        try:
            px, py = self.winfo_pointerxy()
            wx = widget.winfo_rootx()
            wy = widget.winfo_rooty()
            ww = widget.winfo_width()
            wh = widget.winfo_height()
            return wx <= px <= wx + ww and wy <= py <= wy + wh
        except Exception:
            return False

    def _apply_white_button_theme(self, root=None):
        node = root or self
        try:
            children = node.winfo_children()
        except Exception:
            return
        for child in children:
            if isinstance(child, ctk.CTkButton):
                self._style_button_white(child)
            self._apply_white_button_theme(child)

    def _setup_auto_scrollbar(self, scroll_frame):
        canvas = getattr(scroll_frame, "_parent_canvas", None)
        scrollbar = getattr(scroll_frame, "_scrollbar", None)
        if canvas is None or scrollbar is None:
            return

        def _toggle(_event=None):
            try:
                canvas.update_idletasks()
                first, last = canvas.yview()
                # Si el rang visible cobreix tot el contingut, no cal scrollbar.
                needs_scroll = (last - first) < 0.999
                if needs_scroll:
                    if not scrollbar.winfo_ismapped():
                        scrollbar.grid()
                else:
                    if scrollbar.winfo_ismapped():
                        scrollbar.grid_remove()
            except Exception:
                pass

        try:
            canvas.bind("<Configure>", _toggle, add="+")
            scroll_frame.bind("<Configure>", _toggle, add="+")
        except Exception:
            pass
        self.after(60, _toggle)

    def _set_google_login_buttons_state(self, state: str):
        for btn_name in (
            "google_login_btn_1",
            "google_login_btn_2",
            "google_logout_btn_1",
            "google_logout_btn_2",
        ):
            btn = getattr(self, btn_name, None)
            if btn:
                try:
                    btn.configure(state=state)
                except Exception:
                    pass

    def _update_google_auth_status(self):
        oauth_path = self._oauth_client_path()
        if self._google_auth_in_progress:
            status = "Google Login en curs..."
            color = UPC_BLUE
        elif not os.path.exists(oauth_path):
            status = f"Falta oauth_client.json ({oauth_path})"
            color = DANGER
        elif self._is_google_session_available():
            status = ""
            color = SUCCESS
        else:
            status = "Sense sessió activa. Prem 'Iniciar sessió amb Google'."
            color = STATUS_NEUTRAL

        self.google_auth_status.set(status)
        self._update_google_action_buttons()
        self._sync_google_sheets_rows_visibility()
        show_status = bool(status.strip())
        for row_name in ("google_auth_row", "html_google_auth_row"):
            row = getattr(self, row_name, None)
            if not row:
                continue
            try:
                if show_status:
                    row.grid()
                else:
                    row.grid_remove()
            except Exception:
                pass
        for lbl_name in ("google_auth_status_label_1", "google_auth_status_label_2"):
            lbl = getattr(self, lbl_name, None)
            if lbl:
                try:
                    lbl.configure(text_color=color)
                except Exception:
                    pass

    def google_login_clicked(self):
        if self._google_auth_in_progress:
            return
        if self._is_google_session_available():
            self.google_logout_clicked()
            return

        oauth_path = self._oauth_client_path()
        if not os.path.exists(oauth_path):
            messagebox.showerror("Google Login", f"No s'ha trobat oauth_client.json:\n{oauth_path}")
            self._update_google_auth_status()
            return

        self._google_auth_in_progress = True
        self._set_google_login_buttons_state("disabled")
        self._update_google_auth_status()
        self.println("Google Login: iniciant autenticació...")
        threading.Thread(target=self._google_login_background, daemon=True).start()

    def google_logout_clicked(self):
        if self._google_auth_in_progress:
            return

        token_file = self._token_file_path()
        candidates = [self._resolve_token_storage_path(token_file)]
        if token_file and os.path.isabs(token_file):
            candidates.append(token_file)
        else:
            candidates.append(os.path.abspath(token_file or self._default_token_file))

        removed = 0
        seen = set()
        for path in candidates:
            if not path or path in seen:
                continue
            seen.add(path)
            try:
                if os.path.exists(path):
                    os.remove(path)
                    removed += 1
            except Exception as e:
                messagebox.showerror("Sortir de Google", f"No s'ha pogut eliminar el token:\n{path}\n\n{e}")
                return

        if removed > 0:
            self.println("Sessió de Google tancada. Token eliminat.")
            messagebox.showinfo("Sortir de Google", "Sessió tancada. Pots iniciar amb un altre compte.")
        else:
            self.println("No hi havia cap token actiu per eliminar.")
            messagebox.showinfo("Sortir de Google", "No hi havia cap sessió activa.")

        self._google_profile_name = ""
        self._google_profile_email = ""
        self._update_google_auth_status()
        self._run_live_validation()

    def _google_login_background(self):
        oauth_path = self._oauth_client_path()
        token_file = self._token_file_path()
        try:
            core.get_oauth_client(
                oauth_client_json=oauth_path,
                token_file=token_file,
            )
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "Google Login",
                    "Sessió iniciada correctament. Ja pots treballar amb Google Sheets.",
                ),
            )
            self.after(0, lambda: self.println("Google Login completat."))
        except Exception as e:
            msg = str(e)
            self.after(0, lambda: self.println(f"Google Login error: {msg}"))
            self.after(0, lambda: messagebox.showerror("Google Login", msg))
        finally:
            self._google_auth_in_progress = False
            self.after(0, lambda: self._set_google_login_buttons_state("normal"))
            self.after(0, self._update_google_auth_status)
            self.after(0, self._run_live_validation)

    def _list_google_sheet_files(self):
        oauth_path = self._oauth_client_path()
        token_file = self._token_file_path()
        client = core.get_oauth_client(
            oauth_client_json=oauth_path,
            token_file=token_file,
        )
        files = client.list_spreadsheet_files() or []
        normalized = []
        for it in files:
            name = (it.get("name") or "").strip()
            file_id = (it.get("id") or "").strip()
            modified = (it.get("modifiedTime") or "").strip()
            if not name or not file_id:
                continue
            normalized.append({"name": name, "id": file_id, "modified": modified})
        normalized.sort(key=lambda x: x.get("modified", ""), reverse=True)
        return client, normalized

    def _infer_first_worksheet(self, client, spreadsheet_id: str) -> str:
        try:
            sh = client.open_by_key(spreadsheet_id)
            worksheets = sh.worksheets() or []
            if worksheets:
                def _norm_tab(value: str) -> str:
                    txt = unicodedata.normalize("NFKD", (value or "").strip().lower())
                    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
                    txt = re.sub(r"[^a-z0-9]+", "", txt)
                    return txt

                preferred_names = {"faqs", "faq"}
                for ws in worksheets:
                    title = (ws.title or "").strip()
                    if _norm_tab(title) in preferred_names:
                        return title
                return (worksheets[0].title or "").strip()
        except Exception:
            pass
        return ""

    def _open_google_sheets_picker(self, target: str):
        oauth_path = self._oauth_client_path()
        if not os.path.exists(oauth_path):
            messagebox.showerror("Google Sheets", f"No s'ha trobat oauth_client.json:\n{oauth_path}")
            self._update_google_auth_status()
            return

        try:
            client, files = self._list_google_sheet_files()
        except Exception as e:
            messagebox.showerror("Google Sheets", f"No s'han pogut carregar els Sheets:\n{e}")
            self._update_google_auth_status()
            return

        self._update_google_auth_status()
        if not files:
            messagebox.showinfo("Google Sheets", "No hi ha cap Google Sheet disponible en aquest compte.")
            return

        picker = ctk.CTkToplevel(self)
        picker.title("Examinar Google Sheets")
        picker.geometry("760x520")
        picker.transient(self)
        picker.grab_set()
        picker.grid_columnconfigure(0, weight=1)
        picker.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            picker,
            text="Selecciona un Google Sheet",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=UPC_BLUE,
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 8))

        list_wrap = ctk.CTkScrollableFrame(
            picker,
            fg_color=self._surface_color,
            scrollbar_button_color=self._scrollbar_color,
            scrollbar_button_hover_color=self._scrollbar_hover_color,
        )
        list_wrap.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 10))
        list_wrap.grid_columnconfigure(0, weight=1)

        choice_var = ctk.StringVar(value="")
        by_id = {f["id"]: f for f in files}

        for i, it in enumerate(files):
            subtitle = (it.get("modified") or "").replace("T", " ").replace("Z", "")
            txt = it["name"] if not subtitle else f"{it['name']}  ·  {subtitle}"
            rb = ctk.CTkRadioButton(
                list_wrap,
                text=txt,
                variable=choice_var,
                value=it["id"],
            )
            rb.grid(row=i, column=0, sticky="w", padx=10, pady=5)

        actions = ctk.CTkFrame(picker, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="e", padx=12, pady=(0, 12))

        def _apply_choice():
            picked_id = (choice_var.get() or "").strip()
            if not picked_id or picked_id not in by_id:
                messagebox.showwarning("Google Sheets", "Selecciona un fitxer.")
                return
            picked = by_id[picked_id]
            title = picked["name"]
            tab_name = self._infer_first_worksheet(client, picked_id)

            if target == "scrape":
                self.sheet_target_mode.set("Examinar")
                self._selected_output_sheet_id = picked_id
                self.output_sheet_title.set(title)
                if tab_name:
                    self.output_sheet_tab.set(tab_name)
            else:
                self.html_sheet_target_mode.set("Examinar")
                self._selected_html_sheet_id = picked_id
                self.html_sheet_title.set(title)
                if tab_name:
                    self.html_sheet_tab.set(tab_name)
            self._run_live_validation()
            picker.destroy()

        ctk.CTkButton(actions, text="Cancelar", width=110, command=picker.destroy).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(actions, text="Seleccionar", width=130, command=_apply_choice).pack(side="left")

    def browse_google_sheets_scrape_clicked(self):
        self.sheet_target_mode.set("Examinar")
        self._open_google_sheets_picker(target="scrape")

    def browse_google_sheets_html_clicked(self):
        self.html_sheet_target_mode.set("Examinar")
        self._open_google_sheets_picker(target="html")

    def new_google_sheets_scrape_clicked(self):
        self.sheet_target_mode.set("Nou")
        self._selected_output_sheet_id = ""
        self._apply_selected_recent_sheet()

    def new_google_sheets_html_clicked(self):
        self.html_sheet_target_mode.set("Nou")
        self._selected_html_sheet_id = ""
        self._apply_selected_recent_sheet_html()

    def _sanitize_persisted_text(self, value: str) -> str:
        text = (value or "").strip()
        if not text:
            return ""
        placeholder_values = {
            "escriu aqui el topic",
            "escriu aqui la url",
            "escriu aqui el titol del google sheets",
            "escriu aqui el nom de la pestanya",
        }
        if text.lower() in placeholder_values:
            return ""
        return text

    def _serialize_sources_state(self) -> dict:
        groups = []
        for g in self.topic_groups:
            groups.append(
                {
                    "topic": self._sanitize_persisted_text(g["topic_var"].get()),
                    "selected": bool(g["selected_var"].get()),
                    "expanded": bool(g["expanded_var"].get()),
                    "urls": [
                        {
                            "url": self._sanitize_persisted_text(r["url_var"].get()),
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
                    "topic_subtitle": (it.topic_subtitle or ""),
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
            "recent_google_sheets": list(self.recent_sheets_titles),
            "recent_google_sheets_tabs": dict(self.recent_sheets_tabs),
            "generated_code": self.generated_code_cache or self.log2.get("1.0", "end-1c"),
            "scrape_config": {
                "output_mode": self.output_mode.get(),
                "output_file_path": self._sanitize_persisted_text(self.output_file_path.get()),
                "output_sheet_title": self._sanitize_persisted_text(self.output_sheet_title.get()),
                "output_sheet_tab": self._sanitize_persisted_text(self.output_sheet_tab.get()),
                "output_sheet_id": self._sanitize_persisted_text(getattr(self, "_selected_output_sheet_id", "")),
                "oauth_client_json": (self.oauth_client_json.get() or "").strip(),
                "token_file": (self.token_file.get() or "").strip(),
            },
            "export_config": {
                "html_input_mode": self.html_input_mode.get(),
                "html_input_csv_path": self._sanitize_persisted_text(self.html_input_csv_path.get()),
                "html_sheet_title": self._sanitize_persisted_text(self.html_sheet_title.get()),
                "html_sheet_tab": self._sanitize_persisted_text(self.html_sheet_tab.get()),
                "html_sheet_id": self._sanitize_persisted_text(getattr(self, "_selected_html_sheet_id", "")),
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
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return

        groups = data.get("groups") if isinstance(data, dict) else None
        scraped_items = data.get("scraped_items") if isinstance(data, dict) else None
        review_filter_only_approved = (
            bool(data.get("review_filter_only_approved", False)) if isinstance(data, dict) else False
        )
        generated_code = (data.get("generated_code") or "") if isinstance(data, dict) else ""
        recent_google_sheets = data.get("recent_google_sheets") if isinstance(data, dict) else None
        recent_google_sheets_tabs = (
            data.get("recent_google_sheets_tabs") if isinstance(data, dict) else None
        )
        scrape_config = data.get("scrape_config") if isinstance(data, dict) else None
        export_config = data.get("export_config") if isinstance(data, dict) else None

        self._is_restoring_state = True
        try:
            if isinstance(scrape_config, dict):
                self.output_mode.set("sheets_oauth")
                self.output_file_path.set(self._sanitize_persisted_text(scrape_config.get("output_file_path")))
                self.output_sheet_title.set(self._sanitize_persisted_text(scrape_config.get("output_sheet_title")))
                self.output_sheet_tab.set(
                    self._sanitize_persisted_text(scrape_config.get("output_sheet_tab")) or "FAQs"
                )
                self._selected_output_sheet_id = self._sanitize_persisted_text(scrape_config.get("output_sheet_id"))
                oauth_saved = (scrape_config.get("oauth_client_json") or "").strip()
                token_saved = (scrape_config.get("token_file") or "").strip()
                if oauth_saved and os.path.exists(oauth_saved):
                    self.oauth_client_json.set(oauth_saved)
                else:
                    self.oauth_client_json.set(self._default_oauth_client_json)
                self.token_file.set(token_saved or self._default_token_file)

            if isinstance(export_config, dict):
                self.html_input_mode.set("sheets_oauth")
                self.html_input_csv_path.set(self._sanitize_persisted_text(export_config.get("html_input_csv_path")))
                self.html_sheet_title.set(self._sanitize_persisted_text(export_config.get("html_sheet_title")))
                self.html_sheet_tab.set(
                    self._sanitize_persisted_text(export_config.get("html_sheet_tab")) or "FAQs"
                )
                self._selected_html_sheet_id = self._sanitize_persisted_text(export_config.get("html_sheet_id"))

            if isinstance(recent_google_sheets, list):
                cleaned = []
                for title in recent_google_sheets:
                    t = self._sanitize_persisted_text(title)
                    if t and t not in cleaned:
                        cleaned.append(t)
                self.recent_sheets_titles = cleaned[:8]
            if isinstance(recent_google_sheets_tabs, dict):
                cleaned_tabs: dict[str, str] = {}
                for title, tab in recent_google_sheets_tabs.items():
                    t = self._sanitize_persisted_text(title)
                    tb = self._sanitize_persisted_text(tab)
                    if t and tb:
                        cleaned_tabs[t] = tb
                self.recent_sheets_tabs = cleaned_tabs

            if groups:
                self._clear_all_topic_groups()

                for g in groups:
                    topic_name = self._sanitize_persisted_text(g.get("topic")) if isinstance(g, dict) else ""
                    group = self.add_topic_group(topic_name=topic_name, add_initial_url=False)

                    urls = g.get("urls") if isinstance(g, dict) else None
                    if urls:
                        for u in urls:
                            url_value = self._sanitize_persisted_text(u.get("url")) if isinstance(u, dict) else ""
                            self.add_url_to_topic(group, url_value=url_value)
                            row = group["url_rows"][-1]
                            row["selected_var"].set(bool(u.get("selected", True)) if isinstance(u, dict) else True)
                    else:
                        self.add_url_to_topic(group)

                    group["selected_var"].set(bool(g.get("selected", True)) if isinstance(g, dict) else True)

                    # Ja no exposem UI de col·lapse/expansió dels topics.
                    group["expanded_var"].set(True)

                if not self.topic_groups:
                    self.add_topic_group(topic_name="", add_initial_url=True)

            if scraped_items and isinstance(scraped_items, list):
                items: list[FaqItem] = []
                for it in scraped_items:
                    if not isinstance(it, dict):
                        continue
                    items.append(
                        self._make_faq_item(
                            topic=(it.get("topic") or "").strip(),
                            topic_subtitle=(it.get("topic_subtitle") or "").strip(),
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
            self._update_google_auth_status()
            self._update_source_selection_summary()
            url_count = sum(len(g["url_rows"]) for g in self.topic_groups)
            self._set_restore_summary(len(self.topic_groups), url_count, len(self.scraped_items))
        finally:
            self._is_restoring_state = False

    def _on_close(self):
        self._save_ui_state()
        self.destroy()

    def _show_entry_placeholder_now(self, entry):
        if not entry:
            return
        try:
            if (entry.get() or "").strip():
                return
        except Exception:
            return

        def _activate():
            try:
                if str(entry.cget("state")) != "normal":
                    return
                if hasattr(entry, "_activate_placeholder"):
                    entry._activate_placeholder()
                else:
                    entry.event_generate("<FocusOut>")
            except Exception:
                pass

        self.after(0, _activate)

    def _update_recent_sheets_ui(self):
        return

    def _apply_selected_recent_sheet(self):
        session_active = self._is_google_session_available() and not self._google_auth_in_progress
        browse_state = "normal" if session_active else "disabled"
        entry_state = "normal" if session_active else "disabled"
        show_new_form = self.sheet_target_mode.get() == "Nou"
        try:
            if hasattr(self, "sheet_browse_wrap"):
                browse_managed = str(self.sheet_browse_wrap.winfo_manager()) == "grid"
                if not browse_managed:
                    self.sheet_browse_wrap.grid(row=0, column=0, padx=12, pady=12, sticky="ew")
            if hasattr(self, "sheet_new_wrap"):
                new_managed = str(self.sheet_new_wrap.winfo_manager()) == "grid"
                if show_new_form and not new_managed:
                    self.sheet_new_wrap.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="ew")
                elif not show_new_form and new_managed:
                    self.sheet_new_wrap.grid_remove()
        except Exception:
            pass
        try:
            self.browse_sheets_btn_1.configure(state=browse_state)
        except Exception:
            pass
        try:
            self.new_sheets_btn_1.configure(state=browse_state)
        except Exception:
            pass
        try:
            self.output_sheet_title_entry.configure(state=entry_state)
        except Exception:
            pass
        try:
            self.output_sheet_tab_entry.configure(state=entry_state)
        except Exception:
            pass
        self._show_entry_placeholder_now(getattr(self, "output_sheet_title_entry", None))
        self._show_entry_placeholder_now(getattr(self, "output_sheet_tab_entry", None))
        self._run_live_validation()

    def _apply_selected_recent_sheet_html(self):
        session_active = self._is_google_session_available() and not self._google_auth_in_progress
        browse_state = "normal" if session_active else "disabled"
        try:
            if hasattr(self, "html_sheet_browse_wrap"):
                browse_managed = str(self.html_sheet_browse_wrap.winfo_manager()) == "grid"
                if not browse_managed:
                    self.html_sheet_browse_wrap.grid(row=0, column=0, padx=12, pady=12, sticky="ew")
        except Exception:
            pass
        try:
            self.browse_sheets_btn_2.configure(state=browse_state)
        except Exception:
            pass
        self._run_live_validation()

    def _remember_recent_sheet(self, title: str, tab: str = ""):
        return

    def add_topic_group(self, topic_name: str = "", add_initial_url: bool = True):
        self.topic_seq += 1

        group_frame = ctk.CTkFrame(self.topics_list, fg_color="transparent", corner_radius=8)
        group_frame.pack(fill="x", padx=0, pady=(0, 12))
        # Evita alçades fixes grans dels CTkFrame i ajusta al contingut real.
        group_frame.pack_propagate(True)
        group_frame.grid_propagate(True)
        group_frame.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(group_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=0)
        header.grid_columnconfigure(1, weight=1)

        expanded_var = ctk.BooleanVar(value=True)
        selected_var = ctk.BooleanVar(value=True)
        topic_var = ctk.StringVar(value=topic_name or "")
        selected_var.trace_add("write", lambda *_: self._schedule_save_ui_state())
        topic_var.trace_add("write", lambda *_: self._schedule_save_ui_state())

        topic_controls = ctk.CTkFrame(header, fg_color="transparent")
        topic_controls.grid(row=0, column=0, sticky="nw")
        ctk.CTkLabel(
            topic_controls,
            text="Topic",
            text_color=self._muted_text_color,
            font=self._field_label_font,
        ).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 4))

        topic_entry = ctk.CTkEntry(
            topic_controls,
            textvariable=topic_var,
            width=self._topic_form_width,
            placeholder_text="Escriu aqui el topic",
            font=self._input_italic_font,
            placeholder_text_color=self._placeholder_color,
            height=32,
            fg_color=self._input_bg_color,
            border_width=1,
            border_color=self._surface_border,
            text_color=self._text_color,
        )
        topic_entry.grid(
            row=1, column=0, sticky="w", padx=(0, self._form_row_gap)
        )

        add_topic_btn = ctk.CTkButton(
            topic_controls,
            text="+",
            width=28,
            height=28,
            corner_radius=14,
            fg_color=SUCCESS_BG,
            hover_color=SUCCESS_HOVER,
            text_color=SUCCESS_TEXT,
            border_width=1,
            border_color=SUCCESS_BORDER,
            command=lambda: self.add_topic_group(add_initial_url=True),
        )
        add_topic_btn._keep_custom_color = True
        add_topic_btn.grid(row=1, column=1, padx=(0, self._form_row_gap), sticky="w")

        remove_btn = ctk.CTkButton(
            topic_controls,
            text="X",
            width=28,
            height=28,
            corner_radius=14,
            fg_color=DANGER_BG,
            hover_color=DANGER_HOVER,
            text_color=DANGER_TEXT,
            border_width=1,
            border_color=DANGER_BORDER,
            command=lambda: self.remove_topic_group(group_frame),
        )
        remove_btn._keep_custom_color = True
        remove_btn.grid(row=1, column=2, sticky="w")

        urls_frame = ctk.CTkFrame(header, fg_color="transparent", height=1)
        urls_frame.grid(row=0, column=1, sticky="new", padx=(24, 0))
        urls_frame.grid_propagate(True)
        urls_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            urls_frame,
            text="Web",
            text_color=self._muted_text_color,
            font=self._field_label_font,
        ).pack(anchor="w", pady=(0, 4))

        group = {
            "frame": group_frame,
            "body": header,
            "urls_frame": urls_frame,
            "topic_var": topic_var,
            "selected_var": selected_var,
            "expanded_var": expanded_var,
            "remove_btn": remove_btn,
            "url_rows": [],
        }
        self.topic_groups.append(group)

        if add_initial_url:
            self.add_url_to_topic(group)

        self._update_topic_count(group)
        self._update_source_selection_summary()
        self._refresh_topic_remove_buttons_state()
        self._apply_white_button_theme(group_frame)
        self._schedule_save_ui_state()
        return group

    def toggle_topic_group(self, group):
        if "toggle_btn" not in group:
            group["expanded_var"].set(True)
            return
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
        alive_groups = [g for g in self.topic_groups if g["frame"].winfo_exists()]
        if len(alive_groups) <= 1:
            messagebox.showinfo("Topic requerit", "Cal almenys un topic per afegir URLs.")
            return
        frame.destroy()
        self.topic_groups = [g for g in self.topic_groups if g["frame"] != frame and g["frame"].winfo_exists()]
        self._refresh_topic_remove_buttons_state()
        self._update_source_selection_summary()
        self._schedule_save_ui_state()
        self._run_live_validation()

    def _refresh_topic_remove_buttons_state(self):
        alive_groups = [g for g in self.topic_groups if g["frame"].winfo_exists()]
        disable_remove = len(alive_groups) <= 1
        for g in alive_groups:
            btn = g.get("remove_btn")
            if not btn:
                continue
            try:
                if disable_remove:
                    btn.configure(state="disabled", fg_color=self._subtle_panel, hover_color=self._subtle_panel, text_color=self._placeholder_color)
                else:
                    btn.configure(
                        state="normal",
                        width=28,
                        height=28,
                        corner_radius=14,
                        fg_color=DANGER_BG,
                        hover_color=DANGER_HOVER,
                        text_color=DANGER_TEXT,
                        border_width=1,
                        border_color=DANGER_BORDER,
                    )
            except Exception:
                pass

    def add_url_to_selected_topic(self):
        if not self.topic_groups:
            group = self.add_topic_group(topic_name="", add_initial_url=False)
        else:
            group = next((g for g in self.topic_groups if g["selected_var"].get()), self.topic_groups[0])
        self.add_url_to_topic(group)

    def add_url_to_topic(self, group, url_value: str = ""):
        row_frame = ctk.CTkFrame(group["urls_frame"], fg_color="transparent")
        row_frame.pack(fill="x", pady=(0, self._form_row_gap))
        row_frame.grid_columnconfigure(0, weight=1)

        selected_var = ctk.BooleanVar(value=True)
        url_var = ctk.StringVar(value=url_value)
        selected_var.trace_add("write", lambda *_: self._schedule_save_ui_state())
        url_var.trace_add("write", lambda *_: self._on_url_value_changed())

        entry = ctk.CTkEntry(
            row_frame,
            textvariable=url_var,
            width=self._url_form_width,
            placeholder_text="Escriu aqui la URLs",
            font=self._input_italic_font,
            placeholder_text_color=self._placeholder_color,
            height=32,
            fg_color=self._input_bg_color,
            border_width=1,
            border_color=self._surface_border,
            text_color=self._text_color,
        )
        entry.grid(row=0, column=0, sticky="ew", padx=(0, self._form_row_gap))

        add_url_btn = ctk.CTkButton(
            row_frame,
            text="+",
            width=28,
            height=28,
            corner_radius=14,
            fg_color=SUCCESS_BG,
            hover_color=SUCCESS_HOVER,
            text_color=SUCCESS_TEXT,
            border_width=1,
            border_color=SUCCESS_BORDER,
            command=lambda: self.add_url_to_topic(group),
        )
        add_url_btn._keep_custom_color = True
        add_url_btn.grid(row=0, column=1, padx=(0, self._form_row_gap))

        remove_url_btn = ctk.CTkButton(
            row_frame,
            text="X",
            width=28,
            height=28,
            corner_radius=14,
            fg_color=DANGER_BG,
            hover_color=DANGER_HOVER,
            text_color=DANGER_TEXT,
            border_width=1,
            border_color=DANGER_BORDER,
            command=lambda: self.remove_url_row(group, row_frame),
        )
        remove_url_btn._keep_custom_color = True
        remove_url_btn.grid(row=0, column=2)

        group["url_rows"].append({
            "frame": row_frame,
            "url_var": url_var,
            "selected_var": selected_var,
            "entry": entry,
        })

        self._update_topic_count(group)
        self._update_source_selection_summary()
        self._apply_white_button_theme(row_frame)
        self._schedule_save_ui_state()
        self._run_live_validation()

    def remove_url_row(self, group, frame):
        if len(group["url_rows"]) <= 1:
            messagebox.showinfo("URL requerida", "Cada topic ha de tenir com a mínim una URL.")
            return
        frame.destroy()
        group["url_rows"] = [r for r in group["url_rows"] if r["frame"] != frame]
        self._sync_topic_with_children(group)
        self._update_topic_count(group)
        self._update_source_selection_summary()
        self._schedule_save_ui_state()
        self._run_live_validation()

    def _on_topic_selected_changed(self, group):
        selected = group["selected_var"].get()
        for row in group["url_rows"]:
            row["selected_var"].set(selected)
        self._update_topic_count(group)
        self._update_source_selection_summary()
        self._schedule_save_ui_state()
        self._run_live_validation()

    def _on_url_selected_changed(self, group):
        self._sync_topic_with_children(group)
        self._update_topic_count(group)
        self._update_source_selection_summary()
        self._schedule_save_ui_state()
        self._run_live_validation()

    def _on_url_value_changed(self):
        self._schedule_save_ui_state()
        self._run_live_validation()

    def _sync_topic_with_children(self, group):
        rows = group["url_rows"]
        if not rows:
            return
        any_selected = any(r["selected_var"].get() for r in rows)
        group["selected_var"].set(any_selected)

    def _update_topic_count(self, group):
        total = len(group["url_rows"])
        selected = sum(1 for r in group["url_rows"] if r["selected_var"].get())
        count_label = group.get("count_label")
        if count_label:
            count_label.configure(text=f"{selected}/{total} URLs")

    def _update_source_selection_summary(self):
        for g in self.topic_groups:
            self._update_topic_count(g)
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
        topic_subtitle: str,
        question: str,
        answer: str,
        source: str,
        approved: bool = False,
        forced_id: str = "",
    ) -> FaqItem:
        fid = forced_id or self._make_id(topic, topic_subtitle, question, source)
        approved_var = ctk.BooleanVar(value=approved)
        approved_var.trace_add(
            "write",
            lambda *_: (self._schedule_save_ui_state(), self._run_live_validation()),
        )
        return FaqItem(
            id=fid,
            topic=topic,
            topic_subtitle=topic_subtitle,
            question=question,
            answer=answer,
            source=source,
            approved_var=approved_var,
        )

    def _load_scraped_into_ui(self, flat_items: list[tuple[str, str, str, str, str]]):
        """
        flat_items: [(topic_title, topic_subtitle, question, answer, source), ...]
        Aquesta funció s'executa al fil principal (UI).
        """
        items = [
            self._make_faq_item(
                topic=topic,
                topic_subtitle=topic_subtitle,
                question=question,
                answer=answer,
                source=source,
                approved=False,
            )
            for topic, topic_subtitle, question, answer, source in flat_items
        ]

        self.scraped_items = items
        self.review_filter_only_approved.set(False)
        self._refresh_review_list()
        self._open_section_download()
        self._run_live_validation()
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

    def _toggle_log_details(self):
        self._set_log_details_visible(not getattr(self, "_log_details_open", False))

    def _on_window_configure(self, event):
        if event is not None and event.widget is not self:
            return
        try:
            current_size = (int(event.width), int(event.height)) if event is not None else (
                int(self.winfo_width() or 0),
                int(self.winfo_height() or 0),
            )
        except Exception:
            current_size = None
        if current_size and current_size == self._last_configured_size:
            return
        self._last_configured_size = current_size
        self._refresh_centered_content_areas()
        self._refresh_responsive_form_widths()
        return

    def _ensure_visible_section_state(self):
        if getattr(self, "_restoring_visible_section", False):
            return

        self._restoring_visible_section = True
        try:
            showing_home = bool(getattr(self, "_is_home_visible", False))

            if showing_home:
                if hasattr(self, "workspace_frame") and self.workspace_frame.winfo_manager():
                    self.workspace_frame.grid_remove()
                if hasattr(self, "home_frame") and not self.home_frame.winfo_manager():
                    self.home_frame.grid()
                self._refresh_home_nav_button_state()
                return

            if hasattr(self, "home_frame") and self.home_frame.winfo_manager():
                self.home_frame.grid_remove()
            if hasattr(self, "workspace_frame") and not self.workspace_frame.winfo_manager():
                self.workspace_frame.grid()

            desired_tab = getattr(self, "current_tab_name", "") or getattr(self, "tab_name_scrape", "")
            tabs = getattr(self, "tabs", None)
            if tabs and desired_tab:
                try:
                    current_tab = tabs.get()
                except Exception:
                    current_tab = ""
                if current_tab != desired_tab:
                    tabs.set(desired_tab)
                self._fix_tab_text_colors(tabs)
            self._refresh_home_nav_button_state()
        finally:
            self._restoring_visible_section = False

    def _set_log_details_visible(self, visible: bool):
        if bool(visible) == bool(getattr(self, "_log_details_open", False)):
            return
        self._details_transition = True
        try:
            if visible:
                self._log_details_open = True
                self.log_card.grid()
                self.log_toggle_btn.configure(text="Amagar detalls")
                self._apply_details_window_size(True)
            else:
                self.log_card.grid_remove()
                self.log_toggle_btn.configure(text="Veure més detalls")
                self._apply_details_window_size(False)
                self._log_details_open = False
        finally:
            self._details_transition = False

    def _apply_details_window_size(self, details_open: bool):
        self.update_idletasks()
        base_w = max(self._base_min_w, int(self._collapsed_width))
        collapsed_h = max(self._base_min_h, int(self._collapsed_height_fixed))
        expanded_h = max(collapsed_h + 1, int(self._expanded_height_fixed))

        if details_open:
            self.minsize(self._base_min_w, expanded_h)
            self.geometry(f"{base_w}x{expanded_h}")
        else:
            self.minsize(self._base_min_w, self._base_min_h)
            self.geometry(f"{base_w}x{collapsed_h}")

    def _show_generated_code(self, code: str):
        self.generated_code_cache = code or ""
        code = self._format_code_for_preview(code)
        self.log2.delete("1.0", "end")
        self.log2.insert("1.0", code)
        self.log2.see("1.0")
        self._schedule_save_ui_state()

    def _prepend_html_diagnostics_comment(self, html_text: str, diagnostics: dict | None) -> str:
        if not diagnostics:
            return html_text or ""

        headers = diagnostics.get("headers") or []
        subtopics = diagnostics.get("subtopics_preview") or []
        topics = diagnostics.get("topics_preview") or []
        empty_subtopics = diagnostics.get("empty_subtopics", 0)

        lines = ["DIAGNOSTIC HTML"]
        if headers:
            lines.append("Headers: " + ", ".join(str(h) for h in headers))
        if subtopics:
            lines.append("Subtopics detectats: " + ", ".join(str(s) for s in subtopics))
        else:
            lines.append("Subtopics detectats: cap")
        lines.append(f"Files aprovades amb Subtopic buit: {empty_subtopics}")
        if topics:
            lines.append("Temes detectats: " + ", ".join(str(t) for t in topics))

        comment = "<!--\n" + "\n".join(lines) + "\n-->\n"
        return comment + (html_text or "")

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

    def _setup_live_validation(self):
        watched_vars = [
            self.output_mode,
            self.output_file_path,
            self.output_sheet_title,
            self.output_sheet_tab,
            self.oauth_client_json,
            self.html_input_mode,
            self.html_input_csv_path,
            self.html_sheet_title,
            self.html_sheet_tab,
        ]
        for var in watched_vars:
            var.trace_add("write", lambda *_: self._run_live_validation())
        self._run_live_validation()

    def _is_valid_url(self, value: str) -> bool:
        text = (value or "").strip()
        if not text:
            return False
        parsed = urlparse(text)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _set_entry_valid(self, entry, is_valid: bool, *, neutral_when_empty: bool = False, value: str = ""):
        if not entry:
            return
        color = self._surface_border
        try:
            entry.configure(border_color=color)
        except Exception:
            pass

    def _run_live_validation(self):
        self._validate_scrape_form(live_only=True)
        if hasattr(self, "html_input_mode"):
            self._validate_export_form(live_only=True)

    def _validate_scrape_form(self, live_only: bool = False):
        valid_sources = len(self.get_sources_from_ui())
        for group in self.topic_groups:
            for row in group["url_rows"]:
                url = row["url_var"].get()
                selected = row["selected_var"].get()
                is_valid = self._is_valid_url(url)
                self._set_entry_valid(
                    row.get("entry"),
                    is_valid=not selected or is_valid,
                    neutral_when_empty=True,
                    value=url,
                )

        mode = self.output_mode.get()
        msg = ""
        if valid_sources == 0:
            msg = "Cal almenys una URL."
        elif mode == "csv":
            out = self.output_file_path.get().strip()
            ok = bool(out and out.lower().endswith(".csv"))
            self._set_entry_valid(getattr(self, "output_file_entry", None), is_valid=ok, neutral_when_empty=True, value=out)
            if not ok:
                msg = "El fitxer de sortida ha d'acabar en .csv."
        elif mode == "sheets_oauth":
            title = self.output_sheet_title.get().strip()
            tab = self.output_sheet_tab.get().strip()
            oauth = self._oauth_client_path()
            self._set_entry_valid(
                getattr(self, "output_sheet_title_entry", None),
                is_valid=bool(title),
                neutral_when_empty=True,
                value=title,
            )
            self._set_entry_valid(
                getattr(self, "output_sheet_tab_entry", None),
                is_valid=bool(tab),
                neutral_when_empty=True,
                value=tab,
            )
            if not title or not tab:
                msg = "Completa títol i pestanya del Google Sheet."
            elif not os.path.exists(oauth):
                msg = f"Falta oauth_client.json al projecte: {oauth}"

        if hasattr(self, "scrape_validation_label"):
            self.scrape_validation_label.configure(text="")
            self.scrape_validation_label.grid_remove()
        if not live_only:
            return msg == ""
        return True

    def _validate_export_form(self, live_only: bool = False):
        mode = self.html_input_mode.get()
        msg = ""
        if mode == "csv":
            path = self.html_input_csv_path.get().strip()
            ok = bool(path and os.path.exists(path))
            self._set_entry_valid(getattr(self, "html_csv_entry", None), is_valid=ok, neutral_when_empty=True, value=path)
            if not ok:
                msg = "Selecciona un CSV vàlid per exportar."
        elif mode == "sheets_oauth":
            title = self.html_sheet_title.get().strip()
            tab = self.html_sheet_tab.get().strip()
            oauth = self._oauth_client_path()
            self._set_entry_valid(
                getattr(self, "html_sheet_title_entry", None),
                is_valid=bool(title),
                neutral_when_empty=True,
                value=title,
            )
            self._set_entry_valid(
                getattr(self, "html_sheet_tab_entry", None),
                is_valid=bool(tab),
                neutral_when_empty=True,
                value=tab,
            )
            if not title or not tab:
                msg = "Completa títol i pestanya del Google Sheet."
            elif not os.path.exists(oauth):
                msg = f"Falta oauth_client.json al projecte: {oauth}"

        if hasattr(self, "export_validation_label"):
            self.export_validation_label.configure(text="")
            self.export_validation_label.grid_remove()
        if not live_only:
            return msg == ""
        return True

    def _on_tab_changed(self):
        selected = self.tabs.get()
        self.current_tab_name = selected
        self._fix_tab_text_colors(self.tabs)
        self._refresh_tab_switch_button()

    def _focus_review_search(self, _event=None):
        if hasattr(self, "review_search_entry"):
            self._open_section_download()
            self.review_search_entry.focus_set()
            self.review_search_entry.select_range(0, "end")
        return "break"

    def _set_progress(self, done: int, total: int):
        if not hasattr(self, "progress"):
            return
        total_safe = max(1, int(total or 1))
        done_safe = max(0, min(int(done or 0), total_safe))
        scraping_ratio = done_safe / total_safe
        ratio = scraping_ratio * 0.9
        pct = int(round(ratio * 100))
        elapsed = max(0.0, time.time() - (self._run_started_at or time.time()))
        eta = int((elapsed / done_safe) * (total_safe - done_safe)) if done_safe else 0
        self.after(0, lambda: self.progress.set(ratio))
        self.after(
            0,
            lambda: self.progress_status.configure(
                text=(
                    f"{pct}% · URL {done_safe}/{total_safe} · ETA {eta}s"
                    if done_safe < total_safe
                    else "90% · Exportant resultats..."
                )
            ),
        )

    def _set_progress_complete(self):
        if not hasattr(self, "progress"):
            return
        self.progress.set(1)
        self.progress_status.configure(text="100% · Completat")

    def _set_restore_summary(self, groups_count: int, url_count: int, faq_count: int):
        self.println(
            f"Estat restaurat: {groups_count} temes, {url_count} URLs i {faq_count} FAQs."
        )

    # ====UI state / refresh
    def _sync_google_sheets_rows_visibility(self):
        session_active = self._is_google_session_available() and not self._google_auth_in_progress

        if hasattr(self, "out_sheets_row") and hasattr(self, "output_mode"):
            if self.output_mode.get() == "sheets_oauth":
                self.out_sheets_row.grid()
            else:
                self.out_sheets_row.grid_remove()

        if hasattr(self, "html_sheets_row") and hasattr(self, "html_input_mode"):
            if self.html_input_mode.get() == "sheets_oauth" and session_active:
                self.html_sheets_row.grid()
            else:
                self.html_sheets_row.grid_remove()

        self._apply_selected_recent_sheet()
        self._apply_selected_recent_sheet_html()

    # REFRESH D'ESTAT UI
    def _refresh_ui(self):
        if self.output_mode.get() != "sheets_oauth":
            self.output_mode.set("sheets_oauth")
            return
        self.google_auth_row.grid()
        if hasattr(self, "google_login_btn_1") and not self.google_login_btn_1.winfo_manager():
            self.google_login_btn_1.pack(anchor="w", pady=(10, 0))
        self._update_google_auth_status()
        self._sync_google_sheets_rows_visibility()
        self._run_live_validation()

    def _refresh_html_ui(self):
        if self.html_input_mode.get() != "sheets_oauth":
            self.html_input_mode.set("sheets_oauth")
            return
        self.html_google_auth_row.grid()
        if hasattr(self, "google_login_btn_2") and not self.google_login_btn_2.winfo_manager():
            self.google_login_btn_2.pack(anchor="w", pady=(10, 0))
        self.log2.delete("1.0", "end")
        self._update_google_auth_status()
        self._sync_google_sheets_rows_visibility()
        self._run_live_validation()
    def _needs_oauth(self) -> bool:
        return self.output_mode.get() == "sheets_oauth"

    # ====Validations
    # VALIDACIONS
    def validate_inputs(self):

        # INPUT (UI rows)
        sources = self.get_sources_from_ui()
        if not sources:
            return False, "Cal almenys una URL."

        # OUTPUT
        mode = self.output_mode.get()

        if mode == "csv":
            out = self.output_file_path.get().strip()
            if not out:
                return False, "Selecciona un fitxer de sortida."
            if not out.lower().endswith(".csv"):
                return False, "En mode CSV, el fitxer de sortida ha d'acabar en .csv"
        else:  # sheets_oauth
            if not self._is_google_session_available():
                return False, "Inicia sessió amb Google abans de triar el Sheet."
            if not self.output_sheet_title.get().strip():
                return False, "Omple el títol del Google Sheet."
            if not self.output_sheet_tab.get().strip():
                return False, "Omple el nom de la pestanya."
            oauth_file = self._oauth_client_path()
            if not os.path.exists(oauth_file):
                return False, f"Falta el fitxer OAuth: {oauth_file}"

        return True, ""

    def validate_html_inputs(self):
        mode = self.html_input_mode.get()

        if mode == "csv":
            path = self.html_input_csv_path.get().strip()
            if not path:
                return False, "Selecciona el CSV d'entrada."
            if not os.path.exists(path):
                return False, "El CSV d'entrada no existeix."
            return True, ""

        if mode == "sheets_oauth":
            if not self._is_google_session_available():
                return False, "Inicia sessió amb Google abans de triar el Sheet."
            if not self.html_sheet_title.get().strip():
                return False, "Omple el títol del Google Sheet."
            if not self.html_sheet_tab.get().strip():
                return False, "Omple el nom de la pestanya."
            oauth_file = self._oauth_client_path()
            if not os.path.exists(oauth_file):
                return False, f"Falta el fitxer OAuth: {oauth_file}"
            return True, ""

        return False, "Mode d'entrada desconegut."

    # ====Actions
    # ACCIONS (BOTO EXECUTA / GENERA)
    def run_clicked(self):
        ok, err = self.validate_inputs()
        if not ok:
            messagebox.showerror("Error", err)
            return

        # UI state
        self._run_started_at = time.time()
        self.run_btn.configure(state="disabled")
        self.progress.configure(mode="determinate")
        self.progress.set(0)
        self.progress_status.configure(text="0% · Iniciant...")

        self.println("\n> Executant...")

        t = threading.Thread(target=self._run_background, daemon=True)
        t.start()

    def generate_html_clicked(self):
        ok, err = self.validate_html_inputs()
        if not ok:
            messagebox.showerror("Error", err)
            return

        self._set_export_buttons_enabled(False)
        self.ui_log2(f"\n> Executant ({self.html_input_mode.get()})...")

        t = threading.Thread(target=self._generate_html_background, daemon=True)
        t.start()

    def show_source_code_clicked(self):
        ok, err = self.validate_html_inputs()
        if not ok:
            messagebox.showerror("Error", err)
            return

        self._set_export_buttons_enabled(False)
        self.ui_log2(f"\n> Generant codi font ({self.html_input_mode.get()})...")

        t = threading.Thread(target=self._show_source_code_background, daemon=True)
        t.start()

    def _set_export_buttons_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        try:
            self.show_code_btn.configure(state=state)
        except Exception:
            pass

    def _reset_ui(self):
        self.progress.configure(mode="determinate")
        self.progress.set(0)
        self.progress_status.configure(text="0% · Preparat")
        self.run_btn.configure(state="normal")

    # ====Background workers (threads)
    # TREBALL EN SEGON PLA (THREADS)
    def _run_background(self):
        start_time = time.time()
        try:
            output_mode = self.output_mode.get()
            sources = self.get_sources_from_ui()

            def progress_cb(done: int, total: int, _url: str):
                self._set_progress(done, total)

            stats = core.run_pipeline(
                input_mode="ui",
                output_mode=output_mode,
                sources=sources,
                output_sheet_title=self.output_sheet_title.get().strip()
                if output_mode == "sheets_oauth" else None,
                output_sheet_tab=self.output_sheet_tab.get().strip()
                if output_mode == "sheets_oauth" else None,
                output_sheet_id=(self._selected_output_sheet_id or "").strip()
                if output_mode == "sheets_oauth" and self.sheet_target_mode.get() == "Examinar" else None,
                create_output_sheet_if_missing=(
                    output_mode == "sheets_oauth" and self.sheet_target_mode.get() == "Nou"
                ),
                output_file_path=self.output_file_path.get().strip()
                if output_mode == "csv" else None,
                oauth_client_json=self._oauth_client_path(),
                token_file=self._token_file_path(),
                log=self.ui_log,
                debug=False,
                progress_cb=progress_cb,
            )
            errors = stats.get("errors", [])
            if output_mode == "sheets_oauth":
                self.after(
                    0,
                    lambda: self._remember_recent_sheet(
                        self.output_sheet_title.get().strip(),
                        self.output_sheet_tab.get().strip(),
                    ),
                )

            failed_sources = [
                ((e.get("url") or "").strip(), (e.get("topic") or "").strip())
                for e in (errors or [])
                if (e.get("url") or "").strip()
            ]

            elapsed = round(time.time() - start_time, 2)

            summary_lines = [
                "\n" + "-" * 52,
                "PROCESSAMENT FINALITZAT",
                "-" * 52,
                f"URLs processades: {stats.get('total_urls', 0)}",
                f"FAQs trobades: {stats.get('total_faqs', 0)}",
                f"Files generades: {stats.get('total_rows', 0)}",
            ]
            if stats.get("subtopic_errors"):
                summary_lines.append(f"Control subtopics: {stats.get('subtopic_errors')} incidència(es)")

            if stats.get("total_errors"):
                summary_lines.append(f"Errors: {stats.get('total_errors')}")
                for failed_url, _topic in failed_sources[:5]:
                    summary_lines.append(f"- {failed_url}")

            summary_lines.append(f"Temps total: {elapsed} s")
            summary_lines.append("-" * 52)

            self.after(0, self._set_progress_complete)
            self.after(0, lambda: self.println("\n".join(summary_lines)))

        except Exception as e:
            error_msg = str(e)
            self.after(0, lambda: self.println(f"Error: {error_msg}"))
            self.after(0, lambda: self._set_log_details_visible(True))
            self.after(0, lambda: messagebox.showerror("Error", error_msg))
        finally:
            self.after(600, self._reset_ui)

    def _generate_html_background(self):
        try:
            mode = self.html_input_mode.get()

            if mode == "sheets_oauth" and self.html_sheet_target_mode.get() == "Nou":
                approved_rows = self._get_approved_rows()
                if approved_rows:
                    sheet_rows = self._approved_rows_to_sheets_rows(approved_rows)
                    self.ui_log2(
                        f"FAQs aprovades detectades: {len(approved_rows)}. Exportant a Google Sheets..."
                    )
                    core.export_rows_to_google_sheets_oauth(
                        rows=sheet_rows,
                        spreadsheet_title=self.html_sheet_title.get().strip(),
                        worksheet_name=self.html_sheet_tab.get().strip(),
                        spreadsheet_id=(self._selected_html_sheet_id or "").strip() or None,
                        oauth_client_json=self._oauth_client_path(),
                        token_file=self._token_file_path(),
                        log=self.ui_log2,
                    )
                    self.ui_log2(
                        "Procés completat. FAQs aprovades exportades al Google Sheets."
                    )
                    self.after(
                        0,
                        lambda: self._remember_recent_sheet(
                            self.html_sheet_title.get().strip(),
                            self.html_sheet_tab.get().strip(),
                        ),
                    )
                    return

            if mode == "sheets_oauth" and self.html_sheet_target_mode.get() == "Examinar":
                self.ui_log2(
                    f"Llegint FAQs directament de Google Sheets: {self.html_sheet_title.get().strip()} / {self.html_sheet_tab.get().strip()}"
                )

            # --- MODE CSV / SHEETS (com abans) ---
            core.run_approved_to_html_pipeline(
                input_mode=mode,
                input_csv_path=self.html_input_csv_path.get().strip() if mode == "csv" else None,
                sheet_title=self.html_sheet_title.get().strip() if mode == "sheets_oauth" else None,
                sheet_tab=self.html_sheet_tab.get().strip() if mode == "sheets_oauth" else None,
                sheet_id=(self._selected_html_sheet_id or "").strip() if mode == "sheets_oauth" else None,
                oauth_client_json=self._oauth_client_path(),
                token_file=self._token_file_path(),
                log=self.ui_log2,
            )

            self.ui_log2(
                "Procés completat. En aquest mode no es mostra el codi font a la UI."
            )
            if mode == "sheets_oauth":
                self.after(
                    0,
                    lambda: self._remember_recent_sheet(
                        self.html_sheet_title.get().strip(),
                        self.html_sheet_tab.get().strip(),
                    ),
                )

        except Exception as e:
            msg = str(e)
            self.ui_log2(f"Error: {msg}")
            self.after(0, lambda: messagebox.showerror("Error", msg))
        finally:
            self.after(0, lambda: self._set_export_buttons_enabled(True))

    def _show_source_code_background(self):
        try:
            mode = self.html_input_mode.get()

            result = core.run_approved_to_html_pipeline(
                input_mode=mode,
                input_csv_path=self.html_input_csv_path.get().strip() if mode == "csv" else None,
                sheet_title=self.html_sheet_title.get().strip() if mode == "sheets_oauth" else None,
                sheet_tab=self.html_sheet_tab.get().strip() if mode == "sheets_oauth" else None,
                sheet_id=(self._selected_html_sheet_id or "").strip() if mode == "sheets_oauth" else None,
                oauth_client_json=self._oauth_client_path(),
                token_file=self._token_file_path(),
                log=self.ui_log2,
            )
            html_text = result.get("html_text", "") if isinstance(result, dict) else ""
            diagnostics = result.get("diagnostics") if isinstance(result, dict) else None
            html_text = self._prepend_html_diagnostics_comment(html_text, diagnostics)
            self.after(0, lambda: self._show_generated_code(html_text))
            if mode == "sheets_oauth":
                self.after(
                    0,
                    lambda: self._remember_recent_sheet(
                        self.html_sheet_title.get().strip(),
                        self.html_sheet_tab.get().strip(),
                    ),
                )

        except Exception as e:
            msg = str(e)
            self.ui_log2(f"Error: {msg}")
            self.after(0, lambda: messagebox.showerror("Error", msg))
        finally:
            self.after(0, lambda: self._set_export_buttons_enabled(True))

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
        parent.configure(fg_color=BG)
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)
        self.review_search_var = ctk.StringVar(value="")
        self.review_filter_only_pending = ctk.BooleanVar(value=False)
        self.review_filter_topic = ctk.StringVar(value="Tots")
        self.review_search_var.trace_add("write", lambda *_: self._refresh_review_list())
        self.review_filter_only_pending.trace_add("write", lambda *_: self._refresh_review_list())
        self.review_filter_topic.trace_add("write", lambda *_: self._refresh_review_list())

        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        top.grid_columnconfigure(5, weight=1)

        ctk.CTkButton(top, text="Aprovar totes", command=self._approve_all).pack(side="left")
        ctk.CTkButton(top, text="Desmarcar totes", command=self._unapprove_all).pack(side="left", padx=(8, 0))

        ctk.CTkCheckBox(
            top,
            text="Mostrar només aprovades",
            variable=self.review_filter_only_approved,
            command=self._refresh_review_list,
        ).pack(side="left", padx=(12, 0))
        ctk.CTkCheckBox(
            top,
            text="Mostrar només pendents",
            variable=self.review_filter_only_pending,
            command=self._refresh_review_list,
        ).pack(side="left", padx=(12, 0))

        self.review_topic_menu = ctk.CTkOptionMenu(
            top,
            variable=self.review_filter_topic,
            values=["Tots"],
            width=180,
        )
        self.review_topic_menu.pack(side="right", padx=(8, 0))
        self.review_search_entry = ctk.CTkEntry(
            top,
            textvariable=self.review_search_var,
            placeholder_text="Cerca pregunta, resposta o URL (Ctrl+F)",
            width=320,
        )
        self.review_search_entry.pack(side="right", padx=(8, 0))

        self.review_list = ctk.CTkScrollableFrame(
            parent,
            fg_color=LIGHT_PANEL,
            scrollbar_button_color=self._scrollbar_color,
            scrollbar_button_hover_color=self._scrollbar_hover_color,
        )
        self.review_list.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._setup_auto_scrollbar(self.review_list)

        self._refresh_review_list()

    def _refresh_review_list(self):
        if not hasattr(self, "review_list"):
            return

        for w in self.review_list.winfo_children():
            w.destroy()

        if not self.scraped_items:
            ctk.CTkLabel(self.review_list, text="Encara no hi ha FAQs. Fes scraping a la seccio Descarrega.").pack(pady=10)
            return

        only_approved = self.review_filter_only_approved.get()
        only_pending = self.review_filter_only_pending.get()
        selected_topic = (self.review_filter_topic.get() or "Tots").strip()
        query = (self.review_search_var.get() or "").strip().lower()

        topics = sorted({(it.topic or "").strip() for it in self.scraped_items if (it.topic or "").strip()})
        menu_values = ["Tots"] + topics
        if hasattr(self, "review_topic_menu"):
            self.review_topic_menu.configure(values=menu_values)
            if selected_topic not in menu_values:
                self.review_filter_topic.set("Tots")
                selected_topic = "Tots"

        filtered_items: list[FaqItem] = []
        for item in self.scraped_items:
            if only_approved and not item.approved_var.get():
                continue
            if only_pending and item.approved_var.get():
                continue
            if selected_topic != "Tots" and item.topic != selected_topic:
                continue
            if query:
                blob = " ".join([item.question or "", item.answer or "", item.source or ""]).lower()
                if query not in blob:
                    continue
            filtered_items.append(item)

        shown = 0
        total_filtered = len(filtered_items)
        for idx, item in enumerate(filtered_items):
            try:
                self._add_review_row(self.review_list, item)
                shown += 1
            except Exception:
                # Fallback perquè un ítem mal format no trenqui tota la llista.
                row = ctk.CTkFrame(self.review_list, fg_color="transparent")
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
                shown += 1
            if idx < total_filtered - 1:
                self._add_review_separator(self.review_list)
        if shown == 0:
            ctk.CTkLabel(
                self.review_list,
                text="No hi ha resultats amb els filtres actuals.",
                text_color=self._placeholder_color,
            ).pack(pady=10)
        self._run_live_validation()

    def _add_review_separator(self, parent):
        sep_wrap = ctk.CTkFrame(parent, fg_color="transparent")
        sep_wrap.pack(fill="x", padx=8, pady=(4, 8))
        # Línia minimalista però visible sobre el fons gris de la llista.
        sep = ctk.CTkFrame(sep_wrap, fg_color=self._surface_border, height=2, corner_radius=1)
        sep.pack(fill="x", padx=(58, 12))

    def _add_review_row(self, parent, item: FaqItem):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=6, padx=6)

        cb = ctk.CTkCheckBox(row, text="", variable=item.approved_var)
        cb.grid(row=0, column=0, padx=(8, 8), pady=8, sticky="n")

        # Columna 2: Pregunta
        q = ctk.CTkLabel(
            row,
            text=item.question,
            anchor="w",
            justify="left",
            wraplength=340,
        )
        q.grid(row=0, column=1, sticky="nw", padx=(0, 12), pady=8)

        # Columna 3: Resposta (enllaços clicables i negreta)
        a = ctk.CTkTextbox(row, height=96, wrap="word")
        a.grid(row=0, column=2, sticky="nsew", padx=(0, 12), pady=8)
        question_font = q.cget("font")
        a.configure(
            fg_color="transparent",
            text_color="#4B5563",
            border_width=0,
            font=question_font,
        )
        self._render_html_to_textbox(a, item.answer, item.question)

        # Columna 4: Topic
        topic_frame = ctk.CTkFrame(row, fg_color="transparent", width=220)
        topic_frame.grid(row=0, column=3, padx=(0, 12), pady=8, sticky="ne")

        topic_title = ctk.CTkLabel(
            topic_frame,
            text=item.topic,
            anchor="w",
            justify="left",
            wraplength=220,
            text_color="#374151",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        topic_title.pack(fill="x")

        if (item.topic_subtitle or "").strip():
            topic_subtitle = ctk.CTkLabel(
                topic_frame,
                text=item.topic_subtitle,
                anchor="w",
                justify="left",
                wraplength=220,
                text_color=self._placeholder_color,
                font=ctk.CTkFont(size=11),
            )
            topic_subtitle.pack(fill="x", pady=(2, 0))

        row.grid_columnconfigure(2, weight=1)
        row.grid_columnconfigure(3, weight=0)

    def _render_html_to_textbox(self, textbox: ctk.CTkTextbox, html_text: str, question_text: str = ""):
        text = (html_text or "").strip()
        tk_text = getattr(textbox, "_textbox", textbox)
        textbox.configure(state="normal")
        textbox.delete("1.0", "end")

        if not text:
            textbox.configure(state="disabled")
            return

        if "<" not in text or ">" not in text:
            plain = text.strip()
            q = (question_text or "").strip()
            if q and plain.lower().startswith(q.lower()):
                plain = plain[len(q):].lstrip(" :-\n\t")
            textbox.insert("1.0", plain)
            textbox.configure(state="disabled")
            return

        soup = BeautifulSoup(text, "html.parser")
        link_count = 0
        first_meaningful_seen = False
        normalized_question = re.sub(r"\s+", " ", (question_text or "").strip()).lower()

        # Manté exactament la mateixa font/mida de la pregunta.
        try:
            base_font = tkfont.nametofont(tk_text.cget("font"))
            bold_font = base_font.copy()
            bold_font.configure(weight="bold")
            textbox._bold_font = bold_font
            tk_text.tag_configure("bold", font=bold_font)
        except Exception:
            tk_text.tag_configure("bold", font=ctk.CTkFont(size=13, weight="bold"))

        def _insert(t: str, tags=()):
            if t:
                textbox.insert("end", t, tags)

        def _insert_newline(tags=()):
            if textbox.compare("end-1c", ">", "1.0"):
                last = textbox.get("end-2c", "end-1c")
                if last == "\n":
                    return
            _insert("\n", tags)

        def _walk(node, active_tags=()):
            nonlocal link_count, first_meaningful_seen

            if isinstance(node, NavigableString):
                raw = str(node)
                if not raw or not raw.strip():
                    return
                normalized = re.sub(r"\s+", " ", raw).strip()
                if not normalized:
                    return

                _insert(normalized, active_tags)
                return

            name = getattr(node, "name", None)
            if not name:
                return
            name = name.lower()

            # Si el primer bloc visible és exactament la pregunta, el saltem complet.
            if not first_meaningful_seen and normalized_question and name in {"p", "div", "span", "strong", "b"}:
                node_text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip().lower()
                if node_text == normalized_question:
                    first_meaningful_seen = True
                    return

            next_tags = list(active_tags)
            if name in {"b", "strong"}:
                next_tags.append("bold")

            if name == "a":
                href = (node.get("href") or "").strip()
                if href:
                    tag_name = f"link_{link_count}"
                    link_count += 1
                    tk_text.tag_configure(tag_name, foreground=LINK, underline=True)
                    tk_text.tag_bind(tag_name, "<Button-1>", lambda _e, u=href: webbrowser.open_new_tab(u))
                    next_tags.append(tag_name)

            if name == "br":
                _insert_newline(active_tags)
                return

            if name == "li":
                _insert("- ", active_tags)

            for child in getattr(node, "children", []):
                _walk(child, tuple(next_tags))

            if name in {"p", "ul", "ol", "li"}:
                _insert_newline(active_tags)

            if not first_meaningful_seen:
                node_text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
                if node_text:
                    first_meaningful_seen = True

        for n in soup.contents:
            _walk(n)

        # Treu espais/salts inicials que venen de l'HTML original (indentació).
        while textbox.compare("1.0", "<", "end-1c"):
            ch = textbox.get("1.0", "1.1")
            if ch in {" ", "\t", "\n", "\r"}:
                textbox.delete("1.0", "1.1")
                continue
            break

        def _norm_cmp(value: str) -> str:
            norm = unicodedata.normalize("NFKD", (value or "").strip().lower())
            norm = "".join(c for c in norm if unicodedata.category(c) != "Mn")
            norm = re.sub(r"[^a-z0-9]+", "", norm)
            return norm

        # Si la resposta comença repetint la pregunta, elimina aquest prefix.
        q = (question_text or "").strip()
        if q:
            current = textbox.get("1.0", "end-1c").strip()
            if current.lower().startswith(q.lower()):
                textbox.delete("1.0", f"1.0 + {len(q)}c")
                while textbox.compare("1.0", "<", "end-1c"):
                    ch = textbox.get("1.0", "1.1")
                    if ch in {" ", ":", "-", "\n", "\t", "\r"}:
                        textbox.delete("1.0", "1.1")
                        continue
                    break

        # Tall segur del prefix de pregunta encara que hi hagi apostrofs/accents diferents.
        if q and textbox.compare("end-1c", ">", "1.0"):
            body = textbox.get("1.0", "end-1c")
            lines = body.splitlines()
            if lines:
                first = lines[0].strip()
                if _norm_cmp(first) == _norm_cmp(q):
                    textbox.delete("1.0", "2.0")
                    while textbox.compare("1.0", "<", "end-1c"):
                        ch = textbox.get("1.0", "1.1")
                        if ch in {" ", ":", "-", "\n", "\t", "\r"}:
                            textbox.delete("1.0", "1.1")
                            continue
                        break

        # Si ha quedat una primera línia idèntica a la pregunta, la traiem.
        if q and textbox.compare("end-1c", ">", "1.0"):
            first_line = textbox.get("1.0", "1.end").strip()
            if _norm_cmp(first_line) == _norm_cmp(q):
                textbox.delete("1.0", "2.0")
                while textbox.compare("1.0", "<", "end-1c"):
                    ch = textbox.get("1.0", "1.1")
                    if ch in {" ", "\n", "\t", "\r"}:
                        textbox.delete("1.0", "1.1")
                        continue
                    break

        # Compacta salts múltiples: màxim 1 línia en blanc entre blocs.
        while textbox.compare("1.0", "<", "end-1c"):
            body = textbox.get("1.0", "end-1c")
            m = re.search(r"\n{3,}", body)
            if not m:
                break
            start = f"1.0 + {m.start()}c"
            end = f"1.0 + {m.end()}c"
            textbox.delete(start, end)
            textbox.insert(start, "\n\n")

        # Assegura que la caixa sempre mostri l'inici (evita "espais" aparents per scroll intern).
        try:
            textbox.yview_moveto(0.0)
        except Exception:
            pass

        # Manté els tags (bold/enllaços): no reescriure el contingut.
        # Només traiem salts finals sobrants.
        if textbox.compare("end-1c", ">", "1.0"):
            end_text = textbox.get("end-2c", "end-1c")
            while end_text == "\n" and textbox.compare("end-2c", ">", "1.0"):
                textbox.delete("end-2c", "end-1c")
                end_text = textbox.get("end-2c", "end-1c")
        try:
            tk_text.configure(disabledforeground=self._muted_text_color)
        except Exception:
            pass
        textbox.configure(state="disabled")


    def _approve_all(self):
        for it in self.scraped_items:
            it.approved_var.set(True)
        self._refresh_review_list()
        self._run_live_validation()


    def _unapprove_all(self):
        for it in self.scraped_items:
            it.approved_var.set(False)
        self._refresh_review_list()
        self._run_live_validation()


    def _get_approved_rows(self) -> list[list[str]]:
        rows = []
        for it in self.scraped_items:
            if it.approved_var.get():
                rows.append([
                    (it.topic or "").strip(),
                    (it.topic_subtitle or "").strip() or "-",
                    it.question,
                    it.answer,
                    it.source,
                ])
        return rows

    def _approved_rows_to_sheets_rows(self, approved_rows: list[list[str]]) -> list[list[str]]:
        rows: list[list[str]] = []
        for topic, subtopic, question, answer, source in approved_rows:
            rows.append(
                [
                    topic or "",
                    subtopic or "",
                    question or "",
                    answer or "",
                    "Pendent",
                    "",
                    "",
                    "",
                    "",
                    source or "",
                ]
            )
        return rows


    def _make_id(self, topic: str, topic_subtitle: str, question: str, source: str) -> str:
        s = f"{topic}|{topic_subtitle}|{question}|{source}".encode()
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
            messagebox.showinfo("Copiat", "Codi copiat al porta-retalls")
        except Exception as e:
            messagebox.showerror("Error", f"No s'ha pogut copiar: {e}")

    # ESTILS DE TABS
    def _style_tabview(self, tabview: ctk.CTkTabview):
        tabview.configure(
            fg_color=BG,

            segmented_button_fg_color=self._subtle_panel,
            segmented_button_selected_color=UPC_BLUE_TAB,
            segmented_button_selected_hover_color=UPC_BLUE_TAB,
            segmented_button_unselected_color=self._surface_color,
            segmented_button_unselected_hover_color=self._subtle_panel,

            # IMPORTANT: aquí NO posem blanc, posem fosc perquè les no seleccionades es llegeixin
            text_color=self._text_color,
            text_color_disabled=self._placeholder_color,
        )

        try:
            sb = tabview._segmented_button
            sb.configure(
                corner_radius=12,
                border_width=0,
                height=38,
                font=ctk.CTkFont(size=13, weight="bold"),

                # Algunes versions permeten aquests camps i arreglen del tot el tema del text:
                text_color=self._text_color,
                text_color_disabled=self._placeholder_color,
            )
        except Exception:
            pass

    def _fix_tab_text_colors(self, tabview: ctk.CTkTabview):
        """Força colors de text: selected blanc, unselected fosc (per versions de CTk que ho liïn)."""
        try:
            sb = tabview._segmented_button
            current = tabview.get()

            # Posa totes fosques
            for btn in sb._buttons_dict.values():
                btn.configure(text_color=self._text_color)

            # La seleccionada en blanc
            if current in sb._buttons_dict:
                sb._buttons_dict[current].configure(text_color="white")
        except Exception:
            pass

# ENTRY POINT
if __name__ == "__main__":
    App().mainloop()




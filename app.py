import os
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image

import core

UPC_BLUE = "#0066A1"
BG = "#FFFFFF"

ctk.set_appearance_mode("light")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("UPC FAQ Scraper")
        self.geometry("1040x720")
        self.configure(fg_color=BG)
        self.export_to_sheets = ctk.BooleanVar(value=False)
        self.sheet_name = ctk.StringVar(value="UPC FAQ Export")
        self.sheet_tab = ctk.StringVar(value="FAQs")

        # Icona barra tasques
        try:
            self.iconbitmap("assets/upc_logo.ico")
        except Exception:
            pass

        # Variables
        self.input_mode = ctk.StringVar(value="csv")     # "csv" | "sheets"
        self.output_mode = ctk.StringVar(value="csv")    # "csv" | "sheets"

        self.sources_path = ctk.StringVar()
        self.output_path = ctk.StringVar()
        self.creds_path = ctk.StringVar()

        self.sources_sheet_title = ctk.StringVar(value="faqs-sources")
        self.sources_sheet_tab = ctk.StringVar(value="sources")

        self.output_sheet_title = ctk.StringVar(value="Proves-faqs-mentors")
        self.output_sheet_tab = ctk.StringVar(value="FAQs")

        # Header
        header = ctk.CTkFrame(self, fg_color=UPC_BLUE, corner_radius=0, height=92)
        header.pack(fill="x")
        header.pack_propagate(False)

        logo_image = ctk.CTkImage(
            light_image=Image.open("assets/upc_logo.png"),
            size=(58, 58)
        )
        ctk.CTkLabel(header, image=logo_image, text="").pack(side="left", padx=(18, 10))

        ctk.CTkLabel(
            header,
            text="UNIVERSITAT POLITÈCNICA DE CATALUNYA · BARCELONATECH",
            text_color="white",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left", padx=6)

        ctk.CTkLabel(
            header,
            text="FAQ Scraper",
            text_color="white",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(side="right", padx=18)

        # Body
        body = ctk.CTkFrame(self, fg_color=BG)
        body.pack(fill="both", expand=True, padx=18, pady=18)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(99, weight=1)

        # Ajuda
        help_box = ctk.CTkFrame(body, fg_color="#F3F4F6", corner_radius=10)
        help_box.grid(row=0, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 14))
        help_text = (
            "📌 Com funciona?\n"
            "1) Tria el mode d’ENTRADA (CSV local o Google Sheets)\n"
            "2) Tria el mode de SORTIDA (CSV local o Google Sheets)\n"
            "3) Si algun mode és Google Sheets, cal seleccionar el fitxer de credencials JSON.\n"
            "Exemple sources CSV: columnes URL, topic"
        )
        ctk.CTkLabel(help_box, text=help_text, justify="left").pack(anchor="w", padx=12, pady=10)

        # --- Entrada ---
        ctk.CTkLabel(body, text="ENTRADA", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=1, column=0, padx=6, pady=(6, 0), sticky="w"
        )

        in_mode_frame = ctk.CTkFrame(body, fg_color="transparent")
        in_mode_frame.grid(row=2, column=0, columnspan=3, sticky="w", padx=6, pady=(6, 6))

        ctk.CTkRadioButton(
            in_mode_frame, text="CSV local", variable=self.input_mode, value="csv", command=self._refresh_ui
        ).pack(side="left", padx=(0, 18))

        ctk.CTkRadioButton(
            in_mode_frame, text="Google Sheets", variable=self.input_mode, value="sheets", command=self._refresh_ui
        ).pack(side="left")

        # Entrada CSV row
        self.in_csv_row = ctk.CTkFrame(body, fg_color="transparent")
        self.in_csv_row.grid(row=3, column=0, columnspan=3, sticky="ew", padx=0, pady=0)
        self.in_csv_row.grid_columnconfigure(1, weight=1)
        self._file_row_in(self.in_csv_row, 0, "Fitxer sources (CSV: URL + topic)", self.sources_path, save=False,
                          types=[("CSV", "*.csv")])

        # Entrada Sheets rows
        self.in_sheets_row = ctk.CTkFrame(body, fg_color="transparent")
        self.in_sheets_row.grid(row=4, column=0, columnspan=3, sticky="ew", padx=0, pady=0)
        self.in_sheets_row.grid_columnconfigure(1, weight=1)
        self._text_row(self.in_sheets_row, 0, "Google Sheet sources (títol)", self.sources_sheet_title)
        self._text_row(self.in_sheets_row, 1, "Pestanya sources", self.sources_sheet_tab)

        # --- Sortida ---
        ctk.CTkLabel(body, text="SORTIDA", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=5, column=0, padx=6, pady=(14, 0), sticky="w"
        )

        out_mode_frame = ctk.CTkFrame(body, fg_color="transparent")
        out_mode_frame.grid(row=6, column=0, columnspan=3, sticky="w", padx=6, pady=(6, 6))

        ctk.CTkRadioButton(
            out_mode_frame, text="CSV local", variable=self.output_mode, value="csv", command=self._refresh_ui
        ).pack(side="left", padx=(0, 18))

        ctk.CTkRadioButton(
            out_mode_frame, text="Google Sheets", variable=self.output_mode, value="sheets", command=self._refresh_ui
        ).pack(side="left")

        # Sortida CSV row
        self.out_csv_row = ctk.CTkFrame(body, fg_color="transparent")
        self.out_csv_row.grid(row=7, column=0, columnspan=3, sticky="ew", padx=0, pady=0)
        self.out_csv_row.grid_columnconfigure(1, weight=1)
        self._file_row_in(self.out_csv_row, 0, "Fitxer de sortida (CSV)", self.output_path, save=True,
                          types=[("CSV", "*.csv")])

        # Sortida Sheets rows
        self.out_sheets_row = ctk.CTkFrame(body, fg_color="transparent")
        self.out_sheets_row.grid(row=8, column=0, columnspan=3, sticky="ew", padx=0, pady=0)
        self.out_sheets_row.grid_columnconfigure(1, weight=1)
        self._text_row(self.out_sheets_row, 0, "Google Sheet sortida (títol)", self.output_sheet_title)
        self._text_row(self.out_sheets_row, 1, "Pestanya sortida", self.output_sheet_tab)

        # Credencials (només si cal)
        self.creds_row = ctk.CTkFrame(body, fg_color="transparent")
        self.creds_row.grid(row=9, column=0, columnspan=3, sticky="ew", padx=0, pady=(10, 0))
        self.creds_row.grid_columnconfigure(1, weight=1)
        self._file_row_in(self.creds_row, 0, "Credencials (JSON compte servei)", self.creds_path, save=False,
                          types=[("JSON", "*.json")])

        # Botons
        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.grid(row=10, column=0, columnspan=3, sticky="w", padx=6, pady=(12, 6))

        self.run_btn = ctk.CTkButton(btns, text="Executa", command=self.run_clicked, width=140)
        self.run_btn.pack(side="left")

        self.sample_btn = ctk.CTkButton(btns, text="Crear CSV d’exemple", command=self.create_sample_csv, width=180)
        self.sample_btn.pack(side="left", padx=10)

        self.progress = ctk.CTkProgressBar(body)
        self.progress.grid(row=11, column=0, columnspan=3, sticky="ew", padx=6, pady=(6, 10))
        self.progress.set(0)

        # Log
        self.log = ctk.CTkTextbox(body, height=300)
        self.log.grid(row=99, column=0, columnspan=3, padx=6, pady=10, sticky="nsew")

        self.println("✔ Configura l’entrada i la sortida, després prem ‘Executa’.")

        self._refresh_ui()

    # ---------- UI helpers ----------
    def _file_row_in(self, parent, row, label, var, save, types):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, padx=6, pady=10, sticky="w")
        ctk.CTkEntry(parent, textvariable=var).grid(row=row, column=1, padx=6, pady=10, sticky="ew")

        def browse():
            if save:
                path = filedialog.asksaveasfilename(defaultextension=types[0][1], filetypes=types)
            else:
                path = filedialog.askopenfilename(filetypes=types)
            if path:
                var.set(path)

        ctk.CTkButton(parent, text="Navega…", width=110, command=browse).grid(row=row, column=2, padx=6, pady=10)

    def _text_row(self, parent, row, label, var):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(parent, textvariable=var).grid(row=row, column=1, padx=6, pady=6, sticky="ew")
        ctk.CTkLabel(parent, text="").grid(row=row, column=2, padx=6, pady=6)  # spacer

    def println(self, msg):
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    def ui_log(self, msg: str):
        self.after(0, lambda: self.println(msg))

    def _needs_creds(self) -> bool:
        return self.input_mode.get() == "sheets" or self.output_mode.get() == "sheets"

    def _refresh_ui(self):
        # Mostrar/ocultar entrada
        if self.input_mode.get() == "csv":
            self.in_csv_row.grid()
            self.in_sheets_row.grid_remove()
        else:
            self.in_csv_row.grid_remove()
            self.in_sheets_row.grid()

        # Mostrar/ocultar sortida
        if self.output_mode.get() == "csv":
            self.out_csv_row.grid()
            self.out_sheets_row.grid_remove()
        else:
            self.out_csv_row.grid_remove()
            self.out_sheets_row.grid()

        # Mostrar/ocultar credencials
        if self._needs_creds():
            self.creds_row.grid()
        else:
            self.creds_row.grid_remove()

    # ---------- Actions ----------
    def create_sample_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        sample = "URL,topic\nhttps://www.upc.edu/ca/graus/faqs/preinscripcio-i-assignacio,graus_preinscripcio\n"
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write(sample)
        self.sources_path.set(path)
        self.println(f"✅ CSV d’exemple creat: {path}")

    def validate_inputs(self):
        # input
        if self.input_mode.get() == "csv":
            src = self.sources_path.get().strip()
            if not src or not os.path.exists(src):
                return False, "Selecciona un CSV d’entrada existent."
        else:
            if not self.sources_sheet_title.get().strip() or not self.sources_sheet_tab.get().strip():
                return False, "Omple el títol i la pestanya del Google Sheet de sources."

        # output
        if self.output_mode.get() == "csv":
            out = self.output_path.get().strip()
            if not out:
                return False, "Selecciona un fitxer CSV de sortida."
        else:
            if not self.output_sheet_title.get().strip() or not self.output_sheet_tab.get().strip():
                return False, "Omple el títol i la pestanya del Google Sheet de sortida."

        # creds if needed
        if self._needs_creds():
            creds = self.creds_path.get().strip()
            if not creds or not os.path.exists(creds):
                return False, "Selecciona el fitxer de credencials JSON (obligatori per Google Sheets)."

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
        try:
            # Prepare args
            input_mode = self.input_mode.get()
            output_mode = self.output_mode.get()

            creds = self.creds_path.get().strip() if self._needs_creds() else None

            stats = core.run_pipeline(
                input_mode=input_mode,
                output_mode=output_mode,

                sources_csv_path=self.sources_path.get().strip() if input_mode == "csv" else None,
                sources_sheet_title=self.sources_sheet_title.get().strip() if input_mode == "sheets" else None,
                sources_sheet_tab=self.sources_sheet_tab.get().strip() if input_mode == "sheets" else None,

                output_csv_path=self.output_path.get().strip() if output_mode == "csv" else None,
                output_sheet_title=self.output_sheet_title.get().strip() if output_mode == "sheets" else None,
                output_sheet_tab=self.output_sheet_tab.get().strip() if output_mode == "sheets" else None,

                credentials_json=creds,
                log=self.ui_log
            )

            self.after(0, lambda: self.println(
                f"\n✅ Fet. URLs: {stats['total_urls']} | Files exportades: {stats['total_rows']}"
            ))

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

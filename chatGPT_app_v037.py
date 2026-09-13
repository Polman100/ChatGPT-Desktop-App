from __future__ import annotations

import copy
import datetime
import queue
import threading
import tkinter as tk

from tkinter import END, Listbox, messagebox, scrolledtext

from app_config import (
    AVAILABLE_MODELS,
    HISTORY_DIR,
    ensure_directories,
    load_api_key,
)

from api_service import ApiService
from markdown_renderer import MarkdownRenderer
from storage import ConversationStorage
from usage_function import get_usage_function


class ChatApplication:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ChatGPT - Tkinter")
        self.root.geometry("1200x800")
        self.root.configure(bg="#1e1e1e")

        ensure_directories()

        self.api_service = ApiService(load_api_key())
        self.storage = ConversationStorage(HISTORY_DIR)
        self.renderer = MarkdownRenderer(root)

        self.chat_history_list = []
        self.current_conv_file = None

        self.stream_queue = queue.Queue()
        self.stream_finished = False
        self.stream_error = None
        self.streaming = False

        # True oznacza, że okno rozmowy śledzi najnowszą
        # streamowaną treść.
        #
        # False oznacza, że użytkownik czyta wcześniejszą część
        # rozmowy. W takim przypadku nowe tokeny są zapisywane
        # w chat_history_list, ale widget nie jest przebudowywany.
        # Dzięki temu jego zawartość pozostaje całkowicie stabilna.
        self.auto_scroll = True

        # Chroni przed interpretowaniem operacji wykonywanych
        # przez aplikację jako przewijania użytkownika.
        self.is_rendering_chat = False

        # Podczas przeciągania suwaka nie wolno ponownie włączać
        # automatycznego śledzenia, nawet jeśli suwak chwilowo
        # znajdzie się na dole.
        self.scrollbar_dragging = False

        self.selected_model = tk.StringVar(
            value=AVAILABLE_MODELS[2]
        )

        self.search_var = tk.StringVar()

        self.usage_text = tk.StringVar(
            value="Trwa pobieranie danych o zużyciu..."
        )

        self.build_ui()
        self.bind_events()
        self.refresh_conversation_list()

        self.root.after(
            50,
            self.process_stream_queue
        )

        threading.Thread(
            target=self.load_usage_worker,
            daemon=True
        ).start()

    # ========================================================
    # UI CONSTRUCTION
    # ========================================================

    def build_ui(self) -> None:
        self.build_top_bar()

        self.main_frame = tk.Frame(
            self.root,
            bg="#1e1e1e"
        )

        self.main_frame.pack(
            fill=tk.BOTH,
            expand=True
        )

        self.main_frame.rowconfigure(0, weight=7)
        self.main_frame.rowconfigure(1, weight=2)
        self.main_frame.rowconfigure(2, weight=1)

        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=3)
        self.main_frame.columnconfigure(2, weight=1)

        self.build_left_panel()
        self.build_chat_area()
        self.build_bottom_buttons()

        self.renderer.configure_tags(
            self.chat_history
        )

    def build_top_bar(self) -> None:
        frame = tk.Frame(
            self.root,
            bg="#1e1e1e"
        )

        frame.pack(
            pady=5,
            fill=tk.X
        )

        label = tk.Label(
            frame,
            text="Wybierz model:",
            bg="#1e1e1e",
            fg="white",
            font=("Arial", 12)
        )

        label.pack(
            side=tk.LEFT,
            padx=(10, 5)
        )

        model_menu = tk.OptionMenu(
            frame,
            self.selected_model,
            *AVAILABLE_MODELS
        )

        model_menu.config(
            bg="#333333",
            fg="white",
            font=("Arial", 12),
            highlightthickness=0
        )

        model_menu["menu"].config(
            bg="#333333",
            fg="white",
            font=("Arial", 12)
        )

        model_menu.pack(
            side=tk.LEFT
        )

    def build_left_panel(self) -> None:
        self.left_frame = tk.Frame(
            self.main_frame,
            bg="#151515"
        )

        self.left_frame.grid(
            row=0,
            column=0,
            rowspan=3,
            padx=(10, 5),
            pady=10,
            sticky="nsew"
        )

        search_frame = tk.Frame(
            self.left_frame,
            bg="#151515"
        )

        search_frame.pack(
            fill=tk.X,
            padx=5,
            pady=(5, 0)
        )

        search_label = tk.Label(
            search_frame,
            text="Szukaj:",
            bg="#151515",
            fg="white"
        )

        search_label.pack(
            side=tk.LEFT,
            padx=(0, 5)
        )

        search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            bg="#2b2b2b",
            fg="white",
            insertbackground="white"
        )

        search_entry.pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True
        )

        title = tk.Label(
            self.left_frame,
            text="Historia rozmów",
            bg="#151515",
            fg="white"
        )

        title.pack(
            pady=(5, 0)
        )

        self.conv_listbox = Listbox(
            self.left_frame,
            bg="#202020",
            fg="white",
            selectbackground="#333333",
            relief=tk.FLAT
        )

        self.conv_listbox.pack(
            fill=tk.BOTH,
            expand=True,
            padx=5,
            pady=5
        )

        button_frame = tk.Frame(
            self.left_frame,
            bg="#151515"
        )

        button_frame.pack(
            fill=tk.X,
            padx=5,
            pady=(0, 5)
        )

        self.new_conv_button = tk.Button(
            button_frame,
            text="Nowa rozmowa",
            bg="#007acc",
            fg="white",
            command=self.new_conversation
        )

        self.new_conv_button.pack(
            side=tk.LEFT,
            expand=True,
            fill=tk.X,
            padx=(0, 3)
        )

        self.delete_conv_button = tk.Button(
            button_frame,
            text="Usuń",
            bg="#cc3300",
            fg="white",
            command=self.delete_conversation
        )

        self.delete_conv_button.pack(
            side=tk.LEFT,
            expand=True,
            fill=tk.X,
            padx=(3, 0)
        )

    def build_chat_area(self) -> None:
        self.chat_history = scrolledtext.ScrolledText(
            self.main_frame,
            wrap=tk.WORD,
            state="normal",
            bg="#252526",
            fg="white",
            font=("Arial", 12),
            insertbackground="white",
            relief=tk.FLAT,
            padx=10,
            pady=10,
            selectbackground="#4169a1",
            selectforeground="#ffffff",
            inactiveselectbackground="#4169a1",
            exportselection=False
        )

        self.chat_history.grid(
            row=0,
            column=1,
            padx=10,
            pady=(10, 5),
            sticky="nsew"
        )

        self.entry = scrolledtext.ScrolledText(
            self.main_frame,
            height=4,
            bg="#333333",
            fg="white",
            font=("Arial", 12),
            wrap=tk.WORD,
            insertbackground="white",
            relief=tk.FLAT
        )

        self.entry.grid(
            row=1,
            column=1,
            padx=10,
            pady=5,
            sticky="nsew"
        )

        usage_frame = tk.Frame(
            self.main_frame,
            bg="#252526",
            width=400
        )

        usage_frame.grid(
            row=0,
            column=2,
            padx=10,
            pady=10,
            sticky="nsew"
        )

        usage_frame.grid_propagate(False)

        usage_label = tk.Label(
            usage_frame,
            textvariable=self.usage_text,
            fg="white",
            bg="#252526",
            font=("Arial", 12)
        )

        usage_label.pack(
            padx=10,
            pady=10
        )

    def build_bottom_buttons(self) -> None:
        frame = tk.Frame(
            self.main_frame,
            bg="#1e1e1e"
        )

        frame.grid(
            row=2,
            column=1,
            padx=10,
            pady=(5, 10),
            sticky="ew"
        )

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=3)
        frame.columnconfigure(2, weight=1)

        self.send_button = tk.Button(
            frame,
            text="Wyślij",
            command=self.send_message,
            bg="#007acc",
            fg="white",
            font=("Arial", 12, "bold")
        )

        self.send_button.grid(
            row=0,
            column=1,
            pady=5
        )

        clear_button = tk.Button(
            frame,
            text="Wyczyść historię",
            command=self.clear_chat,
            bg="#cc3300",
            fg="white",
            font=("Arial", 12)
        )

        clear_button.grid(
            row=0,
            column=2,
            padx=5,
            sticky="e"
        )

    # ========================================================
    # EVENT BINDINGS
    # ========================================================

    def bind_events(self) -> None:
        self.conv_listbox.bind(
            "<<ListboxSelect>>",
            self.on_conversation_selected
        )

        self.search_var.trace_add(
            "write",
            lambda *_: self.refresh_conversation_list()
        )

        self.entry.bind(
            "<KeyPress-Return>",
            self.on_entry_key
        )

        self.chat_history.bind(
            "<KeyPress>",
            self.block_chat_editing
        )

        # Windows oraz macOS.
        self.chat_history.bind(
            "<MouseWheel>",
            self.on_chat_scroll_event
        )

        # Linux.
        self.chat_history.bind(
            "<Button-4>",
            self.on_chat_scroll_event
        )

        self.chat_history.bind(
            "<Button-5>",
            self.on_chat_scroll_event
        )

        self.chat_history.bind(
            "<<Paste>>",
            lambda event: "break"
        )

        self.chat_history.bind(
            "<<Cut>>",
            lambda event: "break"
        )

        self.chat_history.bind(
            "<Control-v>",
            lambda event: "break"
        )

        self.chat_history.bind(
            "<Control-x>",
            lambda event: "break"
        )

        self.chat_history.bind(
            "<BackSpace>",
            lambda event: "break"
        )

        self.chat_history.bind(
            "<Delete>",
            lambda event: "break"
        )

        try:
            self.chat_history.vbar.bind(
                "<ButtonPress-1>",
                self.on_scrollbar_press
            )

            self.chat_history.vbar.bind(
                "<B1-Motion>",
                self.on_scrollbar_motion
            )

            self.chat_history.vbar.bind(
                "<ButtonRelease-1>",
                self.on_scrollbar_release
            )

        except AttributeError:
            pass

    def on_entry_key(self, event):
        if event.keysym != "Return":
            return None

        shift_pressed = event.state & 0x0001

        if shift_pressed:
            self.entry.insert(
                tk.INSERT,
                "\n"
            )

            return "break"

        self.send_message()
        return "break"

    def block_chat_editing(self, event):
        control_pressed = event.state & 0x0004

        if control_pressed and event.keysym.lower() in {
            "c",
            "a"
        }:
            return None

        navigation_keys = {
            "Up",
            "Down",
            "Home",
            "End",
            "Prior",
            "Next"
        }

        harmless_keys = {
            "Left",
            "Right",
            "Shift_L",
            "Shift_R",
            "Control_L",
            "Control_R",
            "Alt_L",
            "Alt_R"
        }

        if event.keysym in navigation_keys:
            if not self.is_rendering_chat:
                # Wyłączamy śledzenie jeszcze przed wykonaniem
                # standardowej obsługi klawisza przez Tkinter.
                self.auto_scroll = False

                # Po wykonaniu przewinięcia sprawdzamy, czy użytkownik
                # dotarł na sam dół.
                self.root.after_idle(
                    self.update_auto_scroll_state
                )

            return None

        if event.keysym in harmless_keys:
            return None

        return "break"

    # ========================================================
    # SCROLL MANAGEMENT
    # ========================================================

    def is_chat_at_bottom(self) -> bool:
        try:
            _, bottom = self.chat_history.yview()

            # Niewielka tolerancja zabezpiecza przed błędami
            # zmiennoprzecinkowymi zwracanymi przez Tkinter.
            return bottom >= 0.999

        except tk.TclError:
            return True

    def update_auto_scroll_state(self) -> None:
        """
        Uruchamiane po zakończeniu obsługi zdarzenia przewijania.

        Jeżeli użytkownik wrócił na dół, ponownie włączamy śledzenie
        i od razu renderujemy wszystkie tokeny zgromadzone podczas
        czytania wcześniejszej części rozmowy.
        """

        if self.is_rendering_chat:
            return

        if self.scrollbar_dragging:
            return

        at_bottom = self.is_chat_at_bottom()
        was_auto_scrolling = self.auto_scroll

        self.auto_scroll = at_bottom

        if at_bottom and not was_auto_scrolling:
            self.refresh_chat_widget()

    def on_chat_scroll_event(self, event=None):
        """
        Obsługa kółka myszy.

        Automatyczne śledzenie jest wyłączane natychmiast, jeszcze
        zanim Tkinter wykona swoje standardowe przewinięcie. Dzięki
        temu timer streamingu nie zdąży przebudować widgetu pomiędzy
        zdarzeniem użytkownika a faktycznym przesunięciem widoku.
        """

        if self.is_rendering_chat:
            return None

        self.auto_scroll = False

        self.root.after_idle(
            self.update_auto_scroll_state
        )

        return None

    def on_scrollbar_press(self, event=None):
        """
        Początek używania pionowego paska przewijania.
        """

        if self.is_rendering_chat:
            return None

        self.scrollbar_dragging = True
        self.auto_scroll = False

        return None

    def on_scrollbar_motion(self, event=None):
        """
        Podczas przeciągania suwaka pozostawiamy pełną kontrolę
        użytkownikowi i nie próbujemy włączać śledzenia.
        """

        if self.is_rendering_chat:
            return None

        self.auto_scroll = False

        return None

    def on_scrollbar_release(self, event=None):
        """
        Po puszczeniu suwaka sprawdzamy jego ostateczną pozycję.
        """

        if self.is_rendering_chat:
            self.scrollbar_dragging = False
            return None

        self.scrollbar_dragging = False

        self.root.after_idle(
            self.update_auto_scroll_state
        )

        return None

    def get_chat_scroll_anchor(self) -> tuple[bool, str]:
        """
        Zapisuje indeks tekstu widocznego na górze widgetu.

        Jest to zabezpieczenie dla operacji innych niż streaming.
        Podczas odłączonego streamingu widget nie jest przebudowywany,
        więc pozycja użytkownika pozostaje całkowicie nieruchoma.
        """

        try:
            top_index = self.chat_history.index(
                "@0,0"
            )

        except tk.TclError:
            top_index = "1.0"

        return self.auto_scroll, top_index

    # ========================================================
    # CHAT RENDERING
    # ========================================================

    def refresh_chat_widget(self) -> None:
        """
        Renderuje aktualną historię rozmowy.

        Ważne:
        Nie wywołujemy tutaj root.update_idletasks(), ponieważ przy
        streamingu wymuszałoby to widoczne przerysowanie widgetu po
        jego wyczyszczeniu, ale przed przewinięciem na dół. Efektem
        było miganie pomiędzy starszym fragmentem rozmowy a końcem
        streamowanej odpowiedzi.
        """

        follow_stream, top_index = (
            self.get_chat_scroll_anchor()
        )

        self.is_rendering_chat = True

        try:
            self.renderer.copy_button_counter = 0
            self.renderer.link_counter = 0

            self.chat_history.delete(
                "1.0",
                END
            )

            for message in self.chat_history_list:
                role = message.get("role", "")
                content = message.get("content", "")

                if role == "system":
                    continue

                if role == "user":
                    self.chat_history.insert(
                        END,
                        "Ty:\n",
                        ("user_tag", "align_right")
                    )

                    self.chat_history.insert(
                        END,
                        content + "\n\n",
                        "align_right"
                    )

                elif role == "assistant":
                    self.chat_history.insert(
                        END,
                        "ChatGPT:\n",
                        "bot_tag"
                    )

                    self.renderer.insert_markdown(
                        self.chat_history,
                        content
                    )

                    self.chat_history.insert(
                        END,
                        "\n"
                    )

                else:
                    self.chat_history.insert(
                        END,
                        f"{role}: {content}\n"
                    )

            try:
                self.chat_history.tag_raise("sel")

            except tk.TclError:
                pass

            if follow_stream:
                # see(END) jest stabilniejsze niż yview_moveto(1.0)
                # przy zmiennej wysokości linii, word-wrap oraz
                # osadzonych przyciskach „Kopiuj kod”.
                self.chat_history.see(END)

            else:
                # Ta gałąź jest głównie zabezpieczeniem dla ręcznych
                # odświeżeń. W trakcie odłączonego streamingu widget
                # nie jest przebudowywany, więc użytkownik nie traci
                # swojej pozycji.
                try:
                    self.chat_history.yview(
                        top_index
                    )

                except tk.TclError:
                    self.chat_history.yview_moveto(0.0)

        finally:
            self.is_rendering_chat = False

    # ========================================================
    # CONVERSATION LIST
    # ========================================================

    def refresh_conversation_list(self) -> None:
        self.conv_listbox.delete(
            0,
            END
        )

        query = self.search_var.get().strip().lower()

        for path in self.storage.list_files():
            if not query or query in path.name.lower():
                self.conv_listbox.insert(
                    END,
                    path.name
                )

    def on_conversation_selected(self, event=None) -> None:
        if self.streaming:
            return

        selection = self.conv_listbox.curselection()

        if not selection:
            return

        filename = self.conv_listbox.get(
            selection[0]
        )

        path = HISTORY_DIR / filename

        try:
            self.chat_history_list = self.storage.load(
                path
            )

            self.current_conv_file = path
            self.auto_scroll = True
            self.scrollbar_dragging = False

            self.refresh_chat_widget()

        except Exception as error:
            messagebox.showerror(
                "Błąd",
                f"Nie udało się wczytać rozmowy:\n{error}"
            )

    def delete_conversation(self) -> None:
        if self.streaming:
            return

        selection = self.conv_listbox.curselection()

        if not selection:
            return

        filename = self.conv_listbox.get(
            selection[0]
        )

        path = HISTORY_DIR / filename

        answer = messagebox.askyesno(
            "Usuń konwersację",
            f"Czy na pewno chcesz usunąć konwersację:\n\n"
            f"{filename}\n\n?"
        )

        if not answer:
            return

        try:
            self.storage.delete(
                path
            )

            if self.current_conv_file == path:
                self.clear_chat()

            self.refresh_conversation_list()

        except Exception as error:
            messagebox.showerror(
                "Błąd",
                f"Nie udało się usunąć rozmowy:\n{error}"
            )

    # ========================================================
    # SENDING AND STREAMING
    # ========================================================

    def send_message(self) -> None:
        if self.streaming:
            return

        user_message = self.entry.get(
            "1.0",
            END
        ).strip()

        if not user_message:
            return

        self.entry.delete(
            "1.0",
            END
        )

        if self.current_conv_file is None:
            self.current_conv_file = (
                self.storage.create_filename_from_prompt(
                    user_message
                )
            )

        self.chat_history_list.append(
            {
                "role": "user",
                "content": user_message
            }
        )

        self.storage.save(
            self.current_conv_file,
            self.chat_history_list
        )

        # Wysłanie nowej wiadomości zawsze przenosi rozmowę na dół.
        self.auto_scroll = True
        self.scrollbar_dragging = False

        self.refresh_chat_widget()

        self.set_controls_enabled(
            False
        )

        self.streaming = True
        self.stream_finished = False
        self.stream_error = None

        # Dodajemy pustą wiadomość asystenta. Kolejne tokeny będą
        # dopisywane do jej pola content.
        self.chat_history_list.append(
            {
                "role": "assistant",
                "content": ""
            }
        )

        self.refresh_chat_widget()

        messages_for_api = copy.deepcopy(
            self.chat_history_list[:-1]
        )

        model = self.selected_model.get()

        threading.Thread(
            target=self.stream_worker,
            args=(model, messages_for_api),
            daemon=True
        ).start()

    def stream_worker(
        self,
        model: str,
        messages: list[dict]
    ) -> None:
        full_reply = ""

        try:
            for token in self.api_service.stream_chat(
                model,
                messages
            ):
                full_reply += token

                self.stream_queue.put(
                    ("token", token)
                )

            self.stream_queue.put(
                ("finished", full_reply)
            )

        except Exception as error:
            self.stream_queue.put(
                ("error", str(error))
            )

    def process_stream_queue(self) -> None:
        changed = False

        try:
            while True:
                event_type, payload = (
                    self.stream_queue.get_nowait()
                )

                if event_type == "token":
                    self.chat_history_list[-1]["content"] += (
                        payload
                    )

                    changed = True

                elif event_type == "finished":
                    self.chat_history_list[-1]["content"] = (
                        payload
                    )

                    self.stream_finished = True
                    changed = True

                elif event_type == "error":
                    self.stream_error = payload
                    self.stream_finished = True

        except queue.Empty:
            pass

        # Najważniejsza zmiana:
        #
        # Gdy użytkownik odłączył się od streamu, NIE przebudowujemy
        # widgetu. Tokeny nadal są dopisywane do chat_history_list,
        # ale widoczny tekst pozostaje nieruchomy.
        #
        # Po powrocie użytkownika na dół update_auto_scroll_state()
        # wyrenderuje całą aktualną treść.
        if changed and self.auto_scroll:
            self.refresh_chat_widget()

        if self.stream_finished:
            self.finish_stream()

        self.root.after(
            50,
            self.process_stream_queue
        )

    def finish_stream(self) -> None:
        if not self.streaming:
            return

        self.streaming = False

        if self.stream_error:
            error_text = (
                "\n\nWystąpił błąd podczas komunikacji z API:\n"
                f"{self.stream_error}"
            )

            self.chat_history_list[-1]["content"] = (
                error_text
            )

            # Nie przesuwamy i nie przebudowujemy okna, jeśli
            # użytkownik czyta wcześniejszą część rozmowy.
            if self.auto_scroll:
                self.refresh_chat_widget()

        self.storage.save(
            self.current_conv_file,
            self.chat_history_list
        )

        self.set_controls_enabled(
            True
        )

        self.refresh_conversation_list()

        threading.Thread(
            target=self.load_usage_worker,
            daemon=True
        ).start()

    # ========================================================
    # UI STATE
    # ========================================================

    def set_controls_enabled(
        self,
        enabled: bool
    ) -> None:
        state = (
            tk.NORMAL
            if enabled
            else tk.DISABLED
        )

        self.send_button.config(
            state=state
        )

        self.new_conv_button.config(
            state=state
        )

        self.delete_conv_button.config(
            state=state
        )

        self.conv_listbox.config(
            state=state
        )

    def clear_chat(self) -> None:
        if self.streaming:
            return

        self.chat_history_list = []
        self.current_conv_file = None
        self.auto_scroll = True
        self.scrollbar_dragging = False

        self.chat_history.delete(
            "1.0",
            END
        )

        self.conv_listbox.selection_clear(
            0,
            END
        )

    def new_conversation(self) -> None:
        self.clear_chat()

    # ========================================================
    # USAGE
    # ========================================================

    def load_usage_worker(self) -> None:
        try:
            end_date = (
                datetime.date.today()
                + datetime.timedelta(days=2)
            )

            start_date = (
                end_date
                - datetime.timedelta(days=30)
            )

            total_spend = (
                self.api_service.get_usage(
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                    usage_function=get_usage_function
                )
            )

            text = (
                "Zużycie API (ostatnie 30 dni):\n"
                f"Total Spend: ${total_spend:.2f}\n"
                "Pozostały kredyt: brak danych"
            )

        except Exception as error:
            text = f"Błąd: {error}"

        self.root.after(
            0,
            lambda: self.usage_text.set(text)
        )


def main() -> None:
    root = tk.Tk()
    ChatApplication(root)
    root.mainloop()


if __name__ == "__main__":
    main()
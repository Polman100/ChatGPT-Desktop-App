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
        self.auto_scroll = True

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

        self.renderer.configure_tags(self.chat_history)

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

        menu = tk.OptionMenu(
            frame,
            self.selected_model,
            *AVAILABLE_MODELS
        )

        menu.config(
            bg="#333333",
            fg="white",
            font=("Arial", 12),
            highlightthickness=0
        )

        menu["menu"].config(
            bg="#333333",
            fg="white",
            font=("Arial", 12)
        )

        menu.pack(side=tk.LEFT)

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
        title.pack(pady=(5, 0))

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

    def block_chat_editing(self, event):
        control_pressed = event.state & 0x0004

        if control_pressed and event.keysym.lower() in {
            "c",
            "a"
        }:
            return None

        allowed_keys = {
            "Left",
            "Right",
            "Up",
            "Down",
            "Home",
            "End",
            "Prior",
            "Next",
            "Shift_L",
            "Shift_R",
            "Control_L",
            "Control_R",
            "Alt_L",
            "Alt_R"
        }

        if event.keysym in allowed_keys:
            return None

        return "break"

    def on_entry_key(self, event):
        if event.keysym != "Return":
            return None

        shift_pressed = event.state & 0x0001

        if shift_pressed:
            self.entry.insert(tk.INSERT, "\n")
            return "break"

        self.send_message()
        return "break"

    def refresh_chat_widget(self) -> None:
        self.renderer.copy_button_counter = 0
        self.renderer.link_counter = 0

        self.chat_history.delete("1.0", END)

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

        try:
            self.chat_history.tag_raise("sel")
        except tk.TclError:
            pass

        if self.auto_scroll:
            self.chat_history.yview_moveto(1.0)

    def refresh_conversation_list(self) -> None:
        self.conv_listbox.delete(0, END)

        query = self.search_var.get().strip().lower()

        for path in self.storage.list_files():
            if not query or query in path.name.lower():
                self.conv_listbox.insert(
                    END,
                    path.name
                )

    def send_message(self) -> None:
        if self.streaming:
            return

        user_message = self.entry.get(
            "1.0",
            END
        ).strip()

        if not user_message:
            return

        self.entry.delete("1.0", END)

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

        self.refresh_chat_widget()
        self.set_controls_enabled(False)

        self.streaming = True
        self.stream_finished = False
        self.stream_error = None

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
                self.stream_queue.put(("token", token))

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
                event_type, payload = self.stream_queue.get_nowait()

                if event_type == "token":
                    self.chat_history_list[-1]["content"] += payload
                    changed = True

                elif event_type == "finished":
                    self.chat_history_list[-1]["content"] = payload
                    self.stream_finished = True
                    changed = True

                elif event_type == "error":
                    self.stream_error = payload
                    self.stream_finished = True

        except queue.Empty:
            pass

        if changed:
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

            self.chat_history_list[-1]["content"] = error_text
            self.refresh_chat_widget()

        self.storage.save(
            self.current_conv_file,
            self.chat_history_list
        )

        self.set_controls_enabled(True)
        self.refresh_conversation_list()

        threading.Thread(
            target=self.load_usage_worker,
            daemon=True
        ).start()

    def set_controls_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED

        self.send_button.config(state=state)
        self.new_conv_button.config(state=state)
        self.delete_conv_button.config(state=state)
        self.conv_listbox.config(state=state)

    def clear_chat(self) -> None:
        if self.streaming:
            return

        self.chat_history_list = []
        self.current_conv_file = None

        self.chat_history.delete("1.0", END)
        self.conv_listbox.selection_clear(0, END)

    def new_conversation(self) -> None:
        self.clear_chat()

    def on_conversation_selected(self, event=None) -> None:
        if self.streaming:
            return

        selection = self.conv_listbox.curselection()

        if not selection:
            return

        filename = self.conv_listbox.get(selection[0])
        path = HISTORY_DIR / filename

        try:
            self.chat_history_list = self.storage.load(path)
            self.current_conv_file = path
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

        filename = self.conv_listbox.get(selection[0])
        path = HISTORY_DIR / filename

        answer = messagebox.askyesno(
            "Usuń konwersację",
            f"Czy na pewno chcesz usunąć konwersację:\n\n"
            f"{filename}\n\n?"
        )

        if not answer:
            return

        try:
            self.storage.delete(path)

            if self.current_conv_file == path:
                self.clear_chat()

            self.refresh_conversation_list()

        except Exception as error:
            messagebox.showerror(
                "Błąd",
                f"Nie udało się usunąć rozmowy:\n{error}"
            )

    def load_usage_worker(self) -> None:
        try:
            end_date = (
                datetime.date.today()
                + datetime.timedelta(days=2)
            )

            start_date = end_date - datetime.timedelta(days=30)

            total_spend = self.api_service.get_usage(
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                usage_function=get_usage_function
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
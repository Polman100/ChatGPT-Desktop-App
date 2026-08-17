import openai
import os
import tkinter as tk
import threading
from tkinter import scrolledtext, Listbox, END, messagebox
from dotenv import load_dotenv
from usage_function import get_usage_function
import datetime
import json
import re
import unicodedata
import copy
import webbrowser

TITLE_MODEL = "gpt-4o-mini"  # stały, tańszy model do generowania tytułów

# Ustaw katalog roboczy na lokalizację tego pliku
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

print("Bieżący katalog roboczy to:")
print(os.getcwd())

# Wczytaj klucz API
load_dotenv("key.env")
api_key = os.getenv("OPENAI_API_KEY")
if api_key is None:
    raise ValueError("Brak klucza API. Sprawdź plik key.env!")

openai_client = openai.OpenAI(api_key=api_key)

# Folder na historię
history_folder = os.path.join(script_dir, "Conversation history")
os.makedirs(history_folder, exist_ok=True)

# Lock do bezpiecznego zapisu plików
file_lock = threading.Lock()

# Zmienna przechowująca aktualny plik konwersacji (pełna ścieżka) lub None
current_conv_file = None

# Licznik tagów linków
link_tag_counter = 0

# Tworzenie okna aplikacji
root = tk.Tk()
root.title("ChatGPT - Tkinter")
root.geometry("1200x800")
root.configure(bg="#1e1e1e")

# Dostępne modele
available_models = [
    "gpt-5.4", "gpt-5.4-mini", "gpt-5.2", "gpt-5.1", "gpt-5",
    "gpt-5-mini", "gpt-5-nano", "gpt-3.5-turbo", "gpt-4.1",
    "gpt-4o-mini", "gpt-4o", "gpt-4.5-preview"
]
selected_model = tk.StringVar(value=available_models[1])

# === Górny pasek wyboru modelu ===
model_frame = tk.Frame(root, bg="#1e1e1e")
model_frame.pack(pady=5, fill=tk.X)
model_label = tk.Label(model_frame, text="Wybierz model:", bg="#1e1e1e", fg="white", font=("Arial", 12))
model_label.pack(side=tk.LEFT, padx=(10, 5))
model_menu = tk.OptionMenu(model_frame, selected_model, *available_models)
model_menu.config(bg="#333333", fg="white", font=("Arial", 12), highlightthickness=0)
model_menu["menu"].config(bg="#333333", fg="white", font=("Arial", 12))
model_menu.pack(side=tk.LEFT)

# Przechowywanie historii czatu
chat_history_list = []

# Główna ramka
main_frame = tk.Frame(root, bg="#1e1e1e")
main_frame.pack(fill=tk.BOTH, expand=True)

main_frame.rowconfigure(0, weight=7)
main_frame.rowconfigure(1, weight=2)
main_frame.rowconfigure(2, weight=1)
main_frame.columnconfigure(0, weight=1)
main_frame.columnconfigure(1, weight=3)
main_frame.columnconfigure(2, weight=1)

# -- LEWY PANEL: wyszukiwarka + lista konwersacji --
left_frame = tk.Frame(main_frame, bg="#151515")
left_frame.grid(row=0, column=0, rowspan=3, padx=(10, 5), pady=10, sticky="nsew")

search_frame = tk.Frame(left_frame, bg="#151515")
search_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
search_label = tk.Label(search_frame, text="Szukaj:", bg="#151515", fg="white")
search_label.pack(side=tk.LEFT, padx=(0, 5))
search_var = tk.StringVar(value="")
search_entry = tk.Entry(search_frame, textvariable=search_var, bg="#2b2b2b", fg="white", insertbackground="white")
search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

left_title = tk.Label(left_frame, text="Historia rozmów", bg="#151515", fg="white")
left_title.pack(pady=(5, 0))
conv_listbox = Listbox(left_frame, bg="#202020", fg="white", selectbackground="#333333", relief=tk.FLAT)
conv_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

conv_btn_frame = tk.Frame(left_frame, bg="#151515")
conv_btn_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
new_conv_btn = tk.Button(conv_btn_frame, text="Nowa rozmowa", bg="#007acc", fg="white")
new_conv_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 3))
delete_conv_btn = tk.Button(conv_btn_frame, text="Usuń", bg="#cc3300", fg="white")
delete_conv_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(3, 0))

# Pole na historię czatu
chat_history = scrolledtext.ScrolledText(
    main_frame,
    wrap=tk.WORD,
    state='disabled',
    bg="#252526",
    fg="white",
    font=("Arial", 12)
)
chat_history.grid(row=0, column=1, padx=10, pady=(10, 5), sticky="nsew")

# Pole wpisywania
entry = scrolledtext.ScrolledText(main_frame, height=4, bg="#333333", fg="white", font=("Arial", 12), wrap=tk.WORD)
entry.grid(row=1, column=1, padx=10, pady=5, sticky="nsew")

# RAMKA Z INFORMACJAMI O ZUŻYCIU
usage_frame = tk.Frame(main_frame, bg="#252526", width=400)
usage_frame.grid(row=0, column=2, padx=10, pady=10, sticky="nsew")
usage_frame.grid_propagate(False)
usage_text = tk.StringVar(value="Trwa pobieranie danych o zużyciu...")
usage_label = tk.Label(usage_frame, textvariable=usage_text, fg="white", bg="#252526", font=("Arial", 12))
usage_label.pack(padx=10, pady=10)

def get_usage():
    try:
        end_date = datetime.date.today() + datetime.timedelta(days=2)
        start_date = end_date - datetime.timedelta(days=30)
        total_spend = get_usage_function(start_date=start_date.isoformat(), end_date=end_date.isoformat())
        usage_text.set(f"Zużycie API (ostatnie 30 dni):\nTotal Spend: ${total_spend:.2f}\nPozostały kredyt: brak danych")
    except Exception as e:
        usage_text.set(f"Błąd: {str(e)}")

def is_at_bottom(widget, epsilon=0.01):
    return abs(widget.yview()[1] - 1.0) < epsilon

def remove_diacritics(s):
    nkfd = unicodedata.normalize('NFKD', s)
    return "".join([c for c in nkfd if not unicodedata.combining(c)])

def sanitize_filename(s):
    s = s.strip()
    s = s.replace("\n", " ")
    s = remove_diacritics(s)
    s = re.sub(r"[^A-Za-z0-9 _-]", "", s)
    s = s[:40].strip()
    if not s:
        s = "conversation"
    return s

def make_unique_filename(base):
    candidate = base + ".txt"
    i = 1
    while os.path.exists(os.path.join(history_folder, candidate)):
        candidate = f"{base} ({i}).txt"
        i += 1
    return os.path.join(history_folder, candidate)

def create_filename_from_prompt(prompt):
    date_part = datetime.datetime.now().strftime("%Y.%m.%d")
    time_part = datetime.datetime.now().strftime("%H%M")
    words = prompt.strip().split()
    short = sanitize_filename(" ".join(words[:10]) if words else "conv")
    base = f"{date_part} {time_part} - {short}"
    return make_unique_filename(base)

def save_conversation_content(path, content_list):
    try:
        with file_lock:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(content_list, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
    except Exception as e:
        print("Błąd zapisu konwersacji:", e)

def save_conversation_to_file(path):
    save_conversation_content(path, chat_history_list)

def load_conversation_from_file(path):
    global chat_history_list, current_conv_file
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        chat_history_list = data
        current_conv_file = path
        refresh_chat_widget()
    except Exception as e:
        print("Błąd wczytywania konwersacji:", e)

# =========================
# MARKDOWN / LINKI / TABELE
# =========================

def open_link(url):
    try:
        webbrowser.open(url)
    except Exception as e:
        print("Błąd otwierania linku:", e)

def add_link(widget, text, url):
    global link_tag_counter
    start_index = widget.index(END)
    widget.insert(END, text)
    end_index = widget.index(END)

    tag_name = f"link_{link_tag_counter}"
    link_tag_counter += 1

    widget.tag_add(tag_name, start_index, end_index)
    widget.tag_configure(tag_name, foreground="#4ea1ff", underline=True)
    widget.tag_bind(tag_name, "<Button-1>", lambda e, u=url: open_link(u))
    widget.tag_bind(tag_name, "<Enter>", lambda e: widget.config(cursor="hand2"))
    widget.tag_bind(tag_name, "<Leave>", lambda e: widget.config(cursor="xterm"))

def parse_inline_segments(text):
    """
    Zwraca listę segmentów:
    ("text", ...)
    ("bold", ...)
    ("italic", ...)
    ("code", ...)
    ("link", visible_text, url)

    Obsługuje:
    - [tekst](url)
    - **bold**
    - *italic*
    - `code`
    - surowe URL-e
    """
    pattern = r'(\[.*?\]\(https?://[^\s)]+(?:\)[^\s)]*)?\)|https?://[^\s]+|\*\*.*?\*\*|`.*?`|\*.*?\*)'
    parts = re.split(pattern, text)

    segments = []
    for part in parts:
        if not part:
            continue

        md_link = re.match(r'^\[(.*?)\]\((https?://[^\s]+)\)$', part)
        if md_link:
            segments.append(("link", md_link.group(1), md_link.group(2)))
        elif re.match(r'^https?://[^\s]+$', part):
            segments.append(("link", part, part))
        elif part.startswith("**") and part.endswith("**") and len(part) >= 4:
            segments.append(("bold", part[2:-2]))
        elif part.startswith("*") and part.endswith("*") and len(part) >= 2:
            segments.append(("italic", part[1:-1]))
        elif part.startswith("`") and part.endswith("`") and len(part) >= 2:
            segments.append(("code", part[1:-1]))
        else:
            segments.append(("text", part))

    return segments

def insert_inline_segments(widget, text):
    for seg in parse_inline_segments(text):
        seg_type = seg[0]

        if seg_type == "text":
            widget.insert(END, seg[1])
        elif seg_type == "bold":
            widget.insert(END, seg[1], "md_bold")
        elif seg_type == "italic":
            widget.insert(END, seg[1], "md_italic")
        elif seg_type == "code":
            widget.insert(END, seg[1], "md_code")
        elif seg_type == "link":
            add_link(widget, seg[1], seg[2])

def is_table_separator_line(line):
    stripped = line.strip()
    if "|" not in stripped:
        return False
    cells = [c.strip() for c in stripped.strip("|").split("|")]
    if not cells:
        return False
    return all(re.match(r"^:?-{3,}:?$", c) for c in cells if c != "")

def is_table_line(line):
    stripped = line.strip()
    return "|" in stripped and len(stripped.strip("|").split("|")) >= 2

def parse_table(lines, start_index):
    """
    Próbuje sparsować markdownową tabelę od start_index.
    Zwraca (table_lines_count, rendered_table_text) albo (0, None)
    """
    if start_index + 1 >= len(lines):
        return 0, None

    header = lines[start_index]
    separator = lines[start_index + 1]

    if not is_table_line(header) or not is_table_separator_line(separator):
        return 0, None

    table_rows = [header]
    i = start_index + 2

    while i < len(lines) and is_table_line(lines[i]) and lines[i].strip() != "":
        table_rows.append(lines[i])
        i += 1

    parsed_rows = []
    for row in table_rows:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        parsed_rows.append(cells)

    col_count = max(len(r) for r in parsed_rows)
    for r in parsed_rows:
        while len(r) < col_count:
            r.append("")

    col_widths = [0] * col_count
    for r in parsed_rows:
        for idx, cell in enumerate(r):
            col_widths[idx] = max(col_widths[idx], len(cell))

    rendered = ""
    header_row = parsed_rows[0]
    rendered += " | ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(header_row)) + "\n"
    rendered += "-+-".join("-" * col_widths[i] for i in range(col_count)) + "\n"

    for r in parsed_rows[1:]:
        rendered += " | ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(r)) + "\n"

    return len(table_rows) + 1, rendered  # +1 dla separatora

def insert_markdown(widget, content):
    """
    Obsługuje:
    - # ## ###
    - **bold**, *italic*, `code`
    - listy: -, *, 1., a., a)
    - cytaty >
    - linki [tekst](url) i surowe URL
    - bloki kodu ```
    - tabele markdown
    """
    lines = content.splitlines()
    in_code_block = False
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # start/stop bloku kodu
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            if not in_code_block:
                widget.insert(END, "\n")
            i += 1
            continue

        if in_code_block:
            widget.insert(END, line + "\n", "md_codeblock")
            i += 1
            continue

        # tabela
        consumed, rendered_table = parse_table(lines, i)
        if consumed > 0 and rendered_table:
            widget.insert(END, rendered_table, "md_table")
            widget.insert(END, "\n")
            i += consumed
            continue

        # nagłówki
        if stripped.startswith("### "):
            widget.insert(END, stripped[4:] + "\n", "md_h3")
            i += 1
            continue
        elif stripped.startswith("## "):
            widget.insert(END, stripped[3:] + "\n", "md_h2")
            i += 1
            continue
        elif stripped.startswith("# "):
            widget.insert(END, stripped[2:] + "\n", "md_h1")
            i += 1
            continue

        # cytaty
        if stripped.startswith(">"):
            quote_text = re.sub(r"^>\s?", "", stripped)
            widget.insert(END, "▌ ", "md_quote_bar")
            insert_inline_segments(widget, quote_text)
            widget.insert(END, "\n", "md_quote")
            i += 1
            continue

        # listy punktowane
        if stripped.startswith("- ") or stripped.startswith("* "):
            widget.insert(END, "• ", "md_bullet")
            insert_inline_segments(widget, stripped[2:])
            widget.insert(END, "\n", "md_bullet")
            i += 1
            continue

        # lista numerowana
        num_match = re.match(r"^(\d+\.)\s+(.*)", stripped)
        if num_match:
            widget.insert(END, num_match.group(1) + " ", "md_number")
            insert_inline_segments(widget, num_match.group(2))
            widget.insert(END, "\n", "md_number")
            i += 1
            continue

        # podpunkty literowe: a. xxx / a) xxx / A. xxx / A) xxx
        alpha_match = re.match(r"^([A-Za-z][\.\)])\s+(.*)", stripped)
        if alpha_match:
            widget.insert(END, alpha_match.group(1) + " ", "md_alpha")
            insert_inline_segments(widget, alpha_match.group(2))
            widget.insert(END, "\n", "md_alpha")
            i += 1
            continue

        # pusta linia
        if stripped == "":
            widget.insert(END, "\n")
            i += 1
            continue

        # zwykły tekst
        insert_inline_segments(widget, line)
        widget.insert(END, "\n")
        i += 1

def refresh_chat_widget():
    chat_history.config(state='normal')
    chat_history.delete("1.0", tk.END)

    for m in chat_history_list:
        role = m.get("role", "")
        content = m.get("content", "")

        if role == "system":
            continue

        if role == "user":
            chat_history.insert(END, "Ty:\n", ("user_tag", "align_right"))
            chat_history.insert(END, content + "\n\n", "align_right")

        elif role == "assistant":
            chat_history.insert(END, "ChatGPT:\n", "bot_tag")
            insert_markdown(chat_history, content)
            chat_history.insert(END, "\n")

        else:
            chat_history.insert(END, f"{role}: {content}\n")

    chat_history.config(state='disabled')
    chat_history.yview(END)

def refresh_conversation_listbox():
    conv_listbox.delete(0, END)
    all_files = [f for f in os.listdir(history_folder) if os.path.isfile(os.path.join(history_folder, f))]
    all_files.sort(key=lambda f: os.path.getmtime(os.path.join(history_folder, f)), reverse=True)
    q = search_var.get().strip().lower()
    for f in all_files:
        if q == "" or q in f.lower():
            conv_listbox.insert(END, f)

def get_ai_title_for_prompt(prompt_text, max_chars=40):
    try:
        trimmed_prompt = (prompt_text[:1000]) if len(prompt_text) > 1000 else prompt_text

        sys_msg = (
            "Jesteś pomocnym narzędziem, którego zadaniem jest wygenerowanie krótkiego tytułu dla konwersacji. "
            "Zwróć wyłącznie krótki tytuł (bez dodatkowych wyjaśnień), najlepiej do {} znaków."
        ).format(max_chars)

        user_msg = (
            f"Na podstawie tej treści podaj krótką nazwę konwersacji (tylko nazwa, bez cudzysłowów):\n\n"
            f"\"{trimmed_prompt}\""
        )

        response = openai_client.chat.completions.create(
            model=TITLE_MODEL,
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg}
            ],
            max_completion_tokens=32,
            stream=False
        )

        content = ""
        try:
            content = response.choices[0].message.content.strip()
        except Exception:
            content = ""

        content = content.splitlines()[0].strip()
        content = re.sub(r'[\"`]', '', content)

        return content[:max_chars]
    except Exception as e:
        print("Błąd przy generowaniu tytułu przez AI:", e)
        return ""

def send_message():
    global current_conv_file
    user_message = entry.get("1.0", END).strip()
    if not user_message:
        return
    entry.delete("1.0", END)

    # tymczasowe wyświetlenie usera
    chat_history.config(state='normal')
    chat_history.insert(END, "\n")
    chat_history.insert(END, "Ty:\n", ("user_tag", "align_right"))
    chat_history.insert(END, user_message + "\n", "align_right")
    chat_history.config(state='disabled')
    chat_history.yview(END)

    is_first_message = (current_conv_file is None)
    chat_history_list.append({"role": "user", "content": user_message})

    if not is_first_message and current_conv_file:
        save_conversation_to_file(current_conv_file)

    conv_listbox.config(state='disabled')
    new_conv_btn.config(state='disabled')
    delete_conv_btn.config(state='disabled')
    send_button.config(state='disabled')

    messages_for_api = copy.deepcopy(chat_history_list)
    conv_path_for_thread = current_conv_file

    def worker():
        nonlocal conv_path_for_thread

        try:
            if is_first_message:
                try:
                    title = get_ai_title_for_prompt(user_message, max_chars=40)
                    if not title:
                        title = sanitize_filename(user_message[:40] or "conversation")
                    else:
                        title = sanitize_filename(title)

                    date_part = datetime.datetime.now().strftime("%Y.%m.%d")
                    time_part = datetime.datetime.now().strftime("%H%M")
                    new_base = f"{date_part} {time_part} - {title}"
                    new_path = make_unique_filename(new_base)

                    conv_path_for_thread = new_path
                    save_conversation_content(conv_path_for_thread, chat_history_list)

                    def after_title_ready():
                        global current_conv_file
                        current_conv_file = conv_path_for_thread
                        refresh_conversation_listbox()
                        name_only = os.path.basename(conv_path_for_thread)
                        idxs = [i for i in range(conv_listbox.size()) if conv_listbox.get(i) == name_only]
                        if idxs:
                            conv_listbox.select_clear(0, END)
                            conv_listbox.select_set(idxs[0])
                            conv_listbox.activate(idxs[0])
                    root.after(0, after_title_ready)

                except Exception as e_title:
                    print("Błąd przy generowaniu tytułu przez AI (pierwsza wiadomość):", e_title)
                    if conv_path_for_thread is None:
                        conv_path_for_thread = create_filename_from_prompt(user_message)
                        save_conversation_content(conv_path_for_thread, chat_history_list)

                        def after_fallback_title():
                            global current_conv_file
                            current_conv_file = conv_path_for_thread
                            refresh_conversation_listbox()
                        root.after(0, after_fallback_title)

            model = selected_model.get()
            print(f"[DEBUG] Używany model: {model}")

            stream_enabled = True
            print(f"[DEBUG] stream_enabled = {stream_enabled}")

            def init_bot_line():
                if conv_path_for_thread != current_conv_file:
                    return
                chat_history.config(state='normal')
                chat_history.insert(END, "ChatGPT:\n", "bot_tag")
                chat_history.config(state='disabled')
                chat_history.yview(END)
            root.after(0, init_bot_line)

            response = openai_client.chat.completions.create(
                model=model,
                messages=messages_for_api,
                stream=stream_enabled
            )
            print("[DEBUG] API response created")

            full_reply = ""

            if stream_enabled:
                def append_token_to_ui(token_chunk):
                    try:
                        if conv_path_for_thread != current_conv_file:
                            return
                        chat_history.config(state='normal')
                        chat_history.insert(END, token_chunk)
                        chat_history.config(state='disabled')
                        if is_at_bottom(chat_history):
                            chat_history.yview(END)
                    except Exception as e:
                        print("[DEBUG] Błąd w append_token_to_ui:", e)

                try:
                    for chunk in response:
                        token = ""
                        try:
                            token = chunk.choices[0].delta.content or ""
                        except Exception as e_inner:
                            print("[DEBUG] Błąd pobierania tokenu ze strumienia:", e_inner)
                            token = ""
                        if token:
                            full_reply += token
                            root.after(0, append_token_to_ui, token)
                except Exception as e_stream:
                    print("[DEBUG] Błąd w pętli stream:", e_stream)

            else:
                try:
                    full_reply = response.choices[0].message.content or ""
                except Exception as e_nostream:
                    print("[DEBUG] Błąd odczytu odpowiedzi w trybie bez streamu:", e_nostream)
                    full_reply = ""

                def append_full_reply():
                    try:
                        if conv_path_for_thread != current_conv_file:
                            return
                        chat_history.config(state='normal')
                        chat_history.insert(END, full_reply)
                        chat_history.config(state='disabled')
                        chat_history.yview(END)
                    except Exception as e:
                        print("[DEBUG] Błąd w append_full_reply:", e)
                root.after(0, append_full_reply)

            print("[DEBUG] Pełna odpowiedź długość:", len(full_reply))

            def update_memory_and_save():
                try:
                    chat_history_list.append({"role": "assistant", "content": full_reply})
                    if conv_path_for_thread:
                        save_conversation_content(conv_path_for_thread, chat_history_list)

                    if conv_path_for_thread == current_conv_file:
                        refresh_chat_widget()

                except Exception as e:
                    print("[DEBUG] Błąd w update_memory_and_save:", e)
            root.after(0, update_memory_and_save)

            def finish_in_main_thread():
                try:
                    conv_listbox.config(state='normal')
                    new_conv_btn.config(state='normal')
                    delete_conv_btn.config(state='normal')
                    send_button.config(state='normal')

                    if conv_path_for_thread == current_conv_file:
                        chat_history.config(state='disabled')
                        chat_history.yview(END)

                    threading.Thread(target=refresh_conversation_listbox, daemon=True).start()
                    threading.Thread(target=get_usage, daemon=True).start()
                except Exception as e:
                    print("Błąd w finish_in_main_thread:", e)
            root.after(0, finish_in_main_thread)

        except Exception as e:
            print("Błąd w workerze send_message:", e)

            def restore_ui():
                conv_listbox.config(state='normal')
                new_conv_btn.config(state='normal')
                delete_conv_btn.config(state='normal')
                send_button.config(state='normal')
            root.after(0, restore_ui)

    threading.Thread(target=worker, daemon=True).start()

def clear_chat():
    global chat_history_list, current_conv_file
    chat_history.config(state='normal')
    chat_history.delete("1.0", END)
    chat_history.config(state='disabled')
    chat_history_list = []
    current_conv_file = None
    conv_listbox.select_clear(0, END)

# Przycisk Wyślij i Wyczyść
button_frame = tk.Frame(main_frame, bg="#1e1e1e")
button_frame.grid(row=2, column=1, padx=10, pady=(5, 10), sticky="ew")
button_frame.columnconfigure(0, weight=1)
button_frame.columnconfigure(1, weight=3)
button_frame.columnconfigure(2, weight=1)

send_button = tk.Button(button_frame, text="Wyślij", command=send_message, bg="#007acc", fg="white", font=("Arial", 12, "bold"))
send_button.grid(row=0, column=1, pady=5, sticky="")
clear_button = tk.Button(button_frame, text="Wyczyść historię", command=clear_chat, bg="#cc3300", fg="white", font=("Arial", 12))
clear_button.grid(row=0, column=2, padx=5, sticky="e")

# Enter wysyła, Shift+Enter nowa linia
def on_entry_key(event):
    if event.keysym == "Return":
        if event.state & 0x0001:
            entry.insert(tk.INSERT, "\n")
            return 'break'
        else:
            send_message()
            return 'break'

entry.bind('<KeyPress-Return>', on_entry_key)

# ===== TAGI =====

chat_history.tag_configure("user_tag", foreground="lightgreen", font=("Arial", 12, "bold"))
chat_history.tag_configure("bot_tag", foreground="violet", font=("Arial", 12, "bold"))

chat_history.tag_configure("md_h1", font=("Arial", 18, "bold"), foreground="#dcdcdc")
chat_history.tag_configure("md_h2", font=("Arial", 16, "bold"), foreground="#dcdcdc")
chat_history.tag_configure("md_h3", font=("Arial", 14, "bold"), foreground="#dcdcdc")
chat_history.tag_configure("md_bold", font=("Arial", 12, "bold"))
chat_history.tag_configure("md_italic", font=("Arial", 12, "italic"))
chat_history.tag_configure("md_code", font=("Consolas", 11), background="#2d2d2d", foreground="#ffd700")
chat_history.tag_configure("md_codeblock", font=("Consolas", 11), background="#2D2F31", foreground="#ffffff")
chat_history.tag_configure("md_bullet", lmargin1=25, lmargin2=45)
chat_history.tag_configure("md_number", lmargin1=25, lmargin2=45)
chat_history.tag_configure("md_alpha", lmargin1=45, lmargin2=65)
chat_history.tag_configure("md_quote", foreground="#b8b8b8", lmargin1=25, lmargin2=45, spacing1=2, spacing3=2)
chat_history.tag_configure("md_quote_bar", foreground="#7f848e", font=("Arial", 12, "bold"))
chat_history.tag_configure("md_table", font=("Consolas", 11), foreground="#dcdcdc", background="#2D2F31")

# wyrównanie użytkownika do prawej
chat_history.tag_configure("align_right", justify="right", rmargin=20, lmargin1=120, lmargin2=120)

# Obsługa wyboru konwersacji
def on_conv_select(evt):
    global current_conv_file
    if not conv_listbox.curselection():
        return
    idx = conv_listbox.curselection()[0]
    name = conv_listbox.get(idx)
    path = os.path.join(history_folder, name)
    if os.path.exists(path):
        load_conversation_from_file(path)

conv_listbox.bind('<<ListboxSelect>>', on_conv_select)

# Nowa rozmowa
def on_new_conversation():
    clear_chat()

new_conv_btn.config(command=on_new_conversation)

# Usuwanie z potwierdzeniem
def on_delete_conversation():
    global current_conv_file
    if not conv_listbox.curselection():
        return
    idx = conv_listbox.curselection()[0]
    name = conv_listbox.get(idx)
    path = os.path.join(history_folder, name)
    if not os.path.exists(path):
        refresh_conversation_listbox()
        return

    ans = messagebox.askyesno("Usuń konwersację", f"Czy na pewno chcesz usunąć konwersację:\n\n{name}\n\n?")
    if not ans:
        return

    try:
        os.remove(path)
    except Exception as e:
        print("Nie udało się usunąć:", e)

    refresh_conversation_listbox()
    if current_conv_file and os.path.basename(current_conv_file) == name:
        clear_chat()

delete_conv_btn.config(command=on_delete_conversation)

# Search binding
def on_search_change(*args):
    refresh_conversation_listbox()

search_var.trace_add("write", on_search_change)

# Inicjalne wczytanie listy i usage
refresh_conversation_listbox()
threading.Thread(target=get_usage, daemon=True).start()

root.mainloop()
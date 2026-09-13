from __future__ import annotations

import re
import tkinter as tk
import webbrowser


class MarkdownRenderer:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.link_counter = 0
        self.copy_button_counter = 0

    def configure_tags(self, widget: tk.Text) -> None:
        widget.tag_configure(
            "user_tag",
            foreground="lightgreen",
            font=("Arial", 12, "bold")
        )

        widget.tag_configure(
            "bot_tag",
            foreground="violet",
            font=("Arial", 12, "bold")
        )

        widget.tag_configure(
            "md_h1",
            font=("Arial", 18, "bold"),
            foreground="#dcdcdc"
        )

        widget.tag_configure(
            "md_h2",
            font=("Arial", 16, "bold"),
            foreground="#dcdcdc"
        )

        widget.tag_configure(
            "md_h3",
            font=("Arial", 14, "bold"),
            foreground="#dcdcdc"
        )

        widget.tag_configure(
            "md_bold",
            font=("Arial", 12, "bold")
        )

        widget.tag_configure(
            "md_italic",
            font=("Arial", 12, "italic")
        )

        widget.tag_configure(
            "md_code",
            font=("Consolas", 11),
            background="#2d2d2d",
            foreground="#ffd700"
        )

        widget.tag_configure(
            "md_bullet",
            lmargin1=25,
            lmargin2=45
        )

        widget.tag_configure(
            "md_number",
            lmargin1=25,
            lmargin2=45
        )

        widget.tag_configure(
            "md_alpha",
            lmargin1=45,
            lmargin2=65
        )

        widget.tag_configure(
            "md_quote",
            foreground="#b8b8b8",
            lmargin1=25,
            lmargin2=45,
            spacing1=2,
            spacing3=2
        )

        widget.tag_configure(
            "md_quote_bar",
            foreground="#7f848e",
            font=("Arial", 12, "bold")
        )

        widget.tag_configure(
            "md_table",
            font=("Consolas", 11),
            foreground="#dcdcdc",
            background="#2d2f31"
        )

        widget.tag_configure(
            "align_right",
            justify="right",
            rmargin=20,
            lmargin1=120,
            lmargin2=120
        )

        widget.tag_configure(
            "sel",
            background="#4169a1",
            foreground="#ffffff"
        )

        try:
            widget.tag_raise("sel")
        except tk.TclError:
            pass

    def open_link(self, url: str) -> None:
        try:
            webbrowser.open_new_tab(url)
        except Exception as error:
            print("Błąd otwierania linku:", error)

    def add_link(
        self,
        widget: tk.Text,
        text: str,
        url: str
    ) -> None:
        start = widget.index(tk.INSERT)

        widget.insert(tk.INSERT, text)

        end = widget.index(tk.INSERT)
        tag_name = f"link_{self.link_counter}"
        self.link_counter += 1

        widget.tag_add(tag_name, start, end)
        widget.tag_configure(
            tag_name,
            foreground="#4ea1ff",
            underline=True
        )

        widget.tag_bind(
            tag_name,
            "<Button-1>",
            lambda event: self.open_link(url)
        )

        widget.tag_bind(
            tag_name,
            "<Enter>",
            lambda event: widget.config(cursor="hand2")
        )

        widget.tag_bind(
            tag_name,
            "<Leave>",
            lambda event: widget.config(cursor="xterm")
        )

    def parse_inline(self, text: str) -> list[tuple]:
        segments = []
        index = 0

        while index < len(text):
            remaining = text[index:]

            markdown_link = re.match(
                r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
                remaining
            )

            if markdown_link:
                segments.append(
                    (
                        "link",
                        markdown_link.group(1),
                        markdown_link.group(2)
                    )
                )
                index += markdown_link.end()
                continue

            if text[index] == "`":
                end = text.find("`", index + 1)

                if end != -1:
                    segments.append(
                        ("code", text[index + 1:end])
                    )
                    index = end + 1
                    continue

            if text[index:index + 2] == "**":
                end = text.find("**", index + 2)

                if end != -1:
                    segments.append(
                        ("bold", text[index + 2:end])
                    )
                    index = end + 2
                    continue

            if text[index] == "*":
                end = text.find("*", index + 1)

                if end != -1:
                    segments.append(
                        ("italic", text[index + 1:end])
                    )
                    index = end + 1
                    continue

            raw_url = re.match(
                r"https?://[^\s<>\"]+",
                remaining
            )

            if raw_url:
                url = raw_url.group(0)
                visible_url = url.rstrip(".,;:!?)]}")

                segments.append(
                    ("link", visible_url, visible_url)
                )

                index += len(url)
                continue

            special_positions = []

            for marker in (
                "[",
                "`",
                "*",
                "http://",
                "https://"
            ):
                position = text.find(marker, index + 1)

                if position != -1:
                    special_positions.append(position)

            next_position = (
                min(special_positions)
                if special_positions
                else len(text)
            )

            segments.append(
                ("text", text[index:next_position])
            )

            index = next_position

        return segments

    def insert_inline(
        self,
        widget: tk.Text,
        text: str
    ) -> None:
        for segment in self.parse_inline(text):
            segment_type = segment[0]

            if segment_type == "text":
                widget.insert(tk.INSERT, segment[1])

            elif segment_type == "bold":
                widget.insert(
                    tk.INSERT,
                    segment[1],
                    "md_bold"
                )

            elif segment_type == "italic":
                widget.insert(
                    tk.INSERT,
                    segment[1],
                    "md_italic"
                )

            elif segment_type == "code":
                widget.insert(
                    tk.INSERT,
                    segment[1],
                    "md_code"
                )

            elif segment_type == "link":
                self.add_link(
                    widget,
                    segment[1],
                    segment[2]
                )

    def is_table_separator(self, line: str) -> bool:
        stripped = line.strip()

        if "|" not in stripped:
            return False

        cells = [
            cell.strip()
            for cell in stripped.strip("|").split("|")
        ]

        return bool(cells) and all(
            re.match(r"^:?-{3,}:?$", cell)
            for cell in cells
            if cell
        )

    def parse_table(
        self,
        lines: list[str],
        start: int
    ) -> tuple[int, str | None]:
        if start + 1 >= len(lines):
            return 0, None

        header = lines[start]
        separator = lines[start + 1]

        if "|" not in header:
            return 0, None

        if not self.is_table_separator(separator):
            return 0, None

        rows = [header]
        index = start + 2

        while index < len(lines):
            line = lines[index]

            if "|" not in line or not line.strip():
                break

            rows.append(line)
            index += 1

        parsed_rows = [
            [
                cell.strip()
                for cell in row.strip().strip("|").split("|")
            ]
            for row in rows
        ]

        column_count = max(
            len(row)
            for row in parsed_rows
        )

        for row in parsed_rows:
            while len(row) < column_count:
                row.append("")

        widths = [0] * column_count

        for row in parsed_rows:
            for column, cell in enumerate(row):
                widths[column] = max(
                    widths[column],
                    len(cell)
                )

        output = []

        output.append(
            " | ".join(
                cell.ljust(widths[column])
                for column, cell in enumerate(parsed_rows[0])
            )
        )

        output.append(
            "-+-".join("-" * width for width in widths)
        )

        for row in parsed_rows[1:]:
            output.append(
                " | ".join(
                    cell.ljust(widths[column])
                    for column, cell in enumerate(row)
                )
            )

        return len(rows) + 1, "\n".join(output) + "\n"

    def insert_code_block(
        self,
        widget: tk.Text,
        code: str
    ) -> None:
        widget.insert(tk.INSERT, "\n")

        button = tk.Button(
            widget,
            text="Kopiuj kod",
            font=("Arial", 9, "bold"),
            bg="#3a3d41",
            fg="white",
            activebackground="#4a4d52",
            activeforeground="white",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            command=lambda: self.copy_to_clipboard(code)
        )

        widget.window_create(
            tk.INSERT,
            window=button
        )

        widget.insert(tk.INSERT, "\n")

        start = widget.index(tk.INSERT)

        widget.insert(
            tk.INSERT,
            code.rstrip() + "\n"
        )

        end = widget.index(tk.INSERT)

        tag_name = (
            f"codeblock_{self.copy_button_counter}"
        )
        self.copy_button_counter += 1

        widget.tag_add(tag_name, start, end)
        widget.tag_configure(
            tag_name,
            font=("Consolas", 11),
            background="#2d2f31",
            foreground="#ffffff",
            lmargin1=20,
            lmargin2=20,
            rmargin=20,
            spacing1=4,
            spacing3=8
        )

        widget.insert(tk.INSERT, "\n")

    def copy_to_clipboard(self, text: str) -> None:
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
        except Exception as error:
            print("Błąd kopiowania do schowka:", error)

    def insert_markdown(
        self,
        widget: tk.Text,
        content: str
    ) -> None:
        lines = content.splitlines()
        code_lines = []
        in_code_block = False
        index = 0

        while index < len(lines):
            line = lines[index]
            stripped = line.strip()

            if stripped.startswith("```"):
                if in_code_block:
                    self.insert_code_block(
                        widget,
                        "\n".join(code_lines)
                    )
                    code_lines = []
                    in_code_block = False
                else:
                    in_code_block = True

                index += 1
                continue

            if in_code_block:
                code_lines.append(line)
                index += 1
                continue

            consumed, table = self.parse_table(lines, index)

            if consumed and table:
                widget.insert(
                    tk.INSERT,
                    table,
                    "md_table"
                )
                widget.insert(tk.INSERT, "\n")
                index += consumed
                continue

            if stripped.startswith("### "):
                widget.insert(
                    tk.INSERT,
                    stripped[4:] + "\n",
                    "md_h3"
                )
                index += 1
                continue

            if stripped.startswith("## "):
                widget.insert(
                    tk.INSERT,
                    stripped[3:] + "\n",
                    "md_h2"
                )
                index += 1
                continue

            if stripped.startswith("# "):
                widget.insert(
                    tk.INSERT,
                    stripped[2:] + "\n",
                    "md_h1"
                )
                index += 1
                continue

            if stripped.startswith(">"):
                quote = re.sub(
                    r"^>\s?",
                    "",
                    stripped
                )

                widget.insert(
                    tk.INSERT,
                    "▌ ",
                    "md_quote_bar"
                )

                self.insert_inline(widget, quote)
                widget.insert(
                    tk.INSERT,
                    "\n",
                    "md_quote"
                )

                index += 1
                continue

            if stripped.startswith("- ") or stripped.startswith("* "):
                widget.insert(
                    tk.INSERT,
                    "• ",
                    "md_bullet"
                )

                self.insert_inline(
                    widget,
                    stripped[2:]
                )

                widget.insert(
                    tk.INSERT,
                    "\n",
                    "md_bullet"
                )

                index += 1
                continue

            numbered = re.match(
                r"^(\d+\.)\s+(.*)",
                stripped
            )

            if numbered:
                widget.insert(
                    tk.INSERT,
                    numbered.group(1) + " ",
                    "md_number"
                )

                self.insert_inline(
                    widget,
                    numbered.group(2)
                )

                widget.insert(
                    tk.INSERT,
                    "\n",
                    "md_number"
                )

                index += 1
                continue

            alphabetic = re.match(
                r"^([A-Za-z][.)])\s+(.*)",
                stripped
            )

            if alphabetic:
                widget.insert(
                    tk.INSERT,
                    alphabetic.group(1) + " ",
                    "md_alpha"
                )

                self.insert_inline(
                    widget,
                    alphabetic.group(2)
                )

                widget.insert(
                    tk.INSERT,
                    "\n",
                    "md_alpha"
                )

                index += 1
                continue

            if not stripped:
                widget.insert(tk.INSERT, "\n")
            else:
                self.insert_inline(widget, line)
                widget.insert(tk.INSERT, "\n")

            index += 1

        if in_code_block and code_lines:
            self.insert_code_block(
                widget,
                "\n".join(code_lines)
            )
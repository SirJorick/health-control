import tkinter as tk
from tkinter import ttk, messagebox
import json
import os

def load_lab_tests():
    """Load lab tests from lab_tests.json and return a list of test names."""
    try:
        with open("lab_tests.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            tests = data.get("common_tests", [])
            # Extract only the test names (if tests are objects)
            names = []
            for test in tests:
                if isinstance(test, dict):
                    names.append(test.get("name", ""))
                else:
                    names.append(str(test))
            return names
    except Exception as e:
        messagebox.showerror("Error", f"Could not load lab_tests.json: {e}")
        return []

def copy_selected_text():
    """Copy the selected text from the Text widget to the clipboard."""
    try:
        selected_text = text_widget.get(tk.SEL_FIRST, tk.SEL_LAST)
        root.clipboard_clear()
        root.clipboard_append(selected_text)
    except tk.TclError:
        # No text selected
        pass

def show_context_menu(event):
    """Show right-click context menu."""
    context_menu.tk_popup(event.x_root, event.y_root)

# Create main window
root = tk.Tk()
root.title("Lab Tests List")
root.geometry("500x600")

# Create a Text widget with a vertical scrollbar using a smaller font
text_widget = tk.Text(root, wrap="word", font=("Arial", 10))
scrollbar = ttk.Scrollbar(root, command=text_widget.yview)
text_widget.configure(yscrollcommand=scrollbar.set)
text_widget.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

# Load lab test names from JSON file
lab_test_names = load_lab_tests()

# Sort the test names alphabetically
lab_test_names = sorted(lab_test_names)

# Get count of tests
count = len(lab_test_names)

# Insert the count and lab test names into the Text widget
text_widget.insert(tk.END, f"Total Lab Tests: {count}\n\n")
for name in lab_test_names:
    text_widget.insert(tk.END, name + "\n")

# Create a context menu with a Copy command
context_menu = tk.Menu(root, tearoff=0)
context_menu.add_command(label="Copy", command=copy_selected_text)

# Bind right-click (Button-3) event to show the context menu
text_widget.bind("<Button-3>", show_context_menu)

root.mainloop()

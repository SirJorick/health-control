import tkinter as tk
from tkinter import scrolledtext, messagebox
import json
import os

def list_disease_names(json_file, text_widget):
    # Check if the file exists
    if not os.path.exists(json_file):
        text_widget.insert(tk.END, f"Error: The file '{json_file}' does not exist.\n")
        return

    # Load the JSON data with explicit encoding
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        text_widget.insert(tk.END, f"Error reading JSON file: {e}\n")
        return

    # Assume data is a dictionary where keys are disease IDs
    diseases = list(data.keys())
    diseases.sort()

    # Insert the count at the top
    text_widget.insert(tk.END, f"Total Diseases: {len(diseases)}\n\n")

    # Insert each formatted disease name (one per line) into the Text widget
    for disease in diseases:
        formatted_name = " ".join(word.capitalize() for word in disease.split("_"))
        text_widget.insert(tk.END, formatted_name + "\n")

def copy_selection():
    try:
        selected_text = text_widget.get(tk.SEL_FIRST, tk.SEL_LAST)
        root.clipboard_clear()
        root.clipboard_append(selected_text)
    except tk.TclError:
        # No text selected
        pass

def show_context_menu(event):
    context_menu.tk_popup(event.x_root, event.y_root)

def main():
    global root, text_widget, context_menu

    # Create main window
    root = tk.Tk()
    root.title("Disease List")
    root.geometry("500x600")

    # Create a scrolled text widget with a smaller font and word wrapping enabled
    text_widget = scrolledtext.ScrolledText(root, wrap="word", font=("Arial", 10))
    text_widget.pack(fill="both", expand=True)

    # Create a context menu for right-click copy
    context_menu = tk.Menu(root, tearoff=0)
    context_menu.add_command(label="Copy", command=copy_selection)
    text_widget.bind("<Button-3>", show_context_menu)

    # Load and list disease names from the JSON file (e.g., "symptoms.json")
    json_file = "symptoms.json"
    list_disease_names(json_file, text_widget)

    root.mainloop()

if __name__ == "__main__":
    main()

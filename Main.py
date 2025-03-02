import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkfont
import json
import threading
import re
import requests
import socket  # For checking Tor
from bs4 import BeautifulSoup
from PIL import Image, ImageTk
import io
import urllib.parse
import os
import webbrowser
import subprocess
import pyttsx3  # For text-to-speech
# For TF-IDF:
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pythoncom  # For COM initialization in TTS threads
import textwrap
import time  # For debouncing

# --- Configuration File Handling ---
CONFIG_FILE = "gui_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print("[DEBUG] Error loading config:", e)
    return {}

def save_config():
    config = {
        "geometry": root.geometry(),
        "left_frame_width": left_frame.winfo_width(),
        "right_frame_width": right_frame.winfo_width(),
        "right_frame_height": right_frame.winfo_height(),
        "image_frame_width": image_frame.winfo_width(),
        "pitch_scale": pitch_scale.get(),
        "speed_scale": speed_scale.get(),
        "speak_enabled": speak_enabled_var.get(),
        "last_search": additional_search_var.get() if additional_search_var is not None else "",
        "last_disease": diagnosis_label.cget("text"),
        "last_diagnosis_results": last_results  # Save the last computed diagnosis ranking
    }
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
    except Exception as e:
        print("[DEBUG] Error saving config:", e)

# --- Feedback File Handling ---
FEEDBACK_FILE = "feedback.json"

def load_feedback():
    if os.path.exists(FEEDBACK_FILE):
        try:
            with open(FEEDBACK_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print("[DEBUG] Error loading feedback:", e)
    return {}

def save_feedback(feedback):
    try:
        with open(FEEDBACK_FILE, "w") as f:
            json.dump(feedback, f)
    except Exception as e:
        print("[DEBUG] Error saving feedback:", e)

# --- Check if Tor is running ---
def is_tor_running(port=9050):
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=2)
        s.close()
        return True
    except Exception:
        return False

# --- Load lab test keywords (with descriptions) from external JSON file ---
try:
    with open("lab_tests.json", "r", encoding="utf-8") as f:
        lab_tests_data = json.load(f)
        common_tests = lab_tests_data.get("common_tests", [])
except Exception as e:
    print("[DEBUG] Error loading lab tests:", e)
    common_tests = []

# Global variables for additional search and TTS
additional_search_var = None
current_tts_engine = None

# Global progress variables
dynamic_progress = 0
search_in_progress = False
dynamic_after_id = None
narration_after_id = None
preview_after_id = None

diagnosis_search_in_progress = False
diagnosis_dynamic_progress = 0
diagnosis_after_id = None

# Global variable to hold last diagnosis results
last_results = []

# --- Create Root Window and load config ---
root = tk.Tk()
config = load_config()
root.geometry(config.get("geometry", "1700x900"))
root.title("Advanced Disease Diagnosis")

# --- Top Panel: External Scripts Buttons ---
top_buttons_frame = tk.Frame(root)
top_buttons_frame.pack(side="top", fill="x")

button_labtests = tk.Button(top_buttons_frame, text="List All Lab Tests",
                            command=lambda: subprocess.Popen(["python", "list_all_labtest.py"]))
button_labtests.pack(side="left", padx=5, pady=5)

button_diseases = tk.Button(top_buttons_frame, text="List Down Disease",
                            command=lambda: subprocess.Popen(["python", "list_down_disease.py"]))
button_diseases.pack(side="left", padx=5, pady=5)

# --- Top Image Functions ---
def fetch_top_image(disease):
    query = disease.replace("_", " ")
    url = "https://www.google.com/search?tbm=isch&q=" + urllib.parse.quote(query)
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        imgs = soup.find_all("img")
        for img in imgs:
            src = img.get("data-src") or img.get("src")
            if src and src.startswith("http"):
                return src
    except Exception as e:
        print("Error fetching top image:", e)
    return None

def display_top_image(disease):
    for widget in images_tab.winfo_children():
        widget.destroy()
    top_image_url = fetch_top_image(disease)
    if top_image_url:
        try:
            r = requests.get(top_image_url, timeout=5)
            image = Image.open(io.BytesIO(r.content))
            max_size = (500, 500)
            image.thumbnail(max_size, Image.ANTIALIAS)
            photo = ImageTk.PhotoImage(image)
            label = tk.Label(images_tab, image=photo)
            label.image = photo
            label.pack()
        except Exception as e:
            print("Error processing top image:", e)
    else:
        print("No top image found.")

# --- Web Output Formatting Helper ---
def format_web_output(text):
    """Indent non-heading lines to improve readability in the Web output."""
    lines = text.split("\n")
    formatted_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped == "" or stripped.endswith(":"):
            formatted_lines.append(stripped)
        else:
            formatted_lines.append("    " + stripped)
    return "\n".join(formatted_lines)

# --- Cleaning Helper ---
def clean_text(text):
    text = text.replace("…", "...")
    text = re.sub(r'\.{2,}', '. ', text)
    text = re.sub(r'(?<![A-Za-z0-9])\.(?![A-Za-z0-9])', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# --- Revised Search Functions ---
def new_fetch_html(url, headers):
    proxies = {}
    if is_tor_running():
        proxies = {
            "http": "socks5h://127.0.0.1:9050",
            "https": "socks5h://127.0.0.1:9050"
        }
    try:
        resp = requests.get(url, headers=headers, proxies=proxies, timeout=15)
        print(f"[DEBUG] GET {url} returned {resp.status_code}")
        if resp.status_code != 200 or "unusual traffic" in resp.text.lower():
            raise Exception("Blocked or non-200 response")
        return resp.text
    except Exception as e:
        print(f"[DEBUG] Request failed for {url}: {e}")
        return ""

def new_format_text(text):
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return "\n".join(sentence.strip() for sentence in sentences if sentence)

def new_fetch_web_details_duckduckgo(query):
    query_str = query + " uses"
    query_encoded = urllib.parse.quote(query_str)
    url = "https://html.duckduckgo.com/html/?q=" + query_encoded
    headers = {"User-Agent": "Mozilla/5.0"}
    print(f"[DEBUG] DuckDuckGo query: {query_str}")
    html = new_fetch_html(url, headers)
    snippets = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for result in soup.find_all("div", class_="result"):
            snippet_elem = result.find("a", class_="result__snippet") or result.find("div", class_="result__snippet")
            if snippet_elem:
                text = snippet_elem.get_text().strip()
                if text and len(text.split()) > 5:
                    snippets.append(text)
            if len(snippets) >= 5:
                break
    if snippets:
        return "\n".join(new_format_text(s) for s in snippets)
    else:
        return "No additional web details found."

def new_fetch_web_details_google(query):
    query_encoded = urllib.parse.quote(query)
    url = "https://www.google.com/search?q=" + query_encoded
    headers = {"User-Agent": "Mozilla/5.0"}
    print(f"[DEBUG] Google query: {query}")
    html = new_fetch_html(url, headers)
    snippets = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for snippet in soup.find_all("div", class_="BNeawe"):
            text = snippet.get_text().strip()
            if text and len(text.split()) > 5:
                snippets.append(text)
            if len(snippets) >= 5:
                break
    if snippets:
        return "\n".join(new_format_text(s) for s in snippets)
    return ""

def new_fetch_web_details_tor(query):
    tor_port = 9050
    proxies = {
        "http": f"socks5h://127.0.0.1:{tor_port}",
        "https": f"socks5h://127.0.0.1:{tor_port}"
    }
    query_encoded = urllib.parse.quote(query)
    url = "https://www.google.com/search?q=" + query_encoded
    headers = {"User-Agent": "Mozilla/5.0"}
    print(f"[DEBUG] Tor query: {query}")
    try:
        resp = requests.get(url, headers=headers, proxies=proxies, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            snippets = []
            for snippet in soup.find_all("div", class_="BNeawe"):
                text = snippet.get_text().strip()
                if text and len(text.split()) > 5:
                    snippets.append(text)
                if len(snippets) >= 5:
                    break
            if snippets:
                return "\n".join(new_format_text(s) for s in snippets)
        return ""
    except Exception as e:
        print(f"[DEBUG] Tor request failed: {e}")
        return ""

def new_fetch_images_google(query):
    query_encoded = urllib.parse.quote(query)
    url = "https://www.google.com/search?tbm=isch&q=" + query_encoded
    headers = {"User-Agent": "Mozilla/5.0"}
    print(f"[DEBUG] Fetching images from Google for: {query}")
    html = new_fetch_html(url, headers)
    results = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a['href']
            if href.startswith("/imgres?"):
                parsed = urllib.parse.urlparse(href)
                params = urllib.parse.parse_qs(parsed.query)
                if 'imgurl' in params and 'imgrefurl' in params:
                    img_url = params['imgurl'][0]
                    site_link = params['imgrefurl'][0]
                    results.append((img_url, site_link))
            if len(results) >= 20:
                break
        if not results:
            for img in soup.find_all("img"):
                src = img.get("src")
                if src and src.startswith("http"):
                    results.append((src, query))
                if len(results) >= 20:
                    break
    else:
        print("[DEBUG] Error fetching images.")
    return results

def create_scrollable_frame(parent):
    canvas = tk.Canvas(parent)
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill=tk.BOTH, expand=True)
    scrollbar.pack(side="right", fill=tk.Y)
    return scrollable_frame, canvas, scrollbar

# --- Function to Copy Image to Clipboard ---
def copy_image_to_clipboard(pil_image):
    try:
        from io import BytesIO
        import win32clipboard
        import win32con
    except ImportError:
        messagebox.showerror("Error",
                             "PyWin32 is not available.\nPlease install it with 'pip install pywin32' to copy images to clipboard.")
        print("[DEBUG] PyWin32 module not found.")
        return
    try:
        output = BytesIO()
        pil_image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]
        output.close()
        print("[DEBUG] Image data converted to BMP format.")
        win32clipboard.OpenClipboard()
        print("[DEBUG] Clipboard opened.")
        win32clipboard.EmptyClipboard()
        print("[DEBUG] Clipboard emptied.")
        win32clipboard.SetClipboardData(win32con.CF_DIB, data)
        print("[DEBUG] Clipboard data set with image.")
        win32clipboard.CloseClipboard()
        print("[DEBUG] Clipboard closed.")
        print("[DEBUG] Image copied to clipboard successfully.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to copy image to clipboard: {e}")
        print("[DEBUG] Failed to copy image to clipboard:", e)

def on_image_left_click(url):
    webbrowser.open(url)

def on_image_right_click(event, pil_img):
    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="Copy Selected Image", command=lambda: copy_image_to_clipboard(pil_img))
    menu.tk_popup(event.x_root, event.y_root)

def update_dynamic_progress():
    global dynamic_progress, search_in_progress, dynamic_after_id
    if search_in_progress:
        dynamic_progress += 0.5
        secondary_progress_bar.config(value=dynamic_progress)
        secondary_progress_label.config(text=f"Overall: {dynamic_progress:.0f}%")
        dynamic_after_id = root.after(200, update_dynamic_progress)

def update_diagnosis_progress():
    global diagnosis_dynamic_progress, diagnosis_search_in_progress, diagnosis_after_id
    if diagnosis_search_in_progress:
        diagnosis_dynamic_progress += 1
        if diagnosis_dynamic_progress > 100:
            diagnosis_dynamic_progress = 100
        diagnosis_progress_bar.config(value=diagnosis_dynamic_progress)
        diagnosis_progress_label.config(text=f"Progress: {diagnosis_dynamic_progress}%")
        diagnosis_after_id = root.after(200, update_diagnosis_progress)

# --- New Function: Search Tests for Selected Disease via Web Search ---
def search_tests_for_disease():
    disease = diagnosis_label.cget("text")
    if not disease:
        messagebox.showinfo("Info", "No disease selected.")
        return
    global diagnosis_search_in_progress, diagnosis_dynamic_progress
    diagnosis_search_in_progress = True
    diagnosis_dynamic_progress = 0
    update_diagnosis_progress()
    query = "lab tests for " + disease
    duck_results = new_fetch_web_details_duckduckgo(query)
    google_results = new_fetch_web_details_google(query)
    tor_results = new_fetch_web_details_tor(query)
    combined = "\n".join([duck_results, google_results, tor_results])
    combined_lower = combined.lower()

    for item in diagnosis_tree.get_children():
        diagnosis_tree.delete(item)

    matching_tests = []
    for test in common_tests:
        test_name = test.get("name", "").lower()
        if test_name in combined_lower:
            matching_tests.append(test)

    if matching_tests:
        for test in matching_tests:
            raw_desc = test.get("description", "")
            clean_desc = clean_text(raw_desc)
            wrapped_desc = "\n\n".join(textwrap.wrap(clean_desc, width=50))
            diagnosis_tree.insert("", "end", values=(test.get("name"), wrapped_desc))
    else:
        heuristic_keywords = ["test", "panel", "scan", "imaging", "antibody", "antigen"]
        heuristic_matches = []
        for line in combined.splitlines():
            if any(kw in line.lower() for kw in heuristic_keywords):
                cleaned_line = clean_text(line)
                heuristic_matches.append(cleaned_line)
        if heuristic_matches:
            for match in heuristic_matches:
                diagnosis_tree.insert("", "end", values=(match, "Scraped from web"))
        else:
            diagnosis_tree.insert("", "end", values=("No matching lab tests found", ""))

    diagnosis_search_in_progress = False
    diagnosis_progress_bar.config(value=100)
    diagnosis_progress_label.config(text="Progress: 100%")

# --- Speech Helpers ---
def stop_current_speech():
    global current_tts_engine
    if current_tts_engine is not None:
        try:
            current_tts_engine.stop()
        except Exception as e:
            print("[DEBUG] Error stopping TTS engine:", e)
        current_tts_engine = None

def speak_text(text):
    global current_tts_engine
    stop_current_speech()
    pythoncom.CoInitialize()
    engine = pyttsx3.init()
    current_tts_engine = engine
    speed_value = speed_scale.get()
    engine.setProperty("rate", speed_value)
    pitch_value = pitch_scale.get()
    if pitch_value == 0:
        pitch_str = "default"
    elif pitch_value > 0:
        pitch_str = f"+{pitch_value}%"
    else:
        pitch_str = f"{pitch_value}%"
    ssml_text = f'<speak><prosody pitch="{pitch_str}">{text}</prosody></speak>'
    engine.say(ssml_text)
    try:
        engine.runAndWait()
    except Exception as e:
        print("[DEBUG] TTS error:", e)
    engine.stop()
    pythoncom.CoUninitialize()
    current_tts_engine = None

# --- Revised Search Thread (for Disease Selection) ---
def revised_fetch_web_info_threaded():
    global search_in_progress, dynamic_progress, dynamic_after_id
    stop_current_speech()
    if not tree_diagnosis.selection():
        return
    text_web.delete("1.0", tk.END)
    progress_bar.config(value=0)
    progress_label.config(text="Searching...")
    secondary_progress_bar.config(value=0)
    secondary_progress_label.config(text="Overall: 0%")
    for widget in images_tab.winfo_children():
        widget.destroy()
    search_in_progress = True
    dynamic_progress = 0
    update_dynamic_progress()
    item = tree_diagnosis.selection()[0]
    disease = tree_diagnosis.item(item, "values")[0]
    print(f"[DEBUG] Revised search thread started for disease: {disease}")
    display_top_image(disease)
    root.update()
    details = new_fetch_web_details_duckduckgo(disease)
    formatted_details = format_web_output(details)
    text_web.insert(tk.END, formatted_details)
    if "No additional web details found." in details:
        google_details = new_fetch_web_details_google(disease)
        if google_details:
            text_web.insert(tk.END, "\n" + format_web_output(google_details))
        tor_details = new_fetch_web_details_tor(disease)
        if tor_details:
            text_web.insert(tk.END, "\n" + format_web_output(tor_details))
    categories = [
        ("medication OR treatment", "Medication/Treatment"),
        ("dosage OR mg OR milligram OR capsule OR tablet OR UI", "Dosage"),
        ("herbal OR natural remedy", "Herbal"),
        ("alternative medicine OR alternative treatment", "Alternative"),
        ("how to prepare OR recipe OR formulation", "How to Prepare")
    ]
    for keyword, title in categories:
        cat_summary = new_fetch_web_details_duckduckgo(f'"{disease}" {keyword}')
        text_web.insert(tk.END, f"\n{title}:\n" + format_web_output(cat_summary) + "\n")
    progress_bar.config(value=100)
    progress_label.config(text="Search completed.")
    image_results = new_fetch_images_google(disease)
    for widget in images_tab.winfo_children():
        widget.destroy()
    scrollable_frame, canvas, scrollbar = create_scrollable_frame(images_tab)
    photos = []
    columns = 4
    for index, (img_url, caption_text) in enumerate(image_results):
        try:
            img_resp = requests.get(img_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            pil_img = Image.open(io.BytesIO(img_resp.content))
            pil_img = pil_img.resize((175, 175))
            photo = ImageTk.PhotoImage(pil_img)
            photos.append(photo)
            container = tk.Frame(scrollable_frame, bd=1, relief=tk.RAISED)
            container.grid(row=index // columns, column=index % columns, padx=5, pady=5)
            img_label = tk.Label(container, image=photo, cursor="hand2")
            img_label.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            img_label.bind("<Button-1>", lambda e, url=caption_text: on_image_left_click(url))
            current_img = pil_img
            img_label.bind("<Button-3>", lambda e, img=current_img: on_image_right_click(e, img))
            cap = tk.Label(container, text=caption_text, fg="blue", cursor="hand2",
                           font=("Helvetica", 10, "underline"), wraplength=175)
            cap.pack(side=tk.BOTTOM, fill=tk.X)
            cap.bind("<Button-1>", lambda e, url=caption_text: on_image_left_click(url))
            cap.bind("<Button-3>", lambda e, img=current_img: on_image_right_click(e, img))
        except Exception as e:
            print("[DEBUG] Image error:", e)
    scrollable_frame.update_idletasks()
    canvas.config(scrollregion=canvas.bbox("all"))
    images_tab.photos = photos
    search_in_progress = False
    if dynamic_after_id is not None:
        root.after_cancel(dynamic_after_id)
        dynamic_after_id = None
    secondary_progress_bar.config(value=100)
    secondary_progress_label.config(text="Overall: 100%")
    print("[DEBUG] Revised search thread finished.")

# --- Additional Web Search (via Additional Search Bar) ---
def additional_web_search_thread(query):
    stop_current_speech()
    text_web.delete("1.0", tk.END)
    progress_bar.config(value=0)
    progress_label.config(text="Searching...")
    secondary_progress_bar.config(value=0)
    secondary_progress_label.config(text="Overall: 0%")
    for widget in images_tab.winfo_children():
        widget.destroy()
    details = new_fetch_web_details_duckduckgo(query)
    text_web.insert(tk.END, format_web_output(details))
    if "No additional web details found." in details:
        google_details = new_fetch_web_details_google(query)
        if google_details:
            text_web.insert(tk.END, "\n" + format_web_output(google_details))
        tor_details = new_fetch_web_details_tor(query)
        if tor_details:
            text_web.insert(tk.END, "\n" + format_web_output(tor_details))
    categories = [
        ("medication OR treatment", "Medication/Treatment"),
        ("dosage OR mg OR milligram OR capsule OR tablet OR UI", "Dosage"),
        ("herbal OR natural remedy", "Herbal"),
        ("alternative medicine OR alternative treatment", "Alternative"),
        ("how to prepare OR recipe OR formulation", "How to Prepare")
    ]
    for keyword, title in categories:
        cat_summary = new_fetch_web_details_duckduckgo(f'"{query}" {keyword}')
        text_web.insert(tk.END, f"\n{title}:\n" + format_web_output(cat_summary) + "\n")
    progress_bar.config(value=100)
    progress_label.config(text="Search completed.")
    image_results = new_fetch_images_google(query)
    for widget in images_tab.winfo_children():
        widget.destroy()
    scrollable_frame, canvas, scrollbar = create_scrollable_frame(images_tab)
    photos = []
    columns = 4
    for index, (img_url, caption_text) in enumerate(image_results):
        try:
            img_resp = requests.get(img_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            pil_img = Image.open(io.BytesIO(img_resp.content))
            pil_img = pil_img.resize((175, 175))
            photo = ImageTk.PhotoImage(pil_img)
            photos.append(photo)
            container = tk.Frame(scrollable_frame, bd=1, relief=tk.RAISED)
            container.grid(row=index // columns, column=index % columns, padx=5, pady=5)
            img_label = tk.Label(container, image=photo, cursor="hand2")
            img_label.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            img_label.bind("<Button-1>", lambda e, url=caption_text: on_image_left_click(url))
            current_img = pil_img
            img_label.bind("<Button-3>", lambda e, img=current_img: on_image_right_click(e, img))
            cap = tk.Label(container, text=caption_text, fg="blue", cursor="hand2",
                           font=("Helvetica", 10, "underline"), wraplength=175)
            cap.pack(side=tk.BOTTOM, fill=tk.X)
            cap.bind("<Button-1>", lambda e, url=caption_text: on_image_left_click(url))
            cap.bind("<Button-3>", lambda e, img=current_img: on_image_right_click(e, img))
        except Exception as e:
            print("[DEBUG] Image error:", e)
    scrollable_frame.update_idletasks()
    canvas.config(scrollregion=canvas.bbox("all"))
    images_tab.photos = photos
    secondary_progress_bar.config(value=100)
    secondary_progress_label.config(text="Overall: 100%")
    print("[DEBUG] Additional search finished.")

def additional_web_search():
    query = additional_search_var.get().strip()
    if query:
        threading.Thread(target=additional_web_search_thread, args=(query,), daemon=True).start()
    else:
        messagebox.showinfo("Info", "Please enter a search query.")

# --- Function to Speak Highlighted Web Search Result ---
def speak_highlighted():
    stop_current_speech()
    try:
        start_index = text_web.index("sel.first")
        end_index = text_web.index("sel.last")
        selected_text = text_web.get(start_index, end_index)
        if selected_text.strip():
            text_web.tag_configure("highlighted", background="lightblue")
            text_web.tag_add("highlighted", start_index, end_index)

            def speak_and_retain():
                speak_text(selected_text)
                root.after(0, lambda: text_web.tag_remove("highlighted", start_index, end_index))

            threading.Thread(target=speak_and_retain, daemon=True).start()
        else:
            messagebox.showinfo("Info", "Please select text in the web search result to speak.")
    except tk.TclError:
        messagebox.showinfo("Info", "Please select text in the web search result to speak.")

# --- Auto-complete and Symptom Functions ---
def select_symptom(event):
    item_id = tree_symptoms.focus()
    if item_id:
        symptom = tree_symptoms.item(item_id, "values")[0]
        autocomplete_entry.delete(0, tk.END)
        autocomplete_entry.insert(tk.END, symptom)

def remove_symptom(event):
    item_id = tree_symptoms.focus()
    if item_id:
        symptom = tree_symptoms.item(item_id, "values")[0]
        if symptom in selected_symptoms:
            selected_symptoms.remove(symptom)
        tree_symptoms.delete(item_id)
        update_diagnosis()

class AutocompleteEntry(tk.Entry):
    def __init__(self, symptom_list, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.symptom_list = symptom_list
        self.var = kwargs.get("textvariable", tk.StringVar())
        self.config(textvariable=self.var)
        self.var.trace('w', self.changed)
        self.bind("<Right>", self.selection)
        self.bind("<Down>", self.move_down)
        self.listbox = None

    def changed(self, name, index, mode):
        pattern = self.var.get().upper()
        if pattern == '':
            if self.listbox:
                self.listbox.destroy()
                self.listbox = None
        else:
            words = self.comparison()
            if words:
                if not self.listbox:
                    self.listbox = tk.Listbox(width=self["width"])
                    self.listbox.bind("<Double-Button-1>", self.selection)
                    self.listbox.bind("<Right>", self.selection)
                    x = self.winfo_x()
                    y = self.winfo_y() + self.winfo_height()
                    self.listbox.place(in_=self.master, x=x, y=y)
                self.listbox.delete(0, tk.END)
                for w in words:
                    self.listbox.insert(tk.END, w)
            else:
                if self.listbox:
                    self.listbox.destroy()
                    self.listbox = None

    def selection(self, event):
        if self.listbox:
            self.var.set(self.listbox.get(tk.ACTIVE))
            self.icursor(tk.END)
            self.listbox.destroy()
            self.listbox = None
        return "break"

    def move_down(self, event):
        if self.listbox:
            self.listbox.focus()
            self.listbox.selection_set(0)
        return "break"

    def comparison(self):
        pattern = self.var.get().upper()
        return [w for w in self.symptom_list if pattern in w]

def add_symptom():
    input_text = autocomplete_entry.get().strip().upper()
    if input_text:
        symptoms = input_text.split()
        added = False
        for symptom in symptoms:
            if symptom and symptom not in selected_symptoms:
                selected_symptoms.add(symptom)
                tree_symptoms.insert("", "end", values=(symptom,))
                added = True
        if not added:
            messagebox.showinfo("Info", "Symptom(s) already added.")
        autocomplete_entry.delete(0, tk.END)
        update_diagnosis()
    else:
        messagebox.showinfo("Info", "Please enter a symptom.")

# --- Function to show dropdown of all symptom options ---
def show_all_symptoms():
    if autocomplete_entry.listbox:
        autocomplete_entry.listbox.destroy()
    autocomplete_entry.listbox = tk.Listbox(width=autocomplete_entry["width"])
    autocomplete_entry.listbox.bind("<Double-Button-1>", autocomplete_entry.selection)
    autocomplete_entry.listbox.bind("<Right>", autocomplete_entry.selection)
    x = autocomplete_entry.winfo_x()
    y = autocomplete_entry.winfo_y() + autocomplete_entry.winfo_height()
    autocomplete_entry.listbox.place(in_=autocomplete_entry.master, x=x, y=y)
    autocomplete_entry.listbox.delete(0, tk.END)
    for word in symptom_options:
        autocomplete_entry.listbox.insert(tk.END, word)

# --- Functions for Single vs. Double Click on Disease ---
def narrate_disease_details():
    stop_current_speech()
    text_details.delete("1.0", tk.END)
    for item in diagnosis_tree.get_children():
        diagnosis_tree.delete(item)
    item = tree_diagnosis.focus()
    if item:
        values = tree_diagnosis.item(item, "values")
        disease = values[0].replace("_", " ")
        print(f"[DEBUG] Single-click: Narrating disease: {disease}")
        details = disease_data.get(disease.replace(" ", "_"), {})
        onset = details.get("onset", "N/A")
        notes = details.get("notes", "No description available.")
        symptoms_list = details.get("symptoms", [])
        detail_str = f"Disease: {disease}\nOnset: {onset}\n\nDescription:\n{notes}\n\nSymptoms:\n"
        for s in symptoms_list:
            name = s.get("name", "")
            desc = s.get("description", "No description")
            detail_str += f"    - {name}: {desc}\n"
        text_details.insert(tk.END, detail_str)
        diagnosis_label.config(text=disease)
        threading.Thread(target=search_tests_for_disease, daemon=True).start()
        if speak_enabled_var.get():
            threading.Thread(target=speak_text, args=(detail_str,), daemon=True).start()

def search_web_details():
    stop_current_speech()
    print("[DEBUG] Double-click: Searching web details")
    text_web.delete("1.0", tk.END)
    for widget in images_tab.winfo_children():
        widget.destroy()
    debounce_search()

# --- Debounce Implementation ---
debounce_delay = 500  # milliseconds
last_search_time = 0

def debounce_search():
    global last_search_time
    now = int(time.time() * 1000)
    if now - last_search_time > debounce_delay:
        last_search_time = now
        threading.Thread(target=revised_fetch_web_info_threaded, daemon=True).start()
    else:
        root.after(debounce_delay, lambda: threading.Thread(target=revised_fetch_web_info_threaded, daemon=True).start())

def on_single_click(event):
    global narration_after_id
    narration_after_id = root.after(300, narrate_disease_details)

def on_double_click(event):
    global narration_after_id
    if narration_after_id:
        root.after_cancel(narration_after_id)
        narration_after_id = None
    debounce_search()

def schedule_preview(event=None):
    global preview_after_id
    if preview_after_id:
        root.after_cancel(preview_after_id)
    preview_after_id = root.after(500, preview_speech)

def preview_speech():
    if speak_enabled_var.get():
        threading.Thread(target=lambda: speak_text("Preview"), daemon=True).start()

def on_speak_toggle_changed(*args):
    if not speak_enabled_var.get():
        stop_current_speech()

# --- Load Disease Data ---
with open("symptoms.json", "r", encoding="utf-8") as f:
    disease_data = json.load(f)

# Build the symptom options list in uppercase (avoiding duplicates)
symptom_options = set()
symptom_descriptions = {}
for details in disease_data.values():
    for symptom in details.get("symptoms", []):
        full_symptom = symptom["name"].strip().upper()
        symptom_options.add(full_symptom)
        for token in full_symptom.split():
            symptom_options.add(token)
        if full_symptom not in symptom_descriptions:
            symptom_descriptions[full_symptom] = symptom.get("description", "No description available.")
symptom_options = sorted(symptom_options)

# Prepare disease documents and TF-IDF matrix
disease_docs = {}
for disease, details in disease_data.items():
    doc = " ".join([(s["name"] + " " + s["description"]).lower() for s in details.get("symptoms", [])])
    disease_docs[disease] = doc

disease_names = list(disease_docs.keys())
corpus = [disease_docs[d] for d in disease_names]
vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b")
tfidf_matrix = vectorizer.fit_transform(corpus)

# --- Optional Training of a Disease Classifier ---
USE_CLASSIFIER = False  # Set to True to enable training

def train_disease_classifier():
    from sklearn.linear_model import LogisticRegression
    clf = LogisticRegression(max_iter=1000, multi_class='multinomial')
    clf.fit(tfidf_matrix, disease_names)
    return clf

classifier = None
if USE_CLASSIFIER:
    classifier = train_disease_classifier()

# --- Updated Matching Algorithm with 70/20/10 Weighting ---
# We assign: cosine_weight=0.7, f1_weight=0.2, classifier_weight=0.1
COSINE_WEIGHT = 0.7
F1_WEIGHT = 0.2
CLASSIFIER_WEIGHT = 0.1

def update_diagnosis():
    global last_results
    for item in tree_diagnosis.get_children():
        tree_diagnosis.delete(item)
    if not selected_symptoms:
        return
    selected_words = set()
    for phrase in selected_symptoms:
        selected_words.update(phrase.lower().split())
    total_selected_words = len(selected_words)
    query_doc = " ".join(selected_words)
    results = []
    feedback = load_feedback()  # Load feedback data
    if classifier is not None:
        X_query = vectorizer.transform([query_doc])
        probas = classifier.predict_proba(X_query)[0]
        query_vec = vectorizer.transform([query_doc])
        similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
        for i, disease in enumerate(disease_names):
            cp = probas[i]
            disease_words = set(disease_docs[disease].split())
            if total_selected_words > 0 and disease_words:
                match_count = len(selected_words.intersection(disease_words))
                recall = match_count / len(disease_words)
                precision = match_count / total_selected_words
                f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0
            else:
                f1 = 0
            final_score = (COSINE_WEIGHT * similarities[i] + F1_WEIGHT * f1 + CLASSIFIER_WEIGHT * cp) * 100
            # Boost based on past feedback (5% per confirmation)
            feedback_data = feedback.get(disease, None)
            if feedback_data:
                boost_factor = 1 + (feedback_data.get("count", 0) * 0.05)
                final_score *= boost_factor
            if final_score > 0:
                results.append((disease.replace("_", " "), final_score))
    else:
        query_vec = vectorizer.transform([query_doc])
        similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
        for i, disease in enumerate(disease_names):
            disease_words = set(disease_docs[disease].split())
            if not disease_words or total_selected_words == 0:
                continue
            match_count = len(selected_words.intersection(disease_words))
            recall = match_count / len(disease_words)
            precision = match_count / total_selected_words
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0
            final_score = ((COSINE_WEIGHT * similarities[i] + F1_WEIGHT * f1) / (COSINE_WEIGHT + F1_WEIGHT)) * 100
            # Boost based on past feedback (5% per confirmation)
            feedback_data = feedback.get(disease, None)
            if feedback_data:
                boost_factor = 1 + (feedback_data.get("count", 0) * 0.05)
                final_score *= boost_factor
            if final_score > 0:
                results.append((disease.replace("_", " "), final_score))
    results.sort(key=lambda x: x[1], reverse=True)
    last_results = results[:]  # Save the results for later use
    for disease, score in results:
        tree_diagnosis.insert("", "end", values=(disease, f"{score:.1f}%"))
    auto_fit_columns(tree_diagnosis)

# --- Function to Confirm Actual Disease (Feedback Recording) ---
def confirm_actual_disease():
    selected_item = tree_diagnosis.selection()
    if not selected_item:
        messagebox.showinfo("Info", "No disease selected.")
        return
    disease_display, score = tree_diagnosis.item(selected_item[0], "values")
    # Convert display name back to key form (with underscores)
    disease_key = disease_display.replace(" ", "_")
    feedback = load_feedback()
    if disease_key in feedback:
        feedback[disease_key]["count"] += 1
    else:
        feedback[disease_key] = {"count": 1}
    save_feedback(feedback)
    messagebox.showinfo("Feedback", f"Recorded feedback for {disease_display}.")

# --- GUI Layout ---
diagnosis_label_text = config.get("last_disease", "")
diagnosis_label = ttk.Label(None, text=diagnosis_label_text, font=("Helvetica", 16))

root.geometry(config.get("geometry", "1700x900"))
root.title("Advanced Disease Diagnosis")
root.attributes("-topmost", True)
root.after(100, lambda: root.attributes("-topmost", False))

speak_enabled_var = tk.BooleanVar(root, value=True)
if "speak_enabled" in config:
    speak_enabled_var.set(config["speak_enabled"])
speak_enabled_var.trace_add("write", on_speak_toggle_changed)

paned = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
paned.pack(fill=tk.BOTH, expand=True)

left_frame = ttk.Frame(paned, padding="10", width=config.get("left_frame_width", 500), borderwidth=2, relief="groove")
left_frame.pack_propagate(False)
paned.add(left_frame, weight=0)

right_frame = ttk.Frame(paned, padding="10", width=config.get("right_frame_width", 600),
                        height=config.get("right_frame_height", 400), borderwidth=2, relief="groove")
right_frame.pack_propagate(False)
paned.add(right_frame, weight=3)

image_frame = ttk.Frame(paned, padding="10", width=config.get("image_frame_width", 400), borderwidth=2, relief="groove")
image_frame.pack_propagate(False)
paned.add(image_frame, weight=1)

image_notebook = ttk.Notebook(image_frame)
image_notebook.pack(fill=tk.BOTH, expand=True)

images_tab = ttk.Frame(image_notebook)
image_notebook.add(images_tab, text="Images")

diagnosis_tab = ttk.Frame(image_notebook)
image_notebook.add(diagnosis_tab, text="Diagnosis")
diagnosis_label = ttk.Label(diagnosis_tab, text=diagnosis_label_text, font=("Helvetica", 16))
diagnosis_label.pack(padx=10, pady=10)
search_tests_button = ttk.Button(diagnosis_tab, text="Search Tests",
                                 command=lambda: threading.Thread(target=search_tests_for_disease, daemon=True).start())
search_tests_button.pack(padx=5, pady=5)
diagnosis_progress_frame = ttk.Frame(diagnosis_tab, borderwidth=2, relief="ridge")
diagnosis_progress_frame.pack(fill=tk.X, padx=5, pady=5)
diagnosis_progress_label = ttk.Label(diagnosis_progress_frame, text="Progress: 0%")
diagnosis_progress_label.pack(side=tk.LEFT)
diagnosis_progress_bar = ttk.Progressbar(diagnosis_progress_frame, orient="horizontal", mode="determinate", maximum=100)
diagnosis_progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
diagnosis_tree = ttk.Treeview(diagnosis_tab, columns=("Test", "Description"), show="headings", height=10)
diagnosis_tree.heading("Test", text="Required Test")
diagnosis_tree.heading("Description", text="Description")
diagnosis_tree.column("Test", width=200)
diagnosis_tree.column("Description", width=400)
diagnosis_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
if config.get("last_diagnosis_results"):
    for disease, score in config["last_diagnosis_results"]:
        diagnosis_tree.insert("", "end", values=(disease, f"{score:.1f}%"))
# --- Confirm Actual Disease Button ---
confirm_button = ttk.Button(diagnosis_tab, text="Confirm Actual Disease", command=confirm_actual_disease)
confirm_button.pack(pady=5)

notebook = ttk.Notebook(right_frame)
notebook.pack(fill=tk.BOTH, expand=True)

details_tab = ttk.Frame(notebook, padding="10")
notebook.add(details_tab, text="Details")
ttk.Label(details_tab, text="Selected Disease Details:").pack(anchor=tk.W)
text_details = tk.Text(details_tab, height=8, wrap=tk.WORD)
text_details.pack(fill=tk.BOTH, expand=True)

web_tab = ttk.Frame(notebook, padding="10")
notebook.add(web_tab, text="Web")
filter_frame = ttk.Frame(web_tab, borderwidth=2, relief="ridge")
filter_frame.pack(fill=tk.X, expand=False)
speak_button = ttk.Button(filter_frame, text="SPEAK", command=speak_highlighted, width=6)
speak_button.pack(side=tk.LEFT, padx=5, pady=2)
text_web = tk.Text(web_tab, wrap=tk.WORD)
text_web.pack(fill=tk.BOTH, expand=True)
text_web.tag_configure("highlighted", background="lightblue")
progress_frame = ttk.Frame(web_tab, borderwidth=2, relief="ridge")
progress_frame.pack(fill=tk.X, pady=5)
progress_label = ttk.Label(progress_frame, text="Idle")
progress_label.pack(side=tk.LEFT)
progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate", maximum=100)
progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
secondary_progress_frame = ttk.Frame(web_tab, borderwidth=2, relief="ridge")
secondary_progress_frame.pack(fill=tk.X, pady=5)
secondary_progress_label = ttk.Label(secondary_progress_frame, text="Overall: 0%")
secondary_progress_label.pack(side=tk.LEFT)
secondary_progress_bar = ttk.Progressbar(secondary_progress_frame, orient="horizontal", mode="determinate", maximum=100)
secondary_progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

control_frame = ttk.Frame(left_frame, padding="10", borderwidth=2, relief="ridge")
control_frame.pack(fill=tk.X, expand=True)

sliders_frame = ttk.Frame(control_frame)
sliders_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
pitch_scale = tk.Scale(sliders_frame, from_=-20, to=20, orient=tk.HORIZONTAL, label="Pitch (%)", resolution=1)
if "pitch_scale" in config:
    pitch_scale.set(config["pitch_scale"])
else:
    pitch_scale.set(0)
pitch_scale.pack(side=tk.LEFT, padx=5)
speed_scale = tk.Scale(sliders_frame, from_=100, to=300, orient=tk.HORIZONTAL, label="Speed", resolution=1)
if "speed_scale" in config:
    speed_scale.set(config["speed_scale"])
else:
    speed_scale.set(200)
speed_scale.pack(side=tk.LEFT, padx=5)
speak_toggle = ttk.Checkbutton(sliders_frame, text="Enable Speak", variable=speak_enabled_var)
speak_toggle.pack(side=tk.LEFT, padx=5)
pitch_scale.bind("<ButtonRelease-1>", schedule_preview)
speed_scale.bind("<ButtonRelease-1>", schedule_preview)

input_frame = ttk.Frame(control_frame)
input_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
ttk.Label(input_frame, text="Symptom:").pack(side=tk.LEFT)
autocomplete_entry = AutocompleteEntry(symptom_options, master=input_frame, textvariable=tk.StringVar(), width=30)
autocomplete_entry.pack(side=tk.LEFT, padx=5)
show_all_button = ttk.Button(input_frame, text="Show All", command=show_all_symptoms)
show_all_button.pack(side=tk.LEFT, padx=5)
add_button = ttk.Button(input_frame, text="Add", command=add_symptom)
add_button.pack(side=tk.LEFT, padx=5)

additional_search_var = tk.StringVar(root, value=config.get("last_search", ""))
additional_search_frame = ttk.Frame(control_frame)
additional_search_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
ttk.Label(additional_search_frame, text="Additional Search:").pack(side=tk.LEFT)
additional_search_entry = ttk.Entry(additional_search_frame, textvariable=additional_search_var, width=30)
additional_search_entry.pack(side=tk.LEFT, padx=5)
search_button = ttk.Button(additional_search_frame, text="Search", command=additional_web_search)
search_button.pack(side=tk.LEFT, padx=5)

selected_symptoms = set()

tree_frame = ttk.Frame(left_frame, padding="10", borderwidth=2, relief="ridge")
tree_frame.pack(fill=tk.BOTH, expand=True)
tree_symptoms = ttk.Treeview(tree_frame, columns=("Symptom",), show="headings", height=8)
tree_symptoms.heading("Symptom", text="Symptom")
tree_symptoms.column("Symptom", width=400)
tree_symptoms.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
sym_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree_symptoms.yview)
tree_symptoms.configure(yscrollcommand=sym_scroll.set)
sym_scroll.pack(side=tk.RIGHT, fill=tk.Y)

tree_symptoms.bind("<Button-1>", select_symptom)
tree_symptoms.bind("<Double-1>", remove_symptom)

diagnosis_frame = ttk.Frame(left_frame, padding="10", borderwidth=2, relief="ridge")
diagnosis_frame.pack(fill=tk.BOTH, expand=True)
ttk.Label(diagnosis_frame, text="Top Matching Diseases:").pack(anchor=tk.W)
tree_diagnosis = ttk.Treeview(diagnosis_frame, columns=("Disease", "Score"), show="headings", height=10)
tree_diagnosis.heading("Disease", text="Disease", anchor="w")
tree_diagnosis.heading("Score", text="Score (%)", anchor="w")
tree_diagnosis.column("Disease", width=250, anchor="w")
tree_diagnosis.column("Score", width=250, anchor="w")
tree_diagnosis.pack(fill=tk.BOTH, expand=True)
diag_scroll = ttk.Scrollbar(diagnosis_frame, orient=tk.VERTICAL, command=tree_diagnosis.yview)
tree_diagnosis.configure(yscrollcommand=diag_scroll.set)
diag_scroll.pack(side=tk.RIGHT, fill=tk.Y)

tree_diagnosis.bind("<ButtonRelease-1>", on_single_click)
tree_diagnosis.bind("<Double-1>", on_double_click)

def auto_fit_columns(treeview):
    default_font = tkfont.nametofont("TkDefaultFont")
    for col in treeview["columns"]:
        max_width = default_font.measure(col) + 10
        for item in treeview.get_children():
            cell_text = treeview.item(item, "values")[treeview["columns"].index(col)]
            cell_width = default_font.measure(cell_text)
            if cell_width > max_width:
                max_width = cell_width + 10
        treeview.column(col, width=max_width)

root.protocol("WM_DELETE_WINDOW", lambda: (
    save_config(),
    root.destroy()
))
root.mainloop()

# Advanced Disease Diagnosis

**Advanced Disease Diagnosis** is a comprehensive desktop application designed to help users 
evaluate potential disease diagnoses based on entered symptoms. This executable integrates 
web scraping, text-to-speech narration, and a TF-IDF-based matching algorithm enhanced by a 
built-in feedback loop.

## Features

- **Graphical User Interface (GUI):** An intuitive interface built with Tkinter.
- **Symptom Auto-Completion:** Quickly add and select symptoms with real-time suggestions.
- **Dynamic Diagnosis Ranking:** Uses a weighted 70/20/10 algorithm (cosine similarity, F1 score, and optional classifier probability) to rank potential diseases.
- **Feedback Loop:** Confirmed diagnoses are saved locally (in `feedback.json`) to improve future matching.
- **Web Integration:** Fetch additional disease details and images via web scraping.
- **Text-to-Speech:** Narrates disease details using built-in TTS functionality.
- **Executable Distribution:** Distributed as a standalone executable, ready to run without further installation.

## Installation and Usage

Since this is a pre-built executable, simply download and run the file on a Windows PC.

1. **Download the Executable:**
   - Ensure all associated files (including `feedback.json` and `gui_config.json`, if present) 
     are located in the same directory as the executable.

2. **Run the Software:**
   - Double-click the EXE file to launch the application.

3. **Using the Application:**
   - **Add Symptoms:** Use the auto-complete input to enter symptoms.
   - **View Diagnosis:** The application will rank diseases based on your input.
   - **Confirm Diagnosis:** If a disease is correct, click the **Confirm Actual Disease** button.
     This saves feedback (in `feedback.json`) that boosts the disease's future ranking.
   - **Additional Details:** Use built-in web search and TTS features to gather more information.

## Developer Information

- **Developer:** Jose Ricky A. Gelbolingo  
- **Contact:** 09673071950  
- **GitHub:** [SirJorick](https://github.com/SirJorick)

## License and Disclaimer

This Software is provided under the terms set out in the accompanying **ULA.txt**.  
It is provided "as is" without warranty. The Developer shall not be liable for any damages 
arising from its use. For more details, please refer to the **ULA.txt**.

## Feedback

Your confirmation of a diagnosis is recorded locally in `feedback.json` to enhance future evaluations. 
This data is stored solely for internal algorithm improvement and is not transmitted externally.

## Support

If you encounter issues or have suggestions, please contact the developer via the GitHub page or 
the provided contact number.

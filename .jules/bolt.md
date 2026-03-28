## 2026-03-23 - Performance Analysis in Desktop GUIs
**Learning:** Running heavy NLP tasks (like pymorphy3 lemmatization on thousands of messages) on the main GUI thread causes fatal Application Not Responding (ANR) states.
**Action:** Always move expensive operations to background threads (e.g., QThread in PyQt) and use signals/slots to update the UI with a progress bar.

## 2026-03-23 - XSS and UI Breaking in PyQt
**Learning:** Displaying raw user chat text directly in a PyQt QTextBrowser using HTML string concatenation is dangerous and breaks the layout if messages contain `<` or `>`.
**Action:** Always use `html.escape()` when rendering user-generated text into an HTML widget.

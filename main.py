import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QPushButton, QLineEdit, QTextBrowser,
                            QFileDialog, QLabel, QListWidget, QTabWidget, QSplitter,
                            QTableWidget, QTableWidgetItem, QCheckBox, QComboBox,
                            QDateEdit, QHeaderView, QAbstractItemView, QGraphicsView,
                            QGraphicsScene, QGraphicsPixmapItem, QListWidgetItem, QProgressBar)
from PyQt6.QtCore import Qt, QDate, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QCursor, QPixmap, QImage
from PyQt6.QtWidgets import QMessageBox
import html

from parser import TelegramParser
from features import SmartFeatures

class ParserThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, directory):
        super().__init__()
        self.directory = directory

    def run(self):
        try:
            parser = TelegramParser()
            self.progress.emit(10) # parsing started

            messages = parser.parse_directory(self.directory)
            self.progress.emit(90) # parsing finished

            self.finished.emit(messages)
            self.progress.emit(100)
        except Exception as e:
            self.error.emit(str(e))


class AnalysisThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, features):
        super().__init__()
        self.features = features

    def run(self):
        try:
            self.progress.emit(10)
            stats = self.features.get_analytics()

            self.progress.emit(30)
            sentiment = self.features.analyze_sentiment()

            self.progress.emit(50)
            profanity = self.features.profanity_check()

            self.progress.emit(70)
            top_words = self.features.get_word_frequency(50)

            self.progress.emit(90)
            word_cloud_data = self.features.generate_word_cloud()

            self.progress.emit(100)

            results = {
                'stats': stats,
                'sentiment': sentiment,
                'profanity': profanity,
                'top_words': top_words,
                'word_cloud_data': word_cloud_data
            }
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class TGReaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TG Export Reader PRO - Bolt Edition ⚡")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(800, 600)

        self.messages = []
        self.features = None
        self.bookmarks = set()
        self.is_dark_mode = True

        self.init_ui()
        self.apply_theme()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Top toolbar
        toolbar_layout = QHBoxLayout()

        self.btn_open = QPushButton("📂 Открыть папку экспорта")
        self.btn_open.clicked.connect(self.open_directory)
        self.btn_open.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.btn_theme = QPushButton("🌓 Тема")
        self.btn_theme.clicked.connect(self.toggle_theme)
        self.btn_theme.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.lbl_status = QLabel("Готов к работе. Выберите папку с .html файлами Telegram.")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        toolbar_layout.addWidget(self.btn_open)
        toolbar_layout.addWidget(self.btn_theme)
        toolbar_layout.addWidget(self.lbl_status)
        toolbar_layout.addWidget(self.progress_bar)
        toolbar_layout.addStretch()

        main_layout.addLayout(toolbar_layout)

        # Main content area
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)

        # Left sidebar (Controls & Search)
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)

        # Search area
        search_layout = QVBoxLayout()
        search_layout.addWidget(QLabel("Умный поиск (С учетом морфологии):"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Например: Пукси, котик, работа...")
        self.search_input.returnPressed.connect(self.perform_search)

        self.btn_search = QPushButton("🔍 Искать")
        self.btn_search.clicked.connect(self.perform_search)

        # Filters
        self.cb_regex = QCheckBox("Использовать RegEx")

        self.combo_users = QComboBox()
        self.combo_users.addItem("Все пользователи")
        self.combo_users.currentTextChanged.connect(self.filter_messages)

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.btn_search)
        search_layout.addWidget(self.cb_regex)
        search_layout.addWidget(QLabel("Фильтр по отправителю:"))
        search_layout.addWidget(self.combo_users)
        search_layout.addWidget(QLabel("С даты:"))
        search_layout.addWidget(self.date_from)
        search_layout.addWidget(QLabel("По дату:"))
        search_layout.addWidget(self.date_to)

        sidebar_layout.addLayout(search_layout)

        # Search Results List
        sidebar_layout.addWidget(QLabel("Результаты поиска:"))
        self.search_results_list = QListWidget()
        self.search_results_list.itemDoubleClicked.connect(self.show_context)
        sidebar_layout.addWidget(self.search_results_list)

        # Bookmarks list
        sidebar_layout.addWidget(QLabel("🔖 Закладки:"))
        self.bookmarks_list = QListWidget()
        self.bookmarks_list.itemDoubleClicked.connect(self.show_context)
        sidebar_layout.addWidget(self.bookmarks_list)

        self.splitter.addWidget(sidebar)

        # Right area (Tabs)
        self.tabs = QTabWidget()
        self.splitter.addWidget(self.tabs)

        # 1. Chat Reader Tab
        self.tab_reader = QWidget()
        reader_layout = QVBoxLayout(self.tab_reader)

        # Teletype controls
        teletype_layout = QHBoxLayout()
        self.btn_teletype = QPushButton("▶️ Телетайп (Слайдшоу)")
        self.btn_teletype.clicked.connect(self.toggle_teletype)
        self.slider_speed = QComboBox()
        self.slider_speed.addItems(["Медленно", "Нормально", "Быстро"])
        self.slider_speed.setCurrentText("Нормально")

        teletype_layout.addWidget(self.btn_teletype)
        teletype_layout.addWidget(self.slider_speed)
        teletype_layout.addStretch()

        self.chat_browser = QTextBrowser()
        self.chat_browser.setOpenExternalLinks(True)
        self.chat_browser.anchorClicked.connect(self.handle_link)

        reader_layout.addLayout(teletype_layout)
        reader_layout.addWidget(self.chat_browser)
        self.tabs.addTab(self.tab_reader, "💬 Чат")

        # 2. Analytics Dashboard Tab
        self.tab_analytics = QWidget()
        analytics_layout = QVBoxLayout(self.tab_analytics)
        self.lbl_analytics_summary = QLabel("Загрузите чат для анализа.")
        self.lbl_analytics_summary.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        analytics_layout.addWidget(self.lbl_analytics_summary)

        self.table_top_words = QTableWidget()
        self.table_top_words.setColumnCount(2)
        self.table_top_words.setHorizontalHeaderLabels(["Слово", "Частота"])
        self.table_top_words.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        analytics_layout.addWidget(QLabel("Топ популярных слов:"))
        analytics_layout.addWidget(self.table_top_words)

        self.tabs.addTab(self.tab_analytics, "📊 Аналитика")

        # 3. Word Cloud Tab
        self.tab_wordcloud = QWidget()
        wc_layout = QVBoxLayout(self.tab_wordcloud)
        self.lbl_wordcloud = QLabel("Загрузите чат для генерации облака слов.")
        self.lbl_wordcloud.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wc_layout.addWidget(self.lbl_wordcloud)
        self.tabs.addTab(self.tab_wordcloud, "☁️ Облако слов")

        # 4. Media Gallery Tab
        self.tab_media = QWidget()
        media_layout = QVBoxLayout(self.tab_media)
        self.media_list = QListWidget()
        self.media_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.media_list.setIconSize(self.media_list.size())
        self.media_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        media_layout.addWidget(QLabel("Медиафайлы (ссылки):"))
        media_layout.addWidget(self.media_list)
        self.tabs.addTab(self.tab_media, "🖼️ Галерея")

        # Set splitter sizes
        self.splitter.setSizes([300, 900])

        # Timer for Teletype mode
        self.teletype_timer = QTimer(self)
        self.teletype_timer.timeout.connect(self.scroll_teletype)
        self.teletype_active = False

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.apply_theme()

    def apply_theme(self):
        if self.is_dark_mode:
            self.setStyleSheet("""
                QMainWindow { background-color: #1e1e2e; color: #cdd6f4; }
                QWidget { background-color: #1e1e2e; color: #cdd6f4; }
                QPushButton { background-color: #89b4fa; color: #11111b; border-radius: 5px; padding: 5px; font-weight: bold; }
                QPushButton:hover { background-color: #b4befe; }
                QLineEdit, QComboBox, QDateEdit, QListWidget, QTableWidget, QTextBrowser {
                    background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 4px; padding: 5px;
                }
                QHeaderView::section { background-color: #313244; color: #cdd6f4; }
                QTabWidget::pane { border: 1px solid #45475a; }
                QTabBar::tab { background-color: #313244; color: #cdd6f4; padding: 8px; border-radius: 4px; margin: 2px; }
                QTabBar::tab:selected { background-color: #89b4fa; color: #11111b; font-weight: bold; }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow { background-color: #f8f9fa; color: #212529; }
                QWidget { background-color: #f8f9fa; color: #212529; }
                QPushButton { background-color: #0d6efd; color: white; border-radius: 5px; padding: 5px; font-weight: bold; }
                QPushButton:hover { background-color: #0b5ed7; }
                QLineEdit, QComboBox, QDateEdit, QListWidget, QTableWidget, QTextBrowser {
                    background-color: white; color: #212529; border: 1px solid #ced4da; border-radius: 4px; padding: 5px;
                }
                QHeaderView::section { background-color: #e9ecef; color: #212529; }
                QTabWidget::pane { border: 1px solid #ced4da; }
                QTabBar::tab { background-color: #e9ecef; color: #212529; padding: 8px; border-radius: 4px; margin: 2px; }
                QTabBar::tab:selected { background-color: #0d6efd; color: white; font-weight: bold; }
            """)

    def open_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Выберите папку с экспортом Telegram (там где файлы messages.html)")
        if dir_path:
            self.lbl_status.setText(f"Чтение файлов из: {dir_path}...")
            self.progress_bar.setVisible(True)
            self.btn_open.setEnabled(False)

            self.worker = ParserThread(dir_path)
            self.worker.progress.connect(self.progress_bar.setValue)
            self.worker.finished.connect(self.on_parsing_finished)
            self.worker.error.connect(self.on_parsing_error)
            self.worker.start()

    def on_parsing_error(self, err_msg):
        self.progress_bar.setVisible(False)
        self.btn_open.setEnabled(True)
        QMessageBox.critical(self, "Ошибка", f"Произошла ошибка при чтении: {err_msg}")
        self.lbl_status.setText("Ошибка при чтении.")

    def on_parsing_finished(self, messages):
        self.messages = messages

        if not self.messages:
            self.progress_bar.setVisible(False)
            self.btn_open.setEnabled(True)
            self.lbl_status.setText("В папке не найдено сообщений. Убедитесь, что там есть файлы messages.html.")
            QMessageBox.warning(self, "Пусто", "Не удалось найти сообщения в выбранной папке.")
            return

        self.features = SmartFeatures(self.messages)
        self.lbl_status.setText(f"Загружено {len(self.messages)} сообщений. Анализируем данные (NLP)...")

        # Start Analysis in background
        self.analysis_thread = AnalysisThread(self.features)
        self.analysis_thread.progress.connect(self.progress_bar.setValue)
        self.analysis_thread.finished.connect(self.on_analysis_finished)
        self.analysis_thread.error.connect(self.on_parsing_error) # reuse error handler
        self.analysis_thread.start()

    def on_analysis_finished(self, results):
        self.progress_bar.setVisible(False)
        self.btn_open.setEnabled(True)
        self.lbl_status.setText(f"Загружено {len(self.messages)} сообщений. Анализ завершен.")
        self.populate_ui_with_data(results)

    def populate_ui_with_data(self, analysis_results):
        # Update users combo
        self.combo_users.clear()
        self.combo_users.addItem("Все пользователи")
        senders = list(set(msg['sender'] for msg in self.messages))
        self.combo_users.addItems(sorted(senders))

        # Update dates if available
        dates = [msg['timestamp'].date() for msg in self.messages if msg.get('timestamp')]
        if dates:
            min_date = min(dates)
            max_date = max(dates)
            self.date_from.setDate(min_date)
            self.date_to.setDate(max_date)

        # Display all messages initially
        self.display_messages(self.messages)

        # Analytics
        stats = analysis_results['stats']
        summary = (f"Всего сообщений: {stats.get('Total Messages', 0)}\n"
                   f"Уникальных отправителей: {stats.get('Unique Senders', 0)}\n"
                   f"Активных дней: {stats.get('Active Days', 0)}")

        sentiment = analysis_results['sentiment']
        summary += f"\n\nАнализ тональности:\nПозитивных: {sentiment['Positive']}\nНегативных: {sentiment['Negative']}\nНейтральных: {sentiment['Neutral']}"

        profanity = analysis_results['profanity']
        summary += f"\n\nСчетчик ругательств: {profanity}"

        self.lbl_analytics_summary.setText(summary)

        # Top Words
        top_words = analysis_results['top_words']
        self.table_top_words.setRowCount(len(top_words))
        for row, (word, count) in enumerate(top_words):
            self.table_top_words.setItem(row, 0, QTableWidgetItem(word))
            self.table_top_words.setItem(row, 1, QTableWidgetItem(str(count)))

        # Word Cloud
        img_data = analysis_results['word_cloud_data']
        if img_data:
            img = QImage.fromData(img_data)
            pixmap = QPixmap.fromImage(img)
            self.lbl_wordcloud.setPixmap(pixmap)
        else:
            self.lbl_wordcloud.setText(f"Не удалось сгенерировать облако слов.")

        # Media Gallery
        self.media_list.clear()
        media_msgs = self.features.get_media_gallery()
        for msg in media_msgs:
            item = QListWidgetItem(f"Медиа от {msg['sender']}")
            item.setData(Qt.ItemDataRole.UserRole, msg['id'])
            self.media_list.addItem(item)

    def display_messages(self, messages_to_display, highlight_text=""):
        html = "<html><body>"

        for msg in messages_to_display:
            import html as html_lib
            sender = html_lib.escape(msg['sender'])
            time_str = msg['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if msg.get('timestamp') else "Unknown time"

            # Escape HTML characters first to prevent XSS / UI breaking
            text = html_lib.escape(msg.get('text', ''))

            # Highlighting
            if highlight_text:
                escaped_highlight = html_lib.escape(highlight_text)
                if escaped_highlight.lower() in text.lower():
                    # Simple case-insensitive highlight
                    import re
                    pattern = re.compile(re.escape(escaped_highlight), re.IGNORECASE)
                    text = pattern.sub(lambda m: f'<span style="background-color: yellow; color: black;">{m.group(0)}</span>', text)

            media_info = f"<br><i>[Вложение: {html_lib.escape(msg['media'])}]</i>" if msg.get('media') else ""

            # Add bookmark link
            bm_link = f'<a href="bookmark:{msg["id"]}">[🔖 В закладки]</a>'

            color = "#89b4fa" if self.is_dark_mode else "#0d6efd"
            html += f"<div style='margin-bottom: 10px; padding: 5px; border-bottom: 1px solid gray;'>"
            html += f"<b style='color: {color};'>{sender}</b> <small>({time_str})</small> {bm_link}<br>"
            html += f"{text}{media_info}"
            html += f"</div>"

        html += "</body></html>"
        self.chat_browser.setHtml(html)

    def handle_link(self, url):
        url_str = url.toString()
        if url_str.startswith("bookmark:"):
            msg_id = url_str.split(":")[1]
            if msg_id not in self.bookmarks:
                self.bookmarks.add(msg_id)
                # Find message
                msg = next((m for m in self.messages if m['id'] == msg_id), None)
                if msg:
                    item_text = f"{msg['sender']}: {msg['text'][:30]}..."
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.ItemDataRole.UserRole, msg_id)
                    self.bookmarks_list.addItem(item)
                    QMessageBox.information(self, "Закладки", "Сообщение добавлено в закладки!")
            else:
                QMessageBox.information(self, "Закладки", "Это сообщение уже в закладках.")

    def perform_search(self):
        if not self.features:
            return

        query = self.search_input.text().strip()
        if not query:
            self.display_messages(self.messages)
            return

        self.search_results_list.clear()

        if self.cb_regex.isChecked():
            results = self.features.regex_search(query)
        else:
            results = self.features.smart_search(query)

        for msg in results:
            time_str = msg['timestamp'].strftime('%Y-%m-%d') if msg.get('timestamp') else ""
            item = QListWidgetItem(f"[{time_str}] {msg['sender']}: {msg['text'][:50]}...")
            item.setData(Qt.ItemDataRole.UserRole, msg['id'])
            self.search_results_list.addItem(item)

        self.display_messages(results, highlight_text=query if not self.cb_regex.isChecked() else "")
        self.lbl_status.setText(f"Найдено сообщений: {len(results)}")

    def filter_messages(self):
        if not self.messages:
            return

        selected_user = self.combo_users.currentText()
        filtered = self.messages

        if selected_user != "Все пользователи":
            filtered = [msg for msg in filtered if msg['sender'] == selected_user]

        self.display_messages(filtered)

    def show_context(self, item):
        msg_id = item.data(Qt.ItemDataRole.UserRole)
        context_msgs = self.features.get_context(msg_id, window=10)
        self.display_messages(context_msgs)
        self.tabs.setCurrentIndex(0) # Switch to chat tab

    def toggle_teletype(self):
        if self.teletype_active:
            self.teletype_timer.stop()
            self.btn_teletype.setText("▶️ Телетайп (Слайдшоу)")
            self.teletype_active = False
        else:
            speed = self.slider_speed.currentText()
            interval = 2000 if speed == "Медленно" else (1000 if speed == "Нормально" else 500)
            self.teletype_timer.start(interval)
            self.btn_teletype.setText("⏸️ Пауза")
            self.teletype_active = True

    def scroll_teletype(self):
        scrollbar = self.chat_browser.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() + 50) # Scroll down a bit
        if scrollbar.value() == scrollbar.maximum():
            self.toggle_teletype() # Auto-stop at the end


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Set a nice font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = TGReaderApp()
    window.show()
    sys.exit(app.exec())

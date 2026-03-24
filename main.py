import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QPushButton, QLineEdit,
                            QFileDialog, QLabel, QListWidget, QTabWidget, QSplitter,
                            QTableWidget, QTableWidgetItem, QCheckBox, QComboBox,
                            QDateEdit, QHeaderView, QAbstractItemView,
                            QListWidgetItem, QProgressBar, QListView, QStyledItemDelegate,
                            QMenu)
from PyQt6.QtCore import Qt, QDate, QTimer, QThread, pyqtSignal, QAbstractListModel, QSize, QPoint
from PyQt6.QtGui import QFont, QColor, QCursor, QPixmap, QImage, QPainter, QTextDocument, QAbstractTextDocumentLayout
from PyQt6.QtWidgets import QMessageBox, QStyle
import html
import re

from parser import TelegramParser
from features import SmartFeatures

class MessageListModel(QAbstractListModel):
    def __init__(self, messages=None, highlight_text="", is_dark_mode=True):
        super().__init__()
        self.messages = messages or []
        self.highlight_text = highlight_text
        self.is_dark_mode = is_dark_mode

    def data(self, index, role):
        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            msg = self.messages[index.row()]
            sender = html.escape(msg['sender'])
            time_str = msg['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if msg.get('timestamp') else "Unknown time"

            # Escape HTML characters first to prevent XSS / UI breaking
            text = html.escape(msg.get('text', ''))

            # Highlighting
            if self.highlight_text:
                escaped_highlight = html.escape(self.highlight_text)
                if escaped_highlight.lower() in text.lower():
                    # Simple case-insensitive highlight
                    pattern = re.compile(re.escape(escaped_highlight), re.IGNORECASE)
                    text = pattern.sub(lambda m: f'<span style="background-color: yellow; color: black;">{m.group(0)}</span>', text)

            media_info = f"<br><i>[Вложение: {html.escape(msg['media'])}]</i>" if msg.get('media') else ""

            color = "#89b4fa" if self.is_dark_mode else "#0d6efd"

            html_content = f"<div style='padding: 5px; font-family: Segoe UI; font-size: 13px;'>"
            html_content += f"<b style='color: {color};'>{sender}</b> <small style='color: gray;'>({time_str})</small><br>"
            html_content += f"{text}{media_info}"
            html_content += f"</div>"
            return html_content

        return None

    def rowCount(self, index=None):
        return len(self.messages)

    def set_messages(self, messages, highlight_text=""):
        self.beginResetModel()
        self.messages = messages
        self.highlight_text = highlight_text
        self.endResetModel()

    def set_dark_mode(self, is_dark):
        self.is_dark_mode = is_dark
        self.layoutChanged.emit()

class HTMLDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        options = option
        self.initStyleOption(options, index)

        painter.save()

        # Draw background
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        else:
            painter.fillRect(option.rect, option.palette.base())

        # Add bottom border
        border_color = QColor("#45475a" if option.palette.base().color().lightness() < 128 else "#ced4da")
        painter.setPen(border_color)
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())

        doc = QTextDocument()
        doc.setHtml(options.text)
        doc.setTextWidth(option.rect.width())

        ctx = QAbstractTextDocumentLayout.PaintContext()

        # Set text color based on selection and theme
        if option.state & QStyle.StateFlag.State_Selected:
            ctx.palette.setColor(doc.documentLayout().palette().color(ctx.palette.ColorRole.Text), option.palette.highlightedText().color())
        else:
            ctx.palette.setColor(doc.documentLayout().palette().color(ctx.palette.ColorRole.Text), option.palette.text().color())

        painter.translate(option.rect.x(), option.rect.y())
        doc.documentLayout().draw(painter, ctx)
        painter.restore()

    def sizeHint(self, option, index):
        options = option
        self.initStyleOption(options, index)

        doc = QTextDocument()
        doc.setHtml(options.text)
        doc.setTextWidth(option.rect.width())

        return QSize(int(doc.idealWidth()), int(doc.size().height()) + 10) # 10 for padding

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

            # Pass a callback so parser can update the UI per file parsed
            messages = parser.parse_directory(
                self.directory,
                progress_callback=lambda p: self.progress.emit(p)
            )
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

        # Virtualized List View for massive performance gains
        self.chat_list_view = QListView()
        self.chat_list_view.setItemDelegate(HTMLDelegate())
        self.chat_model = MessageListModel(is_dark_mode=self.is_dark_mode)
        self.chat_list_view.setModel(self.chat_model)
        self.chat_list_view.setUniformItemSizes(False)
        self.chat_list_view.setWordWrap(True)

        # Context menu for bookmarks
        self.chat_list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chat_list_view.customContextMenuRequested.connect(self.show_context_menu)
        # Double click to show context (if it was a search result)
        self.chat_list_view.doubleClicked.connect(self.on_chat_double_clicked)

        reader_layout.addLayout(teletype_layout)
        reader_layout.addWidget(self.chat_list_view)
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
        self.chat_model.set_dark_mode(self.is_dark_mode)
        self.apply_theme()

    def apply_theme(self):
        if self.is_dark_mode:
            self.setStyleSheet("""
                QMainWindow { background-color: #1e1e2e; color: #cdd6f4; }
                QWidget { background-color: #1e1e2e; color: #cdd6f4; }
                QPushButton { background-color: #89b4fa; color: #11111b; border-radius: 5px; padding: 5px; font-weight: bold; }
                QPushButton:hover { background-color: #b4befe; }
                QLineEdit, QComboBox, QDateEdit, QListWidget, QTableWidget, QListView {
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
                QLineEdit, QComboBox, QDateEdit, QListWidget, QTableWidget, QListView {
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
        # We now use the MVVM approach (QListView + Model) which solves the ANR
        self.chat_model.set_messages(messages_to_display, highlight_text)

    def show_context_menu(self, position: QPoint):
        index = self.chat_list_view.indexAt(position)
        if not index.isValid():
            return

        menu = QMenu()
        action_bookmark = menu.addAction("🔖 Добавить в закладки")
        action_context = menu.addAction("👁️ Показать контекст сообщения")

        action = menu.exec(self.chat_list_view.viewport().mapToGlobal(position))

        if action == action_bookmark:
            self.add_bookmark(index)
        elif action == action_context:
            self.on_chat_double_clicked(index)

    def add_bookmark(self, index):
        msg = self.chat_model.messages[index.row()]
        msg_id = msg['id']

        if msg_id not in self.bookmarks:
            self.bookmarks.add(msg_id)
            item_text = f"{msg['sender']}: {msg.get('text', '')[:30]}..."
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, msg_id)
            self.bookmarks_list.addItem(item)
            QMessageBox.information(self, "Закладки", "Сообщение добавлено в закладки!")
        else:
            QMessageBox.information(self, "Закладки", "Это сообщение уже в закладках.")

    def on_chat_double_clicked(self, index):
        msg = self.chat_model.messages[index.row()]
        self.show_context_by_id(msg['id'])

    def show_context_by_id(self, msg_id):
        context_msgs = self.features.get_context(msg_id, window=10)
        if context_msgs:
            self.display_messages(context_msgs)
            self.tabs.setCurrentIndex(0)

    def perform_search(self):
        if not self.features:
            return

        query = self.search_input.text().strip()

        # We start with all messages and apply filters first
        results = self.messages

        # User filter
        selected_user = self.combo_users.currentText()
        if selected_user != "Все пользователи":
            results = [msg for msg in results if msg['sender'] == selected_user]

        # Date filter
        # Get start of day for 'from' and end of day for 'to' to ensure full coverage
        date_from_dt = self.date_from.date().toPyDate()
        date_to_dt = self.date_to.date().toPyDate()

        # Filter by date only if the message has a timestamp
        results = [msg for msg in results if not msg.get('timestamp') or
                  (date_from_dt <= msg['timestamp'].date() <= date_to_dt)]

        if query:
            # Create a temporary SmartFeatures object with only the filtered messages
            # so that search runs ONLY on the filtered subset for maximum performance
            temp_features = SmartFeatures(results)
            # Re-use our main lemma cache to keep speed high
            temp_features.lemma_cache = self.features.lemma_cache

            if self.cb_regex.isChecked():
                results = temp_features.regex_search(query)
            else:
                results = temp_features.smart_search(query)

        self.search_results_list.clear()

        # UI Performance protection: Cap left-panel list items to prevent QListWidget from freezing.
        # The main view (chat_list_view) is virtualized and can handle all results,
        # but the simple QListWidget cannot handle tens of thousands.
        MAX_UI_RESULTS = 500
        display_results = results[:MAX_UI_RESULTS]

        for msg in display_results:
            time_str = msg['timestamp'].strftime('%Y-%m-%d') if msg.get('timestamp') else ""
            item = QListWidgetItem(f"[{time_str}] {msg['sender']}: {msg.get('text', '')[:50]}...")
            item.setData(Qt.ItemDataRole.UserRole, msg['id'])
            self.search_results_list.addItem(item)

        if len(results) > MAX_UI_RESULTS:
            overflow_item = QListWidgetItem(f"...и еще {len(results) - MAX_UI_RESULTS} сообщений (смотрите в основном окне)")
            overflow_item.setFlags(Qt.ItemFlag.NoItemFlags) # Make unclickable
            self.search_results_list.addItem(overflow_item)

        self.display_messages(results, highlight_text=query if not self.cb_regex.isChecked() else "")
        self.lbl_status.setText(f"Найдено сообщений: {len(results)}")

    def filter_messages(self):
        # Trigger the same pipeline
        self.perform_search()

    def show_context(self, item):
        msg_id = item.data(Qt.ItemDataRole.UserRole)
        self.show_context_by_id(msg_id)

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
        scrollbar = self.chat_list_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() + 50) # Scroll down a bit
        if scrollbar.value() >= scrollbar.maximum():
            self.toggle_teletype() # Auto-stop at the end


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Set a nice font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = TGReaderApp()
    window.show()
    sys.exit(app.exec())

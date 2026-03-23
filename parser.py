import os
from bs4 import BeautifulSoup
from datetime import datetime
import re

class TelegramParser:
    def __init__(self):
        self.messages = []

    def parse_directory(self, directory_path):
        self.messages = []
        html_files = [f for f in os.listdir(directory_path) if f.startswith('messages') and f.endswith('.html')]
        html_files.sort(key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0)

        for file in html_files:
            file_path = os.path.join(directory_path, file)
            self._parse_file(file_path)

        return self.messages

    def _parse_file(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'lxml')

        message_divs = soup.find_all('div', class_='message default clearfix')

        for div in message_divs:
            try:
                # Extract message ID
                msg_id = div.get('id', '')

                # Extract sender
                sender_div = div.find('div', class_='from_name')
                sender = sender_div.text.strip() if sender_div else "Unknown"

                # Extract timestamp
                time_div = div.find('div', class_='pull_right date details')
                timestamp_str = time_div['title'] if time_div and time_div.has_attr('title') else ""

                # Parse timestamp if available (format: DD.MM.YYYY HH:MM:SS)
                timestamp = None
                if timestamp_str:
                    try:
                        timestamp = datetime.strptime(timestamp_str, '%d.%m.%Y %H:%M:%S')
                    except ValueError:
                        pass

                # Extract text
                text_div = div.find('div', class_='text')
                text = text_div.text.strip() if text_div else ""

                # Extract media if any
                media_link = ""
                media_wrap = div.find('a', class_='photo_wrap') or div.find('a', class_='video_wrap')
                if media_wrap and media_wrap.has_attr('href'):
                    media_link = media_wrap['href']

                # Skip system messages or empty messages without media
                if not text and not media_link:
                    continue

                self.messages.append({
                    'id': msg_id,
                    'sender': sender,
                    'timestamp': timestamp,
                    'text': text,
                    'media': media_link
                })
            except Exception as e:
                print(f"Error parsing message in {file_path}: {e}")
                continue

if __name__ == '__main__':
    # Simple test structure
    pass

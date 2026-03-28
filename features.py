import pymorphy3
from rapidfuzz import fuzz, process
from wordcloud import WordCloud
import re
from collections import Counter
import io

class SmartFeatures:
    def __init__(self, messages):
        self.messages = messages
        self.morph = pymorphy3.MorphAnalyzer()

        # Memoization cache for lemmas to massively speed up processing
        self.lemma_cache = {}

        # Stop words for word cloud
        self.stop_words = set([
            'и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то', 'все', 'она',
            'так', 'его', 'но', 'да', 'ты', 'к', 'у', 'же', 'вы', 'за', 'бы', 'по', 'только', 'ее',
            'мне', 'было', 'вот', 'от', 'меня', 'еще', 'нет', 'о', 'из', 'ему', 'теперь', 'когда',
            'даже', 'ну', 'вдруг', 'ли', 'если', 'уже', 'или', 'ни', 'быть', 'был', 'него', 'до',
            'вас', 'нибудь', 'опять', 'уж', 'вам', 'ведь', 'там', 'потом', 'себя', 'ничего', 'ей',
            'может', 'они', 'тут', 'где', 'есть', 'надо', 'ней', 'для', 'мы', 'тебя', 'их', 'чем',
            'была', 'сам', 'чтоб', 'без', 'будто', 'чего', 'раз', 'тоже', 'себе', 'под', 'будет',
            'ж', 'тогда', 'кто', 'этот', 'того', 'потому', 'этого', 'какой', 'совсем', 'ним', 'здесь',
            'этом', 'один', 'почти', 'мой', 'тем', 'чтобы', 'нее', 'сейчас', 'были', 'куда', 'зачем',
            'всех', 'никогда', 'можно', 'при', 'наконец', 'два', 'об', 'другой', 'хоть', 'после',
            'над', 'больше', 'тот', 'через', 'эти', 'нас', 'про', 'всего', 'них', 'какая', 'много',
            'разве', 'три', 'эту', 'моя', 'впрочем', 'хорошо', 'свою', 'этой', 'перед', 'иногда',
            'лучше', 'чуть', 'том', 'нельзя', 'такой', 'им', 'более', 'всегда', 'конечно', 'всю',
            'между', 'это', 'меня', 'тебя', 'он', 'она', 'оно', 'мы', 'вы', 'они'
        ])

    def get_lemma(self, word):
        """⚡ Bolt: Uses memoization cache to convert O(N) NLP overhead into O(1) hash lookups."""
        if word in self.lemma_cache:
            return self.lemma_cache[word]

        parsed = self.morph.parse(word)[0]
        lemma = parsed.normal_form
        self.lemma_cache[word] = lemma
        return lemma

    def smart_search(self, query):
        if not self.messages:
            return []

        # Extract base form of the query word
        words = re.findall(r'\w+', query.lower())
        lemmas = [self.get_lemma(word) for word in words]

        results = []
        for msg in self.messages:
            if not msg.get('text'):
                continue

            text = msg['text'].lower()
            text_words = re.findall(r'\w+', text)

            # Check for exact matches
            if query.lower() in text:
                results.append(msg)
                continue

            # Morphological check (e.g., matching 'пукси' with 'пуксеныш')
            # Fast fuzzy matching
            match = False
            for text_word in text_words:
                text_lemma = self.get_lemma(text_word)
                for lemma in lemmas:
                    # Allow fuzzy matching for nicknames or similar words
                    if fuzz.ratio(lemma, text_lemma) > 80:
                        match = True
                        break
                if match:
                    break

            if match:
                results.append(msg)

        return results

    def get_analytics(self):
        if not self.messages:
            return {}

        total_messages = len(self.messages)

        # Calculate unique senders efficiently
        senders = set()
        dates = set()

        for msg in self.messages:
            senders.add(msg['sender'])
            if msg.get('timestamp'):
                dates.add(msg['timestamp'].date())

        return {
            'Total Messages': total_messages,
            'Unique Senders': len(senders),
            'Active Days': len(dates)
        }

    def get_word_frequency(self, top_n=50):
        all_words = []
        for msg in self.messages:
            if msg.get('text'):
                words = re.findall(r'[а-яА-Яa-zA-Z]+', msg['text'].lower())
                # Filter out stop words and short words
                words = [self.get_lemma(w) for w in words if w not in self.stop_words and len(w) > 2]
                all_words.extend(words)

        return Counter(all_words).most_common(top_n)

    def generate_word_cloud(self):
        words = dict(self.get_word_frequency(200))
        if not words:
            return None

        wc = WordCloud(width=800, height=400, background_color='white', colormap='viridis')
        wc.generate_from_frequencies(words)

        # Save directly using PIL to bypass matplotlib dependency
        img_buffer = io.BytesIO()
        image = wc.to_image()
        image.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        return img_buffer.getvalue()

    def get_top_chatters(self):
        if not self.messages:
            return {}
        counts = Counter(msg['sender'] for msg in self.messages)
        return dict(counts.most_common(10))

    def regex_search(self, pattern):
        results = []
        try:
            regex = re.compile(pattern)
            for msg in self.messages:
                if msg.get('text') and regex.search(msg['text']):
                    results.append(msg)
        except re.error:
            pass # Invalid regex
        return results

    def profanity_check(self):
        # A simple placeholder list of bad words (in a real app, this would be a larger dictionary)
        bad_words = ['хуй', 'пизда', 'ебать', 'блядь', 'сука', 'хер']
        count = 0
        for msg in self.messages:
            if msg.get('text'):
                words = re.findall(r'[а-яА-Я]+', msg['text'].lower())
                for word in words:
                    lemma = self.get_lemma(word)
                    if lemma in bad_words:
                        count += 1
        return count

    def get_media_gallery(self):
        return [msg for msg in self.messages if msg.get('media')]

    def get_time_of_day_stats(self):
        hours = [msg['timestamp'].hour for msg in self.messages if msg.get('timestamp')]
        counts = Counter(hours)
        return dict(sorted(counts.items()))

    def get_context(self, target_msg_id, window=5):
        # Find the index of the message
        idx = next((i for i, msg in enumerate(self.messages) if msg['id'] == target_msg_id), -1)
        if idx == -1:
            return []

        start = max(0, idx - window)
        end = min(len(self.messages), idx + window + 1)
        return self.messages[start:end]

    def analyze_sentiment(self):
        # Note: TextBlob works best with English. For Russian, we would need Dostoevsky or similar,
        # but TextBlob can do basic translation or fallback. We'll use a simple proxy for now.
        positive = 0
        negative = 0
        neutral = 0

        for msg in self.messages:
            if msg.get('text'):
                # Simple approximation for demonstration
                text = msg['text'].lower()
                if any(word in text for word in ['хорошо', 'отлично', 'супер', 'круто', 'спасибо', 'хаха', 'ахах', 'люблю']):
                    positive += 1
                elif any(word in text for word in ['плохо', 'ужас', 'кошмар', 'ненавижу', 'грустно', 'больно', 'блять', 'хуй']):
                    negative += 1
                else:
                    neutral += 1

        return {'Positive': positive, 'Negative': negative, 'Neutral': neutral}

import re
import logging

logger = logging.getLogger(__name__)

class TextFormatter:
    """
    Cleans, auto-corrects, and formats transcribed speech
    with support for English, Bengali (বাংলা), and Hindi (हिन्दी).
    """

    # Spoken punctuation mapping
    # Format: (pattern, replacement, is_indic)
    SPOKEN_PUNCTUATION_RULES = [
        # English
        (r"\b(full stop|period)\b", ".", False),
        (r"\bcomma\b", ",", False),
        (r"\bquestion mark\b", "?", False),
        (r"\b(exclamation mark|exclamation point)\b", "!", False),
        (r"\bcolon\b", ":", False),
        (r"\bsemicolon\b", ";", False),
        (r"\b(new line|next line)\b", "\n", False),
        (r"\b(new paragraph)\b", "\n\n", False),

        # Bengali spoken punctuation
        (r"(^|\s)(দাঁড়ি|দাড়ি)(?=\s|$)", r"\1।", True),
        (r"(^|\s)(কমা)(?=\s|$)", r"\1,", True),
        (r"(^|\s)(প্রশ্নচিহ্ন|প্রশ্নবোধক চিহ্ন)(?=\s|$)", r"\1?", True),
        (r"(^|\s)(নতুন লাইন)(?=\s|$)", "\n", True),

        # Hindi spoken punctuation
        (r"(^|\s)(पूर्ण विराम|खड़ी पाई)(?=\s|$)", r"\1।", True),
        (r"(^|\s)(अल्पविराम|कॉमा)(?=\s|$)", r"\1,", True),
        (r"(^|\s)(प्रश्नवाचक चिन्ह)(?=\s|$)", r"\1?", True),
        (r"(^|\s)(नई लाइन)(?=\s|$)", "\n", True),
    ]

    # Whisper common hallucination artifacts
    HALLUCINATIONS = [
        r"\[blank_audio\]",
        r"\[music\]",
        r"\[applause\]",
        r"\[laughter\]",
        r"\(silence\)",
        r"\(music\)",
        r"\(applause\)",
        r"♪+",
        r"thank you for watching\.?",
        r"thanks for watching\.?",
        r"subtitles by.*",
    ]

    def __init__(self, enable_spoken_punctuation: bool = True, enable_casing: bool = True):
        self.enable_spoken_punctuation = enable_spoken_punctuation
        self.enable_casing = enable_casing

    def clean_hallucinations(self, text: str) -> str:
        """Removes unwanted whisper tags, subtitle credits, and noise markers."""
        cleaned = text
        for pattern in self.HALLUCINATIONS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        
        # Remove repeated phrase loops (e.g., "thank you thank you thank you")
        cleaned = re.sub(r"(\b.+?\b)( \1){3,}", r"\1", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    def replace_spoken_punctuation(self, text: str) -> str:
        """Converts spoken punctuation words into actual punctuation symbols."""
        if not self.enable_spoken_punctuation:
            return text

        formatted = text
        for pattern, replacement, is_indic in self.SPOKEN_PUNCTUATION_RULES:
            if is_indic:
                formatted = re.sub(pattern, replacement, formatted)
            else:
                formatted = re.sub(pattern, replacement, formatted, flags=re.IGNORECASE)
        return formatted

    def fix_spacing_and_punctuation(self, text: str) -> str:
        """Fixes awkward spaces before/after punctuation marks."""
        # Remove space before punctuation: "hello , world" -> "hello, world"
        # Handles English punctuation and Bengali/Hindi Dari (।)
        text = re.sub(r"\s+([,.:;?!।])", r"\1", text)

        # Ensure single space after punctuation if followed by a letter/digit
        text = re.sub(r"([,.:;?!।])([^\s0-9,\.:;?!।\n\"'’])", r"\1 \2", text)

        # Collapse multiple spaces into one (except newlines)
        text = re.sub(r"[^\S\r\n]+", " ", text)

        # Collapse 3+ newlines into 2
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def fix_casing(self, text: str) -> str:
        """Capitalizes sentence starts and common standalone pronouns (English/Latin scripts)."""
        if not self.enable_casing or not text:
            return text

        # Capitalize start of text if ascii
        if text[0].isalpha() and text[0].isascii():
            text = text[0].upper() + text[1:]

        # Capitalize after sentence terminators (. ! ? or Dari । followed by whitespace)
        def capitalize_match(match):
            delim = match.group(1)
            letter = match.group(2)
            return delim + letter.upper()

        text = re.sub(r"([.!?।\n]\s+)([a-z])", capitalize_match, text)

        # Capitalize standalone 'i' contractions in English
        text = re.sub(r"\b(i)\b", "I", text)
        text = re.sub(r"\b(i'm)\b", "I'm", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(i'll)\b", "I'll", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(i've)\b", "I've", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(i'd)\b", "I'd", text, flags=re.IGNORECASE)

        return text

    def format(self, text: str, language: str = "auto") -> str:
        """Runs the complete auto-correction and formatting pipeline."""
        if not text:
            return ""

        formatted = self.clean_hallucinations(text)
        formatted = self.replace_spoken_punctuation(formatted)
        formatted = self.fix_spacing_and_punctuation(formatted)
        formatted = self.fix_casing(formatted)
        return formatted

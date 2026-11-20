import time
import pyperclip
from pynput.keyboard import Controller, Key
import logging

logger = logging.getLogger(__name__)

class TextInjector:
    def __init__(self, mode: str = "clipboard", restore_clipboard: bool = True):
        self.mode = mode
        self.restore_clipboard = restore_clipboard
        self.keyboard = Controller()

    def inject(self, text: str) -> bool:
        """Injects text into the active focused window."""
        if not text:
            return False

        # Ensure clean text formatting
        text_to_insert = text.strip()
        if not text_to_insert:
            return False

        if self.mode == "clipboard":
            return self._paste_text(text_to_insert)
        return self._type_text(text_to_insert)

    def _paste_text(self, text: str) -> bool:
        """Copies text to clipboard, simulates Ctrl+V, and restores previous clipboard."""
        previous_clipboard = None
        if self.restore_clipboard:
            try:
                previous_clipboard = pyperclip.paste()
            except Exception as e:
                logger.debug(f"Could not read previous clipboard: {e}")

        try:
            # Set target text
            pyperclip.copy(text)
            time.sleep(0.03)  # Brief wait to ensure clipboard is populated

            # Simulate Ctrl + V with precise micro-delays for Windows message queue
            self.keyboard.press(Key.ctrl)
            time.sleep(0.015)
            self.keyboard.press('v')
            time.sleep(0.015)
            self.keyboard.release('v')
            time.sleep(0.015)
            self.keyboard.release(Key.ctrl)

            logger.info(f"Pasted text: {text[:40]}...")

            # Wait briefly for application to process paste before restoring
            if self.restore_clipboard and previous_clipboard is not None:
                time.sleep(0.12)
                try:
                    pyperclip.copy(previous_clipboard)
                except Exception as e:
                    logger.debug(f"Could not restore previous clipboard: {e}")

            return True
        except Exception as e:
            logger.error(f"Error pasting text: {e}")
            # Fallback to direct typing
            return self._type_text(text)

    def _type_text(self, text: str) -> bool:
        """Simulates typing character by character."""
        try:
            self.keyboard.type(text)
            logger.info(f"Typed text: {text[:40]}...")
            return True
        except Exception as e:
            logger.error(f"Error typing text: {e}")
            return False

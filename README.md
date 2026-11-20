# 🎙️ TalkType - Next-Gen Local Voice Typing for Windows

TalkType is a studio-grade, 100% offline local voice typing application powered by **faster-whisper** (CTranslate2 INT8) and **PyQt6**. Built with Cursor's developer-editorial design system and a physics-driven **Motion Engine**, TalkType provides fast, fluid, and focus-safe dictation across any Windows application with smart punctuation, multi-language support (English, Bengali বাংলা, Hindi हिन्दी), and a luxury floating capsule HUD.

---

## ✨ Highlights

* **100% Local & Private:** Runs entirely on your CPU with CTranslate2 INT8 quantization—zero external network calls, zero API keys, and zero telemetry during speech recognition.
* **Cursor Editorial Design:**
  * Quietly confident warm cream canvas (`#f7f7f4`) with crisp white cards (`#ffffff`) and warm near-black ink (`#26251e`).
  * Restrained brand voltage in **Cursor Orange** (`#f54e00`).
  * Hairline-only depth (1px `#e6e5e0`); no heavy drop shadows.
  * AI-timeline pastel pill tokens for model dialects (lavender, peach, blue, mint).
* **Physics Motion Engine (`talktype/ui/motion.py`):**
  * **Harmonic Spring Dampers:** Second-order differential equation physics for live audio visualizers and tactile toggle switches.
  * **Animated Stack Transitions:** Smooth slide and crossfade transitions between tabs using `OutCubic` easing.
  * **Dynamic Island Auto-Sizing:** The floating HUD capsule smoothly interpolates width via `QPropertyAnimation` with zero label clipping.
* **Focus-Safe Integration:** Powered by `WS_EX_NOACTIVATE` so typing focus is never stolen from your code editor or document.
* **14 Offline Speech Models:** Rapidly switch between general multilingual models and dedicated fine-tuned models for Bengali and Hindi across Tiny, Small, and Medium tiers.
* **Smart Text Formatter:** Context-aware capitalization, spoken punctuation conversion, and direct clipboard pasting.

---

## 🏗️ Project Architecture

TalkType is organized as a modular, production-ready Python package:

```
talktype-project/
│
├── talktype/                      # Main Python Application Package
│   ├── __init__.py                # Package exports & versioning
│   ├── app.py                     # App orchestrator, tray manager & worker bridge
│   ├── config.py                  # Configuration loader & schema defaults
│   │
│   ├── core/                      # Audio & Dictation Core
│   │   ├── __init__.py
│   │   ├── audio_recorder.py      # Sounddevice microphone streaming & volume telemetry
│   │   ├── hotkey_listener.py     # Pynput global keyboard hook & timing engine
│   │   ├── transcriber.py         # Faster-Whisper / CTranslate2 model runner
│   │   ├── text_formatter.py      # Spoken punctuation & smart case formatting
│   │   ├── text_injector.py       # Focus-safe clipboard / keystroke injector
│   │   └── sound_effects.py       # Acoustic feedback micro-chimes
│   │
│   ├── models/                    # Model Catalog & Distribution
│   │   ├── __init__.py
│   │   └── catalog.py             # 14-model catalog, size verifier & downloader
│   │
│   └── ui/                        # Presentation & Motion Layer
│       ├── __init__.py
│       ├── motion.py              # Physics engine (SpringDamper, AnimatedStackedWidget)
│       ├── dashboard.py           # Studio Dashboard with Cursor editorial design
│       └── pill_hud.py            # Floating capsule HUD overlay
│
├── diagnostics/                   # Diagnostic & Verification Suite
│   ├── test_mic.py                # Live microphone audio test
│   └── verify_all.py              # Comprehensive 5-stage offline audit
│
├── models/                        # Local Offline Model Weights (Git-ignored)
│   ├── small/, base/, tiny/       # Multilingual models
│   ├── *.en/                      # English-only models
│   ├── bengali.*/                 # Specialized Bengali models (Tiny, Small, Medium)
│   └── hindi.*/                   # Specialized Hindi models (Tiny, Small, Medium)
│
├── config.example.json            # Tracked configuration template
├── config.json                    # Local active configuration (Git-ignored)
├── main.py                        # Root launcher entry point
├── run.bat                        # Standard Windows batch launcher
├── run_hidden.vbs                 # Silent background mode launcher
├── requirements.txt               # Pinned Python dependencies
└── README.md                      # Documentation & guides
```

---

## 🎬 Motion Engine & Animation Architecture

TalkType integrates a custom motion system inspired by modern design engineering (`motion.dev` / Framer Motion):

1. **`SpringDamper`:**
   Implements continuous harmonic spring physics:
   $$\ddot{x} + 2 \zeta \omega \dot{x} + \omega^2 x = 0$$
   Used in `CursorVUMeter` and `UnifiedIndicatorWidget` so volume spikes react with lifelike momentum, zero jitter, and smooth return physics.
2. **`AnimatedStackedWidget`:**
   Replaces jarring instant page flips with 240ms horizontal slide transitions using `QEasingCurve.Type.OutCubic`.
3. **`CursorToggleSwitch`:**
   Custom animated toggle that smoothly slides its thumb across the capsule track when clicked.
4. **`FloatingPillHUD` Motion Interpolation:**
   The capsule smoothly expands and contracts when transitioning between states (`Hold`, `Listening`, `Transcribing`, `Done`) without jumping.

---

## ⌨️ How to Use (Long-Press Toggle)

1. **Start Listening:** **Hold `Right Ctrl`** for **1.0 second**. 
   * You will see the circular countdown ring fill and hear an activation chime 🔔.
   * Release the key and speak naturally into your microphone.
2. **Stop & Auto-Paste:** **Tap `Right Ctrl`** once (or hold again). 
   * TalkType transcribes, polishes punctuation, and pastes the text directly at your cursor!

> **Note:** The trigger key and hold duration can be customized at any time in `config.json` or through the Studio Dashboard.

---

## 🧠 Offline Model Catalog (14 Supported Models)

TalkType supports 14 models that can be switched on the fly via the Windows System Tray or Studio Dashboard:

| Language | Model Key | Variant | Speed | RAM | Best For |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Bengali (বাংলা)** | `bengali.tiny` | **Tiny** | ⚡⚡⚡⚡ Instant (~80ms) | ~250 MB | Ultra-light dialect dictation |
| | `bengali` | **Small** | ⚡⚡⚡ Fast (~300ms) | ~600 MB | Accurate Bengali vocabulary & regional speech |
| | `bengali.medium` | **Medium** | ⚡ Studio (~800ms) | ~2.5 GB | Benchmark winner for complex Bengali audio |
| **Hindi (हिन्दी)** | `hindi.tiny` | **Tiny** | ⚡⚡⚡⚡ Instant (~80ms) | ~250 MB | Ultra-fast Hindi voice typing |
| | `hindi` | **Small** | ⚡⚡ Fast (~350ms) | ~1.0 GB | Conversational Hindi & Devanagari script |
| | `hindi.medium` | **Medium** | ⚡ Studio (~800ms) | ~2.5 GB | Maximum precision Devanagari recognition |
| **English Only** | `tiny.en` | Tiny | ⚡⚡⚡⚡ Instant (~60ms) | ~200 MB | Fast English notes & messaging |
| | `base.en` | Base | ⚡⚡⚡ Very Fast (~140ms) | ~350 MB | Everyday English dictation |
| | `small.en` | Small | ⚡⚡ Fast (~300ms) | ~1.0 GB | Coding & technical documentation |
| | `medium.en` | Medium | ⚡ Studio (~650ms) | ~2.5 GB | Studio-grade English precision |
| **Multilingual** | `tiny` | Tiny | ⚡⚡⚡⚡ Instant (~80ms) | ~250 MB | 99 languages lightweight |
| | `base` | Base | ⚡⚡⚡ Very Fast (~180ms) | ~400 MB | 99 languages balanced |
| | `small` | Small | ⚡⚡ Fast (~350ms) | ~1.0 GB | **Recommended** balanced general model |
| | `medium` | Medium | ⚡ Studio (~800ms) | ~2.5 GB | Heavyweight multilingual studio model |

---

## 🚀 Installation & Setup

### Prerequisites
* Windows 10 / 11 (64-bit)
* Python 3.10+
* Working microphone

### 1. Clone the Repository
```bash
git clone https://github.com/SaptarshiCodes/TalkType.git
cd TalkType
```

### 2. Set Up Virtual Environment & Dependencies
```bash
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run TalkType
* **Standard Launch (Console + Tray):**
  ```bash
  python main.py
  ```
  *or double-click `run.bat`*
* **Silent Background Mode (Tray Only):**
  *Double-click `run_hidden.vbs`*

### 4. Run System Verification
```bash
python diagnostics/verify_all.py
```

---

## ⚙️ Configuration (`config.json`)

```json
{
  "hotkey": "ctrl_r",
  "trigger_mode": "long_press_toggle",
  "long_press_seconds": 1.0,
  "model_size": "small",
  "device": "cpu",
  "compute_type": "int8",
  "language": "auto",
  "auto_format": true,
  "initial_prompt": "Hello! Voice typing in English, বাংলা, or हिन्दी.",
  "paste_mode": "clipboard",
  "restore_clipboard": true,
  "sound_feedback": true,
  "show_overlay": true,
  "sample_rate": 16000
}
```

---

## 🛡️ License
MIT License. Built with `faster-whisper` and `PyQt6`.

"""Per-language confirm/deny lexicon data for the voice deterministic guard.

Data only — no logic. See confirm_guard.py for matching behavior.
ADR-0036 D2 / D3. Extends ADR-0026 (deterministic Python guards over LLM
judgment) to spoken-confirmation interpretation.

Each language maps to an "affirm" and "deny" list of whole-word tokens or
whole phrases (native script + common romanized forms). Entries are matched
case-insensitively against normalized, tokenized transcript text — see
confirm_guard.normalize / classify_confirmation.
"""

from __future__ import annotations

CONFIRM_LEXICON: dict[str, dict[str, list[str]]] = {
    "en": {
        "affirm": [
            "yes",
            "yeah",
            "yep",
            "yup",
            "confirm",
            "confirmed",
            "correct",
            "ok",
            "okay",
            "sure",
            "right",
            "go ahead",
            "do it",
            "please do",
        ],
        "deny": [
            "no",
            "nope",
            "nah",
            "cancel",
            "don't",
            "do not",
            "stop",
            "wrong",
            "nevermind",
            "never mind",
        ],
    },
    # COORDINATOR-REVIEW-REQUIRED (native-speaker pass) before 1b.
    "hi": {
        "affirm": [
            "हाँ",
            "हां",
            "जी",
            "जी हाँ",
            "ठीक",
            "ठीक है",
            "सही",
            "करो",
            "कर दो",
            "haan",
            "ji",
            "theek",
            "theek hai",
            "sahi",
            "karo",
            "ok",
        ],
        "deny": [
            "नहीं",
            "ना",
            "मत",
            "रुको",
            "रद्द",
            "नहीं चाहिए",
            "nahi",
            "na",
            "mat",
            "ruko",
            "radd",
        ],
    },
    # COORDINATOR-REVIEW-REQUIRED (native-speaker pass) before 1b.
    "te": {
        "affirm": [
            "అవును",
            "సరే",
            "ఔను",
            "చెయ్యి",
            "ఓకే",
            "avunu",
            "sare",
            "oke",
            "cheyyi",
        ],
        "deny": [
            "వద్దు",
            "లేదు",
            "కాదు",
            "ఆపు",
            "vaddu",
            "ledu",
            "kaadu",
            "aapu",
        ],
    },
    # COORDINATOR-REVIEW-REQUIRED (native-speaker pass) before 1b.
    "ta": {
        "affirm": [
            "ஆம்",
            "ஆமா",
            "சரி",
            "செய்",
            "ஓகே",
            "aam",
            "aama",
            "sari",
            "sei",
            "oke",
        ],
        "deny": [
            "இல்லை",
            "வேண்டாம்",
            "நிறுத்து",
            "illai",
            "vendaam",
            "nirutthu",
        ],
    },
    # COORDINATOR-REVIEW-REQUIRED (native-speaker pass) before 1b.
    "kn": {
        "affirm": [
            "ಹೌದು",
            "ಸರಿ",
            "ಆಗಲಿ",
            "ಮಾಡು",
            "ಓಕೆ",
            "haudu",
            "sari",
            "aagali",
            "maadu",
        ],
        "deny": [
            "ಇಲ್ಲ",
            "ಬೇಡ",
            "ನಿಲ್ಲಿಸು",
            "illa",
            "beda",
            "nillisu",
        ],
    },
    # COORDINATOR-REVIEW-REQUIRED (native-speaker pass) before 1b.
    "ml": {
        "affirm": [
            "അതെ",
            "ശരി",
            "ചെയ്യൂ",
            "ഓകെ",
            "athe",
            "sari",
            "cheyyu",
            "oke",
        ],
        "deny": [
            "ഇല്ല",
            "വേണ്ട",
            "നിർത്തുക",
            "illa",
            "venda",
            "nirthuka",
        ],
    },
    # COORDINATOR-REVIEW-REQUIRED (native-speaker pass) before 1b.
    "mr": {
        "affirm": [
            "हो",
            "होय",
            "बरं",
            "ठीक",
            "ठीक आहे",
            "कर",
            "ओके",
            "ho",
            "hoy",
            "bara",
            "theek aahe",
            "kar",
            "oke",
        ],
        "deny": [
            "नाही",
            "नको",
            "थांबा",
            "रद्द",
            "nahi",
            "nako",
            "thamba",
            "radd",
        ],
    },
    # COORDINATOR-REVIEW-REQUIRED (native-speaker pass) before 1b.
    "gu": {
        "affirm": [
            "હા",
            "હાં",
            "બરાબર",
            "ઠીક",
            "કરો",
            "ઓકે",
            "haa",
            "barabar",
            "theek",
            "karo",
        ],
        "deny": [
            "ના",
            "નહીં",
            "નહિ",
            "રદ",
            "બંધ",
            "na",
            "nahi",
            "radd",
            "bandh",
        ],
    },
    # COORDINATOR-REVIEW-REQUIRED (native-speaker pass) before 1b.
    "bn": {
        "affirm": [
            "হ্যাঁ",
            "হ্যা",
            "ঠিক",
            "ঠিক আছে",
            "করো",
            "ওকে",
            "hyan",
            "thik",
            "thik ache",
            "koro",
            "oke",
        ],
        "deny": [
            "না",
            "নাহ",
            "বন্ধ",
            "বাতিল",
            "na",
            "nah",
            "bondho",
            "batil",
        ],
    },
}

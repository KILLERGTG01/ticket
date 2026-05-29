import re
from langdetect import DetectorFactory, detect, LangDetectException

DetectorFactory.seed = 42

_CC_RE      = re.compile(r'\b(?:\d[ -]?){13,16}\b')
_SSN_RE     = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
_EMAIL_RE   = re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b')
_PHONE_RE   = re.compile(r'(?<![A-Za-z]{2}-)(?<![A-Za-z]{3}-)(\+?\d[\d\s\-().]{7,}\d)')
_NON_PII_ID_RE = re.compile(r'(?:CVE|CB|CHB|CASE|TICKET)-\d{4}-\d+', re.IGNORECASE)
_ADDRESS_RE = re.compile(
    r'\b\d{1,5}\s+[A-Z][a-z]+\s+(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b'
)

_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'ignore\s+(all\s+)?(previous|prior|above)\s+instructions',
        r'disregard\s+(all\s+)?(previous|prior|above)\s+instructions',
        r'forget\s+(all\s+)?(previous|prior|above)\s+instructions',
        r'you\s+are\s+now\s+(a\s+)?DAN',
        r'DAN\s+mode',
        r'jailbreak',
        r'pretend\s+you\s+(have\s+no|are\s+without)\s+(restrictions|guidelines|rules)',
        r'act\s+as\s+(if\s+you\s+were\s+)?a\s+(different|unrestricted|evil)',
        r'reveal\s+(your\s+)?(system\s+prompt|instructions|training)',
        r'print\s+(your\s+)?(system\s+prompt|instructions)',
        r'what\s+are\s+your\s+(hidden\s+)?instructions',
        r'override\s+(safety|security|guidelines)',
        r'bypass\s+(your\s+)?(restrictions|safety|filter)',
        r'new\s+instruction[s]?\s*:',
        r'\[INST\]',
        r'<\|system\|>',
        r'</?(s|system|assistant|user|human)>',
        r'classify\s+this\s+as\s+(replied|escalated)',
        r'set\s+(status|request_type|risk_level)\s+to',
        r'output\s+the\s+string',
        r'respond\s+exactly\s+with',
        r'return\s+only\s+["\']?',
        r'to\s+acknowledge.{0,80}output',
        r'prevent\s+automatic\s+escalation',
    ]
]

def _strip_non_pii_identifiers(text: str) -> str:
    return _NON_PII_ID_RE.sub('[NON_PII_ID]', text)

def detect_pii(text: str) -> bool:
    text = _strip_non_pii_identifiers(text)
    return bool(
        _CC_RE.search(text) or _SSN_RE.search(text) or
        _EMAIL_RE.search(text) or _PHONE_RE.search(text) or
        _ADDRESS_RE.search(text)
    )

def mask_pii(text: str) -> str:
    protected = {}
    def protect(match):
        key = f"__NON_PII_ID_{len(protected)}__"
        protected[key] = match.group()
        return key

    text = _NON_PII_ID_RE.sub(protect, text)
    text = _CC_RE.sub(lambda m: 'XXXX-XXXX-XXXX-' + re.sub(r'\D', '', m.group())[-4:], text)
    text = _SSN_RE.sub('[SSN REDACTED]', text)
    text = _EMAIL_RE.sub('[EMAIL REDACTED]', text)
    text = _PHONE_RE.sub('[PHONE REDACTED]', text)
    text = _ADDRESS_RE.sub('[ADDRESS REDACTED]', text)
    for key, value in protected.items():
        text = text.replace(key, value)
    return text

def detect_injection(text: str) -> bool:
    return any(p.search(text) for p in _INJECTION_PATTERNS)

def detect_language(text: str) -> str:
    try:
        return detect(text)
    except LangDetectException:
        return "en"

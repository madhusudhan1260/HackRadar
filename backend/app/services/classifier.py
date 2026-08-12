"""Classify a hackathon into categories and extract technology tags.

Rule-based by default (fast, free, offline). If ANTHROPIC_API_KEY is set,
`llm_enrich` can refine the result for listings whose text is too vague for
keyword matching.
"""
from __future__ import annotations

import json
import re

from ..config import settings

# --------------------------------------------------------------------------
# Category vocabulary. Order matters only for readability.
# --------------------------------------------------------------------------

CATEGORIES: dict[str, list[str]] = {
    "ai-ml": [
        "ai", "artificial intelligence", "machine learning", "ml", "deep learning",
        "neural network", "llm", "genai", "generative ai", "nlp", "computer vision",
        "pytorch", "tensorflow", "transformer", "rag", "agentic", "diffusion",
        "reinforcement learning", "data science", "mlops",
    ],
    "web": [
        "web", "frontend", "front-end", "backend", "back-end", "full stack",
        "fullstack", "react", "next.js", "nextjs", "vue", "angular", "svelte",
        "node", "django", "flask", "fastapi", "javascript", "typescript",
        "html", "css", "tailwind", "web app", "webdev",
    ],
    "cybersecurity": [
        "cyber", "security", "infosec", "ctf", "capture the flag", "pentest",
        "penetration testing", "cryptography", "malware", "vulnerability",
        "ethical hacking", "appsec", "threat", "forensics", "zero trust",
    ],
    "cloud": [
        "cloud", "aws", "azure", "gcp", "google cloud", "kubernetes", "docker",
        "serverless", "devops", "terraform", "microservices", "cloud native",
        "lambda", "s3", "ci/cd",
    ],
    "blockchain": [
        "blockchain", "web3", "solidity", "ethereum", "smart contract", "defi",
        "nft", "crypto", "polygon", "solana", "zk", "dao",
    ],
    "mobile": [
        "mobile", "android", "ios", "flutter", "react native", "kotlin", "swift",
        "app development", "cross-platform",
    ],
    "data": [
        "data analytics", "big data", "sql", "power bi", "tableau", "etl",
        "data engineering", "spark", "hadoop", "visualization", "dashboard",
    ],
    "iot-hardware": [
        "iot", "embedded", "arduino", "raspberry pi", "robotics", "drone",
        "hardware", "sensor", "firmware", "vlsi", "chip", "semiconductor", "arm",
    ],
    "fintech": [
        "fintech", "banking", "payments", "trading", "quant", "insurance",
        "financial", "upi", "lending",
    ],
    "healthtech": [
        "health", "healthcare", "medtech", "medical", "biotech", "clinical",
        "diagnosis", "patient", "pharma",
    ],
    "gamedev": ["game", "gamedev", "unity", "unreal", "godot", "game jam", "xr", "ar/vr", "metaverse"],
    # Deliberately no bare "design" — it matches "system design", "chip design".
    "design": ["ui/ux", "ux design", "figma", "product design", "prototyping",
               "graphic design", "design thinking", "user experience"],
    "sustainability": ["climate", "sustainab", "green", "energy", "carbon", "environment", "agritech"],
    "open-source": ["open source", "opensource", "oss", "hacktoberfest", "foss"],
}

# Technology tags we want to surface on the card. Keyed by the canonical
# label, valued by the aliases that appear in the wild.
TECH_TAGS: dict[str, list[str]] = {
    "Python": ["python", "django", "flask", "fastapi", "pandas"],
    "JavaScript": ["javascript", "js", "node.js", "nodejs"],
    "TypeScript": ["typescript"],
    "React": ["react", "next.js", "nextjs"],
    "C++": ["c++", "cpp"],
    "Java": ["java "],
    "Go": ["golang"],
    "Rust": ["rust"],
    "SQL": ["sql", "postgres", "mysql"],
    "HTML/CSS": ["html", "css", "tailwind"],
    "Machine Learning": ["machine learning", "ml model", "scikit"],
    "Deep Learning": ["deep learning", "pytorch", "tensorflow", "neural network"],
    "AI": ["ai", "artificial intelligence"],
    "LLM": ["llm", "gpt", "claude", "gemini", "generative ai", "genai", "prompt"],
    "Data Science": ["data science", "data analytics", "pandas"],
    "NLP": ["nlp", "natural language"],
    "Computer Vision": ["computer vision", "opencv", "image recognition"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure"],
    "GCP": ["gcp", "google cloud"],
    "Docker": ["docker", "container"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Solidity": ["solidity", "smart contract"],
    "Flutter": ["flutter", "dart"],
    "Android": ["android", "kotlin"],
    "iOS": ["ios", "swift"],
    "Cybersecurity": ["cybersecurity", "infosec", "pentest", "ctf"],
    "IoT": ["iot", "arduino", "raspberry pi", "embedded"],
    "Blockchain": ["blockchain", "web3", "ethereum"],
    "UI/UX": ["ui/ux", "figma", "ux design"],
}


def _blob(*values: str | None) -> str:
    return " ".join(v for v in values if v).lower()


def classify(title: str, description: str = "", extra_tags: list[str] | None = None) -> list[str]:
    """Return the categories a hackathon belongs to, most confident first."""
    text = _blob(title, description, " ".join(extra_tags or []))
    scores: dict[str, int] = {}
    for category, keywords in CATEGORIES.items():
        hits = sum(1 for kw in keywords if _contains(text, kw))
        if hits:
            # Title mentions count double.
            title_hits = sum(1 for kw in keywords if _contains(title.lower(), kw))
            scores[category] = hits + title_hits
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    result = [c for c, _ in ranked[:4]]
    return result or ["general"]


def canonical_tag(raw: str) -> str | None:
    """Map a platform tag onto our canonical label, if we know it.

    'gcp' and 'Google Cloud' both become 'GCP', so a listing never carries
    the same technology twice under different spellings.
    """
    value = (raw or "").strip().lower()
    if not value:
        return None
    for label, aliases in TECH_TAGS.items():
        if value == label.lower() or any(value == a.strip().lower() for a in aliases):
            return label
    return None


def extract_tags(title: str, description: str = "", extra_tags: list[str] | None = None) -> list[str]:
    """Pull the technology stack out of the listing text."""
    text = _blob(title, description, " ".join(extra_tags or []))
    found = [label for label, aliases in TECH_TAGS.items() if any(_contains(text, a) for a in aliases)]
    seen = {label.lower() for label in found}

    # Keep any platform-supplied theme tags we did not recognise — they are
    # often the most specific signal ("sustainability", "fintech-india").
    for raw in extra_tags or []:
        canonical = canonical_tag(raw)
        if canonical:
            # Already represented (or about to be) by its canonical spelling.
            if canonical.lower() not in seen:
                found.append(canonical)
                seen.add(canonical.lower())
            continue
        pretty = raw.strip().title()
        if pretty and pretty.lower() not in seen and len(found) < 12:
            found.append(pretty)
            seen.add(pretty.lower())
    return found[:12]


def _contains(text: str, keyword: str) -> bool:
    if not keyword:
        return False
    if keyword.isalnum() and len(keyword) <= 3:
        # Short tokens like "ai", "ml", "js" need word boundaries or they
        # match inside unrelated words ("email" would match "ai").
        return re.search(rf"\b{re.escape(keyword)}\b", text) is not None
    return keyword in text


# --------------------------------------------------------------------------
# Optional LLM refinement
# --------------------------------------------------------------------------

_LLM_PROMPT = """You classify hackathon listings. Return ONLY JSON, no prose.

Schema:
{{"categories": [<up to 4 from: {cats}>],
 "tags": [<up to 8 technology names>],
 "summary": "<one sentence, max 25 words>",
 "student_friendly": <true|false>}}

Listing title: {title}
Listing description: {description}"""


def llm_enrich(title: str, description: str) -> dict | None:
    """Refine classification with Claude. Returns None if unavailable."""
    if not settings.ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    prompt = _LLM_PROMPT.format(
        cats=", ".join(CATEGORIES),
        title=title,
        description=(description or "")[:2000],
    )
    try:
        resp = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in resp.content if block.type == "text")
        match = re.search(r"\{.*\}", text, re.S)
        return json.loads(match.group(0)) if match else None
    except Exception:
        # Enrichment is a nice-to-have; never let it break ingestion.
        return None

"""
AI Service - Rewrites stories into viral hooks using local Ollama (Llama 3)
No API keys needed - runs completely free locally
"""

import json
import requests
import re
from typing import Optional

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3"

# Viral hook templates for different niches
HOOK_TEMPLATES = {
    "movie": [
        "Nobody expected {} to react like THIS…",
        "Did you know {} almost quit the movie?",
        "What happened when {} went too far on set?",
        "The {} scene that was COMPLETELY improvised",
        "{} broke character and this is what happened",
    ],
    "celebrity": [
        "The truth about {} will SHOCK you",
        "{} just revealed this and fans went WILD",
        "What {} did next surprised EVERYONE",
        "This {} story will give you goosebumps",
        "{} opened up about this for the FIRST time",
    ],
    "crime": [
        "The detective noticed ONE thing... {}",
        "What police found in {} was disturbing",
        "The {} case that STILL haunts investigators",
        "{} left this clue behind - and it changed everything",
        "Nobody expected the {} twist ending",
    ],
    "sports": [
        "This {} moment broke the internet",
        "What {} did in the final seconds was UNREAL",
        "The {} play that changed the game forever",
        "{} just made history and here's how",
        "This {} comeback was INCREDIBLE",
    ],
    "story": [
        "This {} story will restore your faith in humanity",
        "The moment {} realized everything changed...",
        "Nobody expected this {} twist",
        "This {} went viral for a reason",
        "What happened during {} was UNEXPECTED",
    ],
}


def detect_niche(text: str) -> str:
    """Detect the niche/topic of the story"""
    text_lower = text.lower()
    
    niche_keywords = {
        "movie": ["movie", "film", "actor", "actress", "scene", "director", "hollywood", 
                   "bollywood", "cinema", "starred", "filming", "set", "audition"],
        "celebrity": ["celebrity", "famous", "star", "interview", "revealed", "confessed",
                      "admitted", "opened up", "secret", "rumor"],
        "crime": ["crime", "murder", "killer", "detective", "police", "case", "investigation",
                  "mystery", "suspect", "evidence", "court", "trial"],
        "sports": ["sport", "game", "player", "team", "champion", "match", "win", "victory",
                   "playoff", "tournament", "record"],
    }
    
    best_niche = "story"
    best_score = 0
    
    for niche, keywords in niche_keywords.items():
        score = 0
        for keyword in keywords:
            if keyword in text_lower:
                score += 1
        if score > best_score:
            best_score = score
            best_niche = niche
    
    return best_niche


def generate_hook(text: str) -> str:
    """Generate a viral hook using Ollama or fallback templates"""
    if _is_ollama_available():
        return _generate_with_ollama(text)
    else:
        return _generate_with_template(text)


def _is_ollama_available() -> bool:
    """Check if Ollama is running"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False


def _generate_with_ollama(text: str) -> str:
    """Generate viral hook using local Ollama Llama 3"""
    prompt = f"""You are a viral YouTube Shorts content creator. Rewrite this story into a 
short, attention-grabbing hook that makes people WANT to watch the full video.

Rules:
- Must be under 10 words
- Create curiosity gap (make people ask "what happened?")
- Use emotional triggers (shock, surprise, curiosity)
- NO clickbait that lies
- Add relevant emojis where appropriate (😱🔥👀💀🎬)
- Make it scroll-stopping

Story: {text}

Viral Hook:"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.8,
                    "top_p": 0.9,
                    "max_tokens": 50,
                }
            },
            timeout=30
        )
        
        if response.status_code == 200:
            hook = response.json().get("response", "").strip()
            # Clean up the hook
            hook = hook.strip('"').strip("'")
            hook = re.sub(r'^Hook:\s*', '', hook)
            hook = re.sub(r'^Viral Hook:\s*', '', hook)
            return hook
            
    except Exception as e:
        print(f"Ollama error: {e}")
    
    return _generate_with_template(text)


def _generate_with_template(text: str) -> str:
    """Generate hook using template-based approach (no AI needed)"""
    niche = detect_niche(text)
    templates = HOOK_TEMPLATES.get(niche, HOOK_TEMPLATES["story"])
    
    # Extract key entity (first few meaningful words)
    words = text.split()
    key_entity = " ".join(words[:min(5, len(words))])
    
    # Pick a random template and fill it
    import random
    template = random.choice(templates)
    hook = template.replace("{}", key_entity)
    
    # Add emoji
    emojis = {
        "movie": "🎬",
        "celebrity": "🌟", 
        "crime": "🔍",
        "sports": "🏆",
        "story": "😱",
    }
    emoji = emojis.get(niche, "🔥")
    
    # Truncate if too long
    if len(hook) > 80:
        hook = hook[:77] + "..."
    
    return f"{emoji} {hook}"


def add_hashtags(text: str) -> str:
    """Generate relevant hashtags"""
    niche = detect_niche(text)
    
    niche_hashtags = {
        "movie": "#movies #shorts #viral #facts #hollywood #behindthescenes",
        "celebrity": "#celebrity #shorts #viral #facts #trending",
        "crime": "#truecrime #mystery #shorts #viral #crime",
        "sports": "#sports #shorts #viral #athlete #highlights",
        "story": "#storytime #shorts #viral #fyp #trending",
    }
    
    return niche_hashtags.get(niche, "#shorts #viral #fyp #trending #facts")


def rewrite_story(text: str) -> dict:
    """
    Main function: takes story text, returns dict with:
    - hook: viral hook text
    - niche: detected category
    - hashtags: relevant hashtags
    """
    hook = generate_hook(text)
    niche = detect_niche(text)
    hashtags = add_hashtags(text)
    
    return {
        "hook": hook,
        "niche": niche,
        "hashtags": hashtags,
    }


# ═══════════════════════════════════════
# SEO Metadata (title / description / hashtags / tags)
# ═══════════════════════════════════════

# Per-niche SEO building blocks used by the offline (no-Ollama) fallback
SEO_NICHE_DATA = {
    "movie": {
        "label": "movie facts",
        "tags": "movie facts, behind the scenes, hollywood, film trivia, movie scenes, cinema, actors, movie trivia",
    },
    "celebrity": {
        "label": "celebrity story",
        "tags": "celebrity facts, celebrity news, famous people, hollywood, entertainment, celebrity story, trending",
    },
    "crime": {
        "label": "true crime story",
        "tags": "true crime, crime story, mystery, detective, investigation, crime documentary, unsolved",
    },
    "sports": {
        "label": "sports story",
        "tags": "sports highlights, athlete, sports facts, championship, greatest moments, sports story",
    },
    "story": {
        "label": "story time",
        "tags": "storytime, interesting story, amazing story, facts, viral story, did you know",
    },
}

# Common words skipped when pulling keywords out of the story
_SEO_STOPWORDS = {
    "the", "and", "for", "you", "your", "that", "this", "with", "was", "were",
    "his", "her", "had", "has", "have", "but", "not", "all", "any", "one", "two",
    "who", "what", "when", "where", "why", "how", "they", "them", "their", "there",
    "been", "being", "from", "into", "than", "then", "these", "those", "would",
    "could", "should", "about", "after", "before", "during", "because", "while", "over",
    "just", "like", "out", "got", "get", "did", "does", "done", "youre", "its",
    "also", "very", "really", "much", "many", "some", "only", "even", "still",
}


def _content_keywords(text: str, limit: int = 6) -> list:
    """Extract the most useful content keywords from the story (order preserved)."""
    words = re.findall(r"[A-Za-z']{3,}", text.lower())
    seen, out = set(), []
    for w in words:
        if w in _SEO_STOPWORDS or w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= limit:
            break
    return out


def _clip(text: str, limit: int) -> str:
    """Trim text to a hard character limit with an ellipsis when needed."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _seo_with_ollama(text: str, hook: str, niche: str) -> Optional[dict]:
    """Generate SEO metadata with local Ollama. Returns None on any failure."""
    prompt = f"""You are an expert YouTube Shorts SEO strategist. Generate optimized metadata
for a Short built from the story below. Reply with ONLY a minified JSON object, no other text.

JSON schema:
{{"title":"...","description":"...","hashtags":"#a #b #c","tags":"tag1, tag2, tag3"}}

Rules:
- title: max 95 characters, main keyword near the front, curiosity-driven, at most 1 emoji, no quotes
- description: 2-4 short paragraphs (max 1500 chars). Start with a hook line, summarize the story,
  add a call to action (Like & Follow), then finish with the hashtags line
- hashtags: 8-10 hashtags separated by single spaces, each starting with #
- tags: 12-15 comma-separated search tags (no #), mix of broad and long-tail keywords
- Do not invent facts that are not in the story

Detected niche: {niche}
Viral hook: {hook}
Story: {text}

JSON:"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "top_p": 0.9},
            },
            timeout=60,
        )
        if response.status_code != 200:
            return None

        raw = response.json().get("response", "")
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None

        obj = json.loads(match.group(0))
        title = str(obj.get("title", "")).strip().strip('"\'')
        description = str(obj.get("description", "")).strip()
        hashtags = str(obj.get("hashtags", "")).strip()
        tags = str(obj.get("tags", "")).strip()
        
        if not title or not description:
            return None
        
        # Normalize hashtags: models sometimes return comma-separated words or
        # tokens without a leading '#' — the frontend renders one chip per #tag
        tokens = [t for t in re.split(r"[\s,]+", hashtags) if t.strip()]
        hashtags = " ".join(f"#{t.strip().lstrip('#')}" for t in tokens if t.strip().lstrip('#'))
        
        # Enforce platform limits (YouTube: title 100, description 5000, tags 500)
        return {
            "title": _clip(title, 95),
            "description": description[:4800],
            "hashtags": hashtags[:900],
            "tags": tags[:480],
        }
    except Exception as e:
        print(f"Ollama SEO error: {e}")
    
    return None


def _seo_with_template(text: str, hook: str, niche: str) -> dict:
    """Deterministic SEO metadata fallback (works with no AI running)."""
    niche_data = SEO_NICHE_DATA.get(niche, SEO_NICHE_DATA["story"])
    keywords = _content_keywords(text)
    
    # Title: the viral hook if we have one, otherwise the story's opening words
    title = _clip(hook or " ".join(text.split()[:12]), 95)
    
    snippet = text.strip()
    if len(snippet) > 400:
        snippet = snippet[:397].rstrip() + "..."
    
    hashtags = add_hashtags(text)
    for kw in keywords[:2]:
        if f"#{kw}" not in hashtags:
            hashtags += f" #{kw}"
    hashtags = hashtags[:900]
    
    tag_parts = [t.strip() for t in niche_data["tags"].split(",")]
    tag_parts += ["shorts", "youtube shorts", "viral", niche_data["label"]]
    tag_parts += keywords
    # Dedupe (case-insensitive) while keeping order, then fit YouTube's 500-char tag limit
    seen, tags_list = set(), []
    for t in tag_parts:
        t = t.strip()
        key = t.lower()
        if t and key not in seen:
            seen.add(key)
            tags_list.append(t)
    tags = ", ".join(tags_list)
    while len(tags) > 480 and len(tags_list) > 3:
        tags_list.pop()
        tags = ", ".join(tags_list)
    
    description = (
        f"{hook or title}\n\n"
        f"📖 {snippet}\n\n"
        f"In this video: a {niche_data['label']} you won't want to miss. "
        f"👍 Like & Follow for more!\n\n"
        f"{hashtags}"
    )[:4800]
    
    return {
        "title": title,
        "description": description,
        "hashtags": hashtags,
        "tags": tags,
    }


def generate_seo(text: str, hook: str = "", niche: str = "") -> dict:
    """
    Generate SEO metadata for a finished Short:
    {"title": ..., "description": ..., "hashtags": ..., "tags": ...}
    Uses local Ollama when available, otherwise a deterministic template fallback.
    """
    niche = niche or detect_niche(text)
    
    if _is_ollama_available():
        result = _seo_with_ollama(text, hook, niche)
        if result:
            return result
    
    return _seo_with_template(text, hook, niche)

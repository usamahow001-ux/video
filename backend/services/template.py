"""
Template Service - Defines video templates/styles
Now includes the "Evergreen Clips" style with colored text, borders, and branding
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import json


class TextColor(Enum):
    """Available text colors for multi-colored text"""
    WHITE = "white"        # Normal text
    RED = "red"            # Important names/actions  
    BLUE = "blue"          # Objects/facts
    YELLOW = "yellow"      # Shocking/ending
    ACCENT = "#6C5CE7"     # Purple accent


@dataclass
class LayoutConfig:
    """Complete layout configuration for a template"""
    name: str
    description: str
    
    # Canvas
    width: int = 1080
    height: int = 1920
    
    # Background
    background_color: str = "#000000"
    
    # Borders (left and right red strips)
    border_width: int = 8
    border_color: str = "#FF0000"
    
    # Header (logo + channel name)
    header_y: int = 0
    header_height: int = 150
    logo_size: int = 60
    channel_name_fontsize: int = 28
    channel_handle_fontsize: int = 18
    
    # Text area
    text_y: int = 180
    text_width: int = 950
    text_height: int = 500
    text_fontsize: int = 58
    text_color_white: str = "#FFFFFF"
    text_color_red: str = "#FF3333"
    text_color_blue: str = "#4488FF"
    text_color_yellow: str = "#FFD700"
    
    # Video
    video_y: int = 800
    video_height: int = 600
    
    # Watermark/handle
    handle_y: int = 1800
    handle_fontsize: int = 24
    handle_opacity: float = 0.7


# ==========================================
# Pre-defined Templates
# ==========================================
TEMPLATES: Dict[str, LayoutConfig] = {
    "evergreen": LayoutConfig(
        name="Evergreen Clips",
        description="Viral storytelling style with colored text, red borders, and channel branding",
        background_color="#000000",
        border_width=8,
        border_color="#FF0000",
        header_y=0,
        header_height=360,
        logo_size=170,
        channel_name_fontsize=76,
        channel_handle_fontsize=52,
        text_y=390,
        text_width=950,
        text_height=400,
        text_fontsize=56,
        text_color_white="#FFFFFF",
        text_color_red="#FF3333",
        text_color_blue="#4488FF",
        text_color_yellow="#FFD700",
        video_y=860,
        video_height=580,
        handle_y=1700,
        handle_fontsize=64,
        handle_opacity=0.8,
    ),
    "classic": LayoutConfig(
        name="Classic",
        description="Black background, text top, video middle, logo bottom",
        background_color="#000000",
        border_width=0,
        text_fontsize=42,
        text_y=40,
        video_y=650,
        video_height=900,
    ),
    "movie_facts": LayoutConfig(
        name="Movie Facts",
        description="Movie facts with cinematic feel",
        background_color="#0D0D0D",
        border_width=4,
        border_color="#E50914",
        text_fontsize=48,
        text_color_red="#E50914",
        text_color_blue="#4488FF",
        text_color_yellow="#FFD700",
    ),
    "true_crime": LayoutConfig(
        name="True Crime",
        description="Dark mystery style for crime stories",
        background_color="#000000",
        border_width=6,
        border_color="#8B0000",
        text_fontsize=52,
        text_color_white="#CCCCCC",
        text_color_red="#8B0000",
        text_color_blue="#3366CC",
        text_color_yellow="#CC8800",
    ),
}


def get_template(name: str) -> Optional[LayoutConfig]:
    """Get a template by name (case-insensitive)"""
    name_lower = name.lower().replace(" ", "_")
    if name_lower in TEMPLATES:
        return TEMPLATES[name_lower]
    # Fuzzy match
    for key, config in TEMPLATES.items():
        if name_lower in key or key in name_lower:
            return config
    return TEMPLATES.get("classic")


def get_template_names() -> List[str]:
    """Get all template display names"""
    return [t.name for t in TEMPLATES.values()]


def get_template_for_story(story_text: str) -> LayoutConfig:
    """Auto-select best template based on story content"""
    text_lower = story_text.lower()
    
    niche_scores = {
        "evergreen": ["story", "told", "happened", "fact", "believe", "shocking", "unexpected"],
        "movie_facts": ["movie", "film", "actor", "actress", "scene", "director", "hollywood", 
                        "bollywood", "cinema", "starred", "filming"],
        "true_crime": ["crime", "murder", "killer", "detective", "police", "case", "investigation",
                       "mystery", "body", "death"],
    }
    
    best_template = "classic"
    best_score = 0
    
    for template, keywords in niche_scores.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > best_score:
            best_score = score
            best_template = template
    
    return TEMPLATES.get(best_template, TEMPLATES["classic"])


def assign_text_colors(words: List[str]) -> List[tuple[str, str]]:
    """
    Assign random colors to words based on position and content.
    Returns list of (word, color) tuples.
    
    Color strategy - VIBRANT & COLORFUL:
    - Every word has a GOOD chance of being colored
    - First words: mostly white with some blue/red pop
    - Middle words: frequent red, blue, and yellow accents
    - Last 1-2 words: high chance of yellow for punch
    - Important keywords always get colored
    """
    import random
    
    # Words that always get color treatment
    name_keywords = ["samuel", "jackson", "michelle", "rodriguez", "director", "actor", 
                     "actress", "president", "king", "queen", "star", "ronaldo", "messi",
                     "neymar", "mbappé", "mbappe", "haaland", "salah", "mane", "kane",
                     "lewandowski", "de", "bruyne", "modric", "benzema", "vinicius"]
    fact_keywords = ["film", "movie", "set", "scene", "camera", "studio", "hollywood",
                     "award", "oscar", "million", "billion", "record", "goal", "match",
                     "game", "champion", "league", "final", "title", "trophy", "season"]
    
    total = len(words)
    colored_words = []
    
    for i, word in enumerate(words):
        word_lower = word.lower().strip(",.!?;:'\"")
        position_ratio = i / max(total - 1, 1)
        
        color = "white"  # Default
        
        # Always color name/fact keywords
        if word_lower in name_keywords:
            color = "red"
        elif word_lower in fact_keywords:
            color = "blue"
        else:
            # Random color based on position
            roll = random.random()
            
            if position_ratio < 0.25:
                # BEGINNING - mostly white, some blue pops
                if roll < 0.08:
                    color = "red"
                elif roll < 0.20:
                    color = "blue"
                else:
                    color = "white"
                    
            elif position_ratio < 0.75:
                # MIDDLE - colorful zone! 40% chance of color
                if roll < 0.12:
                    color = "red"
                elif roll < 0.28:
                    color = "blue"
                elif roll < 0.40:
                    color = "yellow"
                else:
                    color = "white"
                    
            else:
                # END - high impact colors for last words
                if i >= total - 2:
                    # Last 2 words: 60% color chance for punch
                    if roll < 0.25:
                        color = "yellow"  # yellow for ending impact!
                    elif roll < 0.40:
                        color = "red"
                    elif roll < 0.60:
                        color = "blue"
                    else:
                        color = "white"
                else:
                    # Other tail words: 35% color chance
                    if roll < 0.12:
                        color = "red"
                    elif roll < 0.25:
                        color = "blue"
                    elif roll < 0.35:
                        color = "yellow"
                    else:
                        color = "white"
        
        colored_words.append((word, color))
    
    return colored_words

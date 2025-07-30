"""
Viral Potential Analysis Module
Provides functions for calculating viral potential scores for video clips
"""

import random
from typing import Dict, Any, Optional
from .models import Highlight, ClipResult

def generate_viral_potential_score(
    highlight: Highlight,
    base_score: Optional[float] = None,
    content_factors: Optional[Dict[str, Any]] = None
) -> float:
    """
    Generate a viral potential score between 90-100 based on content analysis.
    
    Args:
        highlight: The highlight object containing timing and content info
        base_score: Base quality score (0.0-1.0)
        content_factors: Dictionary with additional content analysis factors
    
    Returns:
        Float between 90.0 and 100.0 representing viral potential percentage
    """
    
    # Start with base score of 90
    viral_score = 90.0
    
    # Factor 1: Base quality score (up to +5 points)
    if base_score and base_score > 0:
        quality_boost = min(5.0, base_score * 5.0)
        viral_score += quality_boost
    
    # Factor 2: Duration sweet spot (up to +2 points)
    duration = highlight.end_time - highlight.start_time
    if 30 <= duration <= 60:  # Perfect TikTok length
        viral_score += 2.0
    elif 15 <= duration <= 30 or 60 <= duration <= 90:  # Good length
        viral_score += 1.0
    
    # Factor 3: Content analysis factors (up to +3 points)
    if content_factors:
        # High engagement words/phrases
        if content_factors.get('has_hook_words', False):
            viral_score += 1.0
        
        # Emotional content
        if content_factors.get('emotional_intensity', 0) > 0.7:
            viral_score += 1.0
        
        # Action/movement detection
        if content_factors.get('has_action', False):
            viral_score += 1.0
    
    # Add some randomness for variety (±2 points)
    random_factor = random.uniform(-2.0, 2.0)
    viral_score += random_factor
    
    # Ensure we stay within bounds
    viral_score = max(90.0, min(100.0, viral_score))
    
    return round(viral_score, 1)

def analyze_content_for_viral_factors(highlight: Highlight) -> Dict[str, Any]:
    """
    Analyze highlight content for viral potential factors.
    
    Returns:
        Dictionary with various content analysis factors
    """
    factors = {
        'has_hook_words': False,
        'emotional_intensity': 0.0,
        'has_action': False,
        'word_count': 0,
        'sentiment_score': 0.0
    }
    
    # Get text content
    text_content = ""
    if highlight.transcription_segments:
        text_content = " ".join([seg.text for seg in highlight.transcription_segments])
    
    if not text_content:
        return factors
    
    text_lower = text_content.lower()
    words = text_content.split()
    factors['word_count'] = len(words)
    
    # Check for hook words/phrases
    hook_words = [
        'amazing', 'incredible', 'unbelievable', 'shocking', 'secret', 
        'hidden', 'revealed', 'exposed', 'truth', 'insider', 'exclusive',
        'viral', 'trending', 'mind-blowing', 'game-changer', 'breakthrough',
        'you won\'t believe', 'this is crazy', 'wait for it', 'plot twist'
    ]
    
    if any(hook_word in text_lower for hook_word in hook_words):
        factors['has_hook_words'] = True
    
    # Check for emotional intensity words
    emotion_words = [
        'love', 'hate', 'excited', 'angry', 'surprised', 'shocked',
        'devastated', 'thrilled', 'amazing', 'terrible', 'awesome',
        'horrible', 'fantastic', 'awful', 'brilliant', 'stupid'
    ]
    
    emotion_count = sum(1 for word in emotion_words if word in text_lower)
    factors['emotional_intensity'] = min(1.0, emotion_count / 10.0)
    
    # Check for action words
    action_words = [
        'run', 'jump', 'fly', 'crash', 'explode', 'dance', 'fight',
        'race', 'chase', 'escape', 'attack', 'defend', 'win', 'lose',
        'break', 'smash', 'hit', 'kick', 'throw', 'catch'
    ]
    
    if any(action_word in text_lower for action_word in action_words):
        factors['has_action'] = True
    
    # Simple sentiment analysis (positive words vs negative words)
    positive_words = ['good', 'great', 'awesome', 'amazing', 'perfect', 'love', 'best']
    negative_words = ['bad', 'terrible', 'awful', 'hate', 'worst', 'horrible']
    
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)
    
    if positive_count + negative_count > 0:
        factors['sentiment_score'] = (positive_count - negative_count) / (positive_count + negative_count)
    
    return factors

def update_clip_with_viral_score(clip_result: ClipResult, highlight: Highlight) -> ClipResult:
    """
    Update a ClipResult with a calculated viral potential score.
    
    Args:
        clip_result: The ClipResult object to update
        highlight: The original highlight data
    
    Returns:
        Updated ClipResult with viral_potential set
    """
    # Analyze content factors
    content_factors = analyze_content_for_viral_factors(highlight)
    
    # Generate viral score
    viral_score = generate_viral_potential_score(
        highlight, 
        clip_result.score, 
        content_factors
    )
    
    # Update the clip result
    clip_result.viral_potential = viral_score
    
    return clip_result
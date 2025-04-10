import re
import time
import google.generativeai as genai
import datetime
import os
import random
from typing import List, Dict, Tuple, Optional, Any

# Global API key usage tracking
api_key_usage = {}

def clean_markdown_blocks(text):
    """Remove markdown code blocks and other artifacts from text"""
    # Remove code block markers with language specifiers
    text = re.sub(r'```\w*\n', '', text)
    text = re.sub(r'```', '', text)
    
    # Remove inline code markers
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # Remove AI response prefixes
    text = re.sub(r'^(AI:|Assistant:|آنالیز:|ترجمه:)\s*', '', text, flags=re.MULTILINE)
    
    # Remove any HTML comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    
    # Clean up duplicate newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text

class APIKeyManager:
    """
    Class to manage multiple API keys, track usage and avoid rate limits
    """
    def __init__(self, primary_key: str, additional_keys: List[str] = None):
        """
        Initialize the API key manager with a primary key and optional additional keys
        """
        self.primary_key = primary_key
        self.additional_keys = additional_keys or []
        self.all_keys = [primary_key] + self.additional_keys
        
        # Initialize usage tracking for all keys
        global api_key_usage
        for key in self.all_keys:
            if key not in api_key_usage:
                api_key_usage[key] = {
                    'count': 0,
                    'last_used': None,
                    'rate_limited_until': None,
                    'rate_limit_count': 0
                }
    
    def get_next_available_key(self) -> str:
        """
        Get the next available API key that's not rate limited
        
        Returns:
            The next available API key
        """
        global api_key_usage
        now = datetime.datetime.now()
        
        # Filter out rate-limited keys
        available_keys = []
        for key in self.all_keys:
            rate_limited_until = api_key_usage[key].get('rate_limited_until')
            if not rate_limited_until or now > rate_limited_until:
                available_keys.append(key)
        
        if not available_keys:
            # If all keys are rate-limited, pick the one that will be available soonest
            soon_available = sorted(
                self.all_keys, 
                key=lambda k: api_key_usage[k].get('rate_limited_until', now)
            )[0]
            wait_time = (api_key_usage[soon_available]['rate_limited_until'] - now).total_seconds()
            print(f"All API keys are rate limited. Using key with shortest wait time: {wait_time:.1f} seconds")
            return soon_available
            
        # Sort available keys by usage count (prefer least used keys)
        available_keys.sort(key=lambda k: api_key_usage[k]['count'])
        
        # Select a key with some randomness (80% chance of using least used key, 20% chance of using others)
        if len(available_keys) > 1 and random.random() > 0.8:
            # Randomly select from all available keys except the most used one
            return random.choice(available_keys[:-1])
        else:
            # Use the least used key
            return available_keys[0]
    
    def mark_key_used(self, key: str):
        """
        Mark an API key as used, updating its usage statistics
        
        Args:
            key: The API key that was used
        """
        global api_key_usage
        api_key_usage[key]['count'] += 1
        api_key_usage[key]['last_used'] = datetime.datetime.now()
    
    def mark_key_rate_limited(self, key: str, duration_minutes: int = 5):
        """
        Mark an API key as rate limited for a specified duration
        
        Args:
            key: The API key that hit a rate limit
            duration_minutes: How long to avoid using this key
        """
        global api_key_usage
        now = datetime.datetime.now()
        api_key_usage[key]['rate_limited_until'] = now + datetime.timedelta(minutes=duration_minutes)
        api_key_usage[key]['rate_limit_count'] += 1
        
        # Increase cooldown period based on number of rate limits this key has hit
        # This helps prevent repeatedly hitting limits on problematic keys
        rate_limit_count = api_key_usage[key]['rate_limit_count']
        if rate_limit_count > 1:
            # Progressive backoff: 5 min, 15 min, 30 min, 60 min max
            backoff_minutes = min(60, 5 * (2 ** (rate_limit_count - 1)))
            api_key_usage[key]['rate_limited_until'] = now + datetime.timedelta(minutes=backoff_minutes)
            print(f"Key has hit rate limit {rate_limit_count} times. Increasing cooldown to {backoff_minutes} minutes")
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics for all API keys
        
        Returns:
            Dictionary containing usage statistics for all keys
        """
        return api_key_usage

def translate_text_to_persian(text: str, api_key: str, model_name: str = "models/gemini-2.0-flash", 
                             conversation=None, api_keys: List[str] = None) -> Tuple[str, Any]:
    """
    Translate text to Persian using Google's generative AI model

    Args:
        text: The text to translate
        api_key: The API key to use for translation
        model_name: The name of the model to use
        conversation: An optional existing conversation to continue
        api_keys: A list of additional API keys to use for rotation

    Returns:
        The translated text and the conversation for continuation
    """
    # Create API key manager if multiple keys are provided
    key_manager = None
    current_key = api_key
    retry_count = 0
    max_retries = 5
    base_wait_time = 2  # seconds
    
    if api_keys:
        key_manager = APIKeyManager(api_key, api_keys)
        current_key = key_manager.get_next_available_key()
    
    while retry_count <= max_retries:
        try:
            # Configure API key
            genai.configure(api_key=current_key)
            
            # Get generative model
            model = genai.GenerativeModel(model_name)
            
            # Create or continue conversation
            if conversation is None:
                conversation = model.start_chat(history=[])
            
            # Add prompt for translation
            prompt = f"""
            Please translate the following text to Persian (Farsi). 
            Maintain the structure of the text including paragraphs, headings, bullet points and numbering.
            Do not add any additional content not in the original text.
            
            {text}
            """
            
            # Generate response
            response = conversation.send_message(prompt)
            
            # Track usage if using key manager
            if key_manager:
                key_manager.mark_key_used(current_key)
            
            return response.text, conversation
            
        except Exception as e:
            error_str = str(e).lower()
            retry_count += 1
            
            # Handle rate limiting specifically
            if "429" in error_str or "rate limit" in error_str or "quota" in error_str:
                if key_manager:
                    # Mark current key as rate limited
                    print(f"API key hit rate limit. Rotating to next key...")
                    key_manager.mark_key_rate_limited(current_key)
                    
                    # Get next available key
                    current_key = key_manager.get_next_available_key()
                    
                    # If we found a different key, reset retry count to give it a fresh chance
                    if current_key != api_key:
                        retry_count -= 1  # don't count this as a retry
                        continue
                
                # If no key manager or no other keys available, add adaptive delay
                wait_time = base_wait_time * (2 ** retry_count)  # Exponential backoff
                print(f"Rate limit encountered. Waiting {wait_time} seconds before retry {retry_count}/{max_retries}")
                time.sleep(wait_time)
            else:
                # For other errors, wait a shorter time
                print(f"Error during translation: {str(e)}")
                print(f"Retrying in {retry_count} seconds... ({retry_count}/{max_retries})")
                time.sleep(retry_count)
            
            # If we've exhausted all retries, raise the error
            if retry_count > max_retries:
                raise Exception(f"Failed to translate after {max_retries} retries: {str(e)}")
    
    # This should not be reached due to the exception above, but just in case
    raise Exception(f"Failed to translate after {max_retries} retries")

def get_api_key_usage_stats():
    """
    Get current API key usage statistics
    
    Returns:
        Dictionary containing usage statistics for all keys
    """
    return api_key_usage 
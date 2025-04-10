import re
import time
import google.generativeai as genai

def clean_markdown_blocks(text):
    """Remove markdown code block markers and other artifacts"""
    # Remove code block markers with language specifier
    text = re.sub(r'```[a-zA-Z0-9_+-]*\n', '', text)
    text = re.sub(r'```', '', text)
    
    # Remove inline code markers
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # Remove AI response prefixes
    text = re.sub(r'^(AI:|Assistant:|ChatGPT:)\s*', '', text, flags=re.MULTILINE)
    
    # Remove potential HTML comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    
    # Clean up duplicate newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text

def translate_text_to_persian(text, api_key, conversation_history=None):
    """Translate text to Persian using Gemini API"""
    if not text.strip():
        return "", conversation_history
    
    # Initialize retry counter
    retries = 0
    max_retries = 3
    wait_time = 60  # seconds
    
    # Analyze text structure to identify special elements
    has_headings = False
    has_bullet_points = False
    has_numbered_list = False
    has_code_blocks = False
    
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if line:
            # Check for headings (Markdown style)
            if re.match(r'^#{1,6}\s+', line):
                has_headings = True
            # Check for bullet points
            elif re.match(r'^\s*[\*\-\+•]\s+', line):
                has_bullet_points = True
            # Check for numbered lists
            elif re.match(r'^\s*\d+\.\s+', line):
                has_numbered_list = True
            # Check for code blocks
            elif '```' in line or line.startswith('    '):
                has_code_blocks = True
    
    # Add additional instructions based on content structure
    structure_instructions = []
    if has_headings:
        structure_instructions.append("Preserve heading levels like '# Heading 1', '## Heading 2' in your translation.")
    if has_bullet_points:
        structure_instructions.append("Maintain bullet point lists in the same format as the original.")
    if has_numbered_list:
        structure_instructions.append("Keep numbered lists with the same numbering as in the original text.")
    if has_code_blocks:
        structure_instructions.append("Do NOT translate code blocks. Keep them exactly as they are in the original.")
    
    # Configure the Gemini API with the API key
    genai.configure(api_key=api_key)
    
    # Create a model instance
    model = genai.GenerativeModel('models/gemini-2.0-flash')
    
    # Create a ChatSession if we don't have one
    if conversation_history is None:
        # Start a conversation with initial prompt for translation guidelines
        system_prompt = """
        You are a highly skilled English to Persian translator with expertise in technical and educational content.
        
        Guidelines:
        1. Translate the provided English text to natural, fluent Persian.
        2. TECHNICAL TERMS POLICY: Keep technical terms, variable names, and code segments in English.
        3. Use HTML tags to highlight preserved English terms, like: <span dir="ltr">technical_term</span>
        4. Maintain the original text structure, including paragraphs, bullet points, and numbering.
        5. For code blocks or technical examples, do not translate code or commands - keep them in the original English.
        6. When translating headings, make sure to retain any numbering or hierarchical structure.
        
        Term categories to KEEP IN ENGLISH (do not translate these):
        - Software engineering concepts: API, REST, HTTP, frontend, backend, etc.
        - Class names: "UserManager", "DataProcessor", etc.
        - Method and function names: "getUser()", "processData()", etc.
        - Variable names: "userId", "dataValue", etc.
        - Design patterns: "Singleton", "Factory", "Observer", etc.
        - Programming languages: Java, Python, JavaScript, TypeScript, etc.
        - Framework names: React, Angular, Spring, Django, etc.
        - Product names: AWS, Azure, Google Cloud, Kubernetes, etc.
        
        Other important guidelines:
        - Translate from English to Persian in a way that feels natural for Persian readers
        - The translation should be Persian, not Farsi written in Latin alphabet
        - Use the proper Persian equivalents of technical terms when they exist and are commonly used
        """
        
        conversation = model.start_chat(history=[
            {
                "role": "user",
                "parts": system_prompt
            },
            {
                "role": "model",
                "parts": "من آماده ترجمه متن انگلیسی به فارسی با رعایت اصول ذکر شده هستم. لطفاً متن مورد نظر برای ترجمه را ارسال کنید."
            }
        ])
    else:
        # Continue with existing conversation
        conversation = conversation_history
    
    while retries < max_retries:
        try:
            # Add structure-specific instructions to the prompt
            prompt = f"""
            Please translate the following English text to Persian:
            
            {text}
            
            Special instructions for this text:
            - {' '.join(structure_instructions)}
            - Remember to keep technical terms in English, wrapped in <span dir="ltr">...</span> tags.
            - Maintain original text structure including paragraphs, lists, and code blocks.
            """
            
            # Get the response
            response = conversation.send_message(prompt)
            translated_text = response.text
            
            # Clean the translated text
            translated_text = clean_markdown_blocks(translated_text)
            
            return translated_text, conversation
            
        except Exception as e:
            retries += 1
            error_message = str(e)
            
            if "RESOURCE_EXHAUSTED" in error_message or "rate limit" in error_message.lower():
                print(f"\nAPI rate limit reached. Waiting {wait_time} seconds before retry ({retries}/{max_retries})...")
                time.sleep(wait_time)
            else:
                print(f"\nTranslation error: {error_message}. Retrying in {wait_time} seconds ({retries}/{max_retries})...")
                time.sleep(wait_time)
    
    print("\nMaximum retries reached. Translation failed.")
    return "", conversation_history 
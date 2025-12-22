from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationSummaryBufferMemory
import os
from dotenv import load_dotenv
import re
from typing import Dict, Tuple
from langdetect import detect
import time
import threading

from helpers.date_agent import DateAgent
from helpers.langsmith_config import setup_langsmith
from helpers.retrieval import get_rag_context

load_dotenv()

# -- date agent --
date_agent = DateAgent(timezone=os.getenv("DEFAULT_TIMEZONE", "Africa/Cairo"))

# -- LangSmith setup --
setup_langsmith()

# -- LLM and prompt setup --
openai_api_key = os.getenv("OPENAI_API_KEY")
llm = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.5")),
    openai_api_key=openai_api_key
)

# =============================================================================
# Memory Management with TTL Eviction
# =============================================================================

# Configuration
MAX_TOKEN_LIMIT = 500
CHAIN_TTL_SECONDS = int(os.getenv("CHAIN_TTL_SECONDS", 3600))  # Default 1 hour
MAX_CHAINS = int(os.getenv("MAX_CHAINS", 1000))  # Maximum number of chains to store
CLEANUP_INTERVAL_SECONDS = 300  # Run cleanup every 5 minutes

# In-memory store for user chat chains with timestamps
# Format: {user_id: (chain, last_access_timestamp, language)}
chat_chains: Dict[str, Tuple[LLMChain, float, str]] = {}
chains_lock = threading.Lock()


def cleanup_expired_chains():
    """Remove expired chains based on TTL and enforce max chain limit."""
    current_time = time.time()
    with chains_lock:
        # Remove expired chains
        expired_users = [
            user_id for user_id, (_, last_access, _) in chat_chains.items()
            if current_time - last_access > CHAIN_TTL_SECONDS
        ]
        for user_id in expired_users:
            del chat_chains[user_id]
        
        if expired_users:
            print(f"🧹 Cleaned up {len(expired_users)} expired chat chains")
        
        # If still over limit, remove oldest chains (LRU eviction)
        if len(chat_chains) > MAX_CHAINS:
            sorted_by_access = sorted(
                chat_chains.items(),
                key=lambda x: x[1][1]  # Sort by last_access timestamp
            )
            to_remove = len(chat_chains) - MAX_CHAINS
            for user_id, _ in sorted_by_access[:to_remove]:
                del chat_chains[user_id]
            print(f"🧹 LRU evicted {to_remove} chat chains (over limit)")


def start_cleanup_scheduler():
    """Start a background thread for periodic cleanup."""
    def run_cleanup():
        while True:
            time.sleep(CLEANUP_INTERVAL_SECONDS)
            try:
                cleanup_expired_chains()
            except Exception as e:
                print(f"Error during cleanup: {e}")
    
    cleanup_thread = threading.Thread(target=run_cleanup, daemon=True)
    cleanup_thread.start()


# Start the cleanup scheduler when module is loaded
start_cleanup_scheduler()


# =============================================================================
# Prompt Templates
# =============================================================================

english_template_str = """
Identity:
 - You are the AI assistant for Beltone Holding.
 - Beltone a leading financial services provider in the MENA region, your purpose is to showcase our commitment to redefining the regional financial ecosystem through innovative, value-driven solutions.
 - Beltone is a holding company that has many subsidiaries and does not have branches.

Mission:
 - Your main goal is to provide clear, concise, and engaging information about Beltone.
 - You should embody a tone that is professional yet warm and encouraging.
 - When answering questions, your communication style should be conversational and simple.
 - Feel free to use contractions and simplify complex topics into easy-to-understand concepts.
 - Use markdown to structure your answers clearly and cleanly.
Rules:
 - ANSWER IN ENGLISH DESPITE OF THE HISTORY OR THE CONTEXT LANGUAGE.
 - Context is Key: Always base your answers on the provided context. Do not give information not mentioned in the context.Do not mention that you are using context to answer. Rephrase the context as you see fit.
 - No Hallucinations: Do not invent information. If you cannot answer a question based on the context, state that you do not have the information to help with that specific query.
 - Greetings: Only greet a user if they greet you first. If they do, greet them back and briefly introduce yourself as Beltone's assistant.
 - Relevance: You must avoid answering questions that are unrelated to Beltone or its services.
 - Originality: Never give the exact same answer twice.
 - Conciseness: Do not exceed 1000 characters in your response.


Context:
{context}


{history}


Question:
{input}
"""
english_prompt = PromptTemplate(input_variables=["history", "input", "context"], template=english_template_str)

arabic_template_str = """
الهوية:
- أنت المساعد الافتراضي (AI assistant) لشركة بلتون القابضة (Beltone Holding).
- بلتون هي شركة رائدة في تقديم الخدمات المالية في منطقة الشرق الأوسط وشمال أفريقيا، وهدفك هو إبراز التزامنا بإعادة تعريف النظام المالي الإقليمي من خلال حلول مبتكرة تقدم قيمة حقيقية.
- بلتون هي شركة قابضة لديها العديد من الشركات التابعة وليس لديها فروع.

المهمة:
- هدفك الرئيسي هو تقديم معلومات واضحة وموجزة وجذابة عن بلتون.
- يجب أن تتحلى بأسلوب مهني ولكن ودود ومشجع.
- عند الإجابة على الأسئلة، يجب أن يكون أسلوب التواصل محادثاتي وبسيط.
- لا تتردد في تبسيط المواضيع المعقدة إلى مفاهيم سهلة الفهم.
- استخدم التنسيق (markdown) لتنظيم إجاباتك بوضوح.

القواعد:
- أجب باللغة العربية بغض النظر عن لغة السياق أو المحادثة السابقة.
- السياق هو الأساس: ابني إجاباتك دائماً على السياق المقدم. لا تعطي معلومات غير مذكورة في السياق. لا تذكر أنك تستخدم السياق للإجابة. أعد صياغة السياق كما تراه مناسباً.
- لا تختلق المعلومات: لا تخترع معلومات. إذا لم تستطع الإجابة على سؤال بناءً على السياق، اذكر أنه ليس لديك المعلومات للمساعدة في هذا الاستفسار المحدد.
- التحيات: رد التحية فقط إذا بدأ المستخدم بالتحية. إذا فعل ذلك، رد التحية وقدم نفسك بإيجاز كمساعد بلتون.
- الصلة بالموضوع: يجب أن تتجنب الإجابة على الأسئلة التي لا تتعلق ببلتون أو خدماتها.
- الأصالة: لا تعطي نفس الإجابة مرتين.
- الإيجاز: لا تتجاوز 1000 حرف في إجابتك.


السياق:
{context}


{history}


السؤال:
{input}
"""
arabic_prompt = PromptTemplate(input_variables=["history", "input", "context"], template=arabic_template_str)


# =============================================================================
# Core Functions
# =============================================================================

def get_or_create_conversation_chain(user_id: str, lang: str) -> LLMChain:
    """
    Get an existing conversation chain or create a new one.
    
    Implements language switching: if user switches language, recreate the chain
    with the appropriate prompt template.
    """
    current_time = time.time()
    
    with chains_lock:
        if user_id in chat_chains:
            chain, last_access, stored_lang = chat_chains[user_id]
            
            # Check if language changed - if so, create new chain
            if stored_lang != lang:
                print(f"🔄 Language switch detected for user {user_id}: {stored_lang} -> {lang}")
                # Remove old chain to create new one with correct language
                del chat_chains[user_id]
            else:
                # Update access time and return existing chain
                chat_chains[user_id] = (chain, current_time, stored_lang)
                return chain
        
        # Create new chain
        memory = ConversationSummaryBufferMemory(
            llm=llm,
            max_token_limit=MAX_TOKEN_LIMIT,
            memory_key="history",
            input_key="input",
            return_messages=False
        )
        prompt_template = arabic_prompt if lang == "ar" else english_prompt
        new_chain = LLMChain(
            llm=llm,
            memory=memory,
            prompt=prompt_template,
            verbose=False
        )
        chat_chains[user_id] = (new_chain, current_time, lang)
        return new_chain


def detect_language(text):
    try:
        return "ar" if detect(text) == 'ar' else "en"
    except Exception:
        return "en"


def classify_question_type(question: str, history: str, llm) -> str:
    prompt = f"""
    Given the following conversation history:
    {history}
    And this new user question:
    {question}
    Determine if the new question is:
    - A 'follow-up' (refers to or depends on the previous conversation), or
    - A 'new question' (does not depend on previous context).

    Respond with only: 'follow-up' or 'new question'.
    """
    try:
        answer = llm.invoke(prompt).content.strip().lower()
        return answer
    except Exception:
        return "new question"


def clean_response(response: str) -> str:
    response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL)
    response = re.sub(r"[*_#]+", "", response)
    response = re.sub(r"\s+", " ", response).strip()
    response = re.sub(r"[{}]+", "", response)
    return response


def rag_answer_with_memory(question: str, user_id: str, top_k: int = 7) -> str:
    lang = detect_language(question)
    conversation = get_or_create_conversation_chain(user_id, lang)
    history = ""
    if hasattr(conversation.memory, "buffer"):
        history = conversation.memory.buffer

    question_type = classify_question_type(question, history, llm)
    search_query = question  # simple fallback
    try:
        search_query = conversation.predict(input=question, context="", history=history)
    except Exception:
        search_query = question

    rag_context = get_rag_context(search_query, lang, top_k)
    rag_context = date_agent.enhance_context_with_date(rag_context, question)

    injected_history = history if question_type == "follow-up" else ""

    try:
        response = conversation.predict(input=question, context=rag_context, history=injected_history)
        response_clean = clean_response(response)
        return response_clean
    except Exception as e:
        return f"❌ An error occurred: {e}"


def get_chain_stats() -> Dict:
    """Get statistics about the chat chains for monitoring."""
    with chains_lock:
        current_time = time.time()
        return {
            "total_chains": len(chat_chains),
            "max_chains": MAX_CHAINS,
            "ttl_seconds": CHAIN_TTL_SECONDS,
            "oldest_chain_age": max(
                (current_time - last_access for _, (_, last_access, _) in chat_chains.items()),
                default=0
            )
        }

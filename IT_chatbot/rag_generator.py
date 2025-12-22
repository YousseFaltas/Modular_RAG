from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationSummaryBufferMemory
import os
from dotenv import load_dotenv
import re
from typing import Dict
from langdetect import detect

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

# In-memory store for user chat chains
chat_chains: Dict[str, LLMChain] = {}
MAX_TOKEN_LIMIT = 500

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
أنت المساعد الافتراضي (AI assistant) لشركة بلتون القابضة (Beltone Holding).
...
السؤال:
{input}
"""
arabic_prompt = PromptTemplate(input_variables=["history", "input", "context"], template=arabic_template_str)


def get_or_create_conversation_chain(user_id: str, lang: str) -> LLMChain:
    if user_id not in chat_chains:
        memory = ConversationSummaryBufferMemory(
            llm=llm,
            max_token_limit=MAX_TOKEN_LIMIT,
            memory_key="history",
            input_key="input",
            return_messages=False
        )
        prompt_template = arabic_prompt if lang == "ar" else english_prompt
        chat_chains[user_id] = LLMChain(
            llm=llm,
            memory=memory,
            prompt=prompt_template,
            verbose=False
        )
    return chat_chains[user_id]


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

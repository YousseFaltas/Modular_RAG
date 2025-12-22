from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationSummaryBufferMemory
import os
from dotenv import load_dotenv
import re
from typing import Dict
from langdetect import detect

# ==================================================================================
# comment this use it without docker
from helpers.date_agent import DateAgent
from helpers.langsmith_config import setup_langsmith
from helpers.retrieval import get_rag_context

# uncomment this use it without docker
# from helpers.date_agent import DateAgent
# from helpers.final_retreival import  get_rag_context
# from helpers.langsmith_config import setup_langsmith
# ==================================================================================

# Load environment variables from .env file
load_dotenv()

# -- date agent --
date_agent = DateAgent(timezone="Africa/Cairo")

# -- LangSmith setup --
setup_langsmith()

# -- LLM and prompt setup --
openai_api_key = os.getenv("OPENAI_API_KEY")
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.5,
    openai_api_key=openai_api_key
)

# In-memory store for user chat chains
chat_chains: Dict[str, LLMChain] = {}
MAX_TOKEN_LIMIT = 500

# -- English Prompt template --
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

# -- Arabic Prompt template --
arabic_template_str = """
الهوية:
أنت المساعد الافتراضي (AI assistant) لشركة بلتون القابضة (Beltone Holding).
بلتون هي شركة رائدة في تقديم الخدمات المالية في منطقة الشرق الأوسط وشمال أفريقيا، وهدفك هو تسليط الضوء على التزامنا بإعادة صياغة النظام المالي في المنطقة من خلال حلول مبتكرة وذات قيمة مضافة.
بلتون هي شركة قابضة لديها العديد من الشركات التابعة وليس لديها فروع.
المهمة:
هدفك الأساسي هو تقديم معلومات واضحة، موجزة، و ذكية حول بلتون.
يجب أن يكون أسلوبك احترافيًا و ودودًا ومشجعًا في نفس الوقت.
عند الإجابة على الأسئلة، يجب أن يكون أسلوب التواصل حواريًاو ممتع و بسيطًا.
يمكنك استخدام الاختصارات وتبسيط المواضيع المعقدة إلى مواضيع سهلة الفهم.
استخدم لغة ترميز (Markdown) لتنظيم إجاباتك بوضوح ونظافة.
القواعد:
أجب باللغة العرابية بغض النظر عن لغة السجل أو السياق.
السياق هو الأساس: يجب أن تعتمد إجاباتك دائمًا على السياق المتاح. لا تقدم معلومات لم يتم ذكرها في السياق. لا تذكر أنك تستخدم السياق للإجابة. أعد صياغة السياق كما تراه مناسبًا.
لا للهلوسة: لا تختلق معلومات. إذا لم تتمكن من الإجابة على سؤال بناءً على السياق، اذكر أنك لا تملك المعلومات اللازمة للمساعدة في هذا الاستفسار المحدد.
التحية: لا تبادر بالتحية إلا إذا قام المستخدم بتحيتك أولاً. إذا فعلوا ذلك، رحب بهم بإيجاز وقدم نفسك كمساعد بلتون.
الصلة بالموضوع: يجب أن تتجنب الإجابة على الأسئلة غير المتعلقة ببلتون أو خدماتها.
الأصالة: لا تقدم نفس الإجابة مرتين أبدًا.
الإيجاز: لا تتجاوز 1000 حرف في إجابتك.
السياق:
{context}


الحوار السابق:
{history}


السؤال:
{input}
"""

arabic_prompt = PromptTemplate(input_variables=["history", "input", "context"], template=arabic_template_str)

def get_or_create_conversation_chain(user_id: str, lang: str) -> LLMChain:
    """Retrieves or creates a conversation chain for a specific user and language.

    Args:
        user_id (str): The unique identifier for the user.
        lang (str): The language code ('ar' for Arabic, 'en' for English).

    Returns:
        LLMChain: The conversation chain associated with the user and language.
    """
    if user_id not in chat_chains:
        print(f"🧠 Creating new LLM chain for user '{user_id}' in '{lang}'.")
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
            verbose=True
        )
    return chat_chains[user_id]


def detect_language(text):
    if detect(text) == 'ar':
        return "ar"
    else:
        return "en"


def get_search_query(question: str, lang: str) -> str:
    """Generates an optimized search query based on the input question and language.
    
    Args:
        question (str): The user's question.
        lang (str): The language code ('ar' for Arabic, 'en' for English).

    Returns:
        str: The optimized search query.
    """
    search_query = question
    if lang == "ar":
        arabic_search_prompt = f"""
        صِغ الاستعلام العربي التالي ليكون استعلامًا واضحًا ومختصرًا ومناسبًا لاسترجاع المعلومات.
        - لا تضف كلمات إضافية غير ضرورية.
        - إذا كان يحتوي على اختصار (مثل CEO, CFO, CTO ...) قم بتوسيعه بالاسم الكامل باللغة الإنجليزية.
        
        الاستعلام: {question}
        """
        search_query = llm.invoke(arabic_search_prompt).content.strip()
        print(f"🌍 الاستعلام العربي → المحسن: '{question}' → '{search_query}'")
    else:
        english_search_prompt = f"""
        Rewrite the following English user query into a clear, concise query suitable for information retrieval.

        If the query contains acronyms like CEO, CTO, COO, expand them to their full forms and keep both (e.g., CEO → CEO (Chief Executive Officer)).
        Do not expand CFO — keep it exactly as written.
        When resolving positions disregard lines coantaing the words has media_room and awards.
        If the query explicitly refers to a role/title (e.g., chairman, CEO, CFO, president, manager, director) and is clearly tied to a person, company, or organization, add "position" at the end.
        If the query only mentions a role/title without context (no company, no person, no reference), do not add "position".
        Ensure the final query is short, direct, and information-retrieval friendly.

        Query: {question}
        """
        search_query = llm.invoke(english_search_prompt).content.strip()
        print(f"✍ Optimized English Query: '{question}' → '{search_query}'")
    return search_query


def classify_question_type(question: str, history: str, llm) -> str:
    """Classifies the question as either a 'follow-up' or a 'new question' based on the conversation history.
    
    Args:
        question (str): The user's question.
        history (str): The conversation history.
        llm: The language model to use for classification.
        
    Returns:
        str: 'follow-up' or 'new question'.
    
    """
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
    answer = llm.invoke(prompt).content.strip().lower()
    return answer

def clean_response(response: str) -> str:
    # 1. Remove <think>...</think> blocks
    response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL)

    # 2. Remove markdown-like bold/italic and hashtags
    response = re.sub(r"[*_#]+", "", response)

    # 3. Normalize whitespace
    response = re.sub(r"\s+", " ", response).strip()

    # 4. Optional: fix stray brackets or repeated symbols
    response = re.sub(r"[{}]+", "", response)

    return response

def rag_answer_with_memory(question: str, user_id: str, top_k: int = 7) -> str:
    """Generates an answer to the user's question using RAG with memory.

    Args:
        question (str): The user's question.
        user_id (str): The unique identifier for the user.
        top_k (int, optional): Number of top search results in qdrant. Defaults to 7.

    Returns:
        str: The generated answer.
    """
    lang = detect_language(question)
    print(f"lang detected : {lang}")
    conversation = get_or_create_conversation_chain(user_id, lang)
    history = ""
    if hasattr(conversation.memory, "buffer"):
        history = conversation.memory.buffer

    question_type = classify_question_type(question, history, llm)
    print(f"🧐 Question classified as: {question_type}")

    search_query = get_search_query(question, lang)
    rag_context = get_rag_context(search_query, lang, top_k)

    rag_context = date_agent.enhance_context_with_date(rag_context, question)
    print(f"📄 RAG Context: {rag_context[:200]}...")

    # Conditionally set history for prompt rendering
    injected_history = history if question_type == "follow-up" else ""

    try:
        response = conversation.predict(input=question, context=rag_context, history=injected_history)
        response_clean = clean_response(response)

        return response_clean
    except Exception as e:
        print(f"❌ Error during generation: {e}")
        return "❌ An error occurred. Please try again."
    


def main():
    print(f"{'='*10}This is kai's cli let's begin testing{'='*10}\n\n")
    print("type (exit) or (quit) to terminate the session\n\n")
    status = True
    while status:
        prompt = input ("user : ")
        if "quit" in prompt or "exit" in prompt:
            status = False
        else:
            answer = rag_answer_with_memory(question= prompt , user_id= '1')
            print(f"kai's answer : {answer}")
    print(f"{'='*10}Thank you fo testing Kai, Goodbye!{'='*10}")


# uncomment this for testing in the cli
if __name__ == "__main__" :
    main()
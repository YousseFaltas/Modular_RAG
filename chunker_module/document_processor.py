# DOCUMENT EXTRACTION
from docling.document_converter import DocumentConverter
# CHUNKING
from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from dotenv import load_dotenv
from openai import OpenAI
from utils.tokenizer import TikTokenWrapper
import os

load_dotenv()
converter = DocumentConverter()

# --------------------------------------------------------------
# Basic PDF extraction
# --------------------------------------------------------------

result = converter.convert("/home/youssef/github/Modular_RAG/PDFs/1H2025_Earnings_Release.pdf")
document = result.document

# Initialize OpenAI client (make sure you have OPENAI_API_KEY in your environment variables)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

tokenizer = TikTokenWrapper()  # Load our custom tokenizer for OpenAI
MAX_TOKENS = 8191  # text-embedding-3-large's maximum context length

# --------------------------------------------------------------
# Apply hybrid chunking
# --------------------------------------------------------------

chunker = HybridChunker(
    tokenizer=tokenizer,
    max_tokens=MAX_TOKENS,
    merge_peers=True,
)

chunk_iter = chunker.chunk(dl_doc=result.document)
chunks = list(chunk_iter)


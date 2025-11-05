import tiktoken
import logging
from tiktoken import Encoding
from transformers.tokenization_utils_base import PreTrainedTokenizerBase
from typing import Dict, List, Tuple, Optional

# Set up a logger for this module
logger = logging.getLogger(__name__)

class TikTokenWrapper(PreTrainedTokenizerBase):
    """
    A robust adapter class to make OpenAI's `tiktoken` library compatible
    with the Hugging Face `PreTrainedTokenizerBase` interface.

    This class is a **special-purpose wrapper** primarily designed for
    fast token counting and chunking operations.

    ---
    **⚠️ IMPORTANT LIMITATIONS (By Design):**
    ---
    1.  **"Tokens" are Stringified IDs:** The `tokenize()` method does NOT
        return human-readable tokens (e.g., "Hello"). It returns the
        stringified *integer token IDs* (e.g., "9906").
    2.  **Purpose:** This is a deliberate performance optimization for chunkers
        and counters that only need a list of "things" and their `len()`.
    3.  **Not a Full Tokenizer:** Do NOT use this for tasks that need
        to inspect the actual token string content (e.g., finding "##"
        subwords, aligning tokens to text).
    4.  **Vocab is a Stub:** `get_vocab()` returns a simple integer map,
        not the true BPE vocabulary.
    ---

    Args:
        model_name (str):
            The name of the OpenAI model to load the tokenizer for
            (e.g., "gpt-4o", "text-embedding-3-large") OR a direct
            encoding name (e.g., "cl100k_base").
        max_length (int, optional):
            The maximum sequence length for this model.
            Defaults to 8191 (a common `cl100k_base` limit).
    """

    def __init__(
        self,
        model_name: str = "gpt-4",  # A safer, modern default
        max_length: int = 8191,
        **kwargs,
    ):
        try:
            self.tokenizer: Encoding = tiktoken.encoding_for_model(model_name)
            self.encoding_name = self.tokenizer.name
        except KeyError:
            try:
                self.tokenizer: Encoding = tiktoken.get_encoding(model_name)
                self.encoding_name = self.tokenizer.name
                logger.warning(
                    f"Could not find model name '{model_name}'. "
                    f"Treating as direct encoding name '{self.encoding_name}'."
                )
            except KeyError:
                logger.error(
                    f"Invalid model or encoding name: '{model_name}'. "
                    f"Defaulting to 'cl100k_base'."
                )
                self.tokenizer: Encoding = tiktoken.get_encoding("cl100k_base")
                self.encoding_name = "cl100k_base"

        # Correctly calculate vocab size (it's max_token_value + 1)
        self._vocab_size = self.tokenizer.max_token_value + 1

        super().__init__(
            model_max_length=max_length,
            **kwargs,
        )

    def tokenize(self, text: str, **kwargs) -> List[str]:
        if not isinstance(text, str):
            logger.warning(f"Input to tokenize was not a string, received {type(text)}.")
            return []
            
        return [str(t) for t in self.tokenizer.encode(text)]

    def _tokenize(self, text: str) -> List[str]:
        return self.tokenize(text)

    def _convert_token_to_id(self, token: str) -> int:
        try:
            return int(token)
        except ValueError:
            logger.warning(f"Invalid token '{token}' passed to _convert_token_to_id.")
            return 0

    def _convert_id_to_token(self, index: int) -> str:
        return str(index)

    def get_vocab(self) -> Dict[str, int]:
        return {str(i): i for i in range(self.vocab_size)}

    @property
    def vocab_size(self) -> int:
        """Returns the true size of the vocabulary."""
        return self._vocab_size

    # --- THIS IS THE NEWLY ADDED METHOD ---
    def __len__(self) -> int:
        """
        Returns the size of the vocabulary.
        This is required by libraries (like docling) that call `len(tokenizer)`.
        """
        return self.vocab_size
    # -------------------------------------

    def save_vocabulary(self, save_directory: str) -> Tuple[str]:
        return ()

    @classmethod
    def from_pretrained(
        cls,
        pretrained_model_name_or_path: str,
        max_length: Optional[int] = None,
        **kwargs,
    ):
        init_kwargs = kwargs.copy()
        if max_length is not None:
            init_kwargs["max_length"] = max_length

        return cls(
            model_name=pretrained_model_name_or_path,
            **init_kwargs
        )
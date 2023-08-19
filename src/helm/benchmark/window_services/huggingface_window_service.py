from typing import Optional
from helm.proxy.clients.huggingface_tokenizer import HuggingFaceTokenizers
from .local_window_service import LocalWindowService
from .tokenizer_service import TokenizerService
from helm.proxy.clients.huggingface_client import HuggingFaceModelConfig


class HuggingFaceWindowService(LocalWindowService):
    def __init__(
        self, service: TokenizerService, model_config: HuggingFaceModelConfig, max_sequence_length: Optional[int] = None
    ):
        super().__init__(service)
        self._tokenizer_name = model_config.model_id
        tokenizer = HuggingFaceTokenizers.get_tokenizer(self._tokenizer_name)
        self._prefix_token = tokenizer.bos_token
        self._end_of_text_token = tokenizer.eos_token
        # Override max_sequence_length if provided as an argument.
        # Otherwise, auto-infer max_sequence_length from the Hugging Face tokenizer.
        # Note that many Hugging Face tokenizers have incorrect sequence lengths,
        # so it is recommended to set this manually.
        if max_sequence_length:
            self._max_sequence_length = max_sequence_length
        else:
            self._max_sequence_length = tokenizer.model_max_length
        if self._max_sequence_length > 2048:
            self._max_sequence_length = 2048

    @property
    def max_sequence_length(self) -> int:
        """Return the max sequence length of this tokenizer."""
        return self._max_sequence_length

    @property
    def max_request_length(self) -> int:
        """Return the max request length of this tokenizer."""
        return self.max_sequence_length

    @property
    def end_of_text_token(self) -> str:
        """The end of text token."""
        return self._end_of_text_token

    @property
    def tokenizer_name(self) -> str:
        """Name of the tokenizer to use when sending a request."""
        return self._tokenizer_name

    @property
    def prefix_token(self) -> str:
        """The prefix token."""
        return self._prefix_token

from abc import ABC, abstractmethod


class BaseAIProvider(ABC):

    @abstractmethod
    def ask(self, message):
        """
        AI sağlayıcısına mesaj gönderir ve cevap döndürür.
        """
        raise NotImplementedError
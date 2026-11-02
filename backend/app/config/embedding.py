"""Настройки модели эмбеддингов GigaChat.

Векторы считает внешний сервис, поэтому локальных путей и параметров инференса здесь
больше нет: остались имя модели, размерность, размер порции и шаблон поискового запроса.
Ключ авторизации и транспорт приходят из ``GigaChatSettings`` — те же, что у чата.
"""

from pydantic import Field, field_validator

from app.config.gigachat import GigaChatSettings

DEFAULT_MODEL_ID = "EmbeddingsGigaR"
"""Модель эмбеддингов по умолчанию: 2560 измерений, 4096 токенов контекста."""

DEFAULT_DIMENSION = 2560
"""Размерность вектора модели по умолчанию."""

DEFAULT_QUERY_TEMPLATE = (
    "Дан пункт врачебного протокола, необходимо найти абзац клинической рекомендации, "
    "который его покрывает. Пункт: {text}"
)
"""Шаблон поискового запроса: инструкция плюс сам запрос.

Sber рекомендует для retrieval-задач отделять инструкцию переводом строки, но шаблон
задаётся переменной окружения — однострочной, поэтому разделитель здесь текстовый.
Документы кодируются без инструкции.
"""

TEXT_PLACEHOLDER = "{text}"
"""Единственная подстановка, которую обязан содержать шаблон запроса."""


class EmbeddingSettings(GigaChatSettings):
    """Модель эмбеддингов и параметры обращений к сервису.

    Размерность объявлена явно: она сверяется с коллекцией векторного хранилища и с
    длиной пришедшего вектора, и расхождение обязано падать ошибкой, а не подставлять
    чужие векторы.
    """

    model_id: str = Field(
        default=DEFAULT_MODEL_ID,
        validation_alias="EMBEDDING_MODEL",
        description="Имя модели в API: попадает в метаданные клинрека и в запрос",
    )
    dimension: int = Field(
        default=DEFAULT_DIMENSION,
        ge=1,
        validation_alias="EMBEDDING_DIM",
        description="Размерность вектора: сверяется с коллекцией Qdrant и с ответом",
    )
    batch_size: int = Field(
        default=32,
        ge=1,
        validation_alias="EMBEDDING_BATCH_SIZE",
        description="Сколько фрагментов уходит в сервис за один запрос",
    )
    query_template: str = Field(
        default=DEFAULT_QUERY_TEMPLATE,
        validation_alias="EMBEDDING_QUERY_TEMPLATE",
        description="Шаблон запроса с подстановкой {text}: документы кодируются без него",
    )

    @field_validator("query_template")
    @classmethod
    def _require_text_placeholder(cls, value: str) -> str:
        """Шаблон без подстановки отправил бы в поиск одну и ту же инструкцию.

        Ошибка молчаливая: поиск вернул бы фрагменты по тексту инструкции, а не по
        вопросу. Поэтому проверка здесь, а не в момент первого запроса.
        """
        if TEXT_PLACEHOLDER not in value:
            raise ValueError(f"query template must contain {TEXT_PLACEHOLDER}")
        return value

    def build_query(self, text: str) -> str:
        """Подставить запрос в шаблон ровно один раз."""
        return self.query_template.format(text=text)

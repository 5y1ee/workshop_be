from pydantic import BaseModel, Field


class QuizCatalogQuestion(BaseModel):
    category: str
    prompt: str
    options: list[str]
    answer: str


class QuizCategoryCount(BaseModel):
    name: str
    count: int


class QuizCatalog(BaseModel):
    total: int
    categories: list[QuizCategoryCount]
    questions: list[QuizCatalogQuestion]


class QuizSeedRequest(BaseModel):
    season_id: int
    categories: list[str] | None = None
    limit: int | None = Field(default=None, ge=1)
    shuffle: bool = False
    create_session: bool = False
    replace: bool = False
    session_id: int | None = None
    game_title: str = "퀴즈 대결"


class QuizSeedResult(BaseModel):
    seeded: int
    session_id: int
    start_order: int
    removed: int

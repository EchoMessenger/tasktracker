from pydantic import BaseModel, Field
from typing import Any, Optional, List, Generic, TypeVar
from datetime import datetime

T = TypeVar('T')

class StandardResponse(BaseModel):
    """Стандартный ответ для успешных операций"""
    success: bool = True
    message: str
    data: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    """Стандартный ответ для ошибок"""
    success: bool = False
    error: str
    details: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel, Generic[T]):
    """Стандартный ответ для пагинированных списков"""
    success: bool = True
    message: str
    data: List[T]
    pagination: dict = Field(
        default_factory=lambda: {
            "total": 0,
            "page": 1,
            "size": 100,
            "pages": 1,
            "has_next": False,
            "has_prev": False
        }
    )
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True


class PaginationParams(BaseModel):
    """Параметры пагинации для запросов"""
    page: int = Field(1, ge=1, description="Номер страницы")
    size: int = Field(100, ge=1, le=1000, description="Размер страницы")

    def get_offset(self) -> int:
        """Вычисляет offset для SQL запроса"""
        return (self.page - 1) * self.size


class TaskStats(BaseModel):
    """Статистика по задачам"""
    total: int = 0
    open: int = 0
    in_progress: int = 0
    review: int = 0
    completed: int = 0
    overdue: int = 0


class UserStats(BaseModel):
    """Статистика пользователя"""
    user_id: int
    username: str
    total_created: int = 0
    total_assigned: int = 0
    task_stats: TaskStats = Field(default_factory=TaskStats)


class HealthCheckResponse(BaseModel):
    """Ответ для health check эндпоинта"""
    success: bool = True
    message: str
    service: str
    database: str
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True


# Дополнительные утилиты для удобства
class SuccessResponse(StandardResponse):
    """Упрощенный ответ для успешных операций без данных"""
    def __init__(self, message: str = "Operation completed successfully"):
        super().__init__(message=message, data=None)


class CreatedResponse(StandardResponse):
    """Ответ для успешного создания ресурса"""
    def __init__(self, message: str = "Resource created successfully", data: Any = None):
        super().__init__(message=message, data=data)


class DeletedResponse(StandardResponse):
    """Ответ для успешного удаления ресурса"""
    def __init__(self, message: str = "Resource deleted successfully"):
        super().__init__(message=message, data=None)
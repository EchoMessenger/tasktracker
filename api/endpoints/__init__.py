from .v1 import users_router as v1_users_router, tasks_router as v1_tasks_router
from .v2 import users_router as v2_users_router

__all__ = [
    "v1_users_router",
    "v1_tasks_router",
    "v2_users_router"
]
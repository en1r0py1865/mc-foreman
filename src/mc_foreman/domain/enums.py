from enum import Enum


class StrEnum(str, Enum):
    pass


class TaskState(StrEnum):
    PENDING_REVIEW = "pending_review"
    QUEUED = "queued"
    BUILDING = "building"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    FAILED = "failed"


class QueueTier(StrEnum):
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"


class SubmitterType(StrEnum):
    USER = "user"
    AGENT = "agent"
    ADMIN = "admin"

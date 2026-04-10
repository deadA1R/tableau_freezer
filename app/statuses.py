from enum import Enum


class WorkflowStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    VOIDED = "VOIDED"


class RequestResultStatus(str, Enum):
    CREATED = "created"
    EXISTS = "exists"

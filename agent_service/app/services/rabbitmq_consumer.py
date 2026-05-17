"""RabbitMQ contracts for future Agent Service RAG flows.

Task.Created and Schedule.Created will be consumed here once the agent logic is implemented.
"""

from app.schemas import ScheduleCreatedEvent
from app.schemas import TaskCreatedEvent


CONSUMED_EVENTS = ["Task.Created", "Schedule.Created"]


def handle_task_created(event: TaskCreatedEvent) -> None:
    raise NotImplementedError("Lógica RAG pendiente para Task.Created")


def handle_schedule_created(event: ScheduleCreatedEvent) -> None:
    raise NotImplementedError("Lógica RAG pendiente para Schedule.Created")

from __future__ import annotations
from pydantic import BaseModel


class FloorPlanTable(BaseModel):
    id: str
    label: str
    shape: str  # "rect" | "round"
    seats: int
    x: float
    y: float


class FloorPlanLayout(BaseModel):
    tables: list[FloorPlanTable]


class TableAssignment(BaseModel):
    table_id: str
    reservation_id: str
    date: str  # YYYY-MM-DD
    hour: str  # HH:MM


class TableAssignmentResponse(BaseModel):
    table_id: str
    reservation_id: str
    date: str
    hour: str


class AssignmentsForHour(BaseModel):
    date: str
    hour: str
    assignments: list[TableAssignmentResponse]

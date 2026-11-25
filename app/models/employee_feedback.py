from datetime import date, datetime
from typing import Annotated, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Text255 = Annotated[str, Field(min_length=1, max_length=255)]
Text100 = Annotated[str, Field(min_length=1, max_length=100)]
Text50 = Annotated[str, Field(min_length=1, max_length=50)]
Email = Annotated[EmailStr, Field(max_length=255)]
Score = Annotated[int, Field(strict=True, ge=-2147483648, le=2147483647)]


class FeedbackOptionalFields(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    phone_number: Annotated[str, Field(max_length=50)] | None = None
    l0_company: Annotated[str, Field(max_length=255)] | None = None
    l1_directorate: Annotated[str, Field(max_length=255)] | None = None
    l2_management: Annotated[str, Field(max_length=255)] | None = None
    l3_coordination: Annotated[str, Field(max_length=255)] | None = None
    l4_area: Annotated[str, Field(max_length=255)] | None = None
    response_date: date | None = None
    interest_in_position_comments: str | None = None
    contribution_comments: str | None = None
    learning_and_development_comments: str | None = None
    feedback_comments: str | None = None
    manager_interaction_comments: str | None = None
    opportunity_clarity_comments: str | None = None
    permanence_expectation_comments: str | None = None
    enps_comments: str | None = None

    @field_validator('response_date', mode='before')
    @classmethod
    def validate_date(cls, value):
        if value is None or type(value) is date:
            return value
        if isinstance(value, str):
            try:
                parsed = date.fromisoformat(value)
                if parsed.isoformat() == value:
                    return parsed
            except ValueError:
                pass
        raise ValueError('Use a date in YYYY-MM-DD format')


class FeedbackCreate(FeedbackOptionalFields):
    name: Text255
    email: Email
    corporate_email: Email
    department: Text255
    location: Text255
    company_tenure: Text100
    gender: Text50
    generation: Text50
    interest_in_position: Score
    contribution: Score
    learning_and_development: Score
    feedback: Score
    manager_interaction: Score
    opportunity_clarity: Score
    permanence_expectation: Score
    enps: Score


class FeedbackReplace(FeedbackCreate):
    """PUT requires all mandatory fields; omitted nullable fields are cleared."""


class FeedbackUpdate(FeedbackOptionalFields):
    name: Text255 | None = None
    email: Email | None = None
    corporate_email: Email | None = None
    department: Text255 | None = None
    location: Text255 | None = None
    company_tenure: Text100 | None = None
    gender: Text50 | None = None
    generation: Text50 | None = None
    interest_in_position: Score | None = None
    contribution: Score | None = None
    learning_and_development: Score | None = None
    feedback: Score | None = None
    manager_interaction: Score | None = None
    opportunity_clarity: Score | None = None
    permanence_expectation: Score | None = None
    enps: Score | None = None

    @model_validator(mode='after')
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError('Provide at least one field to update')
        for name in self.model_fields_set:
            if FeedbackCreate.model_fields[name].is_required() and getattr(self, name) is None:
                raise ValueError(f'{name} cannot be null')
        return self


class FeedbackResponse(FeedbackCreate):
    id: UUID

    @field_validator('response_date', mode='before')
    @classmethod
    def read_database_date(cls, value):
        return value.date() if isinstance(value, datetime) else value


class FeedbackDeleted(BaseModel):
    id: UUID


DataT = TypeVar('DataT')


class FeedbackEnvelope(BaseModel, Generic[DataT]):
    data: DataT
    meta: dict[str, int] = Field(default_factory=dict)

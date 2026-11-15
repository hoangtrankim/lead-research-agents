"""Structured outputs each agent must return. Claude's answers are validated against these."""

from pydantic import BaseModel, Field


class CompanyProfile(BaseModel):
    name: str = Field(description="Company name")
    summary: str = Field(description="What the company does, in 2-3 sentences")
    industry: str
    products: list[str] = Field(description="Main products or services")
    customers: str = Field(description="Who they sell to")
    signals: list[str] = Field(
        description="Specific, verifiable facts from the site worth mentioning in outreach "
        "(launches, hiring, stated goals, numbers). Empty if none found."
    )
    likely_needs: list[str] = Field(
        description="Problems this company plausibly has that relate to the sender's offer"
    )


class EmailDraft(BaseModel):
    subject: str
    body: str = Field(description="Plain-text email body, ready to send")
    personalization: list[str] = Field(
        description="Which facts from the company profile the email relies on"
    )


class Review(BaseModel):
    score: int = Field(description="Overall quality from 1 (poor) to 10 (excellent)")
    strengths: list[str]
    problems: list[str] = Field(description="Concrete problems. Empty if none.")
    unsupported_claims: list[str] = Field(
        description="Statements about the company that the profile does not support"
    )
    feedback: str = Field(description="Specific instructions for the writer's next revision")

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app, get_llm, get_site_reader
from app.models import CompanyProfile, EmailDraft, Review

PAGES = [{"url": "https://acme.test", "title": "Acme", "text": "Acme sells robots to factories."}]


def profile():
    return CompanyProfile(
        name="Acme",
        summary="Acme sells robots.",
        industry="Robotics",
        products=["Robots"],
        customers="Factories",
        signals=["Launched Robot X"],
        likely_needs=["Support automation"],
    )


def draft(n=1):
    return EmailDraft(subject=f"Draft {n}", body=f"Body {n}", personalization=["Launched Robot X"])


def review(score, unsupported=()):
    return Review(
        score=score,
        strengths=["specific"],
        problems=[] if score >= 8 else ["too generic"],
        unsupported_claims=list(unsupported),
        feedback="Tighten the opening.",
    )


class FakeLLM:
    """Returns scripted reviews in order; counts drafts."""

    def __init__(self, reviews):
        self.reviews = list(reviews)
        self.calls: list[tuple[str, str]] = []
        self.drafts = 0

    async def structured(self, system, user, schema):
        self.calls.append((schema.__name__, user))
        usage = {"input_tokens": 1000, "output_tokens": 200}
        if schema is CompanyProfile:
            return profile(), usage
        if schema is EmailDraft:
            self.drafts += 1
            return draft(self.drafts), usage
        return self.reviews.pop(0), usage


async def fake_reader(url):
    return PAGES


@pytest.fixture
def make_client():
    def _make(llm, reader=fake_reader):
        app.dependency_overrides[get_llm] = lambda: llm
        app.dependency_overrides[get_site_reader] = lambda: reader
        app.dependency_overrides[get_settings] = lambda: Settings(max_revisions=2, approve_score=8)
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()

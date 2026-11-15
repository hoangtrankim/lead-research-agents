import asyncio
import json

from app import web
from app.graph import build_graph
from app.llm import estimate_cost
from tests.conftest import FakeLLM, fake_reader, review

INPUT = {"company_url": "acme.test", "offer": "AI support chatbots for manufacturers", "sender_name": "Hoang"}


def run(llm, **kw):
    return asyncio.run(build_graph(llm, fake_reader, **kw).ainvoke(INPUT))


def test_approved_on_first_review():
    llm = FakeLLM([review(9)])
    state = run(llm)
    assert state["approved"] and state["revisions"] == 0
    assert [c[0] for c in llm.calls] == ["CompanyProfile", "EmailDraft", "Review"]
    assert [u["agent"] for u in state["usage"]] == ["researcher", "writer", "reviewer"]


def test_reviewer_sends_draft_back_then_approves():
    llm = FakeLLM([review(5), review(9)])
    state = run(llm)
    assert state["approved"] and state["revisions"] == 1
    assert state["draft"]["subject"] == "Draft 2"
    revision_prompt = llm.calls[3][1]
    assert "Reviewer feedback" in revision_prompt and "Body 1" in revision_prompt


def test_stops_after_max_revisions():
    llm = FakeLLM([review(3), review(4), review(5)])
    state = run(llm, max_revisions=2)
    assert not state["approved"] and state["revisions"] == 2 and llm.drafts == 3


def test_unsupported_claims_block_approval():
    llm = FakeLLM([review(9, unsupported=["They have 500 staff"]), review(9)])
    state = run(llm)
    assert state["revisions"] == 1 and state["approved"]


def test_estimate_cost():
    usage = [{"input_tokens": 1_000_000, "output_tokens": 0}, {"input_tokens": 0, "output_tokens": 500_000}]
    assert estimate_cost(usage, 4.0, 20.0) == {"input_tokens": 1_000_000, "output_tokens": 500_000, "usd": 14.0}


def parse_sse(text):
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_api_streams_steps_then_result(make_client):
    client = make_client(FakeLLM([review(5), review(9)]))
    res = client.post("/runs", json=INPUT)
    assert res.status_code == 200
    events = parse_sse(res.text)
    steps = [(d["agent"], d["status"]) for e, d in events if e == "step"]
    assert steps[0] == ("researcher", "started")
    assert steps.count(("writer", "finished")) == 2
    assert steps.count(("reviewer", "finished")) == 2
    name, result = events[-1]
    assert name == "result"
    assert result["email"]["subject"] == "Draft 2" and result["revisions"] == 1 and result["approved"]
    assert result["cost"]["input_tokens"] == 5000 and result["cost"]["usd"] == 0.04


def test_api_reports_fetch_error(make_client):
    async def broken(url):
        raise web.FetchError("Could not find the website nope.test")

    events = parse_sse(make_client(FakeLLM([]), broken).post("/runs", json=INPUT).text)
    assert events[-1] == ("error", {"message": "Could not find the website nope.test"})


def test_api_validates_input(make_client):
    assert make_client(FakeLLM([])).post("/runs", json={"company_url": "a.com", "offer": "x"}).status_code == 422

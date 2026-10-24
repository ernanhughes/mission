"""Deterministic Work CLI fixture for adapter tests."""

from __future__ import annotations

import json


OPPORTUNITIES = [
    {
        "id": "work-fixture-1",
        "state": "DISCOVERED",
        "observation": {
            "title": "Fixture AI consulting opportunity",
            "summary": "A grounded fixture opportunity.",
            "buyer": "Fixture Buyer",
            "url": "https://example.invalid/opportunity",
            "source": "fixture",
            "track": "DIRECT_CONTRACT",
            "amount": 1000,
            "currency": "EUR",
            "money_type": "STATED",
            "availability": "OPEN",
            "collected_at": "2026-10-24T00:00:00+00:00",
            "published_at": "2026-10-23T00:00:00+00:00",
            "evidence_urls": ["https://example.invalid/opportunity"],
            "raw": {"buyer_name": "Fixture Buyer", "buyer_country": "IRL"},
        },
        "qualification": {
            "qualified": True,
            "score": 72,
            "bucket": "direct_income",
            "next_action": "Review the fixture opportunity.",
            "evidence": ["https://example.invalid/opportunity"],
            "unknowns": ["Eligibility remains unknown."],
        },
    },
    {
        "id": "work-fixture-2",
        "state": "DISCOVERED",
        "observation": {
            "title": "Fixture rejected opportunity",
            "summary": "A grounded fixture opportunity that is not qualified.",
            "buyer": "Fixture Buyer 2",
            "url": "https://example.invalid/opportunity-2",
            "source": "fixture",
            "track": "EMPLOYMENT",
            "amount": None,
            "currency": None,
            "money_type": "NONE",
            "availability": "OPEN",
            "collected_at": "2026-10-22T00:00:00+00:00",
            "published_at": None,
            "evidence_urls": [],
            "raw": {},
        },
        "qualification": {
            "qualified": False,
            "score": 20,
            "bucket": "direct_income",
            "next_action": "Do not pursue.",
            "evidence": [],
            "unknowns": [],
        },
    },
]


if __name__ == "__main__":
    print(json.dumps(OPPORTUNITIES, indent=2))

#!/usr/bin/env python3
"""Concurrency proof (Coordinator-run): N parallel POSTs for ONE
slot must yield exactly one 201; the rest 409/422.

Usage:
  TOKEN=... python3 scripts/concurrency_test.py \
    --base http://localhost:8000 --facility FID \
    --date YYYY-MM-DD --start HH:MM [--n 20]
Requires: httpx (available in backend venv:
  cd backend && uv run python ../scripts/concurrency_test.py ...)
"""

import argparse
import asyncio
import collections
import os
import sys

import httpx


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://localhost:8000")
    p.add_argument("--facility", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--n", type=int, default=20)
    args = p.parse_args()

    token = os.environ.get("TOKEN")
    if not token:
        print("ERROR: TOKEN env var required", file=sys.stderr)
        return 2

    body = {"facility_id": args.facility, "date": args.date,
            "start": args.start}
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(base_url=args.base, timeout=30) as client:
        responses = await asyncio.gather(*[
            client.post("/api/v1/bookings", json=body, headers=headers)
            for _ in range(args.n)
        ])

    counts = collections.Counter(r.status_code for r in responses)
    codes = collections.Counter(
        r.json().get("code", "OK") for r in responses
    )
    print(f"status counts: {dict(counts)}")
    print(f"body codes:    {dict(codes)}")

    created = counts.get(201, 0)
    if created == 1:
        print("PASS: exactly one booking created under contention")
        return 0
    print(f"FAIL: expected exactly one 201, got {created}")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

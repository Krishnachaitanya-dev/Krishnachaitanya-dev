"""Save the last year of my GitHub contribution calendar to data/contributions.json.

Uses the GraphQL API with GITHUB_TOKEN (the Actions token works). Counts from
private repositories are included because the profile shows private contributions.
Standard library only, so the daily Action needs no installs.
"""
import datetime as dt
import json
import os
import pathlib
import urllib.request

LOGIN = os.environ.get("PROFILE_LOGIN", "Krishnachaitanya-dev")
OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "contributions.json"
QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def main() -> None:
    token = os.environ["GITHUB_TOKEN"]
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-readme-cards"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [
        {"date": d["date"], "count": d["contributionCount"]}
        for w in cal["weeks"]
        for d in w["contributionDays"]
    ]
    data = {
        "login": LOGIN,
        "fetched": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
        "total": cal["totalContributions"],
        "days": days,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1) + "\n")
    print(f"{data['total']} contributions over {len(days)} days -> {OUT.name}")


if __name__ == "__main__":
    main()

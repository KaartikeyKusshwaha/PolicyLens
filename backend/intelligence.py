"""Key-free public intelligence. Known official endpoints only; no arbitrary URL fetches."""

import hashlib
import re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

import httpx
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
from starlette.concurrency import run_in_threadpool

from providers import OFAC_URL, Providers, normalize, parse_sanctions, problem
from store import now

SOURCES = {
    "ofac": {
        "name": "OFAC SDN",
        "url": OFAC_URL,
        "docs": "https://ofac.treasury.gov/sanctions-list-service",
    },
    "un": {
        "name": "United Nations consolidated list",
        "url": "https://scsanctions.un.org/resources/xml/en/consolidated.xml",
        "docs": "https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list",
    },
    "uk": {
        "name": "UK Sanctions List",
        "url": "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.xml",
        "docs": "https://www.gov.uk/government/publications/the-uk-sanctions-list",
    },
}


def parse_public_feed(source, content):
    if source == "ofac":
        return parse_sanctions(content)
    root = ET.fromstring(content)
    for element in root.iter():
        element.tag = element.tag.split("}")[-1]
    entries = []
    if source == "un":
        for item in [*root.findall(".//INDIVIDUAL"), *root.findall(".//ENTITY")]:
            name = " ".join(
                filter(
                    None,
                    [
                        item.findtext("FIRST_NAME"),
                        item.findtext("SECOND_NAME"),
                        item.findtext("THIRD_NAME"),
                        item.findtext("FOURTH_NAME"),
                    ],
                )
            )
            aliases = [
                a.findtext("ALIAS_NAME")
                for a in [
                    *item.findall("INDIVIDUAL_ALIAS"),
                    *item.findall("ENTITY_ALIAS"),
                ]
                if a.findtext("ALIAS_NAME")
            ]
            if name and item.findtext("DATAID"):
                entries.append(
                    {
                        "id": item.findtext("DATAID"),
                        "name": name,
                        "aliases": aliases,
                        "programs": [item.findtext("UN_LIST_TYPE") or "UN"],
                        "type": item.tag.lower(),
                    }
                )
        published = root.attrib.get("dateGenerated")
    else:
        for item in root.findall(".//Designation"):
            names = []
            for name in item.findall(".//Names/Name"):
                value = " ".join(
                    filter(None, [name.findtext(f"Name{i}") for i in range(1, 7)])
                )
                if value:
                    names.append(value)
            if names and item.findtext("UniqueID"):
                entries.append(
                    {
                        "id": item.findtext("UniqueID"),
                        "name": names[0],
                        "aliases": names[1:],
                        "programs": [item.findtext("RegimeName") or "UK"],
                        "type": item.findtext("IndividualEntityShip") or "designation",
                    }
                )
        published = root.findtext("DateGenerated") or root.attrib.get("DateGenerated")
    if not entries:
        raise ValueError("Official feed contained no supported entries")
    return {
        "entries": entries,
        "count": len(entries),
        "published_at": published,
        "sha256": hashlib.sha256(content).hexdigest(),
        "fetched_at": now(),
        "url": SOURCES[source]["url"],
    }


def source_freshness(data, max_age_hours, at=None):
    if not data:
        return "not_synced"
    at = at or datetime.now(timezone.utc)
    try:
        stamp = datetime.fromisoformat(data["fetched_at"])
        fresh = at - timedelta(hours=max_age_hours) < stamp <= at
    except (KeyError, TypeError, ValueError, OverflowError):
        fresh = False
    return "ready" if fresh else "stale"


class Intelligence(Providers):
    def __init__(self, settings, store, client):
        super().__init__(settings, store, client)

    def selected_sources(self):
        from operations import Operations

        return Operations(self.store).preferences()["enabled_sources"]

    def status(self, source):
        data = self.store.source_metadata(source)
        if not data:
            return {
                "id": source,
                **SOURCES[source],
                "status": "not_synced",
                "count": 0,
                "fetched_at": None,
            }
        return {
            "id": source,
            **SOURCES[source],
            **{k: v for k, v in data.items() if k != "entries"},
            "status": source_freshness(data, self.settings.sanctions_max_age_hours),
        }

    async def sync(self, source):
        if source not in SOURCES:
            raise problem(404, "source_unknown", "Unknown intelligence source.")
        try:
            response = await self.client.get(SOURCES[source]["url"], timeout=90)
            response.raise_for_status()
            payload = await run_in_threadpool(
                parse_public_feed, source, response.content
            )
        except (httpx.HTTPError, ValueError, ET.ParseError, DefusedXmlException) as exc:
            self.store.event(
                "source_failed", {"source": source, "error": type(exc).__name__}
            )
            raise problem(
                502,
                "source_unavailable",
                f"{SOURCES[source]['name']} could not be downloaded and validated. Its previous snapshot was not replaced.",
            ) from exc
        self.store.save_source(source, payload)
        self.store.event("source_synced", {"source": source, "count": payload["count"]})
        return self.status(source)

    async def sync_sanctions(self):
        return await self.sync("ofac")

    def sanctions_status(self):
        return self.status("ofac")

    def screen_names(self, names):
        hits = []
        statuses = []
        for source in self.selected_sources():
            status = self.status(source)
            statuses.append(status)
            if status["status"] != "ready":
                raise problem(
                    409,
                    "sanctions_not_ready",
                    f"Sync {SOURCES[source]['name']} before screening. Every enabled source must be fresh.",
                )
            snapshot = self.store.source(source)
            for party, name in names.items():
                needle = normalize(name)
                if len(needle) < 3:
                    raise problem(
                        422,
                        "name_unsupported",
                        "Enter full Latin-script names. This matcher does not cover all transliterations.",
                    )
                for entry in snapshot["entries"]:
                    best, matched = 0, None
                    for candidate_name in [entry["name"], *entry["aliases"]]:
                        candidate = normalize(candidate_name)
                        if (
                            not candidate
                            or abs(len(candidate) - len(needle))
                            > max(len(needle), len(candidate)) * 0.3
                        ):
                            continue
                        score = SequenceMatcher(None, needle, candidate).ratio()
                        if score > best:
                            best, matched = score, candidate_name
                    if best >= 0.88:
                        hits.append(
                            {
                                "party": party,
                                "input_name": name,
                                "source_id": source,
                                "entity_id": entry["id"],
                                "name": entry["name"],
                                "matched_name": matched,
                                "similarity": round(best, 4),
                                "programs": entry["programs"],
                            }
                        )
        hits.sort(key=lambda m: m["similarity"], reverse=True)
        return {
            "source": statuses[0],
            "sources": statuses,
            "matches": hits,
            "scope": "Enabled official sanctions lists, primary names and aliases; normalized name similarity >= 0.88. Potential matches require identity verification. No match is not clearance. Ownership rules, PEP coverage, and all transliterations are not included.",
        }

    def screen(self, transaction):
        return self.screen_names(
            {"sender": transaction.sender, "receiver": transaction.receiver}
        )

    async def gleif(self, lei):
        if not re.fullmatch(r"[A-Z0-9]{18}[0-9]{2}", lei):
            raise problem(422, "invalid_lei", "Enter a 20-character LEI.")
        url = "https://api.gleif.org/api/v1/lei-records/" + lei
        try:
            response = await self.client.get(url, timeout=25)
            if response.status_code == 404:
                raise problem(404, "lei_not_found", "GLEIF has no record for this LEI.")
            response.raise_for_status()
            attributes = response.json()["data"]["attributes"]
            entity = attributes["entity"]
            return {
                "lei": attributes["lei"],
                "legal_name": entity["legalName"]["name"],
                "status": entity["status"],
                "jurisdiction": entity.get("jurisdiction"),
                "legal_address": entity.get("legalAddress"),
                "registration": attributes.get("registration"),
                "source_url": url,
                "fetched_at": now(),
                "scope": "GLEIF legal-entity reference data. This is not identity verification or complete beneficial-ownership coverage.",
            }
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise problem(
                502,
                "gleif_unavailable",
                "GLEIF reference data is unavailable. No replacement data was generated.",
            ) from exc

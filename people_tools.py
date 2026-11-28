"""Brain tools over the People store: ``lookup_person`` and ``list_people``.

Plus ``people_index()``: a short "people you know" list for the system prompt,
so "who is Mike?" works even before the brain thinks of calling a tool.
"""

from __future__ import annotations

import asyncio
import logging

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

from people.store import PeopleStore, Person

logger = logging.getLogger(__name__)

LOOKUP_PERSON_FUNCTION_NAME = "lookup_person"
LIST_PEOPLE_FUNCTION_NAME = "list_people"
INDEX_LIMIT = 40


def _profile(person: Person) -> dict:
    data = {k: v for k, v in person.as_dict().items() if v and k not in {"id", "photos", "created_at"}}
    data["photos_enrolled"] = len(person.photos)
    return data


def people_index(store: PeopleStore | None) -> str:
    """One line per person for the system prompt ("" when nobody is enrolled)."""
    if store is None:
        return ""
    try:
        people = store.list()
    except Exception as exc:  # a broken store must not break the brain
        logger.warning("people index unavailable: %s", exc)
        return ""
    if not people:
        return ""
    lines = "; ".join(p.one_line() for p in people[:INDEX_LIMIT])
    more = f" (and {len(people) - INDEX_LIMIT} more)" if len(people) > INDEX_LIMIT else ""
    return (
        f"People you know: {lines}{more}. Call lookup_person for anyone's full profile "
        "(phone, email, notes, facts) before answering questions about them."
    )


def register_people_tools(llm, store: PeopleStore | None) -> list[FunctionSchema]:
    if store is None:
        return []

    async def lookup(params: FunctionCallParams) -> None:
        name = str((params.arguments or {}).get("name", "")).strip()
        try:
            matches = await asyncio.to_thread(store.find, name)
        except Exception as exc:
            await params.result_callback({"error": f"Could not read people: {exc}"})
            return
        if not matches:
            await params.result_callback({"found": False, "note": f"Nobody named {name!r} is in the people list."})
            return
        await params.result_callback({"found": True, "people": [_profile(p) for p in matches[:5]]})

    async def list_all(params: FunctionCallParams) -> None:
        try:
            people = await asyncio.to_thread(store.list)
        except Exception as exc:
            await params.result_callback({"error": f"Could not read people: {exc}"})
            return
        await params.result_callback({"count": len(people), "people": [p.one_line() for p in people]})

    llm.register_function(LOOKUP_PERSON_FUNCTION_NAME, lookup)
    llm.register_function(LIST_PEOPLE_FUNCTION_NAME, list_all)
    return [
        FunctionSchema(
            name=LOOKUP_PERSON_FUNCTION_NAME,
            description=(
                "Look up a person the user knows (from the People list): relationship, company, role, "
                "phone, email, notes and facts. Call this for questions like 'who is Mike?', "
                "'what's Sarah's number?' or 'what do I know about Dave?'."
            ),
            properties={"name": {"type": "string", "description": "The person's name or first name."}},
            required=["name"],
        ),
        FunctionSchema(
            name=LIST_PEOPLE_FUNCTION_NAME,
            description="List everyone in the user's People list (name, relationship, role, company).",
            properties={},
            required=[],
        ),
    ]

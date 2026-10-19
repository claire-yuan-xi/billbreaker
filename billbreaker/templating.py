"""Jinja setup: template folder plus the helpers every page can use."""

import json
from pathlib import Path

from fastapi.templating import Jinja2Templates

from .reader_questions import QUESTIONS
from .services.links import host_of, is_safe_external_url
from .states import STATE_NAMES, STATES

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))
env = templates.env
env.globals.update(
    STATES=STATES,
    STATE_NAMES=STATE_NAMES,
    QUESTIONS=QUESTIONS,
    is_safe_external_url=is_safe_external_url,
    host_of=host_of,
)
env.filters["tojson_attr"] = lambda value: json.dumps(value)

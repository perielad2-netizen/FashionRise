"""Magic must keep every painted colour where it was drawn.

Regression: a turquoise dress with a black hat and black shoes came back entirely
black, because the studio only sent the last colour chip the user tapped.
"""

from types import SimpleNamespace
from uuid import uuid4

from app.services import sketch_openai

TURQUOISE = "#19B89C"
BLACK = "#141414"

# What the canvas now measures off the ink layer for that outfit.
DRESS_HAT_SHOES = f"{TURQUOISE},bodice/upper+waist/mid+skirt/lower,74;{BLACK},hat/head+shoes/hem,11"


def _job(input_data: dict) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), job_type="sketch_polish", input_data=input_data)


def test_parses_measured_regions():
    regions = sketch_openai._color_regions(_job({"color_regions": DRESS_HAT_SHOES}))

    assert regions == [
        (TURQUOISE, "bodice/upper+waist/mid+skirt/lower", 74),
        (BLACK, "hat/head+shoes/hem", 11),
    ]


def test_malformed_regions_are_ignored():
    job = _job({"color_regions": "garbage;#ABCDEF,bodice,notanumber;#112233,hat/head,5"})

    assert sketch_openai._color_regions(job) == [("#112233", "hat/head", 5)]


def test_multi_colour_sketch_drops_the_single_colour_direction():
    """The reported bug: 'Color direction: Black' repainted the whole dress."""
    job = _job({"color_regions": DRESS_HAT_SHOES, "color": "Black"})

    text = sketch_openai._user_text(job)

    assert TURQUOISE in text
    assert BLACK in text
    assert "Color direction from the studio palette" not in text


def test_single_colour_sketch_still_uses_the_palette_name():
    job = _job({"color_regions": f"{TURQUOISE},bodice/upper+skirt/lower,88", "color": "Turquoise"})

    text = sketch_openai._user_text(job)

    assert "Color direction from the studio palette: Turquoise." in text


def test_no_regions_falls_back_to_palette_name():
    job = _job({"color": "Rose"})

    text = sketch_openai._user_text(job)

    assert "Color direction from the studio palette: Rose." in text


def test_image_prompt_pins_each_colour_to_its_body_area():
    job = _job({"color_regions": DRESS_HAT_SHOES, "color": "Black"})

    prompt = sketch_openai._build_image_prompt({"image_prompt": "elegant column dress"}, "summary", job)

    assert TURQUOISE in prompt
    assert BLACK in prompt
    assert "hat/head+shoes/hem" in prompt
    assert "Never unify the outfit under one of these colors." in prompt


def test_image_prompt_unchanged_without_regions():
    job = _job({"color": "Rose"})

    prompt = sketch_openai._build_image_prompt({"image_prompt": "elegant column dress"}, "summary", job)

    assert "Never unify the outfit under one of these colors." not in prompt

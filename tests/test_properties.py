import pytest
from hypothesis import given
from hypothesis import strategies as st

from pydantic_parsed_env._api import ParseConfig
from pydantic_parsed_env._parsers import parse_list_or_set_from_env


@given(
    values=st.lists(
        st.integers(min_value=-1_000_000, max_value=1_000_000), max_size=30
    ),
)
def test_property_parse_int_list_round_trip(values: list[int]) -> None:
    raw = ",".join(str(v) for v in values)
    parsed = parse_list_or_set_from_env("values", list, (int,), raw, ParseConfig())
    assert parsed == values


@given(
    values=st.lists(
        st.text(
            alphabet=st.characters(
                min_codepoint=32,
                max_codepoint=126,
                blacklist_characters=[","],
            ),
            max_size=20,
        ),
        max_size=20,
    ),
)
def test_property_parse_str_list_round_trip_with_stripping(values: list[str]) -> None:
    padded = [f"  {v}  " for v in values]
    raw = ",".join(padded)
    parsed = parse_list_or_set_from_env("values", list, (str,), raw, ParseConfig())
    expected = [v.strip() for v in padded]
    if not any(item != "" for item in expected):
        assert parsed == []
        return
    assert parsed == expected


@given(
    raw=st.text(
        alphabet=st.characters(
            min_codepoint=32,
            max_codepoint=126,
            blacklist_characters=[","],
        ),
        min_size=1,
        max_size=16,
    ).filter(lambda s: not s.lstrip("+-").isdigit()),
)
def test_property_parse_int_list_rejects_non_integer_segment(raw: str) -> None:
    with pytest.raises(ValueError, match="Could not parse item"):
        parse_list_or_set_from_env(
            "values",
            list,
            (int,),
            f"1,{raw},2",
            ParseConfig(),
        )

import re

import tclock


def test_version_is_semver_like() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+([a-z]+\d+)?", tclock.__version__)

import pytest
from unpin_python.main import parse_specifier

def test_parse_specifier_with_version():
    """Test parsing a specifier with a version."""
    name, with_spaces, canonical = parse_specifier("hatchling==1.27.0")
    assert name == "hatchling"
    assert with_spaces == "hatchling == 1.27.0"
    assert canonical == "hatchling==1.27.0"

def test_parse_specifier_with_spaces():
    """Test parsing a specifier with spaces around the operator."""
    name, with_spaces, canonical = parse_specifier("hatchling >= 1.27.0")
    assert name == "hatchling"
    assert with_spaces == "hatchling >= 1.27.0"
    assert canonical == "hatchling>=1.27.0"

def test_parse_specifier_no_version():
    """Test parsing a specifier with no version, which implies a search for pinning."""
    name, with_spaces, canonical = parse_specifier("hatchling")
    assert name == "hatchling"
    assert with_spaces == "hatchling == "
    assert canonical == "hatchling=="

def test_parse_specifier_with_extra_spaces():
    """Test parsing with extra whitespace."""
    name, with_spaces, canonical = parse_specifier("  hatchling  !=  1.0  ")
    assert name == "hatchling"
    assert with_spaces == "hatchling != 1.0"
    assert canonical == "hatchling!=1.0"

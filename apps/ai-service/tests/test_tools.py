"""Tests for AI service tools."""
import pytest
from app.tools.calculate_budget import CalculateBudgetTool
from app.tools.get_weather import GetWeatherTool
from app.tools.search_places import SearchPlacesTool
from app.tools.calculate_route import CalculateRouteTool


class TestCalculateBudgetTool:
    """Test CalculateBudgetTool independently."""

    def setup_method(self):
        self.tool = CalculateBudgetTool()

    def test_tool_has_name(self):
        assert self.tool.name == "calculate_budget"

    def test_tool_has_description(self):
        assert len(self.tool.description) > 0

    def test_tool_has_parameters(self):
        assert isinstance(self.tool.parameters, dict)


class TestGetWeatherTool:
    """Test GetWeatherTool independently."""

    def setup_method(self):
        self.tool = GetWeatherTool()

    def test_tool_has_name(self):
        assert self.tool.name == "get_weather"

    def test_tool_has_description(self):
        assert len(self.tool.description) > 0


class TestSearchPlacesTool:
    """Test SearchPlacesTool independently."""

    def setup_method(self):
        self.tool = SearchPlacesTool()

    def test_tool_has_name(self):
        assert self.tool.name == "search_places"


class TestCalculateRouteTool:
    """Test CalculateRouteTool independently."""

    def setup_method(self):
        self.tool = CalculateRouteTool()

    def test_tool_has_name(self):
        assert self.tool.name == "calculate_route"

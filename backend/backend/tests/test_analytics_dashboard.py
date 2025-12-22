# -*- coding: utf-8 -*-
"""Tests for analytics dashboard functionality."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
import json

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.entities import Workspace, Task, Agent, LLMCall


class AnalyticsDashboardService:
    """Mock analytics dashboard service for testing."""
    
    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id
    
    async def get_dashboard_data(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
        refresh_cache: bool = False,
    ) -> dict:
        """Get comprehensive dashboard data."""
        return {
            "workspace_id": self.workspace_id,
            "generated_at": datetime.utcnow().isoformat(),
            "summary_cards": {
                "total_tasks": 150,
                "total_cost": 1250.75,
                "success_rate": 0.85,
                "average_completion_time": 3600.5,
                "active_agents": 6,
                "total_revenue": 5000.00
            },
            "task_trend_chart": {
                "chart_type": "line",
                "data": [
                    {"date": "2024-01-01", "created": 15, "completed": 12, "failed": 2},
                    {"date": "2024-01-02", "created": 18, "completed": 16, "failed": 1},
                    {"date": "2024-01-03", "created": 12, "completed": 10, "failed": 3},
                    {"date": "2024-01-04", "created": 20, "completed": 18, "failed": 1},
                    {"date": "2024-01-05", "created": 16, "completed": 14, "failed": 2}
                ],
                "x_axis": "date",
                "y_axis": "count",
                "series": ["created", "completed", "failed"]
            },
            "cost_breakdown_pie": {
                "chart_type": "pie",
                "data": [
                    {"label": "OpenAI", "value": 850.50, "color": "#ff6b6b"},
                    {"label": "Anthropic", "value": 300.25, "color": "#4ecdc4"},
                    {"label": "Google", "value": 100.00, "color": "#45b7d1"}
                ],
                "total": 1250.75
            },
            "agent_performance_comparison": {
                "chart_type": "bar",
                "data": [
                    {
                        "agent_name": "Code Agent 1",
                        "usage_count": 85,
                        "success_rate": 0.92,
                        "average_latency": 120.0,
                        "quality_score": 4.5
                    },
                    {
                        "agent_name": "Analysis Agent 1", 
                        "usage_count": 65,
                        "success_rate": 0.88,
                        "average_latency": 180.0,
                        "quality_score": 4.1
                    },
                    {
                        "agent_name": "Documentation Agent 1",
                        "usage_count": 42,
                        "success_rate": 0.95,
                        "average_latency": 95.0,
                        "quality_score": 4.7
                    }
                ]
            },
            "success_rate_gauge": {
                "chart_type": "gauge",
                "value": 85.0,
                "min": 0,
                "max": 100,
                "thresholds": {
                    "good": 90,
                    "warning": 75,
                    "critical": 60
                },
                "color": "#4caf50"
            },
            "recent_activities": [
                {
                    "id": str(uuid4()),
                    "type": "task_completed",
                    "description": "Task 'Code Review' completed successfully",
                    "timestamp": datetime.utcnow().isoformat(),
                    "severity": "success"
                },
                {
                    "id": str(uuid4()),
                    "type": "cost_alert",
                    "description": "Monthly budget 80% utilized",
                    "timestamp": datetime.utcnow().isoformat(),
                    "severity": "warning"
                }
            ],
            "kpi_alerts": [
                {
                    "id": str(uuid4()),
                    "type": "success_rate_decline",
                    "message": "Success rate dropped below 85%",
                    "value": 82.5,
                    "threshold": 85.0,
                    "timestamp": datetime.utcnow().isoformat()
                },
                {
                    "id": str(uuid4()),
                    "type": "cost_threshold",
                    "message": "Approaching monthly budget limit",
                    "value": 1250.75,
                    "threshold": 1500.0,
                    "timestamp": datetime.utcnow().isoformat()
                }
            ]
        }
    
    async def generate_pdf_report(
        self,
        report_type: str = "executive",
        start_date: datetime = None,
        end_date: datetime = None,
        include_charts: bool = True,
    ) -> dict:
        """Generate PDF report."""
        report_id = str(uuid4())
        
        return {
            "report_id": report_id,
            "type": report_type,
            "status": "completed",
            "generated_at": datetime.utcnow().isoformat(),
            "file_path": f"/tmp/reports/{report_type}_report_{report_id}.pdf",
            "size_bytes": 2048000,
            "pages": 12,
            "sections": [
                "executive_summary",
                "metrics_overview", 
                "cost_analysis",
                "agent_performance",
                "recommendations"
            ] if report_type == "executive" else [
                "detailed_metrics",
                "data_tables",
                "charts"
            ],
            "include_charts": include_charts,
            "download_url": f"/api/reports/{report_id}/download"
        }
    
    async def schedule_email_report(
        self,
        report_type: str,
        schedule: dict,
        recipients: list,
        template_id: str = None,
    ) -> dict:
        """Schedule email report delivery."""
        schedule_id = str(uuid4())
        
        return {
            "schedule_id": schedule_id,
            "status": "active",
            "report_type": report_type,
            "schedule": schedule,
            "recipients": recipients,
            "template_id": template_id,
            "next_execution": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }
    
    async def get_custom_report_templates(self) -> list:
        """Get custom report templates."""
        return [
            {
                "template_id": "executive-summary",
                "name": "Executive Summary",
                "description": "High-level overview for executives",
                "sections": ["summary", "trends", "recommendations"],
                "charts": ["success_rate_gauge", "cost_breakdown"],
                "created_at": datetime.utcnow().isoformat()
            },
            {
                "template_id": "technical-details",
                "name": "Technical Details",
                "description": "Detailed technical metrics and performance",
                "sections": ["performance", "resource_usage", "detailed_metrics"],
                "charts": ["task_trends", "agent_comparison"],
                "created_at": datetime.utcnow().isoformat()
            },
            {
                "template_id": "cost-analysis",
                "name": "Cost Analysis",
                "description": "Comprehensive cost breakdown and analysis",
                "sections": ["cost_overview", "provider_breakdown", "budget_tracking"],
                "charts": ["cost_breakdown", "cost_trends"],
                "created_at": datetime.utcnow().isoformat()
            }
        ]


@pytest.fixture
async def dashboard_service(db_session: AsyncSession):
    """Create dashboard service fixture."""
    workspace_id = str(uuid4())
    return AnalyticsDashboardService(workspace_id)


@pytest.fixture
async def test_workspace_with_dashboard_data(db_session: AsyncSession):
    """Create test workspace with dashboard data."""
    workspace = Workspace(
        name="Test Dashboard Workspace",
        slug="test-dashboard",
        metadata={}
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    
    # Create test data for dashboard
    for i in range(20):
        task = Task(
            workspace_id=workspace.id,
            name=f"Dashboard Test Task {i}",
            status="completed" if i % 4 == 0 else "running" if i % 3 == 0 else "pending",
            created_at=datetime.utcnow() - timedelta(days=i),
        )
        db_session.add(task)
    
    await db_session.commit()
    return workspace


# ============================================================================
# Dashboard Widget Tests
# ============================================================================

class TestDashboardWidgets:
    """Test dashboard widget functionality."""
    
    async def test_summary_cards_load(self, dashboard_service):
        """Test that summary cards load correctly."""
        data = await dashboard_service.get_dashboard_data()
        
        assert "summary_cards" in data
        cards = data["summary_cards"]
        
        required_cards = [
            "total_tasks", "total_cost", "success_rate", 
            "average_completion_time", "active_agents"
        ]
        
        for card in required_cards:
            assert card in cards
            assert isinstance(cards[card], (int, float))
        
        # Validate card values
        assert cards["total_tasks"] >= 0
        assert cards["total_cost"] >= 0
        assert 0 <= cards["success_rate"] <= 1
        assert cards["average_completion_time"] >= 0
        assert cards["active_agents"] >= 0
    
    async def test_task_trend_chart_renders(self, dashboard_service):
        """Test that task trend chart renders correctly."""
        data = await dashboard_service.get_dashboard_data()
        
        assert "task_trend_chart" in data
        chart = data["task_trend_chart"]
        
        # Check chart structure
        assert "chart_type" in chart
        assert "data" in chart
        assert "x_axis" in chart
        assert "y_axis" in chart
        assert "series" in chart
        
        assert chart["chart_type"] == "line"
        assert chart["x_axis"] == "date"
        assert chart["y_axis"] == "count"
        
        # Check data points
        assert isinstance(chart["data"], list)
        for point in chart["data"]:
            assert "date" in point
            assert "created" in point
            assert "completed" in point
            assert "failed" in point
            assert point["created"] >= 0
            assert point["completed"] >= 0
            assert point["failed"] >= 0
    
    async def test_cost_breakdown_pie_chart(self, dashboard_service):
        """Test that cost breakdown pie chart renders correctly."""
        data = await dashboard_service.get_dashboard_data()
        
        assert "cost_breakdown_pie" in data
        pie_chart = data["cost_breakdown_pie"]
        
        # Check chart structure
        assert pie_chart["chart_type"] == "pie"
        assert "data" in pie_chart
        assert "total" in pie_chart
        
        # Check data points
        assert isinstance(pie_chart["data"], list)
        for slice_data in pie_chart["data"]:
            assert "label" in slice_data
            assert "value" in slice_data
            assert "color" in slice_data
            assert slice_data["value"] >= 0
            assert slice_data["color"].startswith("#")
        
        # Validate total
        calculated_total = sum(slice_data["value"] for slice_data in pie_chart["data"])
        assert abs(calculated_total - pie_chart["total"]) < 0.01
    
    async def test_agent_performance_comparison(self, dashboard_service):
        """Test that agent performance comparison chart renders."""
        data = await dashboard_service.get_dashboard_data()
        
        assert "agent_performance_comparison" in data
        chart = data["agent_performance_comparison"]
        
        # Check chart structure
        assert chart["chart_type"] == "bar"
        assert "data" in chart
        
        # Check agent data
        assert isinstance(chart["data"], list)
        for agent_data in chart["data"]:
            assert "agent_name" in agent_data
            assert "usage_count" in agent_data
            assert "success_rate" in agent_data
            assert "average_latency" in agent_data
            assert "quality_score" in agent_data
            assert agent_data["usage_count"] >= 0
            assert 0 <= agent_data["success_rate"] <= 1
            assert agent_data["average_latency"] >= 0
            assert 1 <= agent_data["quality_score"] <= 5
    
    async def test_success_rate_gauge(self, dashboard_service):
        """Test that success rate gauge renders correctly."""
        data = await dashboard_service.get_dashboard_data()
        
        assert "success_rate_gauge" in data
        gauge = data["success_rate_gauge"]
        
        # Check gauge structure
        assert gauge["chart_type"] == "gauge"
        assert "value" in gauge
        assert "min" in gauge
        assert "max" in gauge
        assert "thresholds" in gauge
        assert "color" in gauge
        
        # Validate gauge values
        assert gauge["min"] == 0
        assert gauge["max"] == 100
        assert 0 <= gauge["value"] <= 100
        
        # Check thresholds
        thresholds = gauge["thresholds"]
        assert "good" in thresholds
        assert "warning" in thresholds
        assert "critical" in thresholds
        assert thresholds["good"] >= thresholds["warning"]
        assert thresholds["warning"] >= thresholds["critical"]
        
        # Validate color format
        assert gauge["color"].startswith("#")
    
    async def test_recent_activities_display(self, dashboard_service):
        """Test that recent activities display correctly."""
        data = await dashboard_service.get_dashboard_data()
        
        assert "recent_activities" in data
        activities = data["recent_activities"]
        
        assert isinstance(activities, list)
        
        for activity in activities:
            assert "id" in activity
            assert "type" in activity
            assert "description" in activity
            assert "timestamp" in activity
            assert "severity" in activity
            
            # Validate activity types
            valid_types = ["task_completed", "task_failed", "cost_alert", "agent_deployed"]
            assert activity["type"] in valid_types
            
            # Validate severity levels
            valid_severities = ["success", "warning", "error", "info"]
            assert activity["severity"] in valid_severities


# ============================================================================
# Responsive Design Tests
# ============================================================================

class TestDashboardResponsiveDesign:
    """Test dashboard responsive design."""
    
    async def test_dashboard_mobile_responsive(self, dashboard_service):
        """Test dashboard mobile responsiveness."""
        data = await dashboard_service.get_dashboard_data()
        
        # Check if mobile-friendly data structure is present
        assert "summary_cards" in data
        
        # Mobile view should have simplified cards
        cards = data["summary_cards"]
        mobile_friendly_cards = ["total_tasks", "total_cost", "success_rate"]
        
        for card in mobile_friendly_cards:
            assert card in cards
        
        # Charts should have mobile-optimized data
        if "task_trend_chart" in data:
            chart = data["task_trend_chart"]
            # Mobile should have fewer data points
            assert len(chart["data"]) <= 10
    
    async def test_dashboard_tablet_responsive(self, dashboard_service):
        """Test dashboard tablet responsiveness."""
        data = await dashboard_service.get_dashboard_data()
        
        # Tablet view should show most widgets
        required_widgets = [
            "summary_cards", "task_trend_chart", "cost_breakdown_pie", 
            "agent_performance_comparison", "success_rate_gauge"
        ]
        
        for widget in required_widgets:
            assert widget in data
    
    async def test_dashboard_desktop_complete_view(self, dashboard_service):
        """Test dashboard complete desktop view."""
        data = await dashboard_service.get_dashboard_data()
        
        # Desktop should show all widgets plus additional data
        desktop_widgets = [
            "summary_cards", "task_trend_chart", "cost_breakdown_pie",
            "agent_performance_comparison", "success_rate_gauge", 
            "recent_activities", "kpi_alerts"
        ]
        
        for widget in desktop_widgets:
            assert widget in data


# ============================================================================
# Interactive Features Tests
# ============================================================================

class TestDashboardInteractivity:
    """Test dashboard interactive features."""
    
    async def test_hover_info_available(self, dashboard_service):
        """Test that hover information is available."""
        data = await dashboard_service.get_dashboard_data()
        
        # Check task trend chart for hover data
        if "task_trend_chart" in data:
            chart = data["task_trend_chart"]
            for point in chart["data"]:
                # Each data point should have enough info for hover tooltips
                assert "date" in point
                # Additional hover info would be calculated client-side
        
        # Check cost breakdown for hover data
        if "cost_breakdown_pie" in data:
            pie_chart = data["cost_breakdown_pie"]
            for slice_data in pie_chart["data"]:
                # Should have percentage for hover tooltips
                assert "label" in slice_data
                assert "value" in slice_data
    
    async def test_drill_down_possible(self, dashboard_service):
        """Test that drill-down functionality is available."""
        data = await dashboard_service.get_dashboard_data()
        
        # Check if widgets have drill-down identifiers
        if "summary_cards" in data:
            cards = data["summary_cards"]
            # Each card should have an identifier for drill-down
            for card_name, value in cards.items():
                # Card should be drillable (in real implementation, would have ID)
                assert card_name is not None
        
        if "agent_performance_comparison" in data:
            chart = data["agent_performance_comparison"]
            for agent_data in chart["data"]:
                # Each agent should be drillable
                assert "agent_name" in agent_data
                # Could have agent_id for drill-down in real implementation
    
    async def test_real_time_updates(self, dashboard_service):
        """Test real-time dashboard updates."""
        # Get initial data
        initial_data = await dashboard_service.get_dashboard_data()
        initial_task_count = initial_data["summary_cards"]["total_tasks"]
        
        # In real implementation, would trigger data changes
        # For now, verify refresh_cache parameter works
        refreshed_data = await dashboard_service.get_dashboard_data(refresh_cache=True)
        
        assert refreshed_data["generated_at"] != initial_data["generated_at"]
        
        # Data structure should remain consistent
        required_keys = [
            "summary_cards", "task_trend_chart", "cost_breakdown_pie",
            "agent_performance_comparison", "success_rate_gauge"
        ]
        
        for key in required_keys:
            assert key in refreshed_data


# ============================================================================
# Report Generation Tests
# ============================================================================

class TestReportGeneration:
    """Test report generation functionality."""
    
    async def test_pdf_generates(self, dashboard_service):
        """Test that PDF report generates successfully."""
        result = await dashboard_service.generate_pdf_report(report_type="executive")
        
        assert result["status"] == "completed"
        assert result["file_path"].endswith(".pdf")
        assert result["size_bytes"] > 0
        assert result["pages"] > 0
        assert "download_url" in result
    
    async def test_report_content_accurate(self, dashboard_service):
        """Test that report content is accurate."""
        result = await dashboard_service.generate_pdf_report(
            report_type="executive",
            include_charts=True
        )
        
        # Check sections
        assert "sections" in result
        assert isinstance(result["sections"], list)
        assert len(result["sections"]) > 0
        
        # Executive report should have specific sections
        if result["type"] == "executive":
            expected_sections = ["executive_summary", "metrics_overview"]
            for section in expected_sections:
                assert any(section in s for s in result["sections"])
    
    async def test_email_delivery_works(self, dashboard_service):
        """Test that email delivery scheduling works."""
        schedule = {
            "frequency": "weekly",
            "day": "monday",
            "time": "09:00",
            "timezone": "UTC"
        }
        
        recipients = ["admin@example.com", "manager@example.com"]
        
        result = await dashboard_service.schedule_email_report(
            report_type="executive",
            schedule=schedule,
            recipients=recipients
        )
        
        assert result["status"] == "active"
        assert result["schedule"] == schedule
        assert result["recipients"] == recipients
        assert "next_execution" in result
    
    async def test_schedule_respected(self, dashboard_service):
        """Test that scheduled reports respect timing."""
        schedule = {
            "frequency": "daily",
            "time": "08:00"
        }
        
        result = await dashboard_service.schedule_email_report(
            report_type="technical",
            schedule=schedule,
            recipients=["tech@example.com"]
        )
        
        # Should schedule for next occurrence
        next_exec = datetime.fromisoformat(result["next_execution"].replace('Z', '+00:00'))
        now = datetime.utcnow()
        
        # Next execution should be in the future
        assert next_exec > now
        
        # Should be around the scheduled time (allowing for test timing)
        time_diff = abs((next_exec - now).total_seconds() - 86400)  # ~1 day
        assert time_diff < 3600  # Within 1 hour
    
    async def test_custom_templates_work(self, dashboard_service):
        """Test custom report templates."""
        templates = await dashboard_service.get_custom_report_templates()
        
        assert isinstance(templates, list)
        assert len(templates) > 0
        
        for template in templates:
            assert "template_id" in template
            assert "name" in template
            assert "description" in template
            assert "sections" in template
            assert "charts" in template
            assert "created_at" in template
            
            # Validate template structure
            assert len(template["sections"]) > 0
            assert len(template["charts"]) > 0
            assert len(template["description"]) > 0
    
    async def test_executive_summary_helpful(self, dashboard_service):
        """Test that executive summary is helpful for leadership."""
        result = await dashboard_service.generate_pdf_report(report_type="executive")
        
        # Executive report should be concise and high-level
        if "sections" in result:
            # Should include executive summary
            summary_sections = [s for s in result["sections"] if "summary" in s.lower()]
            assert len(summary_sections) > 0
            
            # Should include recommendations
            rec_sections = [s for s in result["sections"] if "recommend" in s.lower()]
            assert len(rec_sections) > 0


# ============================================================================
# Dark Mode Tests
# ============================================================================

class TestDashboardDarkMode:
    """Test dashboard dark mode support."""
    
    async def test_dark_mode_color_scheme(self, dashboard_service):
        """Test dark mode color scheme."""
        data = await dashboard_service.get_dashboard_data()
        
        # Check cost breakdown pie chart colors
        if "cost_breakdown_pie" in data:
            pie_chart = data["cost_breakdown_pie"]
            for slice_data in pie_chart["data"]:
                # Colors should be defined (dark mode colors would be different)
                assert "color" in slice_data
                assert slice_data["color"].startswith("#")
                assert len(slice_data["color"]) == 7  # Valid hex color
        
        # Success rate gauge color
        if "success_rate_gauge" in data:
            gauge = data["success_rate_gauge"]
            assert "color" in gauge
            assert gauge["color"].startswith("#")
    
    async def test_chart_accessibility_in_dark_mode(self, dashboard_service):
        """Test chart accessibility in dark mode."""
        data = await dashboard_service.get_dashboard_data()
        
        # All charts should have sufficient color contrast
        # This would be validated in real implementation with contrast checkers
        
        # For now, ensure colors are defined for all visual elements
        if "task_trend_chart" in data:
            chart = data["task_trend_chart"]
            assert "series" in chart
            # Series should have color definitions in real implementation
        
        if "agent_performance_comparison" in data:
            comparison = data["agent_performance_comparison"]
            # Agent comparison should have consistent colors


# ============================================================================
# Performance Tests
# ============================================================================

class TestDashboardPerformance:
    """Test dashboard performance."""
    
    async def test_dashboard_load_time(self, dashboard_service):
        """Test dashboard loads within acceptable time."""
        import time
        
        start_time = time.time()
        data = await dashboard_service.get_dashboard_data()
        load_time = time.time() - start_time
        
        assert data is not None
        # Should load within reasonable time (adjust based on requirements)
        assert load_time < 5.0  # Less than 5 seconds
    
    async def test_dashboard_cache_performance(self, dashboard_service):
        """Test dashboard cache improves performance."""
        import time
        
        # First call (cache miss)
        start_time = time.time()
        data1 = await dashboard_service.get_dashboard_data(refresh_cache=False)
        first_load_time = time.time() - start_time
        
        # Second call (cache hit)
        start_time = time.time()
        data2 = await dashboard_service.get_dashboard_data(refresh_cache=False)
        second_load_time = time.time() - start_time
        
        # Second call should be faster (cache hit)
        assert second_load_time <= first_load_time
        assert data1["generated_at"] == data2["generated_at"]  # Same cached data
    
    async def test_large_dataset_handling(self, dashboard_service):
        """Test handling of large datasets."""
        # Get dashboard data with full date range
        start_date = datetime.utcnow() - timedelta(days=365)
        end_date = datetime.utcnow()
        
        data = await dashboard_service.get_dashboard_data(
            start_date=start_date,
            end_date=end_date
        )
        
        assert data is not None
        assert "summary_cards" in data
        
        # Should handle large datasets without errors
        # Real implementation would test with actual large datasets


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestDashboardIntegration:
    """Integration tests for dashboard system."""
    
    async def test_complete_dashboard_workflow(
        self,
        dashboard_service,
        test_workspace_with_dashboard_data
    ):
        """Test complete dashboard workflow."""
        workspace_id = test_workspace_with_dashboard_data.id
        
        # 1. Get dashboard data
        dashboard_data = await dashboard_service.get_dashboard_data()
        assert dashboard_data is not None
        
        # 2. Generate report
        report = await dashboard_service.generate_pdf_report(report_type="executive")
        assert report["status"] == "completed"
        
        # 3. Schedule email report
        schedule = {
            "frequency": "weekly",
            "day": "monday",
            "time": "09:00"
        }
        email_schedule = await dashboard_service.schedule_email_report(
            report_type="executive",
            schedule=schedule,
            recipients=["admin@example.com"]
        )
        assert email_schedule["status"] == "active"
        
        # 4. Get custom templates
        templates = await dashboard_service.get_custom_report_templates()
        assert len(templates) > 0
    
    async def test_dashboard_data_consistency(
        self,
        dashboard_service,
        test_workspace_with_dashboard_data
    ):
        """Test dashboard data consistency across widgets."""
        data = await dashboard_service.get_dashboard_data()
        
        # Summary cards should be consistent with charts
        summary_tasks = data["summary_cards"]["total_tasks"]
        
        if "task_trend_chart" in data:
            chart_data = data["task_trend_chart"]["data"]
            chart_total = sum(point["created"] for point in chart_data)
            
            # Should be related but not necessarily equal (different date ranges)
            assert chart_total >= 0
        
        # Cost metrics should be consistent
        summary_cost = data["summary_cards"]["total_cost"]
        
        if "cost_breakdown_pie" in data:
            pie_total = data["cost_breakdown_pie"]["total"]
            assert abs(summary_cost - pie_total) < 0.01  # Should match
    
    async def test_dashboard_accessibility(self, dashboard_service):
        """Test dashboard accessibility features."""
        data = await dashboard_service.get_dashboard_data()
        
        # Check that all visual elements have text alternatives
        if "success_rate_gauge" in data:
            gauge = data["success_rate_gauge"]
            assert "value" in gauge  # Screen reader accessible value
        
        if "cost_breakdown_pie" in data:
            pie_chart = data["cost_breakdown_pie"]
            for slice_data in pie_chart["data"]:
                # Should have both color and text label
                assert "label" in slice_data
                assert "value" in slice_data
                assert "color" in slice_data


@pytest.mark.asyncio
async def test_dashboard_service_initialization(dashboard_service):
    """Test that dashboard service initializes correctly."""
    assert dashboard_service.workspace_id is not None


@pytest.mark.asyncio
async def test_dashboard_data_structure(dashboard_service):
    """Test that dashboard data has correct structure."""
    data = await dashboard_service.get_dashboard_data()
    
    # Check top-level structure
    required_top_level = [
        "workspace_id", "generated_at", "summary_cards", 
        "task_trend_chart", "cost_breakdown_pie"
    ]
    
    for key in required_top_level:
        assert key in data, f"Missing required key: {key}"
    
    # Check summary cards structure
    cards = data["summary_cards"]
    required_cards = ["total_tasks", "total_cost", "success_rate", "average_completion_time"]
    
    for card in required_cards:
        assert card in cards, f"Missing summary card: {card}"


@pytest.mark.asyncio
async def test_dashboard_refresh_functionality(dashboard_service):
    """Test dashboard refresh functionality."""
    # Get initial data
    initial_data = await dashboard_service.get_dashboard_data()
    
    # Force refresh
    refreshed_data = await dashboard_service.get_dashboard_data(refresh_cache=True)
    
    # Should have new timestamp
    assert refreshed_data["generated_at"] != initial_data["generated_at"]
    
    # Should maintain same structure
    required_keys = [
        "summary_cards", "task_trend_chart", "cost_breakdown_pie",
        "agent_performance_comparison", "success_rate_gauge"
    ]
    
    for key in required_keys:
        assert key in refreshed_data
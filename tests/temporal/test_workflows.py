"""Simple tests for Temporal workflows."""

from around_the_grounds.temporal.shared import WorkflowParams, WorkflowResult


class TestWorkflowDataClasses:
    """Test workflow data classes."""

    def test_workflow_params_defaults(self) -> None:
        """Test WorkflowParams with default values."""
        params = WorkflowParams()
        assert params.config_path is None
        assert params.deploy is False
        assert params.max_parallel_scrapes == 10
        assert params.site_key is None

    def test_workflow_params_custom(self) -> None:
        """Test WorkflowParams with custom values."""
        params = WorkflowParams(
            config_path="/test/config.json",
            deploy=True,
            max_parallel_scrapes=3,
            site_key="ballard-food-trucks",
        )
        assert params.config_path == "/test/config.json"
        assert params.deploy is True
        assert params.max_parallel_scrapes == 3
        assert params.site_key == "ballard-food-trucks"

    def test_workflow_params_site_key_default_persists_schedule_compat(self) -> None:
        """A persisted schedule predating site_key must still deserialize.

        Temporal serializes WorkflowParams as JSON; missing fields fall back
        to Python defaults. This test pins that contract — site_key must
        remain Optional with a None default so existing schedules keep
        firing after a worker upgrade.
        """
        from dataclasses import fields

        site_key_field = next(f for f in fields(WorkflowParams) if f.name == "site_key")
        assert site_key_field.default is None

    def test_workflow_result_minimal(self) -> None:
        """Test WorkflowResult with minimal data."""
        result = WorkflowResult(success=True, message="Test")
        assert result.success is True
        assert result.message == "Test"
        assert result.events_count is None
        assert result.errors is None
        assert result.deployed is False

    def test_workflow_result_full(self) -> None:
        """Test WorkflowResult with full data."""
        result = WorkflowResult(
            success=True,
            message="Test",
            events_count=5,
            errors=["error1"],
            deployed=True,
        )
        assert result.success is True
        assert result.message == "Test"
        assert result.events_count == 5
        assert result.errors == ["error1"]
        assert result.deployed is True


class TestWorkflowLogic:
    """Test workflow logic without Temporal infrastructure."""

    def test_workflow_imports(self) -> None:
        """Test that workflow can be imported without errors."""
        from around_the_grounds.temporal.workflows import FoodTruckWorkflow

        assert FoodTruckWorkflow is not None

    def test_workflow_creation(self) -> None:
        """Test that workflow can be instantiated."""
        from around_the_grounds.temporal.workflows import FoodTruckWorkflow

        workflow = FoodTruckWorkflow()
        assert workflow is not None

    def test_workflow_run_method_exists(self) -> None:
        """Test that workflow has run method."""
        from around_the_grounds.temporal.workflows import FoodTruckWorkflow

        workflow = FoodTruckWorkflow()
        assert hasattr(workflow, "run")
        assert callable(workflow.run)


class TestActivitiesImport:
    """Test activities can be imported."""

    def test_scrape_activities_import(self) -> None:
        """Test ScrapeActivities can be imported."""
        from around_the_grounds.temporal.activities import ScrapeActivities

        activities = ScrapeActivities()
        assert activities is not None

    def test_deployment_activities_import(self) -> None:
        """Test DeploymentActivities can be imported."""
        from around_the_grounds.temporal.activities import DeploymentActivities

        activities = DeploymentActivities()
        assert activities is not None

    def test_activities_have_methods(self) -> None:
        """Test activities have expected methods."""
        from around_the_grounds.temporal.activities import (
            DeploymentActivities,
            ScrapeActivities,
        )

        scrape_activities = ScrapeActivities()
        assert hasattr(scrape_activities, "load_site")
        assert hasattr(scrape_activities, "scrape_single_venue")

        deploy_activities = DeploymentActivities()
        assert hasattr(deploy_activities, "generate_web_data")
        assert hasattr(deploy_activities, "deploy_to_git")

"""Simplified tests for Temporal workflows using mocking."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from around_the_grounds.temporal.workflows import FoodTruckWorkflow
from around_the_grounds.temporal.shared import WorkflowParams, WorkflowResult


@pytest.mark.asyncio
async def test_food_truck_workflow_logic():
    """Test workflow logic by mocking workflow execution methods."""
    workflow = FoodTruckWorkflow()
    
    # Mock workflow.execute_activity_method
    with patch.object(workflow, '_workflow_execute_activity_method', new_callable=AsyncMock) as mock_execute:
        # Mock activity returns
        mock_execute.side_effect = [
            # load_brewery_config result
            [
                {
                    "key": "test-brewery",
                    "name": "Test Brewery",
                    "url": "https://test.com",
                    "parser_config": {}
                }
            ],
            # scrape_food_trucks result  
            (
                [
                    {
                        "brewery_key": "test-brewery",
                        "brewery_name": "Test Brewery",
                        "food_truck_name": "Test Truck",
                        "date": "2025-07-06T00:00:00",
                        "start_time": None,
                        "end_time": None,
                        "description": None,
                        "ai_generated_name": False,
                    }
                ],
                []  # no errors
            )
        ]
        
        # Execute workflow
        params = WorkflowParams(config_path=None, deploy=False)
        
        # Mock the workflow context
        with patch('temporalio.workflow.execute_activity_method', mock_execute):
            result = await workflow.run(params)
        
        assert isinstance(result, WorkflowResult)
        assert result.success is True
        assert result.events_count == 1
        assert result.deployed is False
        assert len(result.errors) == 0


@pytest.mark.asyncio
async def test_food_truck_workflow_with_deployment():
    """Test workflow with deployment enabled."""
    workflow = FoodTruckWorkflow()
    
    with patch.object(workflow, '_workflow_execute_activity_method', new_callable=AsyncMock) as mock_execute:
        # Mock activity returns
        mock_execute.side_effect = [
            # load_brewery_config result
            [
                {
                    "key": "test-brewery",
                    "name": "Test Brewery",
                    "url": "https://test.com",
                    "parser_config": {}
                }
            ],
            # scrape_food_trucks result
            (
                [
                    {
                        "brewery_key": "test-brewery",
                        "brewery_name": "Test Brewery",
                        "food_truck_name": "Test Truck",
                        "date": "2025-07-06T00:00:00",
                        "start_time": None,
                        "end_time": None,
                        "description": None,
                        "ai_generated_name": False,
                    }
                ],
                []  # no errors
            ),
            # generate_web_data result
            {
                "events": [
                    {
                        "date": "2025-07-06T00:00:00",
                        "vendor": "Test Truck",
                        "location": "Test Brewery",
                        "start_time": None,
                        "end_time": None,
                        "description": None,
                    }
                ],
                "total_events": 1,
                "updated": "2025-07-06T00:00:00"
            },
            # deploy_to_git result
            True
        ]
        
        # Execute workflow
        params = WorkflowParams(config_path=None, deploy=True)
        
        # Mock the workflow context
        with patch('temporalio.workflow.execute_activity_method', mock_execute):
            result = await workflow.run(params)
        
        assert isinstance(result, WorkflowResult)
        assert result.success is True
        assert result.events_count == 1
        assert result.deployed is True
        assert len(result.errors) == 0


@pytest.mark.asyncio
async def test_food_truck_workflow_with_errors():
    """Test workflow handling of scraping errors."""
    workflow = FoodTruckWorkflow()
    
    with patch.object(workflow, '_workflow_execute_activity_method', new_callable=AsyncMock) as mock_execute:
        # Mock activity returns with errors
        mock_execute.side_effect = [
            # load_brewery_config result
            [
                {
                    "key": "test-brewery",
                    "name": "Test Brewery",
                    "url": "https://test.com",
                    "parser_config": {}
                }
            ],
            # scrape_food_trucks result with errors
            (
                [],  # no events
                [
                    {
                        "brewery_name": "Test Brewery",
                        "message": "Connection timeout"
                    }
                ]
            )
        ]
        
        # Execute workflow
        params = WorkflowParams(config_path=None, deploy=False)
        
        # Mock the workflow context
        with patch('temporalio.workflow.execute_activity_method', mock_execute):
            result = await workflow.run(params)
        
        assert isinstance(result, WorkflowResult)
        assert result.success is True  # Workflow succeeds even with scraping errors
        assert result.events_count == 0
        assert result.deployed is False
        assert len(result.errors) == 1
        assert "Connection timeout" in result.errors[0]


@pytest.mark.asyncio
async def test_food_truck_workflow_activity_exception():
    """Test workflow handling of activity exceptions."""
    workflow = FoodTruckWorkflow()
    
    with patch.object(workflow, '_workflow_execute_activity_method', new_callable=AsyncMock) as mock_execute:
        # Mock activity exception
        mock_execute.side_effect = Exception("Configuration file not found")
        
        # Execute workflow
        params = WorkflowParams(config_path=None, deploy=False)
        
        # Mock the workflow context
        with patch('temporalio.workflow.execute_activity_method', mock_execute):
            result = await workflow.run(params)
        
        assert isinstance(result, WorkflowResult)
        assert result.success is False
        assert result.events_count == 0
        assert result.deployed is False
        assert len(result.errors) == 1
        assert "Configuration file not found" in result.errors[0]


@pytest.mark.asyncio
async def test_food_truck_workflow_no_events_no_deploy():
    """Test workflow with no events and deployment requested."""
    workflow = FoodTruckWorkflow()
    
    with patch.object(workflow, '_workflow_execute_activity_method', new_callable=AsyncMock) as mock_execute:
        # Mock activity returns with no events
        mock_execute.side_effect = [
            # load_brewery_config result
            [
                {
                    "key": "test-brewery",
                    "name": "Test Brewery",
                    "url": "https://test.com",
                    "parser_config": {}
                }
            ],
            # scrape_food_trucks result with no events
            ([], [])  # no events, no errors
        ]
        
        # Execute workflow with deployment requested
        params = WorkflowParams(config_path=None, deploy=True)
        
        # Mock the workflow context
        with patch('temporalio.workflow.execute_activity_method', mock_execute):
            result = await workflow.run(params)
        
        assert isinstance(result, WorkflowResult)
        assert result.success is True
        assert result.events_count == 0
        assert result.deployed is False  # No deployment when no events
        assert len(result.errors) == 0


def test_workflow_params_dataclass():
    """Test WorkflowParams data class."""
    # Test default values
    params = WorkflowParams()
    assert params.config_path is None
    assert params.deploy is False
    
    # Test custom values
    params = WorkflowParams(config_path="/path/to/config.json", deploy=True)
    assert params.config_path == "/path/to/config.json"
    assert params.deploy is True


def test_workflow_result_dataclass():
    """Test WorkflowResult data class."""
    # Test minimal result
    result = WorkflowResult(success=True, message="Test message")
    assert result.success is True
    assert result.message == "Test message"
    assert result.events_count is None
    assert result.errors is None
    assert result.deployed is False
    
    # Test full result
    result = WorkflowResult(
        success=True,
        message="Test message",
        events_count=5,
        errors=["error1", "error2"],
        deployed=True
    )
    assert result.success is True
    assert result.message == "Test message"
    assert result.events_count == 5
    assert result.errors == ["error1", "error2"]
    assert result.deployed is True
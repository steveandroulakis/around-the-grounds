"""Tests for Temporal workflows."""

import pytest
from unittest.mock import patch, AsyncMock
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from around_the_grounds.temporal.workflows import FoodTruckWorkflow
from around_the_grounds.temporal.activities import ScrapeActivities, DeploymentActivities
from around_the_grounds.temporal.shared import WorkflowParams, WorkflowResult


@pytest.mark.asyncio
async def test_food_truck_workflow_success():
    """Test successful workflow execution without deployment."""
    from temporalio.client import Client
    env = await WorkflowEnvironment.start_local()
    try:
        # Setup activities
        scrape_activities = ScrapeActivities()
        deploy_activities = DeploymentActivities()
        
        # Mock the activities to return test data
        with patch.object(scrape_activities, 'load_brewery_config', new_callable=AsyncMock) as mock_config, \
             patch.object(scrape_activities, 'scrape_food_trucks', new_callable=AsyncMock) as mock_scrape:
            
            # Mock configuration loading
            mock_config.return_value = [
                {
                    "key": "test-brewery",
                    "name": "Test Brewery",
                    "url": "https://test.com",
                    "parser_config": {}
                }
            ]
            
            # Mock scraping results
            mock_scrape.return_value = (
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
            
            # Create worker
            async with Worker(
                env.client,
                task_queue="test-task-queue",
                workflows=[FoodTruckWorkflow],
                activities=[
                    scrape_activities.load_brewery_config,
                    scrape_activities.scrape_food_trucks,
                    deploy_activities.generate_web_data,
                    deploy_activities.deploy_to_git,
                ],
            ):
                # Execute workflow
                params = WorkflowParams(config_path=None, deploy=False)
                result = await env.client.execute_workflow(
                    FoodTruckWorkflow.run,
                    params,
                    id="test-workflow",
                    task_queue="test-task-queue",
                )
                
                assert isinstance(result, WorkflowResult)
                assert result.success is True
                assert result.events_count == 1
                assert result.deployed is False
                assert len(result.errors) == 0
    finally:
        await env.shutdown()


@pytest.mark.asyncio
async def test_food_truck_workflow_with_deploy():
    """Test workflow with deployment enabled."""
    async with WorkflowEnvironment.start_local() as env:
        # Setup activities
        scrape_activities = ScrapeActivities()
        deploy_activities = DeploymentActivities()
        
        # Mock all activities
        with patch.object(scrape_activities, 'load_brewery_config', new_callable=AsyncMock) as mock_config, \
             patch.object(scrape_activities, 'scrape_food_trucks', new_callable=AsyncMock) as mock_scrape, \
             patch.object(deploy_activities, 'generate_web_data', new_callable=AsyncMock) as mock_web, \
             patch.object(deploy_activities, 'deploy_to_git', new_callable=AsyncMock) as mock_git:
            
            # Mock configuration loading
            mock_config.return_value = [
                {
                    "key": "test-brewery",
                    "name": "Test Brewery", 
                    "url": "https://test.com",
                    "parser_config": {}
                }
            ]
            
            # Mock scraping results
            mock_scrape.return_value = (
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
            
            # Mock web data generation
            mock_web.return_value = {
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
            }
            
            # Mock git deployment
            mock_git.return_value = True
            
            # Create worker
            async with Worker(
                env.client,
                task_queue="test-task-queue",
                workflows=[FoodTruckWorkflow],
                activities=[
                    scrape_activities.load_brewery_config,
                    scrape_activities.scrape_food_trucks,
                    deploy_activities.generate_web_data,
                    deploy_activities.deploy_to_git,
                ],
            ):
                # Execute workflow with deployment
                params = WorkflowParams(config_path=None, deploy=True)
                result = await env.client.execute_workflow(
                    FoodTruckWorkflow.run,
                    params,
                    id="test-workflow-deploy",
                    task_queue="test-task-queue",
                )
                
                assert isinstance(result, WorkflowResult)
                assert result.success is True
                assert result.events_count == 1
                assert result.deployed is True
                assert len(result.errors) == 0
                
                # Verify all activities were called
                mock_config.assert_called_once()
                mock_scrape.assert_called_once()
                mock_web.assert_called_once()
                mock_git.assert_called_once()


@pytest.mark.asyncio
async def test_food_truck_workflow_with_errors():
    """Test workflow handling of scraping errors."""
    async with WorkflowEnvironment.start_local() as env:
        # Setup activities
        scrape_activities = ScrapeActivities()
        deploy_activities = DeploymentActivities()
        
        # Mock activities with errors
        with patch.object(scrape_activities, 'load_brewery_config', new_callable=AsyncMock) as mock_config, \
             patch.object(scrape_activities, 'scrape_food_trucks', new_callable=AsyncMock) as mock_scrape:
            
            # Mock configuration loading
            mock_config.return_value = [
                {
                    "key": "test-brewery",
                    "name": "Test Brewery",
                    "url": "https://test.com",
                    "parser_config": {}
                }
            ]
            
            # Mock scraping with errors
            mock_scrape.return_value = (
                [],  # no events
                [
                    {
                        "brewery_name": "Test Brewery",
                        "message": "Connection timeout"
                    }
                ]
            )
            
            # Create worker
            async with Worker(
                env.client,
                task_queue="test-task-queue",
                workflows=[FoodTruckWorkflow],
                activities=[
                    scrape_activities.load_brewery_config,
                    scrape_activities.scrape_food_trucks,
                    deploy_activities.generate_web_data,
                    deploy_activities.deploy_to_git,
                ],
            ):
                # Execute workflow
                params = WorkflowParams(config_path=None, deploy=False)
                result = await env.client.execute_workflow(
                    FoodTruckWorkflow.run,
                    params,
                    id="test-workflow-errors",
                    task_queue="test-task-queue",
                )
                
                assert isinstance(result, WorkflowResult)
                assert result.success is True  # Workflow succeeds even with scraping errors
                assert result.events_count == 0
                assert result.deployed is False
                assert len(result.errors) == 1
                assert "Connection timeout" in result.errors[0]


@pytest.mark.asyncio
async def test_food_truck_workflow_activity_failure():
    """Test workflow handling of activity failures."""
    async with WorkflowEnvironment.start_local() as env:
        # Setup activities
        scrape_activities = ScrapeActivities()
        deploy_activities = DeploymentActivities()
        
        # Mock activities with failure
        with patch.object(scrape_activities, 'load_brewery_config', new_callable=AsyncMock) as mock_config:
            
            # Mock configuration loading failure
            mock_config.side_effect = Exception("Configuration file not found")
            
            # Create worker
            async with Worker(
                env.client,
                task_queue="test-task-queue",
                workflows=[FoodTruckWorkflow],
                activities=[
                    scrape_activities.load_brewery_config,
                    scrape_activities.scrape_food_trucks,
                    deploy_activities.generate_web_data,
                    deploy_activities.deploy_to_git,
                ],
            ):
                # Execute workflow
                params = WorkflowParams(config_path=None, deploy=False)
                result = await env.client.execute_workflow(
                    FoodTruckWorkflow.run,
                    params,
                    id="test-workflow-failure",
                    task_queue="test-task-queue",
                )
                
                assert isinstance(result, WorkflowResult)
                assert result.success is False
                assert result.events_count == 0
                assert result.deployed is False
                assert len(result.errors) == 1
                assert "Configuration file not found" in result.errors[0]


@pytest.mark.asyncio
async def test_food_truck_workflow_no_events_no_deploy():
    """Test workflow with no events found and deployment requested."""
    async with WorkflowEnvironment.start_local() as env:
        # Setup activities
        scrape_activities = ScrapeActivities()
        deploy_activities = DeploymentActivities()
        
        # Mock activities with no events
        with patch.object(scrape_activities, 'load_brewery_config', new_callable=AsyncMock) as mock_config, \
             patch.object(scrape_activities, 'scrape_food_trucks', new_callable=AsyncMock) as mock_scrape, \
             patch.object(deploy_activities, 'generate_web_data', new_callable=AsyncMock) as mock_web, \
             patch.object(deploy_activities, 'deploy_to_git', new_callable=AsyncMock) as mock_git:
            
            # Mock configuration loading
            mock_config.return_value = [
                {
                    "key": "test-brewery",
                    "name": "Test Brewery",
                    "url": "https://test.com",
                    "parser_config": {}
                }
            ]
            
            # Mock scraping with no events
            mock_scrape.return_value = ([], [])  # no events, no errors
            
            # Create worker
            async with Worker(
                env.client,
                task_queue="test-task-queue",
                workflows=[FoodTruckWorkflow],
                activities=[
                    scrape_activities.load_brewery_config,
                    scrape_activities.scrape_food_trucks,
                    deploy_activities.generate_web_data,
                    deploy_activities.deploy_to_git,
                ],
            ):
                # Execute workflow with deployment requested but no events
                params = WorkflowParams(config_path=None, deploy=True)
                result = await env.client.execute_workflow(
                    FoodTruckWorkflow.run,
                    params,
                    id="test-workflow-no-events",
                    task_queue="test-task-queue",
                )
                
                assert isinstance(result, WorkflowResult)
                assert result.success is True
                assert result.events_count == 0
                assert result.deployed is False  # No deployment when no events
                assert len(result.errors) == 0
                
                # Verify deployment activities were not called
                mock_web.assert_not_called()
                mock_git.assert_not_called()
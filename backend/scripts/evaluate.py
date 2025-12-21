#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""backend.scripts.evaluate

CLI tool for AI evaluation framework.
Provides commands for running evaluations, regression tests, and determinism tests.
"""

import asyncio
import json
import logging
import sys
from typing import List, Optional, Dict, Any
from pathlib import Path
import click
from datetime import datetime
import yaml

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.evaluation import EvaluationService, ScenarioLibrary
from services.evaluation.judge import LLMJudgeService
from db.models.entities_evaluation import EvaluationScenario
from db.models.enums import EvaluationType, EvaluationStatus
from db.database import get_db
from schemas import (
    EvaluationRunRequest,
    RegressionTestRequest,
    DeterminismTestRequest
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EvaluationCLI:
    """CLI class for evaluation operations."""
    
    def __init__(self):
        self.eval_service = EvaluationService()
        self.scenario_library = ScenarioLibrary()
        self.db = next(get_db())
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.db.close()
        except:
            pass


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file')
@click.pass_context
def cli(ctx, config):
    """AI Evaluation Framework CLI."""
    ctx.ensure_object(dict)
    if config:
        with open(config, 'r') as f:
            ctx.obj['config'] = yaml.safe_load(f)
    else:
        ctx.obj['config'] = {}


@cli.command()
@click.option('--category', help='Filter scenarios by category')
@click.option('--complexity', type=click.Choice(['easy', 'medium', 'hard', 'expert']), 
              help='Filter scenarios by complexity level')
@click.option('--output', '-o', type=click.Path(), help='Output file for scenarios')
@click.pass_context
def list_scenarios(ctx, category, complexity, output):
    """List available evaluation scenarios."""
    with EvaluationCLI() as cli:
        try:
            scenarios = cli.scenario_library.get_scenarios(
                category=category,
                complexity=complexity
            )
            
            click.echo(f"Found {len(scenarios)} scenarios:")
            for scenario in scenarios:
                click.echo(f"  • {scenario['name']} ({scenario['category']}, {scenario['complexity_level']})")
                click.echo(f"    {scenario['description']}")
                click.echo(f"    Language: {scenario.get('language', 'N/A')}")
                click.echo(f"    Framework: {scenario.get('framework', 'N/A')}")
                click.echo(f"    Duration: {scenario.get('estimated_duration_minutes', 'N/A')} minutes")
                click.echo(f"    Tags: {', '.join(scenario.get('tags', []))}")
                click.echo("")
            
            if output:
                with open(output, 'w') as f:
                    json.dump(scenarios, f, indent=2)
                click.echo(f"Scenarios saved to {output}")
                
        except Exception as e:
            click.echo(f"Error listing scenarios: {e}", err=True)
            sys.exit(1)


@cli.command()
@click.option('--scenario-id', '-s', required=True, help='Scenario ID or name')
@click.option('--output', '-o', required=True, help='Agent output code to evaluate')
@click.option('--judge-config', '-j', type=click.Path(exists=True), required=True,
              help='Judge configuration file')
@click.option('--context-file', type=click.Path(exists=True), help='Additional context file')
@click.option('--commit-hash', help='Git commit hash')
@click.option('--branch-name', help='Git branch name')
@click.option('--output-format', type=click.Choice(['json', 'table']), default='table',
              help='Output format')
def evaluate(scenario_id, output, judge_config, context_file, commit_hash, branch_name, output_format):
    """Run a single evaluation using LLM-as-a-Judge."""
    with EvaluationCLI() as cli:
        try:
            # Load judge configuration
            with open(judge_config, 'r') as f:
                judge_config_data = json.load(f)
            
            # Load agent output
            with open(output, 'r') as f:
                agent_output = f.read()
            
            # Load context if provided
            context = None
            if context_file:
                with open(context_file, 'r') as f:
                    context = json.load(f)
            
            # Find scenario
            scenario = None
            if cli.db:
                # Try to find by ID first
                scenario = cli.db.query(EvaluationScenario).filter(
                    EvaluationScenario.id == scenario_id
                ).first()
                
                # If not found, try to find by name
                if not scenario:
                    scenario = cli.db.query(EvaluationScenario).filter(
                        EvaluationScenario.name == scenario_id
                    ).first()
            
            if not scenario:
                # Create a temporary scenario from library
                lib_scenario = cli.scenario_library.get_scenario_by_name(scenario_id)
                if lib_scenario:
                    scenario = EvaluationScenario(
                        name=lib_scenario['name'],
                        description=lib_scenario['description'],
                        category=lib_scenario['category'],
                        language=lib_scenario.get('language'),
                        framework=lib_scenario.get('framework'),
                        prompt=lib_scenario['prompt'],
                        expected_output=lib_scenario.get('expected_output'),
                        evaluation_criteria=lib_scenario['evaluation_criteria'],
                        estimated_duration_minutes=lib_scenario.get('estimated_duration_minutes'),
                        tags=lib_scenario.get('tags', [])
                    )
                    scenario.id = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                else:
                    click.echo(f"Scenario '{scenario_id}' not found", err=True)
                    sys.exit(1)
            
            # Run evaluation
            click.echo(f"Running evaluation for scenario: {scenario.name}")
            result = asyncio.run(cli.eval_service.run_evaluation(
                scenario_id=scenario.id,
                agent_output=agent_output,
                judge_config=judge_config_data,
                context=context,
                commit_hash=commit_hash,
                branch_name=branch_name
            ))
            
            # Display results
            if output_format == 'json':
                click.echo(json.dumps({
                    'evaluation_id': result.id,
                    'scenario_id': result.scenario_id,
                    'overall_score': result.overall_score,
                    'score_breakdown': {
                        'code_safety': result.code_safety_score,
                        'code_quality': result.code_quality_score,
                        'best_practices': result.best_practices_score,
                        'performance': result.performance_score,
                        'readability': result.readability_score,
                        'functionality': result.functionality_score,
                        'security': result.security_score,
                        'maintainability': result.maintainability_score,
                    },
                    'feedback': {
                        'overall_feedback': result.judge_feedback,
                        'improvement_suggestions': result.improvement_suggestions,
                        'code_violations': result.code_violations,
                        'best_practices_mentioned': result.best_practices_mentioned,
                    },
                    'execution_time_ms': result.execution_time_ms,
                    'judge_model': result.judge_model,
                    'judge_cost_usd': result.judge_cost_usd,
                    'status': result.status.value
                }, indent=2))
            else:
                # Table format
                click.echo(f"\nEvaluation Results for {scenario.name}")
                click.echo("=" * 50)
                click.echo(f"Overall Score: {result.overall_score:.2f}/10.0")
                click.echo(f"Status: {result.status.value}")
                click.echo(f"Execution Time: {result.execution_time_ms}ms")
                click.echo(f"Judge Model: {result.judge_model}")
                click.echo(f"Cost: ${result.judge_cost_usd:.4f}")
                click.echo("")
                
                click.echo("Score Breakdown:")
                click.echo("-" * 30)
                dimensions = [
                    ('Code Safety', result.code_safety_score),
                    ('Code Quality', result.code_quality_score),
                    ('Best Practices', result.best_practices_score),
                    ('Performance', result.performance_score),
                    ('Readability', result.readability_score),
                    ('Functionality', result.functionality_score),
                    ('Security', result.security_score),
                    ('Maintainability', result.maintainability_score),
                ]
                
                for name, score in dimensions:
                    if score is not None:
                        bar = "█" * int(score) + "░" * (10 - int(score))
                        click.echo(f"{name:<15}: {score:.1f}/10 {bar}")
                
                if result.judge_feedback:
                    click.echo("")
                    click.echo("Judge Feedback:")
                    click.echo("-" * 30)
                    click.echo(result.judge_feedback[:500] + "..." if len(result.judge_feedback) > 500 else result.judge_feedback)
                
        except Exception as e:
            click.echo(f"Evaluation failed: {e}", err=True)
            sys.exit(1)


@cli.command()
@click.option('--scenario-id', '-s', required=True, help='Scenario ID or name')
@click.option('--output', '-o', required=True, help='Current agent output to test')
@click.option('--baseline-output', '-b', help='Baseline output (if not using stored baseline)')
@click.option('--judge-config', '-j', type=click.Path(exists=True), required=True,
              help='Judge configuration file')
@click.option('--commit-hash', '-c', required=True, help='Git commit hash')
@click.option('--branch-name', '-r', required=True, help='Git branch name')
@click.option('--threshold', '-t', default=5.0, help='Degradation threshold percentage')
@click.option('--output-format', type=click.Choice(['json', 'table']), default='table',
              help='Output format')
def regression(scenario_id, output, baseline_output, judge_config, commit_hash, branch_name, threshold, output_format):
    """Run regression test comparing current vs baseline performance."""
    with EvaluationCLI() as cli:
        try:
            # Load judge configuration
            with open(judge_config, 'r') as f:
                judge_config_data = json.load(f)
            
            # Load current output
            with open(output, 'r') as f:
                current_output = f.read()
            
            click.echo(f"Running regression test for scenario: {scenario_id}")
            click.echo(f"Commit: {commit_hash} ({branch_name})")
            click.echo(f"Threshold: {threshold}%")
            
            regression_result = asyncio.run(cli.eval_service.run_regression_test(
                scenario_id=scenario_id,
                current_agent_output=current_output,
                judge_config=judge_config_data,
                commit_hash=commit_hash,
                branch_name=branch_name,
                threshold_degradation=threshold
            ))
            
            # Display results
            if output_format == 'json':
                click.echo(json.dumps({
                    'test_id': regression_result.id,
                    'scenario_id': regression_result.scenario_id,
                    'commit_hash': regression_result.commit_hash,
                    'branch_name': regression_result.branch_name,
                    'baseline_score': regression_result.baseline_score,
                    'current_score': regression_result.current_score,
                    'score_change': regression_result.score_change,
                    'score_change_percentage': regression_result.score_change_percentage,
                    'alert_triggered': regression_result.alert_triggered,
                    'alert_message': regression_result.alert_message,
                    'status': regression_result.status
                }, indent=2))
            else:
                # Table format
                click.echo(f"\nRegression Test Results")
                click.echo("=" * 50)
                click.echo(f"Scenario: {regression_result.scenario_id}")
                click.echo(f"Commit: {regression_result.commit_hash}")
                click.echo(f"Branch: {regression_result.branch_name}")
                click.echo("")
                
                if regression_result.baseline_score is not None and regression_result.current_score is not None:
                    change = regression_result.score_change or 0
                    change_pct = regression_result.score_change_percentage or 0
                    
                    click.echo(f"Baseline Score: {regression_result.baseline_score:.2f}")
                    click.echo(f"Current Score: {regression_result.current_score:.2f}")
                    click.echo(f"Score Change: {change:+.2f} ({change_pct:+.1f}%)")
                    click.echo("")
                    
                    if regression_result.alert_triggered:
                        click.echo(f"🚨 REGRESSION DETECTED!")
                        click.echo(f"Alert: {regression_result.alert_message}")
                    else:
                        click.echo("✅ No significant regression detected")
                else:
                    click.echo("⚠️  Unable to compare scores (missing baseline or current)")
                
                click.echo(f"Status: {regression_result.status}")
                
        except Exception as e:
            click.echo(f"Regression test failed: {e}", err=True)
            sys.exit(1)


@cli.command()
@click.option('--scenario-id', '-s', required=True, help='Scenario ID or name')
@click.option('--judge-config', '-j', type=click.Path(exists=True), required=True,
              help='Judge configuration file')
@click.option('--k-values', multiple=True, type=int, default=[1, 5, 10, 20],
              help='k values to test (can be specified multiple times)')
@click.option('--success-threshold', default=7.0, help='Minimum score for success')
@click.option('--output-format', type=click.Choice(['json', 'table']), default='table',
              help='Output format')
def determinism(scenario_id, judge_config, k_values, success_threshold, output_format):
    """Run determinism test (Pass@k) for reliability measurement."""
    with EvaluationCLI() as cli:
        try:
            # Load judge configuration
            with open(judge_config, 'r') as f:
                judge_config_data = json.load(f)
            
            click.echo(f"Running determinism test for scenario: {scenario_id}")
            click.echo(f"k values: {list(k_values)}")
            click.echo(f"Success threshold: {success_threshold}")
            
            # Create a simple agent output provider for testing
            async def agent_output_provider():
                return f"Generated output for determinism testing - {datetime.now().isoformat()}"
            
            pass_k_metrics = asyncio.run(cli.eval_service.run_determinism_test(
                scenario_id=scenario_id,
                agent_output_provider=agent_output_provider,
                judge_config=judge_config_data,
                k_values=list(k_values),
                success_threshold=success_threshold
            ))
            
            # Display results
            if output_format == 'json':
                click.echo(json.dumps({
                    'scenario_id': scenario_id,
                    'pass_k_metrics': [
                        {
                            'k': metric.k_value,
                            'total_runs': metric.total_runs,
                            'successful_runs': metric.successful_runs,
                            'pass_at_k': metric.pass_at_k,
                            'confidence_interval': [
                                metric.confidence_interval_lower,
                                metric.confidence_interval_upper
                            ],
                            'reliability_grade': metric.reliability_grade,
                            'consistency_score': metric.consistency_score
                        }
                        for metric in pass_k_metrics
                    ]
                }, indent=2))
            else:
                # Table format
                click.echo(f"\nDeterminism Test Results for {scenario_id}")
                click.echo("=" * 60)
                
                for metric in pass_k_metrics:
                    click.echo(f"\nPass@{metric.k_value}:")
                    click.echo(f"  Success Rate: {metric.pass_at_k:.2%} ({metric.successful_runs}/{metric.total_runs})")
                    if metric.confidence_interval_lower is not None:
                        click.echo(f"  95% CI: [{metric.confidence_interval_lower:.2%}, {metric.confidence_interval_upper:.2%}]")
                    click.echo(f"  Reliability Grade: {metric.reliability_grade}")
                    click.echo(f"  Consistency Score: {metric.consistency_score:.2f}")
                    
                    # Show pass rate bar
                    bar_length = 20
                    filled = int(bar_length * metric.pass_at_k)
                    bar = "█" * filled + "░" * (bar_length - filled)
                    click.echo(f"  Progress: |{bar}| {metric.pass_at_k:.1%}")
                
        except Exception as e:
            click.echo(f"Determinism test failed: {e}", err=True)
            sys.exit(1)


@cli.command()
@click.option('--output-format', type=click.Choice(['json', 'yaml']), default='json',
              help='Output format')
@click.option('--baseline-only', is_flag=True, help='Only show baseline scenarios')
@click@click.pass_context
def scenarios(ctx, output_format, baseline_only):
    """Show available scenarios in the scenario library."""
    try:
        library = ScenarioLibrary()
        
        if baseline_only:
            scenarios = library.get_baseline_scenarios()
            click.echo("Baseline Scenarios:")
            click.echo("=" * 30)
        else:
            scenarios = list(library.scenarios.values())
            click.echo("All Scenarios:")
            click.echo("=" * 20)
        
        for scenario in scenarios:
            click.echo(f"• {scenario['name']}")
            click.echo(f"  Category: {scenario['category']}")
            click.echo(f"  Complexity: {scenario['complexity_level']}")
            click.echo(f"  Description: {scenario['description']}")
            if 'tags' in scenario and scenario['tags']:
                click.echo(f"  Tags: {', '.join(scenario['tags'])}")
            click.echo("")
        
        if output_format == 'json':
            click.echo(json.dumps(scenarios, indent=2))
        
    except Exception as e:
        click.echo(f"Failed to list scenarios: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--judge-config', '-j', type=click.Path(exists=True), required=True,
              help='Judge configuration file')
@click.option('--scenarios-file', '-s', type=click.Path(exists=True),
              help='File containing scenario configurations')
@click.option('--output', '-o', type=click.Path(), help='Output file for results')
@click.option('--parallel', is_flag=True, help='Run evaluations in parallel')
def batch_evaluate(judge_config, scenarios_file, output, parallel):
    """Run batch evaluations."""
    with EvaluationCLI() as cli:
        try:
            # Load judge configuration
            with open(judge_config, 'r') as f:
                judge_config_data = json.load(f)
            
            # Load scenarios
            if scenarios_file:
                with open(scenarios_file, 'r') as f:
                    scenarios_data = json.load(f)
            else:
                # Use baseline scenarios
                scenarios_data = cli.scenario_library.get_baseline_scenarios()
            
            click.echo(f"Running batch evaluation of {len(scenarios_data)} scenarios")
            if parallel:
                click.echo("Running in parallel mode")
            
            # Create evaluation requests
            evaluations = []
            for i, scenario in enumerate(scenarios_data):
                # Generate sample output for testing
                sample_output = f"# Sample implementation {i+1} for {scenario['name']}"
                
                evaluations.append({
                    'scenario_id': scenario.get('id', f"scenario_{i}"),
                    'agent_output': sample_output,
                    'judge_config': judge_config_data
                })
            
            # Run batch evaluation
            results = asyncio.run(cli.eval_service.run_evaluation_batch(
                evaluations=evaluations,
                judge_config=judge_config_data,
                parallel=parallel
            ))
            
            # Display summary
            click.echo(f"\nBatch Evaluation Summary")
            click.echo("=" * 40)
            click.echo(f"Total scenarios: {len(scenarios_data)}")
            click.echo(f"Successful evaluations: {len(results)}")
            
            if results:
                avg_score = sum(r.overall_score or 0 for r in results) / len(results)
                click.echo(f"Average score: {avg_score:.2f}")
                
                # Best and worst performers
                best = max(results, key=lambda r: r.overall_score or 0)
                worst = min(results, key=lambda r: r.overall_score or 0)
                click.echo(f"Best performer: {best.scenario_id} ({best.overall_score:.2f})")
                click.echo(f"Worst performer: {worst.scenario_id} ({worst.overall_score:.2f})")
            
            # Save results if output specified
            if output:
                results_data = []
                for result in results:
                    results_data.append({
                        'scenario_id': result.scenario_id,
                        'overall_score': result.overall_score,
                        'execution_time_ms': result.execution_time_ms,
                        'judge_cost_usd': result.judge_cost_usd,
                        'status': result.status.value
                    })
                
                with open(output, 'w') as f:
                    json.dump(results_data, f, indent=2)
                click.echo(f"\nResults saved to {output}")
                
        except Exception as e:
            click.echo(f"Batch evaluation failed: {e}", err=True)
            sys.exit(1)


if __name__ == '__main__':
    cli()
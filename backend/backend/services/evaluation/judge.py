# -*- coding: utf-8 -*-
"""backend.services.evaluation.judge

LLM-as-a-Judge service for evaluating code quality, safety, and agent performance.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import re

from ..llm.llm_service import LLMService
from ..llm.registry import ModelRegistry
from ..db.models.entities_evaluation import EvaluationResult, EvaluationScenario
from ..db.models.enums import LLMProvider, EvaluationType, EvaluationStatus
from ...schemas import (
    EvaluationCriteria,
    ScoreBreakdown,
    EvaluationFeedback
)


class LLMJudgeService:
    """Service for LLM-as-a-Judge evaluation of agent outputs."""
    
    def __init__(self, llm_service: LLMService = None):
        self.llm_service = llm_service or LLMService()
        self.model_registry = ModelRegistry()
        self.logger = logging.getLogger(__name__)
        
        # Evaluation dimensions and their weights
        self.evaluation_dimensions = {
            "code_safety": {"weight": 0.20, "description": "Code safety and security practices"},
            "code_quality": {"weight": 0.15, "description": "Overall code quality and structure"},
            "best_practices": {"weight": 0.15, "description": "Adherence to coding best practices"},
            "performance": {"weight": 0.15, "description": "Performance considerations and optimization"},
            "readability": {"weight": 0.10, "description": "Code readability and documentation"},
            "functionality": {"weight": 0.15, "description": "Correctness of functionality"},
            "security": {"weight": 0.10, "description": "Security vulnerabilities and best practices"},
            "maintainability": {"weight": 0.10, "description": "Code maintainability and extensibility"},
        }
    
    async def evaluate_code(
        self,
        agent_output: str,
        scenario: EvaluationScenario,
        judge_config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> EvaluationResult:
        """
        Evaluate agent output using LLM-as-a-Judge.
        
        Args:
            agent_output: The code/content produced by the agent
            scenario: Evaluation scenario with criteria
            judge_config: Judge configuration (model, temperature, etc.)
            context: Additional context for evaluation
            
        Returns:
            EvaluationResult with detailed scoring and feedback
        """
        start_time = time.time()
        
        try:
            # Initialize evaluation result
            evaluation_result = EvaluationResult(
                scenario_id=scenario.id,
                evaluation_type=EvaluationType.LLM_AS_JUDGE,
                status=EvaluationStatus.RUNNING,
                judge_model=judge_config.get("model", "gpt-4o"),
                judge_provider=LLMProvider(judge_config.get("provider", "openai")),
                judge_version=judge_config.get("version"),
                judge_temperature=judge_config.get("temperature", 0.1),
                agent_output=agent_output,
                expected_output=scenario.expected_output,
                started_at=datetime.utcnow()
            )
            
            # Construct evaluation prompt
            evaluation_prompt = self._construct_evaluation_prompt(
                agent_output, scenario, context
            )
            
            # Execute evaluation with judge LLM
            judge_response = await self._execute_judge_evaluation(
                evaluation_prompt, judge_config
            )
            
            # Parse and process judge response
            scores, feedback = self._parse_judge_response(judge_response)
            
            # Calculate overall score
            overall_score = self._calculate_weighted_score(scores)
            
            # Update evaluation result
            evaluation_result.completed_at = datetime.utcnow()
            evaluation_result.execution_time_ms = int((time.time() - start_time) * 1000)
            evaluation_result.status = EvaluationStatus.COMPLETED
            evaluation_result.overall_score = overall_score
            evaluation_result.weighted_score = overall_score
            
            # Set individual dimension scores
            dimension_scores = {
                "code_safety_score": scores.get("code_safety"),
                "code_quality_score": scores.get("code_quality"),
                "best_practices_score": scores.get("best_practices"),
                "performance_score": scores.get("performance"),
                "readability_score": scores.get("readability"),
                "functionality_score": scores.get("functionality"),
                "security_score": scores.get("security"),
                "maintainability_score": scores.get("maintainability"),
            }
            
            for field, value in dimension_scores.items():
                if value is not None:
                    setattr(evaluation_result, field, value)
            
            # Set feedback and analysis
            evaluation_result.judge_feedback = feedback.get("overall_feedback", "")
            evaluation_result.improvement_suggestions = feedback.get("improvement_suggestions", [])
            evaluation_result.code_violations = feedback.get("code_violations", [])
            evaluation_result.best_practices_mentioned = feedback.get("best_practices_mentioned", [])
            
            # Calculate similarity scores if expected output available
            if scenario.expected_output:
                similarity_scores = await self._calculate_similarity_scores(
                    agent_output, scenario.expected_output, judge_config
                )
                evaluation_result.similarity_score = similarity_scores.get("exact_similarity")
                evaluation_result.semantic_similarity = similarity_scores.get("semantic_similarity")
            
            # Track cost and tokens
            evaluation_result.judge_tokens_used = judge_response.get("total_tokens", 0)
            evaluation_result.judge_cost_usd = judge_response.get("estimated_cost", 0)
            
            self.logger.info(
                f"Evaluation completed: scenario={scenario.id}, "
                f"score={overall_score:.2f}, duration={evaluation_result.execution_time_ms}ms"
            )
            
            return evaluation_result
            
        except Exception as e:
            self.logger.error(f"Evaluation failed: {str(e)}", exc_info=True)
            
            # Return error evaluation result
            error_result = EvaluationResult(
                scenario_id=scenario.id,
                evaluation_type=EvaluationType.LLM_AS_JUDGE,
                status=EvaluationStatus.ERROR,
                judge_model=judge_config.get("model", "gpt-4o"),
                judge_provider=LLMProvider(judge_config.get("provider", "openai")),
                error_message=str(e),
                completed_at=datetime.utcnow(),
                execution_time_ms=int((time.time() - start_time) * 1000)
            )
            
            return error_result
    
    def _construct_evaluation_prompt(
        self,
        agent_output: str,
        scenario: EvaluationScenario,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Construct the evaluation prompt for the judge LLM."""
        
        prompt = f"""You are an expert code reviewer and AI judge. Evaluate the following agent output based on the provided scenario and criteria.

## SCENARIO
**Name:** {scenario.name}
**Description:** {scenario.description}
**Category:** {scenario.category}
**Complexity:** {scenario.complexity_level.value}
**Language:** {scenario.language or "N/A"}
**Framework:** {scenario.framework or "N/A"}

## AGENT OUTPUT
```python
{agent_output}
```

## EVALUATION CRITERIA
{json.dumps(scenario.evaluation_criteria, indent=2)}

## EVALUATION DIMENSIONS
Please evaluate the agent output on the following dimensions (score 0-10):

1. **Code Safety (20%):** Security vulnerabilities, input validation, error handling
2. **Code Quality (15%):** Overall code structure, organization, and correctness
3. **Best Practices (15%):** Following industry standards and coding conventions
4. **Performance (15%):** Optimization considerations, algorithmic efficiency
5. **Readability (10%):** Code clarity, documentation, comments
6. **Functionality (15%):** Correct implementation of requirements
7. **Security (10%):** Security best practices, vulnerability prevention
8. **Maintainability (10%):** Code maintainability, extensibility, modularity

## CONTEXT
{json.dumps(context, indent=2) if context else "No additional context provided"}

## RESPONSE FORMAT
Please respond in the following JSON format:

{{
    "scores": {{
        "code_safety": <0-10 score>,
        "code_quality": <0-10 score>,
        "best_practices": <0-10 score>,
        "performance": <0-10 score>,
        "readability": <0-10 score>,
        "functionality": <0-10 score>,
        "security": <0-10 score>,
        "maintainability": <0-10 score>
    }},
    "overall_feedback": "Overall assessment and reasoning",
    "improvement_suggestions": [
        "Specific suggestion 1",
        "Specific suggestion 2"
    ],
    "code_violations": [
        {{
            "type": "security_vulnerability|best_practice|performance|readability",
            "description": "Description of the violation",
            "severity": "low|medium|high|critical",
            "line_number": <if applicable>
        }}
    ],
    "best_practices_mentioned": [
        "Practice 1",
        "Practice 2"
    ]
}}

Provide detailed, constructive feedback focusing on specific areas for improvement."""

        return prompt
    
    async def _execute_judge_evaluation(
        self,
        prompt: str,
        judge_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute evaluation using the judge LLM."""
        
        try:
            # Get judge model configuration
            model_name = judge_config.get("model", "gpt-4o")
            temperature = judge_config.get("temperature", 0.1)
            max_tokens = judge_config.get("max_tokens", 2000)
            
            # Prepare LLM request
            request_config = {
                "model": model_name,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": "json_object"
            }
            
            # Execute LLM call
            response = await self.llm_service.generate(
                prompt=prompt,
                config=request_config
            )
            
            # Parse response metadata
            usage = getattr(response, 'usage', {})
            total_tokens = usage.get('total_tokens', 0)
            
            # Estimate cost (rough approximation)
            cost_per_token = self._get_cost_per_token(model_name)
            estimated_cost = (total_tokens / 1000) * cost_per_token
            
            return {
                "content": response.content if hasattr(response, 'content') else str(response),
                "total_tokens": total_tokens,
                "estimated_cost": estimated_cost
            }
            
        except Exception as e:
            self.logger.error(f"Judge evaluation execution failed: {str(e)}")
            raise
    
    def _parse_judge_response(self, judge_response: Dict[str, Any]) -> Tuple[Dict[str, float], Dict[str, Any]]:
        """Parse the judge's JSON response into structured data."""
        
        try:
            content = judge_response["content"]
            
            # Handle JSON parsing with potential formatting issues
            if isinstance(content, str):
                # Clean the content to extract JSON
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
            
            # Parse JSON
            parsed_response = json.loads(content)
            
            # Extract scores
            scores = parsed_response.get("scores", {})
            
            # Validate and clamp scores to 0-10 range
            validated_scores = {}
            for dimension, score in scores.items():
                try:
                    validated_score = float(score)
                    validated_scores[dimension] = max(0.0, min(10.0, validated_score))
                except (ValueError, TypeError):
                    validated_scores[dimension] = 0.0
            
            # Extract feedback
            feedback = {
                "overall_feedback": parsed_response.get("overall_feedback", ""),
                "improvement_suggestions": parsed_response.get("improvement_suggestions", []),
                "code_violations": parsed_response.get("code_violations", []),
                "best_practices_mentioned": parsed_response.get("best_practices_mentioned", [])
            }
            
            return validated_scores, feedback
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse judge response as JSON: {e}")
            self.logger.debug(f"Response content: {judge_response.get('content', '')}")
            
            # Return default scores and error feedback
            default_scores = {dim: 0.0 for dim in self.evaluation_dimensions.keys()}
            default_feedback = {
                "overall_feedback": "Failed to parse judge evaluation response",
                "improvement_suggestions": [],
                "code_violations": [],
                "best_practices_mentioned": []
            }
            
            return default_scores, default_feedback
    
    def _calculate_weighted_score(self, scores: Dict[str, float]) -> float:
        """Calculate weighted overall score from individual dimension scores."""
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for dimension, score in scores.items():
            if dimension in self.evaluation_dimensions and score is not None:
                weight = self.evaluation_dimensions[dimension]["weight"]
                weighted_sum += score * weight
                total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    async def _calculate_similarity_scores(
        self,
        agent_output: str,
        expected_output: str,
        judge_config: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate similarity scores between agent and expected outputs."""
        
        try:
            # Use a simple approach first - can be enhanced with embeddings
            exact_similarity = self._calculate_exact_similarity(agent_output, expected_output)
            
            # For semantic similarity, we could use embeddings or LLM-based comparison
            semantic_similarity = await self._calculate_semantic_similarity(
                agent_output, expected_output, judge_config
            )
            
            return {
                "exact_similarity": exact_similarity,
                "semantic_similarity": semantic_similarity
            }
            
        except Exception as e:
            self.logger.error(f"Similarity calculation failed: {e}")
            return {"exact_similarity": 0.0, "semantic_similarity": 0.0}
    
    def _calculate_exact_similarity(self, text1: str, text2: str) -> float:
        """Calculate exact string similarity (Jaccard similarity)."""
        
        try:
            # Tokenize and normalize
            tokens1 = set(re.findall(r'\w+', text1.lower()))
            tokens2 = set(re.findall(r'\w+', text2.lower()))
            
            if not tokens1 and not tokens2:
                return 1.0
            
            if not tokens1 or not tokens2:
                return 0.0
            
            intersection = len(tokens1.intersection(tokens2))
            union = len(tokens1.union(tokens2))
            
            return intersection / union if union > 0 else 0.0
            
        except Exception:
            return 0.0
    
    async def _calculate_semantic_similarity(
        self,
        text1: str,
        text2: str,
        judge_config: Dict[str, Any]
    ) -> float:
        """Calculate semantic similarity using LLM-based comparison."""
        
        try:
            comparison_prompt = f"""Compare the semantic similarity between these two pieces of code/content.

**Content 1:**
{text1}

**Content 2:**
{text2}

Rate the semantic similarity from 0.0 (completely different) to 1.0 (essentially identical in meaning and functionality).

Respond with just the numerical score: <score>"""

            # Use a lighter model for comparison
            comparison_config = {
                "model": judge_config.get("model", "gpt-4o"),
                "temperature": 0.1,
                "max_tokens": 10
            }
            
            response = await self.llm_service.generate(
                prompt=comparison_prompt,
                config=comparison_config
            )
            
            content = str(response.content).strip()
            
            # Extract numerical score
            score_match = re.search(r'(\d*\.?\d+)', content)
            if score_match:
                score = float(score_match.group(1))
                return max(0.0, min(1.0, score))
            else:
                return 0.0
                
        except Exception as e:
            self.logger.error(f"Semantic similarity calculation failed: {e}")
            return 0.0
    
    def _get_cost_per_token(self, model_name: str) -> float:
        """Get cost per token for different models (approximate rates)."""
        
        cost_rates = {
            "gpt-4o": 0.005,  # $5 per 1M tokens
            "gpt-4o-mini": 0.00015,  # $0.15 per 1M tokens
            "claude-3-opus": 0.015,  # $15 per 1M tokens
            "claude-3-sonnet": 0.003,  # $3 per 1M tokens
            "claude-3-haiku": 0.00025,  # $0.25 per 1M tokens
        }
        
        return cost_rates.get(model_name, 0.005)  # Default to GPT-4o rate
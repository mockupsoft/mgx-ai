# -*- coding: utf-8 -*-
"""Prompt optimization and compression service for reducing token costs."""

import logging
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PromptOptimizationResult:
    """Result of prompt optimization."""
    original_prompt: str
    optimized_prompt: str
    original_tokens: int
    optimized_tokens: int
    reduction_percent: float
    optimization_techniques: List[str]


class PromptOptimizer:
    """
    Service for optimizing prompts to reduce token usage while preserving important information.
    
    Features:
    - Remove redundant text and whitespace
    - Compress repetitive patterns
    - Optimize context window usage
    - Preserve critical information
    """
    
    def __init__(self, enable_compression: bool = True, min_reduction_percent: float = 5.0, target_reduction_percent: float = 35.0):
        """
        Initialize the prompt optimizer.
        
        Args:
            enable_compression: Enable prompt compression
            min_reduction_percent: Minimum reduction percentage to apply optimization
            target_reduction_percent: Target reduction percentage (30-50% range)
        """
        self.enable_compression = enable_compression
        self.min_reduction_percent = min_reduction_percent
        self.target_reduction_percent = target_reduction_percent
    
    def optimize(
        self,
        prompt: str,
        preserve_sections: Optional[List[str]] = None,
        max_tokens: Optional[int] = None,
    ) -> PromptOptimizationResult:
        """
        Optimize a prompt to reduce token usage.
        
        Args:
            prompt: Original prompt text
            preserve_sections: List of section markers to preserve (e.g., ["```", "---"])
            max_tokens: Maximum target tokens (will compress more aggressively if exceeded)
        
        Returns:
            PromptOptimizationResult with optimization details
        """
        if not self.enable_compression:
            return PromptOptimizationResult(
                original_prompt=prompt,
                optimized_prompt=prompt,
                original_tokens=self._estimate_tokens(prompt),
                optimized_tokens=self._estimate_tokens(prompt),
                reduction_percent=0.0,
                optimization_techniques=[],
            )
        
        original_tokens = self._estimate_tokens(prompt)
        optimized = prompt
        techniques = []
        
        # 1. Remove excessive whitespace
        optimized, removed_ws = self._remove_excessive_whitespace(optimized)
        if removed_ws:
            techniques.append("whitespace_removal")
        
        # 2. Remove redundant newlines
        optimized, removed_nl = self._remove_redundant_newlines(optimized)
        if removed_nl:
            techniques.append("newline_compression")
        
        # 3. Compress repetitive patterns
        optimized, compressed = self._compress_repetitive_patterns(optimized)
        if compressed:
            techniques.append("pattern_compression")
        
        # 4. Optimize code blocks (preserve structure)
        if preserve_sections:
            optimized = self._preserve_sections(optimized, preserve_sections)
        
        # 5. Remove unnecessary words/phrases
        optimized, removed_words = self._remove_unnecessary_words(optimized)
        if removed_words:
            techniques.append("word_optimization")
        
        # 6. Remove redundant explanations and verbose descriptions
        optimized, removed_verbose = self._remove_verbose_descriptions(optimized)
        if removed_verbose:
            techniques.append("verbose_removal")
        
        # 7. Compress code examples (keep structure, reduce comments)
        optimized, compressed_code = self._compress_code_examples(optimized)
        if compressed_code:
            techniques.append("code_compression")
        
        # 8. If max_tokens specified and still exceeded, apply aggressive compression
        optimized_tokens = self._estimate_tokens(optimized)
        if max_tokens and optimized_tokens > max_tokens:
            optimized = self._aggressive_compression(optimized, max_tokens)
            optimized_tokens = self._estimate_tokens(optimized)
            techniques.append("aggressive_compression")
        
        # 9. If target reduction not met, apply additional optimizations
        reduction_percent = ((original_tokens - optimized_tokens) / original_tokens * 100) if original_tokens > 0 else 0.0
        if reduction_percent < self.target_reduction_percent and original_tokens > 500:
            # Apply additional compression passes
            optimized = self._apply_additional_compression(optimized, original_tokens)
            optimized_tokens = self._estimate_tokens(optimized)
            reduction_percent = ((original_tokens - optimized_tokens) / original_tokens * 100) if original_tokens > 0 else 0.0
            techniques.append("additional_compression")
        
        # Only apply if reduction is significant
        if reduction_percent < self.min_reduction_percent:
            optimized = prompt
            optimized_tokens = original_tokens
            reduction_percent = 0.0
            techniques = []
        
        return PromptOptimizationResult(
            original_prompt=prompt,
            optimized_prompt=optimized,
            original_tokens=original_tokens,
            optimized_tokens=optimized_tokens,
            reduction_percent=reduction_percent,
            optimization_techniques=techniques,
        )
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count (rough approximation: ~4 characters per token).
        
        Args:
            text: Text to estimate
        
        Returns:
            Estimated token count
        """
        # Rough approximation: English text averages ~4 characters per token
        # This is a simple heuristic; actual tokenization varies by model
        return len(text) // 4
    
    def _remove_excessive_whitespace(self, text: str) -> Tuple[str, bool]:
        """Remove excessive whitespace while preserving structure."""
        # Replace multiple spaces with single space
        optimized = re.sub(r' +', ' ', text)
        # Remove trailing whitespace from lines
        optimized = '\n'.join(line.rstrip() for line in optimized.split('\n'))
        return optimized, optimized != text
    
    def _remove_redundant_newlines(self, text: str) -> Tuple[str, bool]:
        """Remove redundant newlines (more than 2 consecutive)."""
        optimized = re.sub(r'\n{3,}', '\n\n', text)
        return optimized, optimized != text
    
    def _compress_repetitive_patterns(self, text: str) -> Tuple[str, bool]:
        """Compress repetitive patterns in text."""
        # Find and compress repeated phrases (simple heuristic)
        # This is a basic implementation; more sophisticated NLP could be used
        lines = text.split('\n')
        compressed_lines = []
        prev_line = None
        repeat_count = 0
        
        for line in lines:
            if line.strip() == prev_line:
                repeat_count += 1
                if repeat_count <= 2:  # Keep first 2 occurrences
                    compressed_lines.append(line)
            else:
                if repeat_count > 2:
                    compressed_lines.append(f"[... {repeat_count - 2} more similar lines ...]")
                compressed_lines.append(line)
                prev_line = line.strip() if line.strip() else None
                repeat_count = 0
        
        optimized = '\n'.join(compressed_lines)
        return optimized, optimized != text
    
    def _preserve_sections(self, text: str, markers: List[str]) -> str:
        """Preserve specific sections marked by markers."""
        # This is a placeholder - in practice, you'd parse and preserve code blocks, etc.
        return text
    
    def _remove_unnecessary_words(self, text: str) -> Tuple[str, bool]:
        """Remove unnecessary filler words while preserving meaning."""
        # Common filler words/phrases that can often be removed
        unnecessary_patterns = [
            r'\bplease note that\b',
            r'\bit is important to\b',
            r'\bit should be noted that\b',
            r'\bas you can see\b',
            r'\bas mentioned\b',
            r'\bas stated\b',
        ]
        
        optimized = text
        for pattern in unnecessary_patterns:
            optimized = re.sub(pattern, '', optimized, flags=re.IGNORECASE)
        
        # Clean up extra spaces
        optimized = re.sub(r' +', ' ', optimized)
        
        return optimized, optimized != text
    
    def _remove_verbose_descriptions(self, text: str) -> Tuple[str, bool]:
        """Remove verbose descriptions and explanations."""
        # Remove common verbose patterns
        verbose_patterns = [
            r'\bIt is important to note that\b',
            r'\bPlease be aware that\b',
            r'\bI would like to\b',
            r'\bIn order to\b',
            r'\bFor the purpose of\b',
            r'\bWith regard to\b',
            r'\bIn the context of\b',
            r'\bIt should be emphasized that\b',
        ]
        
        optimized = text
        for pattern in verbose_patterns:
            optimized = re.sub(pattern, '', optimized, flags=re.IGNORECASE)
        
        # Clean up extra spaces
        optimized = re.sub(r' +', ' ', optimized)
        
        return optimized, optimized != text
    
    def _compress_code_examples(self, text: str) -> Tuple[str, bool]:
        """Compress code examples by removing excessive comments."""
        # Find code blocks
        code_block_pattern = r'```[\s\S]*?```'
        
        def compress_code_block(match):
            code_block = match.group(0)
            # Remove single-line comments (keep multi-line comments that might be important)
            compressed = re.sub(r'^\s*#.*$', '', code_block, flags=re.MULTILINE)
            # Remove excessive blank lines
            compressed = re.sub(r'\n{3,}', '\n\n', compressed)
            return compressed
        
        optimized = re.sub(code_block_pattern, compress_code_block, text)
        
        return optimized, optimized != text
    
    def _apply_additional_compression(self, text: str, original_tokens: int) -> str:
        """Apply additional compression passes to reach target reduction."""
        target_tokens = int(original_tokens * (1 - self.target_reduction_percent / 100))
        
        # Split into sentences and prioritize important ones
        sentences = re.split(r'[.!?]\s+', text)
        
        # Score sentences by importance (simple heuristic)
        scored_sentences = []
        for sentence in sentences:
            if not sentence.strip():
                continue
            score = 0
            # Important keywords
            if any(kw in sentence.lower() for kw in ['error', 'required', 'must', 'critical', 'important']):
                score += 2
            if any(kw in sentence.lower() for kw in ['example', 'note', 'see', 'refer']):
                score -= 1
            scored_sentences.append((score, sentence))
        
        # Sort by score (descending) and keep top sentences
        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        
        # Select sentences until we reach target
        selected = []
        current_tokens = 0
        
        for score, sentence in scored_sentences:
            sentence_tokens = self._estimate_tokens(sentence)
            if current_tokens + sentence_tokens <= target_tokens:
                selected.append(sentence)
                current_tokens += sentence_tokens
            elif score >= 2:  # Keep critical sentences even if over limit
                selected.append(sentence[:target_tokens * 4 - current_tokens * 4] + "...")
                break
        
        return '. '.join(selected) + '.' if selected else text[:target_tokens * 4]
    
    def _aggressive_compression(self, text: str, target_tokens: int) -> str:
        """Apply aggressive compression to meet token target."""
        # Split into sentences
        sentences = re.split(r'[.!?]\s+', text)
        
        # Estimate tokens per sentence
        sentence_tokens = [(s, self._estimate_tokens(s)) for s in sentences if s.strip()]
        
        # Keep sentences until we reach target
        result_sentences = []
        current_tokens = 0
        
        for sentence, tokens in sentence_tokens:
            if current_tokens + tokens <= target_tokens:
                result_sentences.append(sentence)
                current_tokens += tokens
            else:
                break
        
        # If still too long, truncate last sentence
        if result_sentences and current_tokens > target_tokens:
            last_sentence = result_sentences[-1]
            max_chars = (target_tokens - (current_tokens - self._estimate_tokens(last_sentence))) * 4
            result_sentences[-1] = last_sentence[:max_chars] + "..."
        
        return '. '.join(result_sentences) + '.' if result_sentences else text[:target_tokens * 4]
    
    def optimize_context_window(
        self,
        context: List[Dict[str, str]],
        max_tokens: int,
        priority_key: str = "importance",
    ) -> List[Dict[str, str]]:
        """
        Optimize context window by selecting most important items.
        
        Args:
            context: List of context items with metadata
            max_tokens: Maximum tokens for context
            priority_key: Key in context items to use for prioritization
        
        Returns:
            Optimized context list
        """
        if not context:
            return []
        
        # Estimate tokens for each item
        items_with_tokens = []
        for item in context:
            text = item.get("content", item.get("text", ""))
            tokens = self._estimate_tokens(text)
            importance = item.get(priority_key, 0)
            items_with_tokens.append({
                "item": item,
                "tokens": tokens,
                "importance": importance,
            })
        
        # Sort by importance (descending)
        items_with_tokens.sort(key=lambda x: x["importance"], reverse=True)
        
        # Select items until we reach max_tokens
        selected = []
        current_tokens = 0
        
        for item_data in items_with_tokens:
            if current_tokens + item_data["tokens"] <= max_tokens:
                selected.append(item_data["item"])
                current_tokens += item_data["tokens"]
            else:
                # Try to fit partial item if it's very important
                if item_data["importance"] > 0.8:
                    remaining_tokens = max_tokens - current_tokens
                    if remaining_tokens > 100:  # Only if significant space remains
                        # Truncate item
                        truncated_item = item_data["item"].copy()
                        max_chars = remaining_tokens * 4
                        content_key = "content" if "content" in truncated_item else "text"
                        if content_key in truncated_item:
                            truncated_item[content_key] = truncated_item[content_key][:max_chars] + "..."
                        selected.append(truncated_item)
                break
        
        return selected


# Global optimizer instance
_optimizer: Optional[PromptOptimizer] = None


def get_prompt_optimizer() -> PromptOptimizer:
    """Get global prompt optimizer instance."""
    global _optimizer
    if _optimizer is None:
        _optimizer = PromptOptimizer()
    return _optimizer


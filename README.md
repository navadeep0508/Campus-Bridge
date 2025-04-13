# Code Review Bot

A smart code review bot that uses OpenAI's GPT-4 to analyze code quality, identify potential bugs, and suggest improvements.

## Features

- Code analysis with detailed feedback
- Version comparison with change analysis
- Focused improvement suggestions
- JSON-formatted responses for easy integration

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

## Usage

```python
from code_review_bot import CodeReviewBot

# Initialize the bot
bot = CodeReviewBot()

# Analyze code
code = """
def calculate_sum(a, b):
    return a + b
"""
analysis = bot.analyze_code(code)
print(analysis)

# Compare versions
old_code = """
def calculate_sum(a, b):
    return a + b
"""
new_code = """
def calculate_sum(a, b):
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError("Inputs must be numbers")
    return a + b
"""
comparison = bot.compare_versions(old_code, new_code)
print(comparison)

# Suggest improvements
improvements = bot.suggest_improvements(code, focus_areas=["error handling", "type checking"])
print(improvements)
```

## Response Format

The bot returns responses in JSON format with the following structure:

### Code Analysis
```json
{
    "overall_quality": "score",
    "potential_bugs": ["list of potential issues"],
    "suggestions": ["list of improvement suggestions"],
    "best_practices": ["list of best practices to follow"]
}
```

### Version Comparison
```json
{
    "changes": ["list of changes"],
    "improvements": ["list of improvements"],
    "potential_issues": ["list of potential issues"],
    "suggestions": ["list of suggestions"]
}
```

### Improvement Suggestions
```json
{
    "suggestions": ["list of specific suggestions"],
    "examples": ["list of example implementations"],
    "benefits": ["list of benefits"]
}
```

## Contributing

Feel free to submit issues and enhancement requests!
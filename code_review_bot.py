import os
import requests
import json
from typing import List, Dict, Optional
import difflib
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class CodeReviewBot:
    def __init__(self):
        """
        Initialize the CodeReviewBot with Google Gemini API configuration.
        """
        # Get API key from environment or use default
        self.api_key = os.getenv("GEMINI_API_KEY", "AIzaSyDzD4_gH5GhvNrWEuYppxMV18rvsYW6tVg")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        
    def _make_api_request(self, prompt: str) -> Dict:
        """
        Make a request to the Gemini API.
        
        Args:
            prompt (str): The prompt to send to the API
            
        Returns:
            Dict: The API response
        """
        headers = {
            'Content-Type': 'application/json'
        }
        
        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        try:
            response = requests.post(
                f"{self.base_url}?key={self.api_key}",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise ValueError(f"API request failed: {str(e)}")
        
    def _handle_api_error(self, error: Exception) -> Dict:
        """
        Handle API errors and provide appropriate guidance.
        
        Args:
            error (Exception): The error that occurred
            
        Returns:
            Dict: Error information and guidance
        """
        error_message = str(error)
        guidance = ""
        
        if "401" in error_message or "Unauthorized" in error_message:
            guidance = """
            Authentication failed. Please check:
            1. Your API key is correct
            2. The API key has the necessary permissions
            3. Your account is active
            """
        elif "quota" in error_message.lower():
            guidance = """
            You have exceeded your API quota. To resolve this:
            1. Check your API usage and limits
            2. Contact Google Cloud support
            3. Consider upgrading your quota
            """
        else:
            guidance = "An unexpected error occurred. Please check your internet connection and try again."
        
        return {
            "error": error_message,
            "guidance": guidance,
            "overall_score": 0,
            "feedback": {},
            "suggestions": [],
            "critical_issues": []
        }
        
    def _extract_response_text(self, response: Dict) -> str:
        """
        Extract the text content from the Gemini API response.
        
        Args:
            response (Dict): The API response
            
        Returns:
            str: The extracted text content
        """
        try:
            # Try to extract text from the standard Gemini response format
            candidates = response.get('candidates', [])
            if candidates:
                content = candidates[0].get('content', {})
                parts = content.get('parts', [])
                if parts:
                    return parts[0].get('text', '')
            
            # If the above fails, try to get the raw response
            return str(response)
        except Exception as e:
            print(f"Warning: Failed to extract response text: {str(e)}")
            return str(response)
        
    def analyze_code(self, code: str, language: str) -> Dict:
        """
        Analyze code and provide feedback using the Gemini API.
        
        Args:
            code (str): The code to analyze
            language (str): Programming language of the code
            
        Returns:
            Dict: Analysis results including feedback and suggestions
        """
        try:
            prompt = f"""
            Please review the following {language} code and provide detailed feedback:
            
            {code}
            
            Please analyze the code for:
            1. Code quality and best practices
            2. Potential bugs or issues
            3. Security vulnerabilities
            4. Performance considerations
            5. Code style and readability
            6. Suggestions for improvement
            
            Format your response as a JSON object with the following structure:
            {{
                "overall_score": <score from 1-10>,
                "feedback": {{
                    "code_quality": <feedback>,
                    "potential_bugs": <feedback>,
                    "security": <feedback>,
                    "performance": <feedback>,
                    "readability": <feedback>
                }},
                "suggestions": [<list of specific suggestions>],
                "critical_issues": [<list of critical issues that need immediate attention>]
            }}
            """
            
            response = self._make_api_request(prompt)
            response_text = self._extract_response_text(response)
            
            try:
                # Try to parse the response as JSON
                analysis = json.loads(response_text)
                return analysis
            except json.JSONDecodeError:
                return {
                    "overall_score": 0,
                    "feedback": {
                        "raw_response": response_text
                    },
                    "suggestions": [],
                    "critical_issues": []
                }
            
        except Exception as e:
            return self._handle_api_error(e)
    
    def compare_versions(self, old_code: str, new_code: str, language: str) -> Dict:
        """
        Compare two versions of code and provide feedback on changes.
        
        Args:
            old_code (str): Previous version of the code
            new_code (str): New version of the code
            language (str): Programming language of the code
            
        Returns:
            Dict: Analysis of changes and their impact
        """
        try:
            # Generate diff
            diff = list(difflib.unified_diff(
                old_code.splitlines(),
                new_code.splitlines(),
                lineterm=''
            ))
            
            prompt = f"""
            Please analyze the following code changes in {language}:
            
            Diff:
            {chr(10).join(diff)}
            
            Please provide feedback on:
            1. Impact of the changes
            2. Potential issues introduced
            3. Improvements made
            4. Suggestions for further refinement
            
            Format your response as a JSON object with the following structure:
            {{
                "change_analysis": {{
                    "impact": <analysis of changes' impact>,
                    "improvements": [<list of improvements>],
                    "new_issues": [<list of potential new issues>]
                }},
                "recommendations": [<list of recommendations>]
            }}
            """
            
            response = self._make_api_request(prompt)
            response_text = self._extract_response_text(response)
            
            try:
                # Try to parse the response as JSON
                analysis = json.loads(response_text)
                return analysis
            except json.JSONDecodeError:
                # If parsing fails, return the raw text in a structured format
                return {
                    "change_analysis": {
                        "raw_response": response_text
                    },
                    "recommendations": []
                }
            
        except Exception as e:
            return self._handle_api_error(e)
    
    def suggest_improvements(self, code: str, language: str, focus_areas: Optional[List[str]] = None) -> Dict:
        """
        Suggest specific improvements for the code.
        
        Args:
            code (str): The code to improve
            language (str): Programming language of the code
            focus_areas (List[str], optional): Specific areas to focus on (e.g., ['performance', 'security'])
            
        Returns:
            Dict: Suggested improvements and refactoring recommendations
        """
        try:
            focus_prompt = ""
            if focus_areas:
                focus_prompt = f"Focus specifically on: {', '.join(focus_areas)}"
            
            prompt = f"""
            Please suggest improvements for the following {language} code:
            
            {code}
            
            {focus_prompt}
            
            Please provide:
            1. Specific refactoring suggestions
            2. Code optimization opportunities
            3. Best practices to implement
            4. Example code for improvements
            
            Format your response as a JSON object with the following structure:
            {{
                "refactoring_suggestions": [<list of refactoring suggestions>],
                "optimizations": [<list of optimization opportunities>],
                "best_practices": [<list of best practices to implement>],
                "example_code": <example code showing improvements>
            }}
            """
            
            response = self._make_api_request(prompt)
            response_text = self._extract_response_text(response)
            
            try:
                # Try to parse the response as JSON
                suggestions = json.loads(response_text)
                return suggestions
            except json.JSONDecodeError:
                # If parsing fails, return the raw text in a structured format
                return {
                    "refactoring_suggestions": [],
                    "optimizations": [],
                    "best_practices": [],
                    "example_code": response_text
                }
            
        except Exception as e:
            return self._handle_api_error(e)

# Example usage
if __name__ == "__main__":
    try:
        # Initialize the bot
        bot = CodeReviewBot()
        
        # Example code to analyze
        sample_code = """
        def calculate_average(numbers):
            sum = 0
            for num in numbers:
                sum += num
            return sum / len(numbers)
        """
        
        # Analyze code
        analysis = bot.analyze_code(sample_code, "Python")
        print("Code Analysis:")
        print(json.dumps(analysis, indent=2))
        
        # Compare versions
        old_code = sample_code
        new_code = """
        def calculate_average(numbers):
            if not numbers:
                return 0
            return sum(numbers) / len(numbers)
        """
        
        comparison = bot.compare_versions(old_code, new_code, "Python")
        print("\nVersion Comparison:")
        print(json.dumps(comparison, indent=2))
        
        # Get improvement suggestions
        improvements = bot.suggest_improvements(sample_code, "Python", ["performance", "readability"])
        print("\nImprovement Suggestions:")
        print(json.dumps(improvements, indent=2))
        
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Please check your API configuration and try again.") 
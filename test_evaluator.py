# test_evaluator.py
from evaluator import evaluate_response

def test_evaluator():
    user_prompt = "What is the capital of France?"
    response = "The capital of France is Paris."
    reference = "Paris is the capital of France."
    
    score, intent, result, fb = evaluate_response(user_prompt, response, reference)
    
    print(f"Test case 1 (High match):")
    print(f"Semantic Score: {score:.4f}")
    print(f"Intent Score: {intent:.4f}")
    print(f"Result: {result}")
    print(f"Feedback: {fb}")
    
    assert score > 0.8
    assert result == "Yes"

    print("\nTest case 2 (Low match):")
    low_response = "Apples are delicious."
    score2, intent2, result2, fb2 = evaluate_response(user_prompt, low_response, reference)
    print(f"Semantic Score: {score2:.4f}")
    print(f"Intent Score: {intent2:.4f}")
    print(f"Result: {result2}")
    print(f"Feedback: {fb2}")
    
    assert score2 < 0.5
    assert result2 == "No"

    print("\nAll evaluator tests passed!")

if __name__ == "__main__":
    test_evaluator()

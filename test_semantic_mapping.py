import sys
import os

# Add the current directory to path so we can import evaluator
sys.path.append(os.getcwd())

from evaluator import evaluate_response

def test_semantic_mapping():
    print("Testing Semantic Score Mapping (Threshold = 0.75)...")
    
    # Test Case 1: High Similarity (Expected: PASS)
    prompt = "Explain photosynthesis"
    resp = "Photosynthesis is the process by which green plants and some other organisms use sunlight to synthesize foods from carbon dioxide and water."
    ref = "Photosynthesis is the biological process of turning sunlight, CO2, and water into food (glucose) in plants."
    
    sem_score, int_score, status, feedback = evaluate_response(prompt, resp, ref)
    print(f"Case 1 (High Similarity): Score={sem_score:.4f}, Status={status}, Feedback='{feedback}'")
    assert status == "PASS", f"Expected PASS for score {sem_score}"
    
    # Test Case 2: Low Similarity (Expected: FAIL)
    prompt = "Explain photosynthesis"
    resp = "The weather today is sunny and bright."
    ref = "Photosynthesis is the biological process of turning sunlight, CO2, and water into food (glucose) in plants."
    
    sem_score, int_score, status, feedback = evaluate_response(prompt, resp, ref)
    print(f"Case 2 (Low Similarity): Score={sem_score:.4f}, Status={status}, Feedback='{feedback}'")
    assert status == "FAIL", f"Expected FAIL for score {sem_score}"

    print("\nAll tests passed successfully!")

if __name__ == "__main__":
    test_semantic_mapping()

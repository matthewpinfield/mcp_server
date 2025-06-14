#!/usr/bin/env python3

import requests
import json
import random
import chromadb
from chromadb.utils import embedding_functions
from collections import defaultdict
import time

def download_flutter_dataset():
    """Download Flutter Q&A dataset from HuggingFace"""
    
    print("📱 Downloading Flutter Q&A dataset from HuggingFace...")
    
    try:
        # HuggingFace datasets API endpoint
        url = "https://datasets-server.huggingface.co/rows"
        params = {
            "dataset": "durrah/flutter_questions_answers_",
            "config": "default",
            "split": "train",
            "offset": 0,
            "length": 100  # Get first 100 questions for evaluation
        }
        
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            questions = []
            
            for row in data.get('rows', []):
                content = row.get('row', {})
                question = content.get('question', '').strip()
                answer = content.get('answer', '').strip()
                
                if question and answer:
                    questions.append({
                        'question': question,
                        'answer': answer,
                        'expected_language': 'flutter'
                    })
            
            print(f"✅ Downloaded {len(questions)} Flutter Q&A pairs")
            return questions
            
        else:
            print(f"❌ Failed to download dataset: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Error downloading Flutter dataset: {e}")
        return []

def create_comprehensive_test_set():
    """Create comprehensive test set with Flutter, Python, and mixed questions"""
    
    # Download Flutter dataset
    flutter_questions = download_flutter_dataset()
    
    # Python-focused questions (similar to StaQC style)
    python_questions = [
        {
            'question': 'How to create async functions in Python?',
            'expected_language': 'python'
        },
        {
            'question': 'How to use FastAPI dependency injection?',
            'expected_language': 'python'
        },
        {
            'question': 'How to handle pandas DataFrame operations efficiently?',
            'expected_language': 'python'
        },
        {
            'question': 'How to implement error handling in Python async code?',
            'expected_language': 'python'
        },
        {
            'question': 'How to use Python type hints with generic types?',
            'expected_language': 'python'
        }
    ]
    
    # Mixed/ambiguous questions that could apply to either
    mixed_questions = [
        {
            'question': 'How to implement state management in applications?',
            'expected_language': 'mixed'  # Could be either Flutter or Python
        },
        {
            'question': 'How to handle HTTP requests and responses?',
            'expected_language': 'mixed'
        },
        {
            'question': 'How to implement unit testing best practices?',
            'expected_language': 'mixed'
        }
    ]
    
    # Combine all test sets
    all_questions = []
    
    # Add Flutter questions (limit to 20 for balanced evaluation)
    if flutter_questions:
        all_questions.extend(random.sample(flutter_questions, min(20, len(flutter_questions))))
    
    all_questions.extend(python_questions)
    all_questions.extend(mixed_questions)
    
    return all_questions

def evaluate_comprehensive_rag():
    """Comprehensive evaluation of RAG database with Flutter and Python questions"""
    
    DATABASE_CONFIG = {
        "path": "./rag_db_final",
        "collection_name": "expert_py_flutter_dart_final",
        "embedding_model": "nomic-embed-text:latest"
    }
    OLLAMA_CONFIG = {"base_url": "http://127.0.0.1:11434"}
    
    print("🔍 Comprehensive RAG Database Evaluation")
    print("Testing with Flutter dataset + Python questions")
    
    # Get test questions
    test_questions = create_comprehensive_test_set()
    
    if not test_questions:
        print("❌ No test questions available")
        return None
    
    print(f"📊 Testing {len(test_questions)} questions")
    
    # Count questions by expected language
    lang_counts = defaultdict(int)
    for q in test_questions:
        lang_counts[q.get('expected_language', 'unknown')] += 1
    
    print(f"Question distribution:")
    for lang, count in lang_counts.items():
        print(f"  {lang}: {count}")
    
    try:
        # Connect to database
        client = chromadb.PersistentClient(path=DATABASE_CONFIG["path"])
        collection = client.get_collection(
            name=DATABASE_CONFIG["collection_name"],
            embedding_function=embedding_functions.OllamaEmbeddingFunction(
                model_name=DATABASE_CONFIG["embedding_model"], 
                url=OLLAMA_CONFIG["base_url"]
            )
        )
        
        results = []
        language_accuracy = defaultdict(list)
        response_quality = defaultdict(list)
        
        print(f"\n🎯 Running evaluation...")
        start_time = time.time()
        
        for i, test_case in enumerate(test_questions):
            if i % 5 == 0:
                print(f"Progress: {i}/{len(test_questions)}")
            
            question = test_case['question']
            expected_lang = test_case.get('expected_language', 'unknown')
            expected_answer = test_case.get('answer', '')
            
            try:
                # Query the database
                search_results = collection.query(
                    query_texts=[question],
                    n_results=3
                )
                
                if search_results['documents'][0]:
                    top_results = []
                    for j in range(len(search_results['documents'][0])):
                        doc = search_results['documents'][0][j]
                        metadata = search_results['metadatas'][0][j]
                        
                        top_results.append({
                            'text': doc,
                            'language': metadata.get('language', 'unknown'),
                            'authority': metadata.get('authority', 'unknown'),
                            'doc_type': metadata.get('doc_type', 'unknown'),
                            'source': metadata.get('source', 'unknown')
                        })
                    
                    # Language accuracy analysis
                    top_language = top_results[0]['language']
                    
                    if expected_lang in ['flutter', 'python']:
                        correct = (top_language == expected_lang)
                        language_accuracy[expected_lang].append(correct)
                    elif expected_lang == 'mixed':
                        # For mixed questions, either language is acceptable
                        correct = top_language in ['flutter', 'python']
                        language_accuracy['mixed'].append(correct)
                    
                    # Quality assessment (length, authority, relevance)
                    quality_score = 0
                    top_result = top_results[0]
                    
                    # Length check (not too short, not too long)
                    if 100 <= len(top_result['text']) <= 2000:
                        quality_score += 1
                    
                    # Authority check (prefer elite code)
                    if top_result['authority'] in ['T2_Elite', 'T1_Official']:
                        quality_score += 1
                    
                    # Source relevance (prefer code examples for how-to questions)
                    if 'how to' in question.lower() and top_result['doc_type'] == 'elite_code_example':
                        quality_score += 1
                    
                    response_quality[expected_lang].append(quality_score)
                    
                    results.append({
                        'question': question,
                        'expected_language': expected_lang,
                        'expected_answer': expected_answer[:200] + "..." if len(expected_answer) > 200 else expected_answer,
                        'top_results': [{
                            'language': r['language'],
                            'authority': r['authority'],
                            'preview': r['text'][:200] + "..." if len(r['text']) > 200 else r['text']
                        } for r in top_results],
                        'success': True
                    })
                else:
                    results.append({
                        'question': question,
                        'expected_language': expected_lang,
                        'success': False
                    })
                    
            except Exception as e:
                print(f"❌ Error querying '{question[:50]}...': {e}")
                results.append({
                    'question': question,
                    'error': str(e),
                    'success': False
                })
        
        end_time = time.time()
        
        # Calculate comprehensive metrics
        print(f"\n📈 COMPREHENSIVE EVALUATION RESULTS")
        
        successful_queries = sum(1 for r in results if r.get('success', False))
        success_rate = (successful_queries / len(results)) * 100
        
        print(f"Query Success Rate: {successful_queries}/{len(results)} ({success_rate:.1f}%)")
        print(f"Average query time: {(end_time - start_time) / len(results):.3f} seconds")
        
        # Language accuracy by type
        print(f"\nLanguage Accuracy by Question Type:")
        overall_accuracy = []
        
        for lang, accuracies in language_accuracy.items():
            if accuracies:
                accuracy = (sum(accuracies) / len(accuracies)) * 100
                print(f"  {lang}: {sum(accuracies)}/{len(accuracies)} ({accuracy:.1f}%)")
                overall_accuracy.extend(accuracies)
        
        if overall_accuracy:
            total_accuracy = (sum(overall_accuracy) / len(overall_accuracy)) * 100
            print(f"  Overall Language Accuracy: {sum(overall_accuracy)}/{len(overall_accuracy)} ({total_accuracy:.1f}%)")
        
        # Response quality analysis
        print(f"\nResponse Quality Analysis (0-3 scale):")
        for lang, qualities in response_quality.items():
            if qualities:
                avg_quality = sum(qualities) / len(qualities)
                print(f"  {lang}: {avg_quality:.2f}/3.0 average quality")
        
        # Show sample results for each language
        print(f"\n🔍 SAMPLE RESULTS BY LANGUAGE")
        
        for target_lang in ['flutter', 'python', 'mixed']:
            lang_results = [r for r in results if r.get('expected_language') == target_lang and r.get('success')]
            if lang_results:
                sample = random.choice(lang_results)
                print(f"\n--- {target_lang.upper()} EXAMPLE ---")
                print(f"Question: {sample['question'][:100]}...")
                if sample.get('top_results'):
                    top = sample['top_results'][0]
                    print(f"Returned Language: {top['language']}")
                    print(f"Authority: {top['authority']}")
                    print(f"Preview: {top['preview'][:150]}...")
        
        # Overall assessment
        if success_rate >= 95 and total_accuracy >= 90:
            overall_rating = "EXCELLENT"
        elif success_rate >= 85 and total_accuracy >= 80:
            overall_rating = "GOOD"
        elif success_rate >= 70 and total_accuracy >= 70:
            overall_rating = "ACCEPTABLE"
        else:
            overall_rating = "NEEDS IMPROVEMENT"
        
        print(f"\n🏆 OVERALL DATABASE RATING: {overall_rating}")
        
        return {
            'total_questions': len(results),
            'success_rate': success_rate,
            'language_accuracy': {k: (sum(v)/len(v)*100 if v else 0) for k, v in language_accuracy.items()},
            'overall_accuracy': total_accuracy if overall_accuracy else 0,
            'response_quality': {k: (sum(v)/len(v) if v else 0) for k, v in response_quality.items()},
            'evaluation_time': end_time - start_time,
            'overall_rating': overall_rating
        }
        
    except Exception as e:
        print(f"❌ Error during evaluation: {e}")
        return None

def main():
    print("🚀 Starting Comprehensive Flutter + Python Evaluation")
    
    evaluation_results = evaluate_comprehensive_rag()
    
    if evaluation_results:
        # Save results
        with open('comprehensive_evaluation_results.json', 'w') as f:
            json.dump(evaluation_results, f, indent=2)
        
        print(f"\n💾 Results saved to 'comprehensive_evaluation_results.json'")
        print(f"⏱️  Total evaluation time: {evaluation_results['evaluation_time']:.2f} seconds")
    else:
        print(f"\n❌ Evaluation failed")

if __name__ == "__main__":
    main()
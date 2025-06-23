#!/usr/bin/env python3

import os
import pickle
import random
import chromadb
from chromadb.utils import embedding_functions
from collections import defaultdict
import json
import time

def load_staqc_data():
    """Load Python question-code pairs from StaQC dataset"""
    
    print(" Loading StaQC Python dataset...")
    
    # Paths to the dataset files
    base_path = "./staqc_dataset/annotation_tool/data/code_solution_labeled_data/source"
    
    # Load question titles
    qid_to_title_file = os.path.join(base_path, "python_how_to_do_it_by_classifier_multiple_qid_to_title.pickle")
    iid_to_code_file = os.path.join(base_path, "python_how_to_do_it_by_classifier_multiple_iid_to_code.pickle")
    
    try:
        # Load the pickled data
        with open(qid_to_title_file, 'rb') as f:
            qid_to_title = pickle.load(f)
        
        with open(iid_to_code_file, 'rb') as f:
            iid_to_code = pickle.load(f)
        
        print(f" Loaded {len(qid_to_title)} questions and {len(iid_to_code)} code snippets")
        
        # Create question-code pairs (using first 100 for evaluation)
        test_pairs = []
        question_ids = list(qid_to_title.keys())[:100]  # Limit to 100 for faster evaluation
        
        for qid in question_ids:
            if qid in qid_to_title:
                question = qid_to_title[qid]
                # For simplicity, we'll use this as both question and expected answer
                # In a real scenario, you'd have proper question-answer mappings
                test_pairs.append({
                    'qid': qid,
                    'question': question,
                    'expected_code': None  # We don't have direct mappings in this dataset structure
                })
        
        return test_pairs
        
    except Exception as e:
        print(f" Error loading StaQC data: {e}")
        return []

def create_golden_test_set():
    """Create a golden test set with manually crafted Python/Flutter questions"""
    
    golden_tests = [
        {
            'qid': 'golden_1',
            'question': 'How to create a stateful widget in Flutter with a counter?',
            'keywords': ['StatefulWidget', 'setState', 'counter', 'Flutter'],
            'expected_language': 'flutter'
        },
        {
            'qid': 'golden_2', 
            'question': 'How to make async HTTP requests in Python using FastAPI?',
            'keywords': ['async', 'await', 'FastAPI', 'HTTP', 'request'],
            'expected_language': 'python'
        },
        {
            'qid': 'golden_3',
            'question': 'How to use dependency injection in FastAPI?',
            'keywords': ['Depends', 'dependency', 'injection', 'FastAPI'],
            'expected_language': 'python'
        },
        {
            'qid': 'golden_4',
            'question': 'How to implement state management with BLoC in Flutter?',
            'keywords': ['BlocProvider', 'BlocBuilder', 'state', 'management'],
            'expected_language': 'flutter'
        },
        {
            'qid': 'golden_5',
            'question': 'How to handle pandas DataFrame operations efficiently?',
            'keywords': ['pandas', 'DataFrame', 'operations', 'efficient'],
            'expected_language': 'python'
        },
        {
            'qid': 'golden_6',
            'question': 'How to create custom widgets in Flutter with proper styling?',
            'keywords': ['custom', 'widget', 'styling', 'Flutter', 'Widget'],
            'expected_language': 'flutter'
        },
        {
            'qid': 'golden_7',
            'question': 'How to use Python type hints with async functions?',
            'keywords': ['type', 'hints', 'async', 'function', 'typing'],
            'expected_language': 'python'
        },
        {
            'qid': 'golden_8',
            'question': 'How to implement navigation between screens in Flutter?',
            'keywords': ['Navigator', 'push', 'pop', 'route', 'screen'],
            'expected_language': 'flutter'
        },
        {
            'qid': 'golden_9',
            'question': 'How to validate request data in FastAPI with Pydantic?',
            'keywords': ['validation', 'Pydantic', 'BaseModel', 'request'],
            'expected_language': 'python'
        },
        {
            'qid': 'golden_10',
            'question': 'How to use Dart streams for reactive programming?',
            'keywords': ['Stream', 'StreamBuilder', 'reactive', 'async'],
            'expected_language': 'flutter'
        }
    ]
    
    return golden_tests

def evaluate_rag_database(test_pairs, n_results=5):
    """Evaluate our RAG database against test questions"""
    
    DATABASE_CONFIG = {
        "path": "./rag_db_final",
        "collection_name": "expert_py_flutter_dart_final",
        "embedding_model": "nomic-embed-text:latest"
    }
    OLLAMA_CONFIG = {"base_url": "http://127.0.0.1:11434"}
    
    print(f"\n🔍 Evaluating RAG Database Performance")
    print(f"Database: {DATABASE_CONFIG['path']}")
    print(f"Test questions: {len(test_pairs)}")
    
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
        keyword_matches = []
        
        print(f"\n Running evaluation on {len(test_pairs)} questions...")
        
        for i, test_case in enumerate(test_pairs):
            if i % 10 == 0:
                print(f"Progress: {i}/{len(test_pairs)} questions processed...")
            
            question = test_case['question']
            expected_lang = test_case.get('expected_language', 'unknown')
            keywords = test_case.get('keywords', [])
            
            try:
                # Query the database
                search_results = collection.query(
                    query_texts=[question],
                    n_results=n_results
                )
                
                if search_results['documents'][0]:
                    # Analyze results
                    top_results = []
                    for j in range(len(search_results['documents'][0])):
                        doc = search_results['documents'][0][j]
                        metadata = search_results['metadatas'][0][j]
                        
                        top_results.append({
                            'text': doc[:200] + "..." if len(doc) > 200 else doc,
                            'language': metadata.get('language', 'unknown'),
                            'authority': metadata.get('authority', 'unknown'),
                            'doc_type': metadata.get('doc_type', 'unknown'),
                            'source': metadata.get('source', 'unknown')
                        })
                    
                    # Check language accuracy (if we have expected language)
                    if expected_lang != 'unknown':
                        top_lang = top_results[0]['language'] if top_results else 'none'
                        lang_correct = (top_lang == expected_lang)
                        language_accuracy[expected_lang].append(lang_correct)
                    
                    # Check keyword matches in top result
                    if keywords and top_results:
                        top_text = top_results[0]['text'].lower()
                        keyword_found = any(keyword.lower() in top_text for keyword in keywords)
                        keyword_matches.append(keyword_found)
                    
                    results.append({
                        'qid': test_case['qid'],
                        'question': question,
                        'expected_language': expected_lang,
                        'keywords': keywords,
                        'top_results': top_results,
                        'success': len(top_results) > 0
                    })
                else:
                    results.append({
                        'qid': test_case['qid'],
                        'question': question,
                        'expected_language': expected_lang,
                        'keywords': keywords,
                        'top_results': [],
                        'success': False
                    })
                    
            except Exception as e:
                print(f" Error querying '{question}': {e}")
                results.append({
                    'qid': test_case['qid'],
                    'question': question,
                    'error': str(e),
                    'success': False
                })
        
        # Calculate metrics
        print(f"\n📊 EVALUATION RESULTS")
        
        successful_queries = sum(1 for r in results if r.get('success', False))
        success_rate = (successful_queries / len(results)) * 100
        
        print(f"Query Success Rate: {successful_queries}/{len(results)} ({success_rate:.1f}%)")
        
        # Language accuracy
        if language_accuracy:
            print(f"\nLanguage Accuracy:")
            for lang, accuracies in language_accuracy.items():
                accuracy = (sum(accuracies) / len(accuracies)) * 100 if accuracies else 0
                print(f"  {lang}: {sum(accuracies)}/{len(accuracies)} ({accuracy:.1f}%)")
        
        # Keyword match rate
        if keyword_matches:
            keyword_success = sum(keyword_matches)
            keyword_rate = (keyword_success / len(keyword_matches)) * 100
            print(f"Keyword Match Rate: {keyword_success}/{len(keyword_matches)} ({keyword_rate:.1f}%)")
        
        # Authority distribution in results
        authority_dist = defaultdict(int)
        doc_type_dist = defaultdict(int)
        
        for result in results:
            if result.get('success') and result.get('top_results'):
                top_result = result['top_results'][0]
                authority_dist[top_result.get('authority', 'unknown')] += 1
                doc_type_dist[top_result.get('doc_type', 'unknown')] += 1
        
        print(f"\nTop Result Authority Distribution:")
        for auth, count in sorted(authority_dist.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / successful_queries) * 100 if successful_queries > 0 else 0
            print(f"  {auth}: {count} ({percentage:.1f}%)")
        
        print(f"\nTop Result Doc Type Distribution:")
        for doc_type, count in sorted(doc_type_dist.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / successful_queries) * 100 if successful_queries > 0 else 0
            print(f"  {doc_type}: {count} ({percentage:.1f}%)")
        
        # Show some example results
        print(f"\n🔍 SAMPLE EVALUATION RESULTS")
        
        sample_results = random.sample([r for r in results if r.get('success')], min(3, len([r for r in results if r.get('success')])))
        
        for result in sample_results:
            print(f"\n--- Question: {result['question'][:80]}... ---")
            print(f"Expected Language: {result.get('expected_language', 'N/A')}")
            if result.get('top_results'):
                top = result['top_results'][0]
                print(f"Top Result Language: {top.get('language', 'N/A')}")
                print(f"Top Result Authority: {top.get('authority', 'N/A')}")
                print(f"Result Preview: {top.get('text', 'N/A')[:150]}...")
        
        return {
            'total_questions': len(results),
            'success_rate': success_rate,
            'language_accuracy': dict(language_accuracy),
            'keyword_match_rate': keyword_rate if keyword_matches else 0,
            'authority_distribution': dict(authority_dist),
            'doc_type_distribution': dict(doc_type_dist)
        }
        
    except Exception as e:
        print(f" Error during evaluation: {e}")
        return None

def main():
    print(" Starting Stack Overflow Code Evaluation")
    
    # Try to load StaQC dataset, fallback to golden test set
    staqc_tests = load_staqc_data()
    golden_tests = create_golden_test_set()
    
    if staqc_tests:
        print(f" Using StaQC dataset with {len(staqc_tests)} questions")
        all_tests = golden_tests + staqc_tests[:20]  # Add 20 StaQC questions to golden set
    else:
        print(f"  Using golden test set only with {len(golden_tests)} questions")
        all_tests = golden_tests
    
    # Save test set for reference
    with open('evaluation_test_set.json', 'w') as f:
        json.dump(all_tests, f, indent=2)
    print(f"💾 Saved test set to 'evaluation_test_set.json'")
    
    # Run evaluation
    start_time = time.time()
    evaluation_results = evaluate_rag_database(all_tests)
    end_time = time.time()
    
    if evaluation_results:
        evaluation_results['evaluation_time'] = end_time - start_time
        evaluation_results['avg_query_time'] = (end_time - start_time) / len(all_tests)
        
        # Save results
        with open('evaluation_results.json', 'w') as f:
            json.dump(evaluation_results, f, indent=2)
        
        print(f"\n⏱  Evaluation completed in {end_time - start_time:.2f} seconds")
        print(f"Average query time: {evaluation_results['avg_query_time']:.3f} seconds")
        print(f"💾 Detailed results saved to 'evaluation_results.json'")
        
        # Overall assessment
        success_rate = evaluation_results['success_rate']
        if success_rate >= 95:
            print(f"\n DATABASE QUALITY: EXCELLENT ({success_rate:.1f}% success rate)")
        elif success_rate >= 85:
            print(f"\n DATABASE QUALITY: GOOD ({success_rate:.1f}% success rate)")
        elif success_rate >= 70:
            print(f"\n  DATABASE QUALITY: ACCEPTABLE ({success_rate:.1f}% success rate)")
        else:
            print(f"\n DATABASE QUALITY: POOR ({success_rate:.1f}% success rate)")
    else:
        print(f"\n Evaluation failed")

if __name__ == "__main__":
    main()
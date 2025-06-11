# Contents of test_ollama_lib.py
import ollama
print("--- Starting Ollama Python Library Test (Inspecting Model Objects) ---")
try:
    client = ollama.Client()
    response = client.list()

    print("\nRaw response (type of response['models'][0] if models exist):")
    if response and 'models' in response and isinstance(response['models'], list) and len(response['models']) > 0:
        first_model_object = response['models'][0]
        print(type(first_model_object))
        print("\nAttributes of the first Model object (dir()):")
        print(dir(first_model_object)) # This will show all attributes and methods
        
        print("\nTrying to access common attributes like 'name' or 'model':")
        if hasattr(first_model_object, 'name'):
            print(f"  first_model_object.name: {first_model_object.name}")
        if hasattr(first_model_object, 'model'): # This is the actual field based on previous raw output
            print(f"  first_model_object.model: {first_model_object.model}") 

        # Correct way to get model names
        available_models = []
        for model_obj in response['models']:
            # Based on the raw output you showed, the field is 'model'
            if hasattr(model_obj, 'model'): 
                available_models.append(model_obj.model)
            elif hasattr(model_obj, 'name'): # Keep 'name' as a fallback just in case
                 available_models.append(model_obj.name)


        print("\nParsed model names (using object attributes):")
        print(available_models)
        
        if 'nomic-embed-text:latest' in available_models:
            print("\nSUCCESS: 'nomic-embed-text:latest' found by Python library using object attributes.")
        else:
            print("\nFAILURE: 'nomic-embed-text:latest' NOT found even using object attributes. Check available_models list.")
    elif response and 'models' in response:
         print(f"\nWARNING: 'models' key exists in response, but it's not a list. Type: {type(response['models'])}")
         print(f"Raw response: {response}")
    elif response:
         print(f"\nFAILURE: 'models' key NOT found in response. Keys available: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
         print(f"Raw response: {response}")
    else:
        print("\nFAILURE: Response from Ollama API was empty or None.")
        print(f"Raw response: {response}")
        
except Exception as e:
    print(f"\nAn error occurred: {e}")

print("\n--- Ollama Python Library Test Finished ---")
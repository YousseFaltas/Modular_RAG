import os
from dotenv import load_dotenv

def setup_langsmith():
    """
    Configures LangSmith by setting the necessary environment variables
    from the .env file.
    """
    # Load all variables from .env into the environment
    load_dotenv()

    print(f"{'='*20}Configuring LangSmith{'='*20}")

    # Set the standard LangChain environment variables
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    
    # The API key is loaded from .env by load_dotenv(), but we ensure it is set for feedback.
    api_key = os.getenv("LANGSMITH_API_KEY")
    if not api_key:
        print("WARNING: LANGSMITH_API_KEY not found in .env file.")
    else:
        # Note: LANGCHAIN_API_KEY is an alias LangSmith SDK also checks.
        # Setting it explicitly is good practice if other tools need it.
        os.environ["LANGCHAIN_API_KEY"] = api_key
        print("LangSmith API key configured.")

    # Explicitly check for and set the project name
    project_name = os.getenv("LANGCHAIN_PROJECT")
    if project_name:
        # This is the key step: setting the environment variable for LangChain to see.
        os.environ["LANGCHAIN_PROJECT"] = project_name
        print(f"LangSmith project set to: '{project_name}'")
    else:
        print("LANGCHAIN_PROJECT not found in .env. Traces will go to the 'default' project.")
        
    print(f"{'='*20}LangSmith configuration complete{'='*20}")

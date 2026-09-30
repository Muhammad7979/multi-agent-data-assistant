import os

import pandas as pd


def transform_load_context(file_path:str):
    """
    This tool transforms the data from the specified file and loads it into the
    desired location (output_folder).

    Args:
        file_path (str): The path to the file containing the data to be transformed.
        output_folder (str): The folder where the transformed data will be saved.
        output_format (str): The format in which to save the transformed data (csv, json, parquet).
    Returns:
        str: A message indicating the success or failure of the operation.
    """

    file_extension = os.path.splitext(file_path)[1].lower()
    if file_extension == ".csv":
        df = pd.read_csv(file_path)
    elif file_extension == ".json":
        df = pd.read_json(file_path, lines=True)
    elif file_extension == ".parquet":
        df = pd.read_parquet(file_path)
    else:
        return f"Unsupported file format: {file_extension}"

    top_3_rows = str(df.head(3))

    return top_3_rows


def execute_code(code:str, *, raise_errors=False):
    """
    This tool executes the provided code and returns the output.

    Args:
        code (str): The code to be executed.
    Returns:
        str: The output of the executed code or an error message if execution fails.
    """

    try:
        exec(code)
        return "Code executed successfully."
    except Exception as e:
        if raise_errors:
            raise
        return f"Failed to execute code: {e}"

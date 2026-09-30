"""LLM tool schemas and transformation-code coordination."""
from langchain.tools import tool

from data_agent.llm import create_llm
from data_agent.services.extraction import extract_load
from data_agent.services.transformation import execute_code, transform_load_context
from data_agent.services.etl_files import ETLFileStore, FORMATS
from data_agent.services.etl_results import failed_result, saved_result
from pathlib import Path


def build_tools(*, data_root, llm_factory=create_llm):
    """Bind operation dependencies without performing any IO."""
    @tool(response_format='content_and_artifact')
    def extract_load_tool(url:str, output_folder:str, format:str, filename_stem:str = '') -> str:
        """
    This tool extracts the data from the API (url) and loads it into the
    the desired location (output_folder).

    Args:
        url (str): The API endpoint from which to extract data.
        output_folder (str): Legacy argument; configured ETL storage controls the destination.
        format (str): The format in which to save the extracted data (csv, json, parquet).
        filename_stem (str): Optional short descriptive dataset name, such as customer_orders.
            Supply a stem only, never paths, extensions, timestamps or identifiers.
    
    Returns:
        str: A message indicating the success or failure of the operation.

    """
        return extract_load(url, output_folder, format, data_root=data_root, filename_stem=filename_stem, structured=True)


    @tool(response_format='content_and_artifact')
    def transform_load_tool(input_file_path:str,output_folder:str,output_format:str, user_question:str) -> str:
        """
    This tool transforms the data from the specified file and loads it into the
    desired location (output_folder).

    Args:
        input_file_path (str): The path to the file containing the data to be transformed.
        output_folder (str): The folder where the transformed data will be saved.
        output_format (str): The format in which to save the transformed data (csv, json, parquet).
    
    Returns:
        str: A message indicating the success or failure of the operation.

    """

        return transform_result(input_file_path, output_format, user_question)

    def transform_result(input_file_path, output_format, user_question):
        class TransformationFailed(Exception):
            pass

        if output_format not in FORMATS:
            return 'Unsupported transformation format.', failed_result('transformation', 'unsupported_format')
        try:
            top_3_rows = transform_load_context(input_file_path)
        except Exception:
            return 'Transformation failed while reading the input.', failed_result('transformation', 'transformation_failed')

        def writer(destination):
            # Require the generated code to create its output, while allowing
            # legitimate zero-byte JSON-lines datasets.
            destination.unlink()
            try:
                generate_and_execute(destination, input_file_path, top_3_rows, user_question, output_format)
            except OSError:
                raise
            except Exception:
                raise TransformationFailed() from None
            if not destination.is_file():
                raise OSError('Transformation did not write an output')

        try:
            stored = ETLFileStore(data_root=data_root).write(source='', format=output_format,
                suggested_name=Path(input_file_path).stem[:40] + '_transformed', writer=writer)
        except TransformationFailed:
            return 'Transformation failed.', failed_result('transformation', 'transformation_failed')
        except Exception:
            return 'Transformed output could not be saved.', failed_result('transformation', 'storage_failed')
        return f'Transformation completed and saved to {stored.path}', saved_result(stored, 'transformation')

    def generate_and_execute(destination, input_file_path, top_3_rows, user_question, output_format):

        llm = llm_factory("claude")

        prompt = f"""
            You are a Python Data Analyst who uses Pandas to analyze data. 
            You need to provide only the Pandas Code that will help to perform the right ETL operations on the data stored in the file : {input_file_path}
            as per the user's question. Do not provide any explanation or comments, only
            the code should be provided. The code should be in a format that can be executed 
            in a Python environment with Pandas installed. 
            Don't write anything else than Pandas Code. \n
            
            Create the Pandas Dataframe from the data stored in the file : {input_file_path} and then 
            write the code to transform and save the data at {str(destination)!r} in {output_format} format.
            This is the exact output file, not a directory. Do not modify the input file.
            For JSON, use orient='records', lines=True. For CSV, use index=False.
            Here's the user's question: {user_question}\n
            Here's the context of the data you will be analyzing: {top_3_rows}\n

        """

        response = llm.invoke(prompt).content 

        # Optional Cleaning
        pandas_code = response.strip()
        if pandas_code.startswith('```') and pandas_code.endswith('```'):
            lines = pandas_code.splitlines()
            if lines[0].strip().lower() in ('```python', '```'):
                pandas_code = '\n'.join(lines[1:-1]).strip()

        # Execute the Pandas code
        execute_code(pandas_code, raise_errors=True)



    return [extract_load_tool, transform_load_tool]
